import os
import sys
import subprocess
import pandas as pd
import streamlit as st

from src.journal import add_trade, load_journal, close_trade

st.set_page_config(page_title="个人投资研究台", layout="wide")
st.title("个人投资研究台")
st.caption("适合手动交易者的本地投资辅助系统：看股票、做计划、记交易、做复盘。")


def run_py(script, *args):
    cmd = [sys.executable, script, *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result


def load_csv(path):
    if os.path.exists(path):
        return pd.read_csv(path)
    return None


# 顶部说明
with st.expander("第一次使用建议先看这里", expanded=True):
    st.markdown("""
### 这个系统是做什么的？
这是一个本地运行的投资辅助系统，适合你继续在 CIBC 或其他券商平台**手动下单**时使用。

### 它不会做什么？
- 不会自动帮你买卖股票
- 不会直接连接 CIBC 自动下单
- 不会替你做最终投资决定

### 它会帮你做什么？
- 更新行情数据
- 生成观察名单
- 生成交易计划
- 查看回测结果
- 读取 SEC 财报摘要
- 记录真实交易
- 做每周复盘

### 推荐使用顺序
1. 每天先点“更新价格数据”
2. 再看“观察名单”和“交易计划”
3. 真正交易后，到“交易日志”里记录
4. 每周末到“每周复盘”查看结果
    """)

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("一、每日更新")
    st.caption("每天收盘后建议按顺序点击，用于更新研究数据。")

    if st.button("1）更新价格数据"):
        r = run_py("src/ingest_prices.py")
        if r.returncode == 0:
            st.success("价格数据已更新")
        else:
            st.error(r.stderr or r.stdout)

    if st.button("2）生成观察名单"):
        r = run_py("src/score_watchlist.py")
        if r.returncode == 0:
            st.success("观察名单已更新")
        else:
            st.error(r.stderr or r.stdout)

    if st.button("3）生成交易计划"):
        r = run_py("src/trade_plan.py")
        if r.returncode == 0:
            st.success("交易计划已生成")
        else:
            st.error(r.stderr or r.stdout)

    if st.button("4）更新财报摘要"):
        r = run_py("src/edgar_summary.py")
        if r.returncode == 0:
            st.success("财报摘要已更新")
        else:
            st.error(r.stderr or r.stdout)

with col2:
    st.subheader("二、策略检查")
    st.caption("用于检查策略在历史上是否有效，不代表未来一定有效。")

    with st.form("backtest_form"):
        bt_ticker = st.text_input("输入要回测的股票代码", value="SPY")
        bt_submit = st.form_submit_button("运行单只股票回测")
        if bt_submit:
            r = run_py("src/backtest_bt.py", bt_ticker)
            if r.returncode == 0:
                st.success("单只股票回测完成")
            else:
                st.error(r.stderr or r.stdout)

    if st.button("运行组合回测"):
        r = run_py("src/backtest_portfolio.py")
        if r.returncode == 0:
            st.success("组合回测完成")
        else:
            st.error(r.stderr or r.stdout)

with col3:
    st.subheader("三、系统文件状态")
    st.caption("这些文件是系统自动生成的结果，用来支撑页面展示。")

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
        label = f.replace("reports/", "")
        st.write("✅" if os.path.exists(f) else "⬜", label)

st.divider()

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["观察名单", "交易计划", "回测结果", "财报摘要", "交易日志", "每周复盘"]
)

