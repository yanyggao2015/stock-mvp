import os
import sys
import subprocess
import pandas as pd
import streamlit as st

from src.journal import add_trade, load_journal, close_trade

st.set_page_config(page_title="Stock MVP", layout="wide")
st.title("AI-assisted Manual Trading Workbench")


def run_py(script, *args):
    cmd = [sys.executable, script, *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result


def load_csv(path):
    if os.path.exists(path):
        return pd.read_csv(path)
    return None


col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("Daily Update")

    if st.button("1. Ingest Prices"):
        r = run_py("src/ingest_prices.py")
        if r.returncode == 0:
            st.success("Prices updated")
        else:
            st.error(r.stderr or r.stdout)

    if st.button("2. Score Watchlist"):
        r = run_py("src/score_watchlist.py")
        if r.returncode == 0:
            st.success("Watchlist scored")
        else:
            st.error(r.stderr or r.stdout)

    if st.button("3. Build Trade Plan"):
        r = run_py("src/trade_plan.py")
        if r.returncode == 0:
            st.success("Trade plan generated")
        else:
            st.error(r.stderr or r.stdout)

    if st.button("4. Pull EDGAR Summaries"):
        r = run_py("src/edgar_summary.py")
        if r.returncode == 0:
            st.success("EDGAR summaries updated")
        else:
            st.error(r.stderr or r.stdout)

with col2:
    st.subheader("Backtest")

    with st.form("backtest_form"):
        bt_ticker = st.text_input("Ticker", value="SPY")
        bt_submit = st.form_submit_button("Run Backtest")
        if bt_submit:
            r = run_py("src/backtest_bt.py", bt_ticker)
            if r.returncode == 0:
                st.success("Backtest finished")
            else:
                st.error(r.stderr or r.stdout)

    if st.button("Run Portfolio Backtest"):
        r = run_py("src/backtest_portfolio.py")
        if r.returncode == 0:
            st.success("Portfolio backtest finished")
        else:
            st.error(r.stderr or r.stdout)

with col3:
    st.subheader("Reports")
    for f in [
        "reports/watchlist.csv",
        "reports/trade_plan.csv",
        "reports/backtest_metrics.csv",
        "reports/backtest_portfolio_metrics.csv",
        "reports/backtest_portfolio_equity.csv",
        "reports/edgar_summary.csv",
        "reports/weekly_review.csv",
        "reports/weekly_review.txt",
        "reports/weekly_diagnostics.csv",
    ]:
        st.write("✅" if os.path.exists(f) else "⬜", f)

st.divider()

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["Watchlist", "Trade Plan", "Backtest", "EDGAR", "Journal", "Weekly Review"]
)

with tab1:
    df = load_csv("reports/watchlist.csv")
    if df is not None:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No watchlist yet")

with tab2:
    df = load_csv("reports/trade_plan.csv")
    if df is not None:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No trade plan yet")

with tab3:
    st.subheader("Single Ticker Backtest")
    df = load_csv("reports/backtest_metrics.csv")
    if df is not None:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No single-ticker backtest results yet")

    st.subheader("Portfolio Backtest")
    portfolio_df = load_csv("reports/backtest_portfolio_metrics.csv")
    if portfolio_df is not None:
        st.dataframe(portfolio_df, use_container_width=True)
    else:
        st.info("No portfolio backtest results yet")

    st.subheader("Portfolio Equity Curve")
    eq_df = load_csv("reports/backtest_portfolio_equity.csv")
    if eq_df is not None and not eq_df.empty:
        eq_df["date"] = pd.to_datetime(eq_df["date"])
        eq_df = eq_df.set_index("date")
        st.line_chart(eq_df["equity"])
    else:
        st.info("No portfolio equity curve yet")

with tab4:
    df = load_csv("reports/edgar_summary.csv")
    if df is not None:
        show_cols = [
            "ticker",
            "security_type",
            "form",
            "filing_date",
            "revenue",
            "net_income",
            "assets",
            "liabilities",
            "summary",
        ]
        existing_cols = [c for c in show_cols if c in df.columns]
        st.dataframe(df[existing_cols], use_container_width=True)

        st.subheader("Latest Filing Links")
        for _, row in df.iterrows():
            ticker = row.get("ticker", "")
            filing_url = row.get("filing_url", "")
            summary = row.get("summary", "")

            st.markdown(f"**{ticker}**")
            if pd.notna(filing_url) and filing_url:
                st.markdown(f"[Open latest filing]({filing_url})")
            st.write(summary)
            st.divider()
    else:
        st.info("No EDGAR summaries yet")

