"""Streamlit dashboard — read-only view of system state."""

from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Alpha Quant Dashboard",
    page_icon="📈",
    layout="wide",
)

DATA_DIR = Path("data")


@st.cache_resource
def _connect() -> tuple[duckdb.DuckDBPyConnection, duckdb.DuckDBPyConnection]:
    analytical = duckdb.connect()
    state_path = DATA_DIR / "state.db"
    state = duckdb.connect(str(state_path))
    return analytical, state


def _load_equity_curve(state: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return state.execute(
        "SELECT equity_date, equity, cash FROM equity_curve ORDER BY equity_date"
    ).fetchdf()


def _load_positions(state: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return state.execute(
        "SELECT symbol, quantity, entry_price, avg_cost, current_price,"
        " stop_price, market_value, unrealized_pl"
        " FROM positions WHERE quantity > 0"
    ).fetchdf()


def _load_journals(state: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return state.execute(
        "SELECT entry_date FROM journal_entries ORDER BY entry_date DESC LIMIT 30"
    ).fetchdf()


def _load_reports(state: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return state.execute(
        "SELECT report_date, report_type FROM reports ORDER BY report_date DESC LIMIT 20"
    ).fetchdf()


def _read_markdown(path: Path) -> str:
    try:
        return path.read_text()
    except FileNotFoundError:
        return f"File not found: {path}"


def overview_tab(analytical: duckdb.DuckDBPyConnection, state: duckdb.DuckDBPyConnection) -> None:
    st.header("Overview")

    equity_df = _load_equity_curve(state)
    if not equity_df.empty:
        latest = equity_df.iloc[-1]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Equity", f"${latest.equity:,.2f}")
        col2.metric("Cash", f"${latest.cash:,.2f}")
        col3.metric(
            "Return",
            f"{((latest.equity / equity_df.iloc[0].equity - 1) * 100):+.2f}%"
            if len(equity_df) > 1
            else "—",
        )
        col4.metric("Days", len(equity_df))

        st.subheader("Equity Curve")
        st.line_chart(equity_df, x="equity_date", y="equity")
    else:
        st.info("No equity data available.")


def portfolio_tab(state: duckdb.DuckDBPyConnection) -> None:
    st.header("Portfolio")

    positions = _load_positions(state)
    if not positions.empty:
        st.dataframe(positions, width="stretch")

        total_value = positions["market_value"].sum()
        total_pl = positions["unrealized_pl"].sum()
        col1, col2 = st.columns(2)
        col1.metric("Total Market Value", f"${total_value:,.2f}")
        col2.metric("Total Unrealized P&L", f"${total_pl:+,.2f}")
    else:
        st.info("No open positions.")


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
            row = state.execute(
                "SELECT content FROM reports WHERE report_date = ? AND report_type = ?",
                [dt_str, rtype],
            ).fetchone()
            if row:
                st.markdown(row[0])
    else:
        st.info("No reports available.")


def concepts_tab() -> None:
    st.header("Concept Cards")

    concepts_dir = Path(__file__).resolve().parent.parent / "concepts"
    manifest_path = concepts_dir / "concepts.json"

    import json

    if manifest_path.exists():
        with manifest_path.open() as f:
            cards = json.load(f)
        card_ids = [c["id"] for c in cards]
        selected = st.selectbox("Select concept", card_ids)
        card_path = concepts_dir / f"{selected}.md"
        content = _read_markdown(card_path)
        st.markdown(content)
    else:
        st.info("No concept cards found.")


def main() -> None:
    st.title("Alpha Quant Dashboard")
    st.caption(f"Data directory: {DATA_DIR.resolve()}")

    if not DATA_DIR.exists():
        st.warning(f"Data directory not found: {DATA_DIR}")
        st.info("Run the pipeline at least once to generate data.")
        return

    analytical, state = _connect()

    tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Portfolio", "Reports", "Concepts"])

    with tab1:
        overview_tab(analytical, state)

    with tab2:
        portfolio_tab(state)

    with tab3:
        reports_tab(state)

    with tab4:
        concepts_tab()


if __name__ == "__main__":
    main()