with tab1:
    st.subheader("观察名单")
    st.caption("这是系统根据规则筛选出的当前值得重点关注的股票列表。分数越高，通常说明趋势或表现更强。")

    df = load_csv("reports/watchlist.csv")
    if df is not None:
        rename_map = {
            "ticker": "股票代码",
            "close": "最新价格",
            "score": "综合分数",
            "ma50": "50日均线",
            "ma200": "200日均线",
            "ret_252": "一年涨跌幅",
            "vol_60": "60日波动率",
            "date": "日期",
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        st.dataframe(df, use_container_width=True)
    else:
        st.info("还没有观察名单，请先点击“生成观察名单”。")

with tab2:
    st.subheader("交易计划")
    st.caption("这是系统根据仓位与风险规则生成的交易参考，不是自动交易指令。")

    df = load_csv("reports/trade_plan.csv")
    if df is not None:
        rename_map = {
            "ticker": "股票代码",
            "plan_date": "计划日期",
            "close": "当前价格",
            "score": "分数",
            "entry_price": "参考买入价",
            "stop_price": "参考止损价",
            "shares": "建议股数",
            "note": "备注",
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        st.dataframe(df, use_container_width=True)
    else:
        st.info("还没有交易计划，请先点击“生成交易计划”。")

with tab3:
    st.subheader("回测结果")
    st.caption("回测用于检查这套规则在过去是否有一定效果。回测好，不代表未来一定有效。")

    st.markdown("### 单只股票回测")
    df = load_csv("reports/backtest_metrics.csv")
    if df is not None:
        rename_map = {
            "run_date": "运行日期",
            "strategy_name": "策略名称",
            "ticker": "股票代码",
            "start_date": "开始日期",
            "end_date": "结束日期",
            "final_value": "期末资产",
            "total_return": "总收益率",
            "max_drawdown": "最大回撤",
            "sharpe": "夏普比率",
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        st.dataframe(df, use_container_width=True)
    else:
        st.info("还没有单票回测结果，请先运行回测。")

    st.markdown("### 组合回测")
    portfolio_df = load_csv("reports/backtest_portfolio_metrics.csv")
    if portfolio_df is not None:
        rename_map = {
            "run_date": "运行日期",
            "strategy_name": "策略名称",
            "ticker": "代码",
            "start_date": "开始日期",
            "end_date": "结束日期",
            "final_value": "期末资产",
            "total_return": "总收益率",
            "max_drawdown": "最大回撤",
            "sharpe": "夏普比率",
        }
        portfolio_df = portfolio_df.rename(columns={k: v for k, v in rename_map.items() if k in portfolio_df.columns})
        st.dataframe(portfolio_df, use_container_width=True)
    else:
        st.info("还没有组合回测结果，请先运行组合回测。")

    st.markdown("### 组合资金曲线")
    eq_df = load_csv("reports/backtest_portfolio_equity.csv")
    if eq_df is not None and not eq_df.empty:
        eq_df["date"] = pd.to_datetime(eq_df["date"])
        eq_df = eq_df.set_index("date")
        st.line_chart(eq_df["equity"])
    else:
        st.info("还没有组合资金曲线。")

with tab4:
    st.subheader("财报摘要")
    st.caption("这里展示的是系统从 SEC EDGAR 抓取并整理的最近申报信息与简要财务摘要。")

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
        display_df = df[existing_cols].copy()

        rename_map = {
            "ticker": "股票代码",
            "security_type": "类型",
            "form": "申报表格",
            "filing_date": "申报日期",
            "revenue": "营收",
            "net_income": "净利润",
            "assets": "总资产",
            "liabilities": "总负债",
            "summary": "中文摘要",
        }
        display_df = display_df.rename(columns={k: v for k, v in rename_map.items() if k in display_df.columns})
        st.dataframe(display_df, use_container_width=True)

        st.markdown("### 最近申报文件链接")
        for _, row in df.iterrows():
            ticker = row.get("ticker", "")
            filing_url = row.get("filing_url", "")
            summary = row.get("summary", "")

            st.markdown(f"**{ticker}**")
            if pd.notna(filing_url) and filing_url:
                st.markdown(f"[打开最近申报文件]({filing_url})")
            st.write(summary)
            st.divider()
    else:
        st.info("还没有财报摘要，请先点击“更新财报摘要”。")

with tab5:
    st.subheader("交易日志")
    st.caption("这里记录你真实发生的交易。日志越完整，后面的每周复盘越有价值。")

    st.markdown("### 新增一笔交易")
    with st.form("add_trade_form"):
        c1, c2, c3 = st.columns(3)

        with c1:
            trade_date = st.date_input("交易日期")
            ticker = st.text_input("股票代码", value="AAPL")
            side = st.selectbox("方向", ["BUY", "SELL"])

        with c2:
            entry_price = st.number_input("买入/卖出价格", min_value=0.0, value=100.0, step=0.01)
            shares = st.number_input("股数", min_value=1, value=10, step=1)
            stop_price = st.number_input("计划止损价", min_value=0.0, value=95.0, step=0.01)

        with c3:
            planned_target = st.number_input("计划目标价", min_value=0.0, value=110.0, step=0.01)
            setup_tag = st.text_input("交易类型标签", value="trend_pullback")
            execution_grade = st.selectbox("执行评分", ["A", "B", "C", "D"])

        thesis = st.text_area("交易理由", value="为什么做这笔交易？")
        submitted = st.form_submit_button("保存交易")

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
            st.success("交易已保存")

    st.markdown("### 平掉一笔已有交易")
    journal_df = load_journal()
    open_df = journal_df[journal_df["exit_date"].isna()] if not journal_df.empty else pd.DataFrame()

    if not open_df.empty:
        trade_options = {
            f'#{row["id"]} {row["trade_date"]} {row["ticker"]} @ {row["entry_price"]}': int(row["id"])
            for _, row in open_df.iterrows()
        }

        with st.form("close_trade_form"):
            selected = st.selectbox("选择要平仓的交易", list(trade_options.keys()))
            exit_date = st.date_input("平仓日期")
            exit_price = st.number_input("平仓价格", min_value=0.0, value=100.0, step=0.01)
            review_note = st.text_area("平仓原因/复盘备注", value="为什么现在退出？")
            close_submitted = st.form_submit_button("确认平仓")

            if close_submitted:
                close_trade(
                    trade_options[selected],
                    str(exit_date),
                    float(exit_price),
                    review_note,
                )
                st.success("交易已平仓")
    else:
        st.info("目前没有未平仓交易。")

    st.markdown("### 全部交易记录")
    journal_df = load_journal()
    if not journal_df.empty:
        rename_map = {
            "id": "编号",
            "trade_date": "交易日期",
            "ticker": "股票代码",
            "side": "方向",
            "entry_price": "建仓价格",
            "shares": "股数",
            "stop_price": "止损价",
            "planned_target": "目标价",
            "thesis": "交易理由",
            "setup_tag": "标签",
            "execution_grade": "执行评分",
            "exit_date": "平仓日期",
            "exit_price": "平仓价格",
            "pnl": "盈亏",
            "review_note": "复盘备注",
            "planned_stop_hit": "是否触发计划止损",
            "exit_discipline": "退出类型",
        }
        journal_df = journal_df.rename(columns={k: v for k, v in rename_map.items() if k in journal_df.columns})
        st.dataframe(journal_df, use_container_width=True)
    else:
        st.info("还没有交易记录。")

with tab6:
    st.subheader("每周复盘")
    st.caption("这里会把你的交易结果、执行质量和组合表现整合起来，帮助你看清问题出在哪里。")

    if st.button("生成每周复盘"):
        r = run_py("src/weekly_review.py")
        if r.returncode == 0:
            st.success("每周复盘已生成")
        else:
            st.error(r.stderr or r.stdout)

    review_df = load_csv("reports/weekly_review.csv")
    if review_df is not None:
        rename_map = {
            "review_date": "复盘日期",
            "new_trades": "本周新交易数",
            "closed_trades": "本周已平仓数",
            "weekly_realized_pnl": "本周已实现盈亏",
            "summary": "结论摘要",
        }
        review_df = review_df.rename(columns={k: v for k, v in rename_map.items() if k in review_df.columns})
        st.dataframe(review_df, use_container_width=True)
    else:
        st.info("还没有每周复盘，请先点击“生成每周复盘”。")

    diag_df = load_csv("reports/weekly_diagnostics.csv")
    if diag_df is not None and not diag_df.empty:
        st.markdown("### 自动诊断")
        rename_map = {
            "metric": "指标",
            "value": "值",
            "comment": "说明",
        }
        diag_df = diag_df.rename(columns={k: v for k, v in rename_map.items() if k in diag_df.columns})
        st.dataframe(diag_df, use_container_width=True)
    else:
        st.info("还没有诊断数据。")

    journal_df = load_journal()
    if journal_df is not None and not journal_df.empty:
        journal_df["trade_date"] = pd.to_datetime(journal_df["trade_date"], errors="coerce")
        journal_df["exit_date"] = pd.to_datetime(journal_df["exit_date"], errors="coerce")

        week_start = pd.Timestamp.today().normalize() - pd.Timedelta(days=7)

        weekly_closed = journal_df[
            journal_df["exit_date"].notna() & (journal_df["exit_date"] >= week_start)
        ].copy()

        if not weekly_closed.empty:
            st.markdown("### 本周已平仓交易盈亏图")
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
                st.markdown("### 本周执行评分分布")
                st.bar_chart(grade_chart.set_index("grade")["count"])

    eq_df = load_csv("reports/backtest_portfolio_equity.csv")
    if eq_df is not None and not eq_df.empty:
        st.markdown("### 组合资金曲线")
        eq_df["date"] = pd.to_datetime(eq_df["date"])
        eq_df = eq_df.set_index("date")
        st.line_chart(eq_df["equity"])

    if os.path.exists("reports/weekly_review.txt"):
        st.markdown("### 文本版复盘")
        with open("reports/weekly_review.txt", "r", encoding="utf-8") as f:
            st.text(f.read())
    else:
        st.info("还没有文本版复盘。")