with tab5:
    st.subheader("Add New Trade")
    with st.form("add_trade_form"):
        c1, c2, c3 = st.columns(3)

        with c1:
            trade_date = st.date_input("Trade Date")
            ticker = st.text_input("Ticker", value="AAPL")
            side = st.selectbox("Side", ["BUY", "SELL"])

        with c2:
            entry_price = st.number_input("Entry Price", min_value=0.0, value=100.0, step=0.01)
            shares = st.number_input("Shares", min_value=1, value=10, step=1)
            stop_price = st.number_input("Stop Price", min_value=0.0, value=95.0, step=0.01)

        with c3:
            planned_target = st.number_input("Planned Target", min_value=0.0, value=110.0, step=0.01)
            setup_tag = st.text_input("Setup Tag", value="trend_pullback")
            execution_grade = st.selectbox("Execution Grade", ["A", "B", "C", "D"])

        thesis = st.text_area("Thesis", value="Why this trade?")
        submitted = st.form_submit_button("Save Trade")

        if submitted:
            add_trade(
                {
                    "trade_date": str(trade_date),
                    "ticker": ticker.upper(),
                    "side": side,
                    "entry_price": float(entry_price),
                    "shares": int(shares),
                    "stop_price": float(stop_price),
                    "planned_target": float(planned_target),
                    "thesis": thesis,
                    "setup_tag": setup_tag,
                    "execution_grade": execution_grade,
                }
            )
            st.success("Trade saved")

    st.subheader("Close Existing Trade")
    journal_df = load_journal()
    open_df = journal_df[journal_df["exit_date"].isna()] if not journal_df.empty else pd.DataFrame()

    if not open_df.empty:
        trade_options = {
            f'#{row["id"]} {row["trade_date"]} {row["ticker"]} @ {row["entry_price"]}': int(row["id"])
            for _, row in open_df.iterrows()
        }

        with st.form("close_trade_form"):
            selected = st.selectbox("Open Trade", list(trade_options.keys()))
            exit_date = st.date_input("Exit Date")
            exit_price = st.number_input("Exit Price", min_value=0.0, value=100.0, step=0.01)
            review_note = st.text_area("Review Note", value="Why did I exit?")
            close_submitted = st.form_submit_button("Close Trade")

            if close_submitted:
                close_trade(
                    trade_options[selected],
                    str(exit_date),
                    float(exit_price),
                    review_note,
                )
                st.success("Trade closed")
    else:
        st.info("No open trades")

    st.subheader("Journal Records")
    journal_df = load_journal()
    if not journal_df.empty:
        st.dataframe(journal_df, use_container_width=True)
    else:
        st.info("No journal records yet")

with tab6:
    st.subheader("Weekly Review")

    if st.button("Generate Weekly Review"):
        r = run_py("src/weekly_review.py")
        if r.returncode == 0:
            st.success("Weekly review generated")
        else:
            st.error(r.stderr or r.stdout)

    review_df = load_csv("reports/weekly_review.csv")
    if review_df is not None:
        st.dataframe(review_df, use_container_width=True)
    else:
        st.info("No weekly review summary yet")

    diag_df = load_csv("reports/weekly_diagnostics.csv")
    if diag_df is not None and not diag_df.empty:
        st.subheader("Diagnostics")
        st.dataframe(diag_df, use_container_width=True)
    else:
        st.info("No diagnostics yet")

    journal_df = load_journal()
    if journal_df is not None and not journal_df.empty:
        journal_df["trade_date"] = pd.to_datetime(journal_df["trade_date"], errors="coerce")
        journal_df["exit_date"] = pd.to_datetime(journal_df["exit_date"], errors="coerce")

        week_start = pd.Timestamp.today().normalize() - pd.Timedelta(days=7)

        weekly_closed = journal_df[
            journal_df["exit_date"].notna() & (journal_df["exit_date"] >= week_start)
        ].copy()

        if not weekly_closed.empty:
            st.subheader("Weekly Closed Trade PnL")
            chart_df = weekly_closed[["ticker", "pnl"]].copy()
            chart_df = chart_df.set_index("ticker")
            st.bar_chart(chart_df["pnl"])

        if "execution_grade" in journal_df.columns:
            weekly_new = journal_df[journal_df["trade_date"] >= week_start].copy()
            if not weekly_new.empty:
                grade_chart = (
                    weekly_new["execution_grade"]
                    .fillna("N/A")
                    .value_counts()
                    .sort_index()
                    .rename_axis("grade")
                    .reset_index(name="count")
                )
                st.subheader("Execution Grade Distribution")
                st.bar_chart(grade_chart.set_index("grade")["count"])

    eq_df = load_csv("reports/backtest_portfolio_equity.csv")
    if eq_df is not None and not eq_df.empty:
        st.subheader("Portfolio Equity Curve")
        eq_df["date"] = pd.to_datetime(eq_df["date"])
        eq_df = eq_df.set_index("date")
        st.line_chart(eq_df["equity"])

    if os.path.exists("reports/weekly_review.txt"):
        st.subheader("Weekly Review Text")
        with open("reports/weekly_review.txt", "r", encoding="utf-8") as f:
            st.text(f.read())
    else:
        st.info("No weekly review text yet")