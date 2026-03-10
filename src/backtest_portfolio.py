import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
import os

DB_PATH = "data/market.sqlite"


def load_prices():
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM prices_daily", con)
    con.close()
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["ticker", "date"])


def build_signals(df):
    rows = []

    for ticker, g in df.groupby("ticker"):
        g = g.copy().sort_values("date")

        if len(g) < 220:
            continue

        g["ret_252"] = g["adj_close"].pct_change(252)
        g["ma200"] = g["adj_close"].rolling(200).mean()
        g["eligible"] = g["adj_close"] > g["ma200"]

        rows.append(g)

    if not rows:
        return pd.DataFrame()

    return pd.concat(rows, ignore_index=True)


def run_portfolio_backtest(top_n=3, initial_cash=100000):
    df = load_prices()
    df = build_signals(df)

    if df.empty:
        raise ValueError("No enough price data to run portfolio backtest.")

    month_ends = (
        df.groupby(df["date"].dt.to_period("M"))["date"]
        .max()
        .sort_values()
        .tolist()
    )

    equity_curve = []
    cash = initial_cash
    positions = {}

    for dt in month_ends:
        snap = df[df["date"] == dt].copy()
        if snap.empty:
            continue

        portfolio_value = cash
        for ticker, shares in positions.items():
            px = snap.loc[snap["ticker"] == ticker, "adj_close"]
            if not px.empty:
                portfolio_value += shares * float(px.iloc[0])

        candidates = snap[snap["eligible"]].sort_values("ret_252", ascending=False).head(top_n)
        selected = set(candidates["ticker"].tolist())

        new_cash = cash
        for ticker, shares in list(positions.items()):
            px = snap.loc[snap["ticker"] == ticker, "adj_close"]
            if px.empty:
                continue
            price = float(px.iloc[0])
            if ticker not in selected:
                new_cash += shares * price
                del positions[ticker]

        portfolio_value = new_cash
        for ticker, shares in positions.items():
            px = snap.loc[snap["ticker"] == ticker, "adj_close"]
            if not px.empty:
                portfolio_value += shares * float(px.iloc[0])

        if len(selected) > 0:
            target_value_each = portfolio_value / len(selected)

            for ticker in selected:
                price = float(snap.loc[snap["ticker"] == ticker, "adj_close"].iloc[0])
                target_shares = int(target_value_each / price)
                current_shares = positions.get(ticker, 0)
                delta = target_shares - current_shares
                new_cash -= delta * price
                positions[ticker] = target_shares

        cash = new_cash

        total_value = cash
        for ticker, shares in positions.items():
            px = snap.loc[snap["ticker"] == ticker, "adj_close"]
            if not px.empty:
                total_value += shares * float(px.iloc[0])

        equity_curve.append({"date": dt, "equity": total_value})

    eq = pd.DataFrame(equity_curve)

    if eq.empty:
        raise ValueError("Portfolio backtest produced no equity curve.")

    eq["ret"] = eq["equity"].pct_change()

    total_return = eq["equity"].iloc[-1] / initial_cash - 1
    rolling_max = eq["equity"].cummax()
    drawdown = eq["equity"] / rolling_max - 1
    max_drawdown = drawdown.min()

    ret_std = eq["ret"].std()
    sharpe = None
    if pd.notna(ret_std) and ret_std != 0:
        sharpe = eq["ret"].mean() / ret_std * np.sqrt(12)

    summary = pd.DataFrame(
        [
            {
                "run_date": datetime.today().strftime("%Y-%m-%d"),
                "strategy_name": f"PortfolioTop{top_n}Momentum",
                "ticker": "PORTFOLIO",
                "start_date": eq["date"].min().strftime("%Y-%m-%d"),
                "end_date": eq["date"].max().strftime("%Y-%m-%d"),
                "final_value": round(eq["equity"].iloc[-1], 2),
                "total_return": round(float(total_return), 4),
                "max_drawdown": round(float(max_drawdown), 4),
                "sharpe": round(float(sharpe), 4) if sharpe is not None else None,
            }
        ]
    )

    os.makedirs("reports", exist_ok=True)
    summary.to_csv("reports/backtest_portfolio_metrics.csv", index=False)
    eq.to_csv("reports/backtest_portfolio_equity.csv", index=False)

    con = sqlite3.connect(DB_PATH)
    summary.to_sql("backtest_results", con, if_exists="append", index=False)
    con.close()

    print(summary.to_string(index=False))
    print("\nSaved:")
    print("- reports/backtest_portfolio_metrics.csv")
    print("- reports/backtest_portfolio_equity.csv")


if __name__ == "__main__":
    run_portfolio_backtest()