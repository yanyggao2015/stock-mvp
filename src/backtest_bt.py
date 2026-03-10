import sqlite3
import pandas as pd
import backtrader as bt
from datetime import datetime
import os

DB_PATH = "data/market.sqlite"


class PandasFeed(bt.feeds.PandasData):
    params = (
        ("datetime", None),
        ("open", "open"),
        ("high", "high"),
        ("low", "low"),
        ("close", "adj_close"),
        ("volume", "volume"),
        ("openinterest", -1),
    )


class MonthlyTrendStrategy(bt.Strategy):
    params = dict(
        ma_period=200,
        printlog=False,
    )

    def __init__(self):
        self.ma = bt.indicators.SimpleMovingAverage(self.data.close, period=self.p.ma_period)
        self.last_month = None

    def log(self, txt):
        if self.p.printlog:
            dt = self.datas[0].datetime.date(0)
            print(f"{dt} {txt}")

    def next(self):
        current_date = self.datas[0].datetime.date(0)
        current_month = (current_date.year, current_date.month)

        if self.last_month == current_month:
            return
        self.last_month = current_month

        if not self.position:
            if self.data.close[0] > self.ma[0]:
                size = int(self.broker.getcash() / self.data.close[0])
                if size > 0:
                    self.buy(size=size)
                    self.log(f"BUY {size} @ {self.data.close[0]:.2f}")
        else:
            if self.data.close[0] < self.ma[0]:
                self.close()
                self.log(f"SELL @ {self.data.close[0]:.2f}")


def load_price_df(ticker):
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT date, open, high, low, close, adj_close, volume FROM prices_daily WHERE ticker = ? ORDER BY date",
        con,
        params=(ticker,),
    )
    con.close()

    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    return df


def run_backtest(ticker="SPY", cash=100000):
    df = load_price_df(ticker)
    if len(df) < 250:
        raise ValueError(f"Not enough data for {ticker}")

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(cash)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.addstrategy(MonthlyTrendStrategy)

    data = PandasFeed(dataname=df)
    cerebro.adddata(data, name=ticker)

    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(
        bt.analyzers.SharpeRatio,
        _name="sharpe",
        timeframe=bt.TimeFrame.Days,
        annualize=True,
    )
    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")

    results = cerebro.run()
    strat = results[0]

    final_value = cerebro.broker.getvalue()
    total_return = (final_value / cash) - 1

    dd = strat.analyzers.drawdown.get_analysis()
    sharpe = strat.analyzers.sharpe.get_analysis()
    max_dd = dd.get("max", {}).get("drawdown", None)
    sharpe_ratio = sharpe.get("sharperatio", None)

    out = {
        "run_date": datetime.today().strftime("%Y-%m-%d"),
        "strategy_name": "MonthlyTrendStrategy",
        "ticker": ticker,
        "start_date": df.index.min().strftime("%Y-%m-%d"),
        "end_date": df.index.max().strftime("%Y-%m-%d"),
        "final_value": round(final_value, 2),
        "total_return": round(total_return, 4),
        "max_drawdown": round(max_dd, 4) if max_dd is not None else None,
        "sharpe": round(sharpe_ratio, 4) if sharpe_ratio is not None else None,
    }

    os.makedirs("reports", exist_ok=True)
    pd.DataFrame([out]).to_csv("reports/backtest_metrics.csv", index=False)

    con = sqlite3.connect(DB_PATH)
    pd.DataFrame([out]).to_sql("backtest_results", con, if_exists="append", index=False)
    con.close()

    print(pd.DataFrame([out]).to_string(index=False))


if __name__ == "__main__":
    import sys

    ticker = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    run_backtest(ticker)