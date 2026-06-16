"""Streamlit dashboard — read-only view of system state."""

import json
import time
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st
import structlog

from alpha_quant.app.config import ConfigError, load_config
from alpha_quant.app.halt import is_halted, read_halt
from alpha_quant.domain.events import (
    CandidateBlocked,
    CandidatePromoted,
    CandidateScored,
    ConsistencyViolation,
    FillBooked,
    PartialTaken,
    StalenessHaltSet,
    StopAdjusted,
    TimeStopTriggered,
)

logger = structlog.get_logger()


_EVT_CANDIDATE_SCORED = CandidateScored.model_fields["event_type"].default  # type: ignore[unresolved-attribute]  # pydantic Literal default — ty can't resolve
_EVT_CANDIDATE_BLOCKED = CandidateBlocked.model_fields["event_type"].default  # type: ignore[unresolved-attribute]  # pydantic Literal default — ty can't resolve
_EVT_CANDIDATE_PROMOTED = CandidatePromoted.model_fields["event_type"].default  # type: ignore[unresolved-attribute]  # pydantic Literal default — ty can't resolve
_EVT_FILL_BOOKED = FillBooked.model_fields["event_type"].default  # type: ignore[unresolved-attribute]  # pydantic Literal default — ty can't resolve
_EVT_STOP_ADJUSTED = StopAdjusted.model_fields["event_type"].default  # type: ignore[unresolved-attribute]  # pydantic Literal default — ty can't resolve
_EVT_PARTIAL_TAKEN = PartialTaken.model_fields["event_type"].default  # type: ignore[unresolved-attribute]  # pydantic Literal default — ty can't resolve
_EVT_TIME_STOP_TRIGGERED = TimeStopTriggered.model_fields["event_type"].default  # type: ignore[unresolved-attribute]  # pydantic Literal default — ty can't resolve
_EVT_STALENESS_HALT_SET = StalenessHaltSet.model_fields["event_type"].default  # type: ignore[unresolved-attribute]  # pydantic Literal default — ty can't resolve
_EVT_CONSISTENCY_VIOLATION = ConsistencyViolation.model_fields["event_type"].default  # type: ignore[unresolved-attribute]  # pydantic Literal default — ty can't resolve

_CACHE_TTL = 60

st.set_page_config(
    page_title="Alpha Quant Dashboard",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
)

DATA_DIR = Path("data")


_HELP_TEXT: dict[str, str] = {
    "Equity": "Current portfolio equity (cash + market value of all positions)",
    "Total Return": "Cumulative return since first available equity data point",
    "Open Positions": "Number of positions currently held with quantity > 0",
    "Total Exposure": "Sum of market value of all open positions",
    "Exposure %": "Total exposure as percentage of current equity",
    "Unrealized P&L": "Total unrealized profit/loss across all open positions",
    "Last Run Type": "Mode of the most recent pipeline run (daily, backtest, fixture)",
    "Run Status": "Completion status of the most recent run",
    "Run Date": "Date of the most recent pipeline run",
    "Promoted": "Candidates promoted to entry in the latest run",
    "Scored": "Candidates scored by the composite mechanism",
    "Blocked": "Candidates blocked by quality gates",
    "Fills": "Fills booked in the latest run",
    "Total Market Value": "Sum of market value of all open positions",
    "Near Stop (<5%)": "Positions where current price is within 5% of stop price",
    "Total Realized P&L": "Total realized profit/loss from closed positions",
}


def _help_text(label: str) -> str:
    return _HELP_TEXT.get(label, "")


def _metric_card(label: str, value: str, delta: str | None = None) -> None:
    st.metric(label=label, value=value, delta=delta, help=_help_text(label))


def _section_header(title: str, description: str = "") -> None:
    st.subheader(title)
    if description:
        st.caption(description)


def _empty_state(message: str, icon: str = ":information_source:", help_text: str = "") -> None:
    _, col, _ = st.columns([1, 2, 1], gap="medium")
    with col:
        st.info(f"{icon} **{message}**")
        if help_text:
            st.caption(help_text)


