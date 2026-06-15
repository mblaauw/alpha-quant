"""Streamlit dashboard — read-only view of system state."""

import json
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st
import structlog

from alpha_quant.app.halt import is_halted, read_halt

logger = structlog.get_logger()

st.set_page_config(
    page_title="Alpha Quant Dashboard",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
)

DATA_DIR = Path("data")


def _safe_query(
    state: duckdb.DuckDBPyConnection, query: str, params: list | None = None
) -> pd.DataFrame:
    try:
        if params:
            return state.execute(query, params).fetchdf()
        return state.execute(query).fetchdf()
    except (duckdb.CatalogException, duckdb.BinderException) as e:
        logger.warning("dashboard_query_failed", query=query[:80], error=str(e))
        return pd.DataFrame()


def _connect() -> tuple[duckdb.DuckDBPyConnection, duckdb.DuckDBPyConnection] | None:
    state_path = DATA_DIR / "state.db"
    if not state_path.exists():
        return None
    try:
        analytical = duckdb.connect()
        state = duckdb.connect(str(state_path))
        return analytical, state
    except duckdb.IOException as e:
        st.error(f":warning: **Database connection error** — {e}")
        return None


def _load_equity_curve(state: duckdb.DuckDBPyConnection, book: str = "PAPER") -> pd.DataFrame:
    return _safe_query(
        state,
        "SELECT equity_date, equity, cash FROM equity_curve WHERE book = ? ORDER BY equity_date",
        [book],
    )


