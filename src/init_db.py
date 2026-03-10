import os
import sqlite3

DB_PATH = "data/market.sqlite"
os.makedirs("data", exist_ok=True)

con = sqlite3.connect(DB_PATH)

con.execute("""
CREATE TABLE IF NOT EXISTS prices_daily(
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

con.execute("""
CREATE TABLE IF NOT EXISTS trade_plan(
    ticker TEXT,
    plan_date TEXT,
    close REAL,
    score REAL,
    entry_price REAL,
    stop_price REAL,
    shares INTEGER,
    note TEXT
)
""")

con.execute("""
CREATE TABLE IF NOT EXISTS backtest_results(
    run_date TEXT,
    strategy_name TEXT,
    ticker TEXT,
    start_date TEXT,
    end_date TEXT,
    final_value REAL,
    total_return REAL,
    max_drawdown REAL,
    sharpe REAL
)
""")

con.execute("""
CREATE TABLE IF NOT EXISTS edgar_filings(
    ticker TEXT,
    cik TEXT,
    security_type TEXT,
    accession_number TEXT,
    form TEXT,
    filing_date TEXT,
    primary_document TEXT,
    filing_url TEXT,
    revenue REAL,
    net_income REAL,
    assets REAL,
    liabilities REAL,
    summary TEXT,
    PRIMARY KEY (ticker, accession_number)
)
""")

con.execute("""
CREATE TABLE IF NOT EXISTS trade_journal(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT,
    ticker TEXT,
    side TEXT,
    entry_price REAL,
    shares INTEGER,
    stop_price REAL,
    planned_target REAL,
    thesis TEXT,
    setup_tag TEXT,
    execution_grade TEXT,
    exit_date TEXT,
    exit_price REAL,
    pnl REAL,
    review_note TEXT
)
""")

# upgrade trade_journal columns if missing
existing_cols = [row[1] for row in con.execute("PRAGMA table_info(trade_journal)").fetchall()]

if "planned_stop_hit" not in existing_cols:
    con.execute("ALTER TABLE trade_journal ADD COLUMN planned_stop_hit INTEGER")

if "exit_discipline" not in existing_cols:
    con.execute("ALTER TABLE trade_journal ADD COLUMN exit_discipline TEXT")

con.commit()
con.close()
print("database initialized")