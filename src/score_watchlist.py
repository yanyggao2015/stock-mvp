import pandas as pd, sqlite3, numpy as np
con = sqlite3.connect("data/market.sqlite")
df = pd.read_sql("SELECT * FROM prices_daily", con)
df["date"] = pd.to_datetime(df["date"])
rows = []

for t, g in df.groupby("ticker"):
    g = g.sort_values("date").copy()
    if len(g) < 220:
        continue
    g["ma50"] = g["adj_close"].rolling(50).mean()
    g["ma200"] = g["adj_close"].rolling(200).mean()
    g["ret_252"] = g["adj_close"].pct_change(252)
    g["vol_60"] = g["adj_close"].pct_change().rolling(60).std() * np.sqrt(252)
    r = g.iloc[-1]
    score = (30 if r["adj_close"] > r["ma50"] else 0) + \
            (30 if r["adj_close"] > r["ma200"] else 0) + \
            40 * float(r["ret_252"] or 0) - 10 * float(r["vol_60"] or 0)
    rows.append([t, r["adj_close"], score])

out = pd.DataFrame(rows, columns=["ticker","close","score"]).sort_values("score", ascending=False)
print(out.head(10).to_string(index=False))
out.to_csv("reports/watchlist.csv", index=False)