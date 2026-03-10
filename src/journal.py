import sqlite3
import pandas as pd

DB_PATH = "data/market.sqlite"


def add_trade(row: dict):
    con = sqlite3.connect(DB_PATH)
    cols = [
        "trade_date",
        "ticker",
        "side",
        "entry_price",
        "shares",
        "stop_price",
        "planned_target",
        "thesis",
        "setup_tag",
        "execution_grade",
        "exit_date",
        "exit_price",
        "pnl",
        "review_note",
        "planned_stop_hit",
        "exit_discipline",
    ]
    values = [row.get(c) for c in cols]

    con.execute(
        f"""
        INSERT INTO trade_journal ({",".join(cols)})
        VALUES ({",".join(["?"] * len(cols))})
        """,
        values,
    )
    con.commit()
    con.close()


def load_journal():
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT * FROM trade_journal ORDER BY trade_date DESC, id DESC",
        con,
    )
    con.close()
    return df


def close_trade(trade_id: int, exit_date: str, exit_price: float, review_note: str = ""):
    con = sqlite3.connect(DB_PATH)
    row = con.execute(
        "SELECT entry_price, shares, side, stop_price FROM trade_journal WHERE id = ?",
        (trade_id,),
    ).fetchone()

    if row is None:
        con.close()
        raise ValueError("trade_id not found")

    entry_price, shares, side, stop_price = row

    if str(side).upper() == "BUY":
        pnl = (exit_price - entry_price) * shares
        planned_stop_hit = 1 if stop_price is not None and exit_price <= stop_price else 0
    else:
        pnl = (entry_price - exit_price) * shares
        planned_stop_hit = 1 if stop_price is not None and exit_price >= stop_price else 0

    if planned_stop_hit:
        exit_discipline = "stop_exit"
    elif pnl > 0:
        exit_discipline = "profit_exit"
    else:
        exit_discipline = "manual_exit"

    con.execute(
        """
        UPDATE trade_journal
        SET exit_date = ?, exit_price = ?, pnl = ?, review_note = ?,
            planned_stop_hit = ?, exit_discipline = ?
        WHERE id = ?
        """,
        (exit_date, exit_price, pnl, review_note, planned_stop_hit, exit_discipline, trade_id),
    )
    con.commit()
    con.close()