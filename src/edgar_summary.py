import os
import sqlite3
import requests
import pandas as pd

DB_PATH = "data/market.sqlite"
TICKER_CIK_URL = "https://www.sec.gov/files/company_tickers.json"


def get_user_agent():
    with open("config/sec_user_agent.txt", "r", encoding="utf-8") as f:
        return f.read().strip()


def sec_get(url):
    headers = {"User-Agent": get_user_agent()}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


def sec_get_optional(url):
    headers = {"User-Agent": get_user_agent()}
    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def load_ticker_to_cik():
    data = sec_get(TICKER_CIK_URL)
    mapping = {}
    for _, item in data.items():
        ticker = item["ticker"].upper()
        cik = str(item["cik_str"]).zfill(10)
        mapping[ticker] = cik
    return mapping


def latest_value(facts, taxonomy, concept):
    if not facts:
        return None
    try:
        units = facts["facts"][taxonomy][concept]["units"]
        if "USD" in units:
            arr = units["USD"]
        else:
            arr = next(iter(units.values()))
        arr = sorted(arr, key=lambda x: (x.get("fy", 0), x.get("fp", "")), reverse=True)
        return arr[0].get("val")
    except Exception:
        return None


def format_money(v):
    if v is None:
        return "暂无"
    try:
        v = float(v)
    except Exception:
        return "暂无"

    abs_v = abs(v)
    if abs_v >= 1_000_000_000:
        return f"{v / 1_000_000_000:.2f}B"
    if abs_v >= 1_000_000:
        return f"{v / 1_000_000:.2f}M"
    return f"{v:,.0f}"


def detect_security_type(submissions):
    try:
        sic_desc = (submissions.get("sicDescription") or "").lower()
        name = (submissions.get("name") or "").lower()

        if "etf" in name or "trust" in name or "fund" in name:
            return "fund_or_etf"
        if "investment" in sic_desc or "fund" in sic_desc or "trust" in sic_desc:
            return "fund_or_etf"
    except Exception:
        pass
    return "operating_company"


def build_filing_url(cik, accession_number, primary_document):
    if not accession_number or not primary_document:
        return None
    cik_no_zero = str(int(cik))
    accession_no_dash = accession_number.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_no_zero}/{accession_no_dash}/{primary_document}"


def build_chinese_summary(
    ticker,
    security_type,
    filing_date,
    form,
    revenue,
    net_income,
    assets,
    liabilities,
    facts_found,
):
    if security_type == "fund_or_etf" and not facts_found:
        return (
            f"{ticker} 更像基金/ETF 类申报主体。当前已抓到最近申报信息，"
            f"但没有标准 companyfacts 财务数据，因此不适合按普通经营公司口径解读营收和净利润。"
        )

    if not facts_found:
        return (
            f"{ticker} 已抓到 SEC 申报记录，但暂未取得标准化 XBRL 财务字段，"
            f"暂时无法生成完整财务摘要。"
        )

    parts = []
    parts.append(f"{ticker} 最近可用财务摘要：")
    if filing_date:
        parts.append(f"最近申报日期 {filing_date}")
    if form:
        parts.append(f"表格类型 {form}")
    parts.append(f"营收 {format_money(revenue)}")
    parts.append(f"净利润 {format_money(net_income)}")
    parts.append(f"总资产 {format_money(assets)}")
    parts.append(f"总负债 {format_money(liabilities)}")

    if net_income is not None and revenue is not None:
        try:
            margin = net_income / revenue if revenue else None
            if margin is not None:
                parts.append(f"净利率约 {margin:.1%}")
        except Exception:
            pass

    return "，".join(parts) + "。"


def get_company_summary(ticker, cik):
    submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

    submissions = sec_get(submissions_url)
    facts = sec_get_optional(facts_url)

    security_type = detect_security_type(submissions)

    recent = pd.DataFrame(submissions["filings"]["recent"])
    if not recent.empty:
        recent = recent[
            recent["form"].isin(
                [
                    "10-K",
                    "10-Q",
                    "10-K/A",
                    "10-Q/A",
                    "N-CSR",
                    "N-CSRS",
                    "497",
                    "485BPOS",
                ]
            )
        ].head(5)

    revenue = latest_value(facts, "us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax")
    if revenue is None:
        revenue = latest_value(facts, "us-gaap", "Revenues")

    net_income = latest_value(facts, "us-gaap", "NetIncomeLoss")
    assets = latest_value(facts, "us-gaap", "Assets")
    liabilities = latest_value(facts, "us-gaap", "Liabilities")

    facts_found = facts is not None
    return recent, revenue, net_income, assets, liabilities, security_type, facts_found


def main():
    tickers = pd.read_csv("config/universe.csv")["ticker"].dropna().tolist()
    ticker_map = load_ticker_to_cik()

    rows = []

    for ticker in tickers:
        us_ticker = ticker.replace(".TO", "").upper()

        if ticker.endswith(".TO"):
            print(f"Skip {ticker}: Canadian listing not handled in SEC EDGAR layer")
            continue

        if us_ticker not in ticker_map:
            print(f"Skip {ticker}: no SEC CIK found")
            continue

        cik = ticker_map[us_ticker]

        try:
            (
                recent,
                revenue,
                net_income,
                assets,
                liabilities,
                security_type,
                facts_found,
            ) = get_company_summary(us_ticker, cik)

            if not recent.empty:
                first = recent.iloc[0]
                accession_number = first.get("accessionNumber")
                form = first.get("form")
                filing_date = first.get("filingDate")
                primary_document = first.get("primaryDocument")
            else:
                accession_number = None
                form = None
                filing_date = None
                primary_document = None

            filing_url = build_filing_url(cik, accession_number, primary_document)
            summary = build_chinese_summary(
                us_ticker,
                security_type,
                filing_date,
                form,
                revenue,
                net_income,
                assets,
                liabilities,
                facts_found,
            )

            rows.append(
                {
                    "ticker": us_ticker,
                    "cik": cik,
                    "security_type": security_type,
                    "accession_number": accession_number,
                    "form": form,
                    "filing_date": filing_date,
                    "primary_document": primary_document,
                    "filing_url": filing_url,
                    "revenue": revenue,
                    "net_income": net_income,
                    "assets": assets,
                    "liabilities": liabilities,
                    "summary": summary,
                }
            )

            print(f"Loaded EDGAR summary for {ticker}")

        except Exception as e:
            print(f"Failed {ticker}: {e}")

    if rows:
        out = pd.DataFrame(rows)
        os.makedirs("reports", exist_ok=True)
        out.to_csv("reports/edgar_summary.csv", index=False)

        con = sqlite3.connect(DB_PATH)
        out.to_sql("edgar_filings", con, if_exists="replace", index=False)
        con.close()

        print("Saved reports/edgar_summary.csv")


if __name__ == "__main__":
    main()