def _data_table(df: pd.DataFrame, height: int = 400) -> None:
    st.dataframe(df, width="stretch", height=height)


def _status_badge(state: str, text: str) -> None:
    if state == "success":
        st.success(text)
    elif state == "warning":
        st.warning(text)
    elif state == "error":
        st.error(text)
    else:
        st.info(text)


def _jump_to_symbol(symbol: str) -> None:
    st.session_state["jump_symbol"] = symbol
    _status_badge("success", f"Symbol {symbol} selected — switch to Decision Explorer tab")


def _safe_json_loads(payload: str) -> dict | None:
    """Parse JSON safely, returning None on failure."""
    try:
        return json.loads(payload)
    except (json.JSONDecodeError, TypeError, ValueError):  # fmt: skip
        return None


def _safe_query(
    state: duckdb.DuckDBPyConnection, query: str, params: list | None = None
) -> pd.DataFrame:
    try:
        if params:
            return state.execute(query, params).fetchdf()
        return state.execute(query).fetchdf()
    except (duckdb.CatalogException, duckdb.BinderException) as e:
        logger.warning("dashboard_query_failed", query=query[:80], error=str(e))
        st.warning(f"Query failed: {e}")
        return pd.DataFrame()


def _connect() -> duckdb.DuckDBPyConnection | None:
    state_path = DATA_DIR / "state.db"
    if not state_path.exists():
        return None
    try:
        return duckdb.connect(str(state_path))
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
        "SELECT run_id, run_type, start_ts, end_ts, status, config_hash"
        " FROM runs ORDER BY start_ts DESC LIMIT 1",
    )


