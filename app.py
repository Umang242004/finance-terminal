import io
import re
import time
from datetime import date, timedelta

import pandas as pd
import streamlit as st
import yfinance as yf
import requests

st.set_page_config(page_title="Finance Terminal", page_icon="📊", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 1.4rem; max-width: 1500px;}
[data-testid="stMetric"] {background: rgba(120,120,120,.08); padding: 12px; border-radius: 10px;}
.small-note {font-size: .82rem; color: #777;}
</style>
""", unsafe_allow_html=True)

st.title("📊 Finance Terminal")
st.caption("Multi-market company research · Financial statements · Screening · Valuation · Excel export")

st.info(
    "Data is fetched on demand. This app does not maintain a permanent financial database. "
    "Short-lived in-memory caching (15 minutes) may be used to reduce repeated provider requests."
)

# ---------- Provider helpers ----------
@st.cache_data(ttl=900, show_spinner=False)
def yahoo_search(query: str):
    try:
        result = yf.Search(query, max_results=12, news_count=0)
        quotes = result.quotes or []
        rows = []
        for q in quotes:
            if q.get("quoteType") in ("EQUITY", "ETF", "MUTUALFUND", "INDEX"):
                rows.append({
                    "Symbol": q.get("symbol", ""),
                    "Name": q.get("longname") or q.get("shortname") or q.get("symbol", ""),
                    "Exchange": q.get("exchDisp") or q.get("exchange", ""),
                    "Type": q.get("quoteType", ""),
                })
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=900, show_spinner=False)
def get_yahoo_data(symbol: str):
    t = yf.Ticker(symbol)
    info = {}
    try:
        info = t.get_info()
    except Exception:
        pass
    def safe_frame(attr):
        try:
            x = getattr(t, attr)
            return x if isinstance(x, pd.DataFrame) else pd.DataFrame()
        except Exception:
            return pd.DataFrame()
    try:
        hist = t.history(period="5y", auto_adjust=False)
    except Exception:
        hist = pd.DataFrame()
    return {
        "info": info,
        "income": safe_frame("income_stmt"),
        "balance": safe_frame("balance_sheet"),
        "cashflow": safe_frame("cashflow"),
        "quarter_income": safe_frame("quarterly_income_stmt"),
        "quarter_balance": safe_frame("quarterly_balance_sheet"),
        "quarter_cashflow": safe_frame("quarterly_cashflow"),
        "history": hist,
    }

@st.cache_data(ttl=3600, show_spinner=False)
def get_sec_ticker_map():
    url = "https://www.sec.gov/files/company_tickers.json"
    headers = {"User-Agent": "FinanceTerminal educational research contact@example.com"}
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    data = r.json()
    rows = list(data.values())
    return pd.DataFrame(rows)

@st.cache_data(ttl=900, show_spinner=False)
def get_sec_companyfacts(cik: str):
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json"
    headers = {"User-Agent": "FinanceTerminal educational research contact@example.com"}
    r = requests.get(url, headers=headers, timeout=25)
    r.raise_for_status()
    return r.json()

def sec_statement_frames(cik: str):
    facts = get_sec_companyfacts(cik)
    us = facts.get("facts", {}).get("us-gaap", {})
    # Common XBRL tags. The first available tag is used; reported concepts vary by issuer.
    groups = {
        "Income Statement": {
            "Revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "Revenues"],
            "Cost of Revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
            "Gross Profit": ["GrossProfit"],
            "Operating Income": ["OperatingIncomeLoss"],
            "Pretax Income": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"],
            "Income Tax": ["IncomeTaxExpenseBenefit"],
            "Net Income": ["NetIncomeLoss", "ProfitLoss"],
            "Diluted EPS": ["EarningsPerShareDiluted"],
        },
        "Balance Sheet": {
            "Cash & Equivalents": ["CashAndCashEquivalentsAtCarryingValue"],
            "Receivables": ["AccountsReceivableNetCurrent"],
            "Inventory": ["InventoryNet"],
            "Current Assets": ["AssetsCurrent"],
            "Total Assets": ["Assets"],
            "Current Liabilities": ["LiabilitiesCurrent"],
            "Total Liabilities": ["Liabilities"],
            "Long-term Debt": ["LongTermDebtCurrent", "LongTermDebt"],
            "Stockholders Equity": ["StockholdersEquity"],
        },
        "Cash Flow": {
            "Operating Cash Flow": ["NetCashProvidedByUsedInOperatingActivities"],
            "Capital Expenditure": ["PaymentsToAcquirePropertyPlantAndEquipment"],
            "Investing Cash Flow": ["NetCashProvidedByUsedInInvestingActivities"],
            "Financing Cash Flow": ["NetCashProvidedByUsedInFinancingActivities"],
            "Depreciation & Amortization": ["DepreciationDepletionAndAmortization"],
        }
    }
    output = {}
    for statement, items in groups.items():
        series_map = {}
        for label, tags in items.items():
            for tag in tags:
                if tag in us:
                    units = us[tag].get("units", {})
                    unit_key = "USD" if "USD" in units else ("USD/shares" if "USD/shares" in units else next(iter(units), None))
                    if not unit_key:
                        continue
                    records = units[unit_key]
                    annual = [x for x in records if x.get("form") in ("10-K", "20-F", "40-F") and x.get("fp") == "FY"]
                    # Deduplicate by fiscal year, retaining the latest filed value.
                    by_year = {}
                    for x in annual:
                        yr = x.get("fy") or int(x.get("end", "0000")[:4])
                        if yr and x.get("val") is not None:
                            by_year[int(yr)] = x["val"]
                    if by_year:
                        series_map[label] = pd.Series(by_year, name=label)
                    break
        if series_map:
            output[statement] = pd.DataFrame(series_map).sort_index()
    return output

def frame_for_excel(frame):
    if frame is None or frame.empty:
        return pd.DataFrame({"Information": ["No data returned by provider"]})
    out = frame.copy()
    if isinstance(out.columns, pd.DatetimeIndex):
        out.columns = [str(c.date()) for c in out.columns]
    else:
        out.columns = [str(c) for c in out.columns]
    out.index = [str(x) for x in out.index]
    out.index.name = "Metric"
    return out.reset_index()

def make_excel(symbol, data, sec_frames=None):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        info = data.get("info", {})
        profile = pd.DataFrame([{
            "Ticker": symbol,
            "Company": info.get("longName") or info.get("shortName"),
            "Exchange": info.get("exchange"),
            "Currency": info.get("currency"),
            "Sector": info.get("sector"),
            "Industry": info.get("industry"),
            "Website": info.get("website"),
            "Market Cap": info.get("marketCap"),
            "Employees": info.get("fullTimeEmployees"),
            "Data Source": "Yahoo Finance via yfinance",
            "Retrieved UTC": pd.Timestamp.utcnow().isoformat(),
        }])
        profile.to_excel(writer, sheet_name="Company Profile", index=False)
        for key, sheet in [
            ("income", "Annual Income"), ("balance", "Annual Balance"),
            ("cashflow", "Annual Cash Flow"), ("quarter_income", "Quarterly Income"),
            ("quarter_balance", "Quarterly Balance"), ("quarter_cashflow", "Quarterly Cash Flow")
        ]:
            frame_for_excel(data.get(key)).to_excel(writer, sheet_name=sheet, index=False)
        hist = data.get("history", pd.DataFrame())
        if not hist.empty:
            hist.reset_index().to_excel(writer, sheet_name="Historical Prices", index=False)
        if sec_frames:
            for name, frame in sec_frames.items():
                frame_for_excel(frame).to_excel(writer, sheet_name=("SEC " + name)[:31], index=False)
        notes = pd.DataFrame({
            "Notes": [
                "This workbook contains data returned by the indicated providers.",
                "Yahoo Finance data is accessed through yfinance; coverage and availability vary by ticker.",
                "SEC statement data is derived from reported US-GAAP XBRL concepts; issuer taxonomy and presentation can differ.",
                "Review original filings and reconcile units, fiscal periods, restatements and consolidated/standalone basis before using in a financial model.",
                "Blank values mean the provider did not return that item; they do not mean zero.",
            ]
        })
        notes.to_excel(writer, sheet_name="Read Me", index=False)
    buffer.seek(0)
    return buffer.getvalue()

def fmt_num(x, currency=""):
    try:
        if x is None or pd.isna(x):
            return "—"
        x = float(x)
        if abs(x) >= 1e12: return f"{currency}{x/1e12:,.2f}T"
        if abs(x) >= 1e9: return f"{currency}{x/1e9:,.2f}B"
        if abs(x) >= 1e6: return f"{currency}{x/1e6:,.2f}M"
        return f"{currency}{x:,.2f}"
    except Exception:
        return "—"

# ---------- Sidebar ----------
with st.sidebar:
    st.header("Research controls")
    st.caption("Search across Yahoo Finance's available symbol universe.")
    query = st.text_input("Company name or ticker", placeholder="e.g. Reliance, TCS, AAPL")
    search_clicked = st.button("Search companies", use_container_width=True)
    st.divider()
    st.caption("Direct ticker lookup also works. Examples:")
    st.code("RELIANCE.NS\nTCS.NS\nAAPL\nMSFT\n7203.T\nBHP.AX", language="text")
    st.caption("For India, use .NS (NSE) or .BO (BSE) suffixes where supported.")

if "search_results" not in st.session_state:
    st.session_state.search_results = pd.DataFrame()
if search_clicked and query.strip():
    with st.spinner("Searching symbols..."):
        st.session_state.search_results = yahoo_search(query.strip())

results = st.session_state.search_results
if not results.empty:
    st.subheader("Company search results")
    st.dataframe(results, use_container_width=True, hide_index=True)
    options = [f"{r['Symbol']} — {r['Name']}" for _, r in results.iterrows()]
    selected = st.selectbox("Choose a company", options)
    ticker = selected.split(" — ")[0]
else:
    ticker = st.text_input("Or enter a ticker directly", value="RELIANCE.NS", help="Examples: RELIANCE.NS, AAPL, MSFT, SAP, 7203.T")

if not ticker:
    st.stop()

with st.spinner(f"Fetching available data for {ticker}..."):
    data = get_yahoo_data(ticker.strip().upper())

info = data["info"]
hist = data["history"]
currency = info.get("currency", "")
name = info.get("longName") or info.get("shortName") or ticker
st.header(f"{name} ({ticker.upper()})")
st.caption(f"{info.get('exchange', 'Exchange not provided')} · {info.get('sector', 'Sector unavailable')} · Currency: {currency or 'Not provided'}")

price = info.get("currentPrice") or info.get("regularMarketPrice")
prev = info.get("previousClose")
mcap = info.get("marketCap")
pe = info.get("trailingPE")
pb = info.get("priceToBook")
ev = info.get("enterpriseValue")
cols = st.columns(5)
cols[0].metric("Price", fmt_num(price, currency + " ") if price else "—")
cols[1].metric("Market cap", fmt_num(mcap, currency + " ") if mcap else "—")
cols[2].metric("Trailing P/E", fmt_num(pe))
cols[3].metric("Price / Book", fmt_num(pb))
cols[4].metric("Enterprise value", fmt_num(ev, currency + " ") if ev else "—")

tabs = st.tabs(["Overview", "Financial Statements", "Ratios & Valuation", "Historical Data", "Peer Comparison", "Screener", "Export"])

with tabs[0]:
    left, right = st.columns([1.3, 1])
    with left:
        st.subheader("Price history")
        if not hist.empty and "Close" in hist:
            st.line_chart(hist["Close"], height=300)
        else:
            st.warning("Historical prices were not returned for this ticker.")
    with right:
        st.subheader("Company profile")
        profile_rows = {
            "Business summary": info.get("longBusinessSummary", "Not provided"),
            "Website": info.get("website", "Not provided"),
            "Country": info.get("country", "Not provided"),
            "Employees": info.get("fullTimeEmployees", "Not provided"),
            "Industry": info.get("industry", "Not provided"),
        }
        for k, v in profile_rows.items():
            st.markdown(f"**{k}:** {v}")

with tabs[1]:
    st.subheader("Annual financial statements")
    st.caption("Statement labels and periods depend on Yahoo Finance coverage. Values are shown as returned by the provider.")
    for key, label in [("income", "Income Statement"), ("balance", "Balance Sheet"), ("cashflow", "Cash Flow Statement")]:
        st.markdown(f"#### {label}")
        frame = data[key]
        if frame.empty:
            st.warning("No annual data returned.")
        else:
            st.dataframe(frame, use_container_width=True)
    st.subheader("Quarterly financial statements")
    for key, label in [("quarter_income", "Quarterly Income Statement"), ("quarter_balance", "Quarterly Balance Sheet"), ("quarter_cashflow", "Quarterly Cash Flow")]:
        with st.expander(label):
            if data[key].empty:
                st.warning("No quarterly data returned.")
            else:
                st.dataframe(data[key], use_container_width=True)

with tabs[2]:
    st.subheader("Reported valuation and profitability metrics")
    ratio_keys = [
        ("trailingPE", "Trailing P/E"), ("forwardPE", "Forward P/E"),
        ("priceToBook", "Price / Book"), ("enterpriseToEbitda", "EV / EBITDA"),
        ("returnOnEquity", "Return on Equity"), ("returnOnAssets", "Return on Assets"),
        ("profitMargins", "Profit Margin"), ("operatingMargins", "Operating Margin"),
        ("grossMargins", "Gross Margin"), ("debtToEquity", "Debt / Equity"),
        ("currentRatio", "Current Ratio"), ("dividendYield", "Dividend Yield"),
        ("beta", "Beta"), ("enterpriseValue", "Enterprise Value"),
    ]
    ratio_df = pd.DataFrame([{"Metric": label, "Value": info.get(key)} for key, label in ratio_keys])
    st.dataframe(ratio_df, use_container_width=True, hide_index=True)
    st.divider()
    st.subheader("Illustrative DCF calculator")
    st.caption("This is a user-input valuation calculator, not an analyst forecast. Enter your own assumptions.")
    c1, c2, c3 = st.columns(3)
    fcf = c1.number_input("Base-year free cash flow", value=1000.0, step=100.0)
    growth = c2.number_input("Annual FCF growth (%)", value=8.0, step=1.0) / 100
    wacc = c3.number_input("Discount rate / WACC (%)", value=10.0, step=0.5) / 100
    c4, c5 = st.columns(2)
    terminal_growth = c4.number_input("Terminal growth (%)", value=3.0, step=0.5) / 100
    years = c5.number_input("Forecast years", min_value=1, max_value=10, value=5)
    if wacc <= terminal_growth:
        st.error("WACC must be greater than terminal growth.")
    else:
        forecast = []
        pv = 0.0
        for year in range(1, int(years) + 1):
            cash = fcf * ((1 + growth) ** year)
            discounted = cash / ((1 + wacc) ** year)
            pv += discounted
            forecast.append({"Year": year, "FCF": cash, "Discount factor": 1/(1+wacc)**year, "Present value": discounted})
        terminal = forecast[-1]["FCF"] * (1 + terminal_growth) / (wacc - terminal_growth)
        pv_terminal = terminal / ((1+wacc) ** int(years))
        st.metric("Illustrative enterprise value", f"{pv + pv_terminal:,.2f} {currency}")
        st.dataframe(pd.DataFrame(forecast), use_container_width=True, hide_index=True)
        st.caption(f"PV of explicit forecast: {pv:,.2f} · PV of terminal value: {pv_terminal:,.2f} {currency}")

with tabs[3]:
    st.subheader("Historical market data")
    if hist.empty:
        st.warning("No historical price data returned.")
    else:
        period = st.selectbox("Display period", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=5)
        st.line_chart(hist["Close"].tail({"1mo":22,"3mo":66,"6mo":132,"1y":252,"2y":504,"5y":2000}[period]))
        st.dataframe(hist.tail(100), use_container_width=True)

with tabs[4]:
    st.subheader("Peer comparison")
    peer_input = st.text_input("Enter peer tickers separated by commas", placeholder="e.g. TCS.NS, INFY.NS, WIPRO.NS")
    if st.button("Compare peers"):
        peers = [x.strip().upper() for x in peer_input.split(",") if x.strip()]
        rows = []
        for sym in list(dict.fromkeys([ticker.upper()] + peers))[:12]:
            try:
                pinfo = yf.Ticker(sym).get_info()
                rows.append({
                    "Ticker": sym,
                    "Company": pinfo.get("longName") or pinfo.get("shortName"),
                    "Market Cap": pinfo.get("marketCap"),
                    "Revenue": pinfo.get("totalRevenue"),
                    "EBITDA": pinfo.get("ebitda"),
                    "P/E": pinfo.get("trailingPE"),
                    "EV/EBITDA": pinfo.get("enterpriseToEbitda"),
                    "ROE": pinfo.get("returnOnEquity"),
                    "Profit Margin": pinfo.get("profitMargins"),
                })
            except Exception:
                rows.append({"Ticker": sym, "Company": "Data unavailable"})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

with tabs[5]:
    st.subheader("Multi-company screener")
    st.caption("Yahoo Finance does not expose a complete free global fundamental screener through yfinance. This module screens a ticker universe you provide, fetching current metrics on demand.")
    uploaded = st.file_uploader("Upload a CSV of ticker symbols (one column named Symbol or Ticker)", type=["csv"])
    default_universe = ["RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS","ITC.NS","LT.NS","AAPL","MSFT","GOOGL","AMZN","NVDA","META","TSLA","BRK-B","JPM","KO","WMT"]
    if uploaded:
        try:
            u = pd.read_csv(uploaded)
            col = next((c for c in u.columns if c.lower() in ("symbol","ticker")), u.columns[0])
            universe = u[col].dropna().astype(str).str.strip().str.upper().unique().tolist()
        except Exception:
            universe = default_universe
            st.error("Could not read that CSV. Using the built-in starter universe.")
    else:
        universe = default_universe
    st.write(f"Universe: {len(universe)} tickers")
    max_scan = st.slider("Maximum companies to scan in this run", 5, min(100, max(5, len(universe))), min(18, max(5, len(universe))))
    min_cap = st.number_input("Minimum market cap (USD equivalent as reported; provider currency may differ)", value=0.0, step=100000000.0)
    min_roe = st.number_input("Minimum reported ROE (decimal; e.g. 0.15 = 15%)", value=0.0, step=0.05)
    if st.button("Run screener"):
        rows = []
        progress = st.progress(0)
        for i, sym in enumerate(universe[:max_scan]):
            try:
                inf = yf.Ticker(sym).get_info()
                rows.append({
                    "Ticker": sym, "Company": inf.get("longName") or inf.get("shortName"),
                    "Market Cap": inf.get("marketCap"), "Revenue": inf.get("totalRevenue"),
                    "P/E": inf.get("trailingPE"), "ROE": inf.get("returnOnEquity"),
                    "ROCE proxy unavailable": None, "Profit Margin": inf.get("profitMargins"),
                    "Debt / Equity": inf.get("debtToEquity"),
                })
            except Exception:
                rows.append({"Ticker": sym, "Company": "Fetch failed"})
            progress.progress((i+1)/max_scan)
            time.sleep(0.15)
        screen_df = pd.DataFrame(rows)
        if "Market Cap" in screen_df:
            screen_df = screen_df[screen_df["Market Cap"].fillna(0) >= min_cap]
        if "ROE" in screen_df:
            screen_df = screen_df[screen_df["ROE"].fillna(-999) >= min_roe]
        st.dataframe(screen_df, use_container_width=True, hide_index=True)
        st.download_button("Download screener results CSV", screen_df.to_csv(index=False).encode(), "screener_results.csv", "text/csv")

with tabs[6]:
    st.subheader("Export company workbook")
    st.write("Exports available Yahoo annual/quarterly statements, company profile, historical prices and a methodology note.")
    sec_frames = None
    if info.get("quoteType") == "EQUITY" and info.get("country") in ("United States", "USA"):
        if st.checkbox("Also attempt official SEC XBRL financial data (US issuers)"):
            try:
                with st.spinner("Looking up SEC company facts..."):
                    sec_map = get_sec_ticker_map()
                    match = sec_map[sec_map["ticker"].str.upper() == ticker.upper()]
                    if not match.empty:
                        cik = str(int(match.iloc[0]["cik_str"]))
                        sec_frames = sec_statement_frames(cik)
                        if sec_frames:
                            st.success("SEC company facts retrieved.")
                        else:
                            st.warning("SEC company facts returned, but common statement tags were not found.")
                    else:
                        st.warning("Ticker was not found in the SEC ticker map.")
            except Exception as e:
                st.warning(f"SEC lookup unavailable: {e}")
    try:
        xlsx = make_excel(ticker.upper(), data, sec_frames)
        st.download_button(
            "⬇️ Download industry-style Excel workbook",
            data=xlsx,
            file_name=f"{re.sub(r'[^A-Za-z0-9._-]+','_',ticker.upper())}_financials.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"Excel export failed: {e}")

st.divider()
st.caption(
    "Important: This is an independent educational research tool, not an official Bloomberg/Screener replacement. "
    "Provider coverage, refresh frequency, historical depth and field definitions vary. "
    "Verify figures against original filings before using them in investment decisions or client work."
)
st.caption("Sources: Yahoo Finance via yfinance; SEC EDGAR company facts for supported US issuers. Indian exchange filings are not yet directly normalised in this release.")