def _load_positions(state: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _safe_query(
        state,
        "SELECT symbol, quantity, entry_price, avg_cost, current_price,"
        " stop_price, trail_price, market_value, unrealized_pl,"
        " entry_date, high_since_entry, partial_taken"
        " FROM positions WHERE quantity > 0",
    )


def _load_journals(state: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _safe_query(
        state,
        "SELECT entry_date FROM journal_entries ORDER BY entry_date DESC LIMIT 30",
    )


def _load_reports(state: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _safe_query(
        state,
        "SELECT report_date, report_type FROM reports ORDER BY report_date DESC LIMIT 20",
    )


def _load_latest_run(state: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _safe_query(
        state,
        "SELECT run_type, start_ts, end_ts, status, config_hash"
        " FROM runs ORDER BY start_ts DESC LIMIT 1",
    )


def _load_quarantine(state: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _safe_query(
        state,
        "SELECT symbol, reason, severity, quarantined_date"
        " FROM quarantine WHERE cleared_date IS NULL",
    )


def _load_staleness_events(state: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _safe_query(
        state,
        "SELECT payload FROM events WHERE event_type = 'staleness_halt_set'"
        " ORDER BY timestamp DESC LIMIT 5",
    )


def _read_markdown(path: Path) -> str:
    try:
        return path.read_text()
    except (FileNotFoundError, PermissionError, IsADirectoryError) as e:
        return f"Error reading {path}: {e}"


def home_tab(state: duckdb.DuckDBPyConnection) -> None:
    st.header("System Status")

    halted = is_halted()
    if halted:
        halt_info = read_halt()
        reason = halt_info.get("reason", "unknown") if halt_info else "unknown"
        st.error(f":warning: **System Halted** — Reason: {reason}")
    else:
        st.success(":white_check_mark: **System Running** — No active halts")

    col1, col2, col3, col4 = st.columns(4)

    runs = _load_latest_run(state)
    if not runs.empty:
        last_run = runs.iloc[0]
        col1.metric("Last Run Type", last_run.run_type.capitalize() if last_run.run_type else "—")
        col2.metric("Run Status", last_run.status.capitalize() if last_run.status else "—")
        col3.metric("Run Date", str(last_run.start_ts)[:10] if last_run.start_ts else "—")
    else:
        col1.metric("Last Run", "No runs found")
        col2.metric("Run Status", "—")
        col3.metric("Run Date", "—")

    equity_df = _load_equity_curve(state)
    latest_equity: float | None = float(equity_df.iloc[-1].equity) if not equity_df.empty else None

    if latest_equity is not None:
        col4.metric("Equity", f"${latest_equity:,.2f}")

        st.subheader("Equity Curve")
        st.line_chart(equity_df, x="equity_date", y="equity")

        first_equity = float(equity_df.iloc[0].equity)
        returns_text = (
            f"{((latest_equity / first_equity - 1) * 100):+.2f}%" if len(equity_df) > 1 else "—"
        )
        st.metric("Total Return", returns_text)
    else:
        col4.metric("Equity", "—")
        st.info("No equity data available. Run a backtest or start paper trading to see results.")

    st.subheader("Data Health")

    quarantined = _load_quarantine(state)
    staleness = _load_staleness_events(state)

    health_col1, health_col2 = st.columns(2)

    if quarantined.empty and staleness.empty:
        health_col1.success(":white_check_mark: All data sources healthy")
        health_col2.metric("Quarantined Symbols", "0")
    else:
        if not quarantined.empty:
            health_col1.warning(f":warning: {len(quarantined)} symbol(s) quarantined")
            with health_col1:
                st.dataframe(quarantined[["symbol", "reason", "severity"]], width="stretch")
        else:
            health_col1.success(":white_check_mark: No quarantined symbols")

        if not staleness.empty:
            health_col2.warning(f":warning: {len(staleness)} data staleness event(s)")
        else:
            health_col2.success(":white_check_mark: No data staleness detected")

    st.subheader("Portfolio Summary")

    positions = _load_positions(state)
    if not positions.empty:
        total_value = float(positions["market_value"].sum())
        total_pl = float(positions["unrealized_pl"].sum())

        equity = latest_equity if latest_equity is not None else 1.0
        exposure_pct = (total_value / equity * 100) if equity > 0 else 0.0

        pos_col1, pos_col2, pos_col3, pos_col4 = st.columns(4)
        pos_col1.metric("Open Positions", len(positions))
        pos_col2.metric("Total Exposure", f"${total_value:,.2f}")
        pos_col3.metric("Exposure %", f"{exposure_pct:.1f}%")
        pos_col4.metric("Unrealized P&L", f"${total_pl:+,.2f}")
    else:
        st.info("No open positions.")


def portfolio_tab(state: duckdb.DuckDBPyConnection) -> None:
    st.header("Portfolio")

    positions = _load_positions(state)
    if positions.empty:
        st.info("No open positions.")
        return

    display = positions.copy()
    total_value = float(positions["market_value"].sum())

    if total_value > 0 and "market_value" in display.columns:
        display["Exposure %"] = display["market_value"] / total_value * 100
    else:
        display["Exposure %"] = 0.0

    if all(c in display.columns for c in ["current_price", "stop_price"]):
        valid_mask = display["stop_price"].notna() & (display["stop_price"] > 0)
        display["Risk-at-Stop $"] = 0.0
        display["Dist-to-Stop %"] = 0.0
        display.loc[valid_mask, "Risk-at-Stop $"] = (
            display.loc[valid_mask, "current_price"] - display.loc[valid_mask, "stop_price"]
        ) * display.loc[valid_mask, "quantity"]
        display.loc[valid_mask, "Dist-to-Stop %"] = (
            (display.loc[valid_mask, "current_price"] - display.loc[valid_mask, "stop_price"])
            / display.loc[valid_mask, "current_price"]
            * 100
        )
        display.loc[~valid_mask, "Dist-to-Stop %"] = None

    if "partial_taken" in display.columns:
        display["Partial"] = display["partial_taken"].map(
            {True: ":white_check_mark: Yes", False: ""}
        )

    st.dataframe(display, width="stretch")

    total_pl = float(positions["unrealized_pl"].sum())
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Market Value", f"${total_value:,.2f}")
    col2.metric("Total Unrealized P&L", f"${total_pl:+,.2f}")
    col3.metric("Open Positions", len(positions))

    near_stop = 0
    if "Dist-to-Stop %" in display.columns:
        near_stop = (display["Dist-to-Stop %"].notna() & (display["Dist-to-Stop %"] < 5.0)).sum()
    col4.metric("Near Stop (<5%)", near_stop)


def reports_tab(state: duckdb.DuckDBPyConnection) -> None:
    st.header("Reports")

    reports = _load_reports(state)
    if not reports.empty:
        selected = st.selectbox(
            "Select report",
            [f"{r.report_date} ({r.report_type})" for _, r in reports.iterrows()],
        )
        if selected:
            dt_str, rtype = selected.split(" (")
            rtype = rtype.rstrip(")")
            row = _safe_query(
                state,
                "SELECT content FROM reports WHERE report_date = ? AND report_type = ?",
                [dt_str, rtype],
            )
            if not row.empty:
                st.markdown(row.iloc[0]["content"])
    else:
        st.info("No reports available.")


def _strip_frontmatter(markdown: str) -> str:
    if markdown.startswith("---"):
        end = markdown.find("---", 3)
        if end != -1:
            return markdown[end + 3 :].strip()
    return markdown


def _build_concepts_manifest(concepts_dir: Path) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    for md_file in sorted(concepts_dir.glob("*.md")):
        content = md_file.read_text()
        card_id = md_file.stem
        title = card_id.replace("-", " ").title()
        difficulty = "beginner"
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                frontmatter = content[3:end].strip()
                for line in frontmatter.split("\n"):
                    if ":" in line:
                        key, val = line.split(":", 1)
                        key = key.strip()
                        val = val.strip().strip('"')
                        if key == "title":
                            title = val
                        elif key == "difficulty":
                            difficulty = val
        cards.append({"id": card_id, "title": title, "difficulty": difficulty})
    return cards


def concepts_tab() -> None:
    st.header("Concept Cards")

    concepts_dir = Path(__file__).resolve().parent.parent / "concepts"
    cards = _build_concepts_manifest(concepts_dir)
    if not cards:
        st.info("No concept cards found.")
        return

    titles = {c["title"]: c["id"] for c in cards}
    difficulty_groups: dict[str, list[str]] = {}
    for c in cards:
        diff = c.get("difficulty", "beginner")
        difficulty_groups.setdefault(diff, []).append(c["title"])

    group_order = ["beginner", "intermediate", "advanced"]
    select_options: list[str] = []
    for group in group_order:
        if group in difficulty_groups:
            titles_in_group = sorted(difficulty_groups[group])
            select_options.append(f"--- {group.title()} ---")
            select_options.extend(titles_in_group)

    selected = st.selectbox("Select concept", select_options or list(titles.keys()))

    if selected and selected in titles:
        card_id = titles[selected]
        card_path = concepts_dir / f"{card_id}.md"
        content = _read_markdown(card_path)
        st.markdown(_strip_frontmatter(content))
    elif selected and not selected.startswith("---"):
        st.info("Select a concept to view its content.")


def decision_tab(state: duckdb.DuckDBPyConnection) -> None:
    st.header("Decision Explorer")

    symbol = st.text_input("Symbol", placeholder="e.g. AAPL").strip().upper()

    if not symbol:
        st.info("Enter a symbol to explore its decision history.")
        return

    decisions = _safe_query(
        state,
        "SELECT decision_id, run_id, symbol, decision_date, action, confidence, reasons,"
        " candidate_json, risk_results, mechanism_results"
        " FROM decisions WHERE symbol = ? ORDER BY decision_date DESC LIMIT 20",
        [symbol],
    )

    events = _safe_query(
        state,
        "SELECT event_type, timestamp, payload FROM events"
        " WHERE event_type IN ('candidate_blocked', 'candidate_scored', 'candidate_promoted',"
        "                      'stop_adjusted', 'partial_taken', 'time_stop_triggered')"
        " AND payload->>'symbol' = ?"
        " ORDER BY timestamp DESC LIMIT 50",
        [symbol],
    )

    st.subheader(f"Timeline for {symbol}")

    if not decisions.empty and not events.empty:
        combined = []
        for _, r in decisions.iterrows():
            combined.append(
                {
                    "date": str(r.decision_date),
                    "type": "decision",
                    "detail": f"{r.action} (confidence: {r.confidence:.2f})",
                    "source": "Decision",
                }
            )
        for _, r in events.iterrows():
            try:
                payload = json.loads(r["payload"])
            except (json.JSONDecodeError, TypeError, ValueError):  # fmt: skip
                payload = {}
            detail = ""
            if r.event_type == "candidate_blocked":
                detail = f"Blocked at gate={payload.get('gate', '?')}: {payload.get('reason', '')}"
            elif r.event_type == "candidate_scored":
                detail = f"Scored {payload.get('composite_score', '?')}"
            elif r.event_type == "candidate_promoted":
                detail = f"Promoted with score {payload.get('score', '?')}"
            elif r.event_type == "stop_adjusted":
                old = payload.get("old_stop", "?")
                new = payload.get("new_stop", "?")
                detail = f"Stop adjusted: {old} : {new}"
            elif r.event_type == "partial_taken":
                qty = payload.get("quantity", "?")
                price = payload.get("price", "?")
                detail = f"Partial take: {qty} @ {price}"
            elif r.event_type == "time_stop_triggered":
                detail = f"Time stop after {payload.get('days_held', '?')} days"
            combined.append(
                {
                    "date": str(r.timestamp)[:10],
                    "type": r.event_type,
                    "detail": detail,
                    "source": "Event",
                }
            )

        combined.sort(key=lambda x: x["date"], reverse=True)
        timeline = pd.DataFrame(combined)
        st.dataframe(timeline, width="stretch")
    elif not decisions.empty:
        st.dataframe(decisions[["decision_date", "action", "confidence"]], width="stretch")
    elif not events.empty:
        st.dataframe(events[["timestamp", "event_type"]], width="stretch")
    else:
        st.info(f"No decision or event history found for symbol: {symbol}")


def journal_tab(state: duckdb.DuckDBPyConnection) -> None:
    st.header("Daily Journal")

    journals = _load_journals(state)
    if not journals.empty:
        dates = journals["entry_date"].tolist()
        selected_date = st.selectbox("Select journal date", dates, format_func=str)

        if selected_date:
            row = _safe_query(
                state,
                "SELECT content FROM journal_entries WHERE entry_date = ?",
                [str(selected_date)],
            )
            if not row.empty:
                st.markdown(row.iloc[0]["content"])
            else:
                st.info("No journal entry for this date.")
    else:
        st.info("No journal entries available. Run the pipeline to generate daily journals.")


def main() -> None:
    st.title("Alpha Quant Dashboard")

    st.warning(
        ":construction: **Beta Release** — This system is in active development. "
        "Data and decisions reflect paper trading only. "
        "Do not use for live trading decisions."
    )

    st.caption(f"Data directory: {DATA_DIR.resolve()}")

    if not DATA_DIR.exists():
        st.warning(f"Data directory not found: {DATA_DIR}")
        st.info("Run the pipeline at least once to generate data.")
        return

    if not (DATA_DIR / "state.db").exists():
        st.warning(f"No state database found at {DATA_DIR / 'state.db'}")
        st.info("Run the pipeline at least once to generate data.")
        return

    conn = _connect()
    if conn is None:
        return

    analytical, state = conn

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        ["Home", "Portfolio", "Reports", "Concepts", "Daily Journal", "Decision Explorer"]
    )

    with tab1:
        home_tab(state)

    with tab2:
        portfolio_tab(state)

    with tab3:
        reports_tab(state)

    with tab4:
        concepts_tab()

    with tab5:
        journal_tab(state)

    with tab6:
        decision_tab(state)


if __name__ == "__main__":
    main()
