import os
import sqlite3
import pandas as pd
import yfinance as yf

DB_PATH = "data/market.sqlite"


def load_universe():
    return pd.read_csv("config/universe.csv")["ticker"].dropna().tolist()


def ensure_tables(con):
    con.execute("""
    CREATE TABLE IF NOT EXISTS prices_daily (
        ticker TEXT NOT NULL,
        date TEXT NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        adj_close REAL,
        volume REAL,
        PRIMARY KEY (ticker, date)
    )
    """)
    con.commit()


def flatten_columns(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            col[0].lower().replace(" ", "_") if isinstance(col, tuple)
            else str(col).lower().replace(" ", "_")
            for col in df.columns
        ]
    else:
        df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
    return df


def main():
    tickers = load_universe()
    os.makedirs("data", exist_ok=True)
    con = sqlite3.connect(DB_PATH)

    # 关键：先确保表存在
    ensure_tables(con)

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

        if "date" not in df.columns:
            if "datetime" in df.columns:
                df = df.rename(columns={"datetime": "date"})
            else:
                raise ValueError(f"{ticker}: cannot find date column, got {df.columns.tolist()}")

        df["ticker"] = ticker

        if "adj_close" not in df.columns:
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
