import pandas as pd, sqlite3
ACCOUNT_SIZE = 50000
RISK_PER_TRADE = 0.01

con = sqlite3.connect("data/market.sqlite")
scored = pd.read_csv("reports/watchlist.csv")
prices = pd.read_sql("SELECT * FROM prices_daily", con)
prices["date"] = pd.to_datetime(prices["date"])

plans = []
for _, row in scored.head(10).iterrows():
    t = row["ticker"]
    g = prices[prices["ticker"] == t].sort_values("date").copy()
    g["atr"] = (g["high"] - g["low"]).rolling(14).mean()
    r = g.iloc[-1]
    entry = round(r["adj_close"] * 0.99, 2)
    stop = round(entry - 2 * float(r["atr"]), 2)
    risk_ps = max(entry - stop, 0.01)
    shares = int((ACCOUNT_SIZE * RISK_PER_TRADE) / risk_ps)
    plans.append([t, r["date"].strftime("%Y-%m-%d"), r["adj_close"], row["score"], entry, stop, shares, "manual via CIBC"])

pd.DataFrame(plans, columns=[
    "ticker","plan_date","close","score","entry_price","stop_price","shares","note"
]).to_csv("reports/trade_plan.csv", index=False)

print("saved reports/trade_plan.csv")