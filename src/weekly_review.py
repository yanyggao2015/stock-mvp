import os
import sqlite3
import pandas as pd

DB_PATH = "data/market.sqlite"


def load_table(query):
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(query, con)
    con.close()
    return df


def safe_read_csv(path):
    if os.path.exists(path):
        return pd.read_csv(path)
    return pd.DataFrame()


def generate_summary():
    today = pd.Timestamp.today().normalize()
    week_start = today - pd.Timedelta(days=7)

    journal = load_table("SELECT * FROM trade_journal")
    if not journal.empty:
        journal["trade_date"] = pd.to_datetime(journal["trade_date"], errors="coerce")
        journal["exit_date"] = pd.to_datetime(journal["exit_date"], errors="coerce")

    new_trades = (
        journal[journal["trade_date"] >= week_start]
        if not journal.empty
        else pd.DataFrame()
    )

    closed_trades = (
        journal[
            journal["exit_date"].notna()
            & (journal["exit_date"] >= week_start)
        ]
        if not journal.empty
        else pd.DataFrame()
    )

    watchlist = safe_read_csv("reports/watchlist.csv")
    bt_single = safe_read_csv("reports/backtest_metrics.csv")
    bt_portfolio = safe_read_csv("reports/backtest_portfolio_metrics.csv")

    weekly_pnl = (
        float(closed_trades["pnl"].sum())
        if not closed_trades.empty and "pnl" in closed_trades.columns
        else 0.0
    )

    grade_counts = {}
    if not new_trades.empty and "execution_grade" in new_trades.columns:
        grade_counts = (
            new_trades["execution_grade"]
            .fillna("N/A")
            .value_counts()
            .to_dict()
        )

    top_watchlist = watchlist.head(10) if not watchlist.empty else pd.DataFrame()

    diagnostics = []

    if not closed_trades.empty:
        losers = closed_trades[closed_trades["pnl"] < 0]
        winners = closed_trades[closed_trades["pnl"] > 0]

        diagnostics.append({
            "metric": "closed_trades_count",
            "value": len(closed_trades),
            "comment": "本周已平仓交易数"
        })
        diagnostics.append({
            "metric": "winning_trades_count",
            "value": len(winners),
            "comment": "本周盈利交易数"
        })
        diagnostics.append({
            "metric": "losing_trades_count",
            "value": len(losers),
            "comment": "本周亏损交易数"
        })

        if "setup_tag" in closed_trades.columns and closed_trades["setup_tag"].notna().any():
            setup_stats = (
                closed_trades.groupby("setup_tag", dropna=False)["pnl"]
                .agg(["count", "sum", "mean"])
                .reset_index()
                .sort_values("sum", ascending=False)
            )

            best_setup = setup_stats.iloc[0]
            diagnostics.append({
                "metric": "best_setup",
                "value": best_setup["setup_tag"],
                "comment": f"本周表现最好 setup，累计PnL={best_setup['sum']:.2f}"
            })

            worst_setup = setup_stats.iloc[-1]
            diagnostics.append({
                "metric": "worst_setup",
                "value": worst_setup["setup_tag"],
                "comment": f"本周表现最差 setup，累计PnL={worst_setup['sum']:.2f}"
            })

        if "planned_stop_hit" in closed_trades.columns:
            stop_hit_count = int(closed_trades["planned_stop_hit"].fillna(0).sum())
            diagnostics.append({
                "metric": "planned_stop_hit_count",
                "value": stop_hit_count,
                "comment": "本周触发计划止损的交易数"
            })

        if "exit_discipline" in closed_trades.columns and closed_trades["exit_discipline"].notna().any():
            discipline_stats = closed_trades["exit_discipline"].value_counts().to_dict()
            for k, v in discipline_stats.items():
                diagnostics.append({
                    "metric": f"exit_discipline_{k}",
                    "value": v,
                    "comment": f"{k} 类型退出次数"
                })

    if grade_counts:
        good = grade_counts.get("A", 0) + grade_counts.get("B", 0)
        bad = grade_counts.get("C", 0) + grade_counts.get("D", 0)

        diagnostics.append({
            "metric": "good_execution_count",
            "value": good,
            "comment": "A/B 执行数"
        })
        diagnostics.append({
            "metric": "bad_execution_count",
            "value": bad,
            "comment": "C/D 执行数"
        })

    diagnostics_df = pd.DataFrame(diagnostics)

    lines = []
    lines.append(
        f"Weekly Review ({week_start.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')})"
    )
    lines.append("=" * 50)
    lines.append(f"New trades this week: {len(new_trades)}")
    lines.append(f"Closed trades this week: {len(closed_trades)}")
    lines.append(f"Weekly realized PnL: {weekly_pnl:.2f}")

    if grade_counts:
        lines.append("Execution grade breakdown:")
        for k, v in grade_counts.items():
            lines.append(f"  {k}: {v}")

    if not bt_single.empty:
        r = bt_single.iloc[-1]
        lines.append("")
        lines.append("Latest single-ticker backtest:")
        lines.append(
            f"  {r.get('ticker')} | Return={r.get('total_return')} | "
            f"MaxDD={r.get('max_drawdown')} | Sharpe={r.get('sharpe')}"
        )

    if not bt_portfolio.empty:
        r = bt_portfolio.iloc[-1]
        lines.append("")
        lines.append("Latest portfolio backtest:")
        lines.append(
            f"  {r.get('strategy_name')} | Return={r.get('total_return')} | "
            f"MaxDD={r.get('max_drawdown')} | Sharpe={r.get('sharpe')}"
        )

    if not top_watchlist.empty:
        lines.append("")
        lines.append("Top watchlist names:")
        for _, row in top_watchlist.iterrows():
            ticker = row.get("ticker", "")
            score = row.get("score", "")
            lines.append(f"  {ticker}: score={score}")

    chinese_summary = []
    chinese_summary.append("本周复盘结论：")

    if len(new_trades) == 0:
        chinese_summary.append("本周没有新增交易，当前系统仍以观察为主。")
    else:
        chinese_summary.append(f"本周共新增 {len(new_trades)} 笔交易。")

    if len(closed_trades) > 0:
        if weekly_pnl > 0:
            chinese_summary.append(f"本周已实现盈亏为正，合计 {weekly_pnl:.2f}。")
        elif weekly_pnl < 0:
            chinese_summary.append(f"本周已实现盈亏为负，合计 {weekly_pnl:.2f}，需要重点检查退出纪律。")
        else:
            chinese_summary.append("本周已平仓交易总体打平。")
    else:
        chinese_summary.append("本周暂无已平仓交易，暂时不能从结果端充分评估执行质量。")

    if grade_counts:
        good = grade_counts.get("A", 0) + grade_counts.get("B", 0)
        bad = grade_counts.get("C", 0) + grade_counts.get("D", 0)
        if good >= bad:
            chinese_summary.append("从执行评分看，整体执行纪律尚可。")
        else:
            chinese_summary.append("从执行评分看，低质量执行偏多，应优先修正交易动作。")

    if not diagnostics_df.empty:
        best_row = diagnostics_df[diagnostics_df["metric"] == "best_setup"]
        worst_row = diagnostics_df[diagnostics_df["metric"] == "worst_setup"]
        stop_row = diagnostics_df[diagnostics_df["metric"] == "planned_stop_hit_count"]

        if not best_row.empty:
            chinese_summary.append(f"本周最有效的 setup 是 {best_row.iloc[0]['value']}。")
        if not worst_row.empty:
            chinese_summary.append(f"本周最需要警惕的 setup 是 {worst_row.iloc[0]['value']}。")
        if not stop_row.empty:
            chinese_summary.append(f"本周共有 {int(stop_row.iloc[0]['value'])} 笔交易触发了计划止损。")

    if not bt_portfolio.empty:
        r = bt_portfolio.iloc[-1]
        chinese_summary.append(
            f"最近一次组合回测收益率为 {r.get('total_return')}，最大回撤为 {r.get('max_drawdown')}。"
        )

    lines.append("")
    lines.append("\n".join(chinese_summary))

    os.makedirs("reports", exist_ok=True)
    report_text = "\n".join(lines)

    with open("reports/weekly_review.txt", "w", encoding="utf-8") as f:
        f.write(report_text)

    review_row = pd.DataFrame(
        [
            {
                "review_date": today.strftime("%Y-%m-%d"),
                "new_trades": len(new_trades),
                "closed_trades": len(closed_trades),
                "weekly_realized_pnl": weekly_pnl,
                "summary": "\n".join(chinese_summary),
            }
        ]
    )

    review_row.to_csv("reports/weekly_review.csv", index=False)
    diagnostics_df.to_csv("reports/weekly_diagnostics.csv", index=False)

    print(report_text)


if __name__ == "__main__":
    generate_summary()