def _load_all_runs(state: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _safe_query(
        state,
        "SELECT run_id, run_type, start_ts, end_ts, status, config_hash"
        " FROM runs ORDER BY start_ts DESC LIMIT 10",
    )


def _load_run_events(state: duckdb.DuckDBPyConnection, run_id: str) -> pd.DataFrame:
    return _safe_query(
        state,
        "SELECT event_type, timestamp, payload FROM events WHERE run_id = ? ORDER BY timestamp",
        [run_id],
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
        f"SELECT payload FROM events WHERE event_type = '{_EVT_STALENESS_HALT_SET}'"
        " ORDER BY timestamp DESC LIMIT 5",
    )


def _load_symbol_options(state: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _safe_query(
        state,
        "SELECT DISTINCT symbol FROM decisions"
        " UNION"
        " SELECT DISTINCT symbol FROM positions WHERE quantity > 0"
        " ORDER BY symbol",
    )


def _get_state_conn() -> duckdb.DuckDBPyConnection | None:
    state = _connect()
    if state is None:
        return None
    return state


@st.cache_data(ttl=_CACHE_TTL)
def _cached_load_equity_curve(conn_id: str, book: str = "PAPER") -> pd.DataFrame:
    state = _get_state_conn()
    if state is None:
        return pd.DataFrame()
    return _load_equity_curve(state, book)


@st.cache_data(ttl=_CACHE_TTL)
def _cached_load_positions(conn_id: str) -> pd.DataFrame:
    state = _get_state_conn()
    if state is None:
        return pd.DataFrame()
    return _load_positions(state)


@st.cache_data(ttl=_CACHE_TTL)
def _cached_load_journals(conn_id: str) -> pd.DataFrame:
    state = _get_state_conn()
    if state is None:
        return pd.DataFrame()
    return _load_journals(state)


@st.cache_data(ttl=_CACHE_TTL)
def _cached_load_reports(conn_id: str) -> pd.DataFrame:
    state = _get_state_conn()
    if state is None:
        return pd.DataFrame()
    return _load_reports(state)


@st.cache_data(ttl=_CACHE_TTL)
def _cached_load_latest_run(conn_id: str) -> pd.DataFrame:
    state = _get_state_conn()
    if state is None:
        return pd.DataFrame()
    return _load_latest_run(state)


@st.cache_data(ttl=_CACHE_TTL)
def _cached_load_all_runs(conn_id: str) -> pd.DataFrame:
    state = _get_state_conn()
    if state is None:
        return pd.DataFrame()
    return _load_all_runs(state)


@st.cache_data(ttl=_CACHE_TTL)
def _cached_load_run_events(conn_id: str, run_id: str) -> pd.DataFrame:
    state = _get_state_conn()
    if state is None:
        return pd.DataFrame()
    return _load_run_events(state, run_id)


@st.cache_data(ttl=_CACHE_TTL)
def _cached_load_quarantine(conn_id: str) -> pd.DataFrame:
    state = _get_state_conn()
    if state is None:
        return pd.DataFrame()
    return _load_quarantine(state)


@st.cache_data(ttl=_CACHE_TTL)
def _cached_load_staleness_events(conn_id: str) -> pd.DataFrame:
    state = _get_state_conn()
    if state is None:
        return pd.DataFrame()
    return _load_staleness_events(state)


@st.cache_data(ttl=_CACHE_TTL)
def _cached_load_symbol_options(conn_id: str) -> pd.DataFrame:
    state = _get_state_conn()
    if state is None:
        return pd.DataFrame()
    return _load_symbol_options(state)


def _read_markdown(path: Path) -> str:
    try:
        return path.read_text()
    except (FileNotFoundError, PermissionError, IsADirectoryError) as e:
        return f"Error reading {path}: {e}"


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


def _daily_briefing(state: duckdb.DuckDBPyConnection, run_id: str | None) -> None:
    _section_header("Daily Briefing", "Latest run summary and portfolio changes")

    halted = is_halted()
    if halted:
        halt_info = read_halt()
        reason = halt_info.get("reason", "unknown") if halt_info else "unknown"
        _status_badge("error", f"System Halted — Reason: {reason}")
    else:
        _status_badge("success", "System Running — No active halts")

    runs = _cached_load_latest_run("state")
    if runs.empty:
        return

    last_run = runs.iloc[0]
    run_type = str(last_run.run_type).capitalize() if last_run.run_type else "—"
    status = str(last_run.status).capitalize() if last_run.status else "—"
    run_date = str(last_run.start_ts)[:10] if last_run.start_ts else "—"
    col1, col2, col3 = st.columns(3, gap="medium")

    col1.metric("Last Run Type", run_type, help=_help_text("Last Run Type"))
    col2.metric("Run Status", status, help=_help_text("Run Status"))
    col3.metric("Run Date", run_date, help=_help_text("Run Date"))

    if run_id:
        events_df = _cached_load_run_events("state", run_id)
        if not events_df.empty:
            scored = len(events_df[events_df["event_type"] == _EVT_CANDIDATE_SCORED])
            blocked = len(events_df[events_df["event_type"] == _EVT_CANDIDATE_BLOCKED])
            promoted = len(events_df[events_df["event_type"] == _EVT_CANDIDATE_PROMOTED])
            filled = len(events_df[events_df["event_type"] == _EVT_FILL_BOOKED])

            _metric_card("Promoted", str(promoted))

            with st.expander("Candidate Funnel"):
                fc1, fc2, fc3, fc4 = st.columns(4, gap="medium")
                fc1.metric("Scored", scored, help=_help_text("Scored"))
                fc2.metric("Blocked", blocked, help=_help_text("Blocked"))
                fc3.metric("Promoted", promoted, help=_help_text("Promoted"))
                fc4.metric("Fills", filled, help=_help_text("Fills"))

    equity_df = _cached_load_equity_curve("state")
    if len(equity_df) >= 2:
        prev_eq = float(equity_df.iloc[-2].equity)
        curr_eq = float(equity_df.iloc[-1].equity)
        delta = curr_eq - prev_eq
        delta_str = f"+${delta:,.2f}" if delta >= 0 else f"-${abs(delta):,.2f}"
        st.caption(f"Equity: **${curr_eq:,.2f}** ({delta_str} from previous run)")
    elif len(equity_df) == 1:
        st.caption(f"Equity: **${float(equity_df.iloc[0].equity):,.2f}**")

    quarantined = _cached_load_quarantine("state")
    staleness = _cached_load_staleness_events("state")
    attention_items: list[str] = []
    if not quarantined.empty:
        attention_items.append(f"{len(quarantined)} quarantined")
    if not staleness.empty:
        attention_items.append(f"{len(staleness)} staleness events")
    if attention_items:
        st.caption(f":warning: Attention: {'; '.join(attention_items)}")


def _attention_center(state: duckdb.DuckDBPyConnection) -> None:
    _section_header("Attention Center", "Items requiring review")

    quarantined = _cached_load_quarantine("state")
    staleness = _cached_load_staleness_events("state")
    positions = _cached_load_positions("state")
    equity_df = _cached_load_equity_curve("state")

    items: list[dict[str, str]] = []

    halted = is_halted()
    if halted:
        halt_info = read_halt()
        reason = halt_info.get("reason", "unknown") if halt_info else "unknown"
        items.append(
            {
                "severity": "critical",
                "title": "System Halted",
                "detail": f"Reason: {reason}",
                "source": "system",
            }
        )

    if not positions.empty and not equity_df.empty:
        for _, pos in positions.iterrows():
            stop = pos.get("stop_price")
            current = pos.get("current_price")
            if stop and current and stop > 0:
                dist_pct = (current - stop) / current * 100
                if dist_pct < 5.0:
                    items.append(
                        {
                            "severity": "watch",
                            "title": f"{pos['symbol']} near stop",
                            "detail": f"Distance to stop: {dist_pct:.1f}%",
                            "source": pos["symbol"],
                        }
                    )

    for _, q in quarantined.iterrows():
        items.append(
            {
                "severity": "warning",
                "title": f"{q['symbol']} quarantined",
                "detail": str(q.get("reason", "")),
                "source": q["symbol"],
            }
        )

    for _ in range(len(staleness)):
        items.append(
            {
                "severity": "warning",
                "title": "Data staleness detected",
                "detail": "Some data sources may be stale",
                "source": "data",
            }
        )

    consistency_violations = _safe_query(
        state,
        f"SELECT payload FROM events WHERE event_type = '{_EVT_CONSISTENCY_VIOLATION}'"
        " ORDER BY timestamp DESC LIMIT 5",
    )
    for _ in range(len(consistency_violations)):
        items.append(
            {
                "severity": "critical",
                "title": "Consistency violation",
                "detail": "System invariants were violated",
                "source": "system",
            }
        )

    if not items:
        _status_badge("success", ":white_check_mark: No action required")
        return

    severity_order = {"critical": 0, "warning": 1, "watch": 2}
    items.sort(key=lambda x: severity_order.get(x["severity"], 99))

    for item in items:
        icon_map = {"critical": ":red_circle:", "warning": ":warning:", "watch": ":eyes:"}
        icon = icon_map.get(item["severity"], ":information_source:")
        st.markdown(f"{icon} **{item['title']}** — {item['detail']}")


def _decision_funnel(state: duckdb.DuckDBPyConnection) -> None:
    _section_header("Decision Funnel", "How candidates moved through the pipeline")

    runs = _cached_load_latest_run("state")
    if runs.empty:
        _empty_state("No run data available")
        return

    run_id = str(runs.iloc[0].get("run_id", ""))
    if not run_id:
        _empty_state("No run ID available")
        return

    events_df = _cached_load_run_events("state", run_id)
    if events_df.empty:
        _empty_state("No events for latest run")
        return

    scored = events_df[events_df["event_type"] == _EVT_CANDIDATE_SCORED]
    blocked = events_df[events_df["event_type"] == _EVT_CANDIDATE_BLOCKED]
    promoted = events_df[events_df["event_type"] == _EVT_CANDIDATE_PROMOTED]
    filled = events_df[events_df["event_type"] == _EVT_FILL_BOOKED]

    fc1, fc2, fc3, fc4 = st.columns(4, gap="medium")
    fc1.metric("Scored", len(scored), help=_help_text("Scored"))
    fc2.metric("Blocked", len(blocked), help=_help_text("Blocked"))
    fc3.metric("Promoted", len(promoted), help=_help_text("Promoted"))
    fc4.metric("Fills", len(filled), help=_help_text("Fills"))

    if not blocked.empty:
        reasons: dict[str, int] = {}
        for _, row in blocked.iterrows():
            payload = _safe_json_loads(row["payload"])
            if not payload:
                continue
            gate = payload.get("gate", "unknown")
            reasons[gate] = reasons.get(gate, 0) + 1
        if reasons:
            st.markdown("**Top block reasons:**")
            reason_df = pd.DataFrame(
                [
                    {"Gate": gate, "Count": count}
                    for gate, count in sorted(reasons.items(), key=lambda x: -x[1])
                ]
            )
            _data_table(reason_df, height=len(reasons) * 35 + 10)

    if not promoted.empty:
        st.markdown("**Promoted symbols:**")
        promo_rows: list[dict] = []
        promo_symbols: list[str] = []
        for _, row in promoted.iterrows():
            payload = _safe_json_loads(row["payload"])
            if not payload:
                continue
            promo_rows.append(
                {
                    "Symbol": payload.get("symbol", "?"),
                    "Score": payload.get("score", "?"),
                    "Target Weight": payload.get("target_weight", "?"),
                }
            )
            sym = str(payload.get("symbol", ""))
            if sym:
                promo_symbols.append(sym)
        if promo_rows:
            _data_table(pd.DataFrame(promo_rows), height=len(promo_rows) * 35 + 10)
        if promo_symbols:
            st.markdown("**Investigate promoted:**")
            promo_cols = st.columns(min(len(promo_symbols), 6), gap="medium")
            for i, sym in enumerate(promo_symbols[:6]):
                if promo_cols[i].button(f"🔍 {sym}", key=f"inv_promo_{sym}"):
                    _jump_to_symbol(sym)

    if not blocked.empty:
        with st.expander("View blocked symbols"):
            block_rows: list[dict] = []
            block_symbols: list[str] = []
            for _, row in blocked.iterrows():
                payload = _safe_json_loads(row["payload"])
                if not payload:
                    continue
                block_rows.append(
                    {
                        "Symbol": payload.get("symbol", "?"),
                        "Gate": payload.get("gate", "?"),
                        "Reason": payload.get("reason", ""),
                    }
                )
                sym = str(payload.get("symbol", ""))
                if sym and sym not in block_symbols:
                    block_symbols.append(sym)
            if block_rows:
                _data_table(pd.DataFrame(block_rows), height=min(len(block_rows) * 35 + 10, 400))
            if block_symbols:
                st.markdown("**Investigate blocked:**")
                block_cols = st.columns(min(len(block_symbols), 6), gap="medium")
                for i, sym in enumerate(block_symbols[:6]):
                    if block_cols[i].button(f"🔍 {sym}", key=f"inv_block_{sym}"):
                        _jump_to_symbol(sym)


def _run_history(state: duckdb.DuckDBPyConnection) -> None:
    _section_header("Run History", "Recent pipeline runs")

    all_runs = _cached_load_all_runs("state")
    if all_runs.empty:
        _empty_state("No runs found")
        return

    display = all_runs.copy()
    if "start_ts" in display.columns:
        display["date"] = display["start_ts"].astype(str).str[:10]
    if "config_hash" in display.columns:
        display["config"] = display["config_hash"].astype(str).str[:8]

    cols = [c for c in ["date", "run_type", "status", "config"] if c in display.columns]
    if cols:
        _data_table(display[cols].head(10), height=min(10 * 35 + 10, 400))

    if len(all_runs) >= 2:
        configs = all_runs["config_hash"].dropna().unique()
        if len(configs) > 1:
            st.caption(f":warning: Config changed between runs ({len(configs)} distinct hashes)")


def home_tab(state: duckdb.DuckDBPyConnection) -> None:
    runs = _cached_load_latest_run("state")
    run_id: str | None = str(runs.iloc[0]["run_id"]) if not runs.empty else None

    _daily_briefing(state, run_id)
    _attention_center(state)

    equity_df = _cached_load_equity_curve("state")
    if not equity_df.empty:
        _section_header("Equity Curve")
        st.line_chart(equity_df, x="equity_date", y="equity")
        first_equity = float(equity_df.iloc[0].equity)
        if len(equity_df) > 1:
            latest_equity = float(equity_df.iloc[-1].equity)
            _metric_card("Total Return", f"{((latest_equity / first_equity - 1) * 100):+.2f}%")
        else:
            _metric_card("Total Return", "—")
    else:
        _empty_state(
            "No equity data available. Run a backtest or start paper trading to see results."
        )

    _decision_funnel(state)

    _section_header("Portfolio Summary")
    positions = _cached_load_positions("state")
    if not positions.empty:
        total_value = float(positions["market_value"].sum())
        total_pl = float(positions["unrealized_pl"].sum())
        latest_equity_val: float = float(equity_df.iloc[-1].equity) if not equity_df.empty else 1.0
        exposure_pct = (total_value / latest_equity_val * 100) if latest_equity_val > 0 else 0.0

        col1, col2, col3, col4 = st.columns(4, gap="medium")
        col1.metric("Open Positions", len(positions), help=_help_text("Open Positions"))
        col2.metric("Total Exposure", f"${total_value:,.2f}", help=_help_text("Total Exposure"))
        col3.metric("Exposure %", f"{exposure_pct:.1f}%", help=_help_text("Exposure %"))
        col4.metric("Unrealized P&L", f"${total_pl:+,.2f}", help=_help_text("Unrealized P&L"))
    else:
        _empty_state("No open positions")

    _run_history(state)


def portfolio_tab(state: duckdb.DuckDBPyConnection) -> None:
    _section_header("Portfolio Risk", "Position-level risk analysis")

    positions = _cached_load_positions("state")
    if positions.empty:
        _empty_state("No open positions")
        return

    display = positions.copy()
    total_value = float(positions["market_value"].sum())
    total_pl = float(positions["unrealized_pl"].sum())

    col1, col2, col3, col4 = st.columns(4, gap="medium")
    col1.metric("Total Market Value", f"${total_value:,.2f}", help=_help_text("Total Market Value"))
    col2.metric("Unrealized P&L", f"${total_pl:+,.2f}", help=_help_text("Unrealized P&L"))
    col3.metric("Open Positions", len(positions), help=_help_text("Open Positions"))

    if all(c in display.columns for c in ["current_price", "stop_price"]):
        valid_mask = display["stop_price"].notna() & (display["stop_price"] > 0)
        display["Dist-to-Stop %"] = 0.0
        display["Risk-at-Stop $"] = 0.0
        display.loc[valid_mask, "Dist-to-Stop %"] = (
            (display.loc[valid_mask, "current_price"] - display.loc[valid_mask, "stop_price"])
            / display.loc[valid_mask, "current_price"]
            * 100
        )
        display.loc[valid_mask, "Risk-at-Stop $"] = (
            display.loc[valid_mask, "current_price"] - display.loc[valid_mask, "stop_price"]
        ) * display.loc[valid_mask, "quantity"]
        display.loc[~valid_mask, "Dist-to-Stop %"] = None
        near_stop = (display["Dist-to-Stop %"].notna() & (display["Dist-to-Stop %"] < 5.0)).sum()
        col4.metric("Near Stop (<5%)", near_stop, help=_help_text("Near Stop (<5%)"))

    if "partial_taken" in display.columns:
        display["Partial"] = display["partial_taken"].map(
            {True: ":white_check_mark: Yes", False: ""}
        )

    near_mask = (
        display["Dist-to-Stop %"].notna() & (display["Dist-to-Stop %"] < 5.0)
        if "Dist-to-Stop %" in display.columns
        else pd.Series([False] * len(display))
    )
    if near_mask.any():
        _status_badge("warning", f"{near_mask.sum()} position(s) near stop — review risk")

    sort_col = "Dist-to-Stop %" if "Dist-to-Stop %" in display.columns else "market_value"
    display = display.sort_values(by=sort_col, ascending=True, na_position="last")
    _data_table(display, height=min(len(display) * 35 + 10, 500))

    st.markdown("**Quick investigate:**")
    sym_list = [str(p.get("symbol", "")) for _, p in positions.iterrows() if p.get("symbol")]
    for row_start in range(0, len(sym_list), 6):
        cols = st.columns(6, gap="medium")
        for i, sym in enumerate(sym_list[row_start : row_start + 6]):
            if cols[i].button(f"🔍 {sym}", key=f"inv_pos_{sym}"):
                _jump_to_symbol(sym)


def reports_tab(state: duckdb.DuckDBPyConnection) -> None:
    _section_header("Reports")

    reports = _cached_load_reports("state")
    if not reports.empty:
        options = {
            f"{r.report_date} | {r.report_type}": (str(r.report_date), r.report_type)
            for _, r in reports.iterrows()
        }
        selected = st.selectbox("Select report", list(options.keys()))
        if selected:
            dt_str, rtype = options[selected]
            row = _safe_query(
                state,
                "SELECT content FROM reports WHERE report_date = ? AND report_type = ?",
                [dt_str, rtype],
            )
            if not row.empty:
                st.markdown(row.iloc[0]["content"])
    else:
        _empty_state("No reports available", ":memo:")


def concepts_tab() -> None:
    _section_header("Concept Cards", "Educational content on trading mechanisms")

    concepts_dir = Path(__file__).resolve().parent.parent / "concepts"
    cards = _build_concepts_manifest(concepts_dir)
    if not cards:
        _empty_state("No concept cards found", ":books:")
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
        _empty_state("Select a concept to view its content", ":books:")


def decision_tab(state: duckdb.DuckDBPyConnection) -> None:
    _section_header("Decision Explorer", "Investigate per-symbol decision and event history")

    symbols_df = _cached_load_symbol_options("state")
    available_symbols: list[str] = symbols_df["symbol"].tolist() if not symbols_df.empty else []

    jump_sym = st.session_state.pop("jump_symbol", "")
    options = [""] + available_symbols
    default_index = 0
    if jump_sym and jump_sym in available_symbols:
        default_index = options.index(jump_sym)

    if available_symbols:
        selected_symbol = st.selectbox(
            "Choose a symbol",
            options,
            index=default_index,
            format_func=lambda x: x or "Select a symbol...",
        )
        symbol = selected_symbol.strip().upper() if selected_symbol else ""
        if not symbol:
            _empty_state("Select or type a symbol to explore its history", ":mag:")
            return
    else:
        symbol = ""
        symbol_input = st.text_input("Symbol", placeholder="e.g. AAPL").strip().upper()
        if symbol_input:
            if not symbol_input.isalnum() or len(symbol_input) > 5:
                st.warning("Enter a valid symbol (1-5 alphanumeric characters)")
            else:
                symbol = symbol_input
        if not symbol:
            _empty_state("Enter a symbol to explore its decision history", ":mag:")
            return

    decisions = _safe_query(
        state,
        "SELECT decision_id, run_id, symbol, decision_date, action, confidence, reasons,"
        " candidate_json, risk_results, mechanism_results"
        " FROM decisions WHERE symbol = ? ORDER BY decision_date DESC LIMIT 20",
        [symbol],
    )

    evt_in = ", ".join(
        f"'{t}'"
        for t in [
            _EVT_CANDIDATE_BLOCKED,
            _EVT_CANDIDATE_SCORED,
            _EVT_CANDIDATE_PROMOTED,
            _EVT_STOP_ADJUSTED,
            _EVT_PARTIAL_TAKEN,
            _EVT_TIME_STOP_TRIGGERED,
            _EVT_FILL_BOOKED,
        ]
    )
    events = _safe_query(
        state,
        f"SELECT event_type, timestamp, payload FROM events"
        f" WHERE event_type IN ({evt_in})"
        f" AND payload->>'symbol' = ?"
        f" ORDER BY timestamp DESC LIMIT 50",
        [symbol],
    )

    st.markdown(f"**Timeline for {symbol}**")

    if not decisions.empty or not events.empty:
        combined: list[dict[str, str]] = []
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
            payload = _safe_json_loads(r["payload"]) or {}
            detail = ""
            if r.event_type == _EVT_CANDIDATE_BLOCKED:
                detail = f"Blocked at gate={payload.get('gate', '?')}: {payload.get('reason', '')}"
            elif r.event_type == _EVT_CANDIDATE_SCORED:
                detail = f"Scored {payload.get('composite_score', '?')}"
            elif r.event_type == _EVT_CANDIDATE_PROMOTED:
                detail = f"Promoted with score {payload.get('score', '?')}"
            elif r.event_type == _EVT_STOP_ADJUSTED:
                old = payload.get("old_stop", "?")
                new = payload.get("new_stop", "?")
                detail = f"Stop adjusted: {old} → {new}"
            elif r.event_type == _EVT_PARTIAL_TAKEN:
                qty = payload.get("quantity", "?")
                price = payload.get("price", "?")
                detail = f"Partial take: {qty} @ {price}"
            elif r.event_type == _EVT_TIME_STOP_TRIGGERED:
                detail = f"Time stop after {payload.get('days_held', '?')} days"
            elif r.event_type == _EVT_FILL_BOOKED:
                detail = "Fill booked"
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
        _data_table(timeline, height=min(len(timeline) * 35 + 10, 500))
    else:
        _empty_state(f"No history found for symbol: {symbol}", ":mag:")


def journal_tab(state: duckdb.DuckDBPyConnection) -> None:
    _section_header("Journal", "Daily journal entries")

    journals = _cached_load_journals("state")
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
                _empty_state("No journal entry for this date", ":memo:")
    else:
        _empty_state(
            "No journal entries available. Run the pipeline to generate daily journals.",
            ":memo:",
        )


def main() -> None:
    st.title("Alpha Quant Dashboard")

    st.warning(
        ":construction: **Beta Release** — This system is in active development. "
        "Data and decisions reflect paper trading only. "
        "Do not use for live trading decisions."
    )

    st.caption(f"Data directory: {DATA_DIR.resolve()}")

    try:
        cfg = load_config()
        refresh_secs = cfg.dashboard.refresh_seconds
    except ConfigError:
        refresh_secs = 0

    if refresh_secs > 0:
        if "last_refresh" not in st.session_state:
            st.session_state.last_refresh = time.time()
        else:
            elapsed = time.time() - st.session_state.last_refresh
            if elapsed >= refresh_secs:
                st.session_state.last_refresh = time.time()
                st.rerun()  # type: ignore[attr-defined]  # Streamlit stubs don't expose rerun()

    if not DATA_DIR.exists():
        st.warning(f"Data directory not found: {DATA_DIR}")
        _empty_state("Run the pipeline at least once to generate data.")
        return

    if not (DATA_DIR / "state.db").exists():
        st.warning(f"No state database found at {DATA_DIR / 'state.db'}")
        _empty_state("Run the pipeline at least once to generate data.")
        return

    state = _connect()
    if state is None:
        return

    with st.sidebar:
        st.markdown("**System Status**")
        if is_halted():
            st.error(":red_circle: Halted")
        else:
            st.success(":green_circle: Running")
        if st.button("Refresh :arrows_counterclockwise:"):
            st.rerun()  # type: ignore[attr-defined]  # Streamlit stubs don't expose rerun()

    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        ["Home", "Portfolio", "Reports", "Concepts", "Journal", "Explorer"]
    )

    with st.spinner("Refreshing..."):
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
