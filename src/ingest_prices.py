import pandas as pd
import sqlite3
import yfinance as yf
import os

DB_PATH = "data/market.sqlite"

def load_universe():
    return pd.read_csv("config/universe.csv")["ticker"].dropna().tolist()

def flatten_columns(df):
    # 如果是 MultiIndex，压平成单层
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            col[0].lower().replace(" ", "_") if isinstance(col, tuple) else str(col).lower().replace(" ", "_")
            for col in df.columns
        ]
    else:
        df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
    return df

def main():
    tickers = load_universe()
    os.makedirs("data", exist_ok=True)
    con = sqlite3.connect(DB_PATH)

    for ticker in tickers:
        print(f"Downloading {ticker} ...")
        df = yf.download(
            ticker,
            start="2020-01-01",
            auto_adjust=False,
            progress=False
        )

        if df.empty:
            print(f"Skip {ticker}: empty data")
            continue

        df = df.reset_index()
        df = flatten_columns(df)

        # 统一日期列名
        if "date" not in df.columns:
            if "datetime" in df.columns:
                df = df.rename(columns={"datetime": "date"})
            else:
                raise ValueError(f"{ticker}: cannot find date column, got {df.columns.tolist()}")

        # 添加 ticker 列
        df["ticker"] = ticker

        # 某些情况下没有 adj_close，就用 close 顶上
        if "adj_close" not in df.columns:
            if "adj close" in df.columns:
                df = df.rename(columns={"adj close": "adj_close"})
            else:
                df["adj_close"] = df["close"]

        required_cols = ["ticker", "date", "open", "high", "low", "close", "adj_close", "volume"]

        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ValueError(f"{ticker}: missing columns {missing}, got {df.columns.tolist()}")

        out = df[required_cols].copy()
        out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")

        rows = list(out.itertuples(index=False, name=None))

        con.executemany("""
            INSERT OR REPLACE INTO prices_daily
            (ticker, date, open, high, low, close, adj_close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)

        print(f"Loaded {ticker}: {len(out)} rows")

    con.commit()
    con.close()
    print("Done.")

if __name__ == "__main__":
    main()