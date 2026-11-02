# Finance Terminal — public cloud website

A Streamlit web app for on-demand company research and Excel exports.

## Important scope and data notes

- No permanent financial database is created. The app fetches data when a visitor searches/opens a ticker.
- `st.cache_data(ttl=900)` keeps short-lived in-memory results to reduce repeat requests. Cache may be cleared when the app restarts.
- Yahoo Finance data is accessed using `yfinance`, an unofficial open-source interface. Availability, coverage, historical depth, and permitted use are subject to Yahoo's terms and provider limits.
- SEC company facts are queried for supported US issuers. SEC requests include a descriptive User-Agent; replace the placeholder contact email in `app.py` with a real contact address before public launch.
- Global tickers must use the provider's ticker suffix conventions where applicable (for example `7203.T`, `BHP.AX`, `RELIANCE.NS`).
- Indian company fundamentals are not fully normalised from official NSE/BSE filings in this first release. Yahoo coverage varies by issuer. Verify figures against official filings.
- The screener scans a supplied ticker list (CSV) or a small starter universe. It is not a complete exchange-wide screener. Scanning large lists may trigger rate limits.
- The DCF is a simple assumption-driven calculator, not an investment recommendation.
- This app is an educational/research prototype, not a Bloomberg/Screener replacement or investment advice.

## Deploy publicly for free with Streamlit Community Cloud

1. Create a GitHub account at https://github.com/ if you do not already have one.
2. Create a **new public repository**, for example `finance-terminal`.
3. Extract this ZIP on Windows.
4. Upload all files and folders inside `FinanceTerminal_Web` to the repository root. Make sure `app.py` and `requirements.txt` are at the top level.
5. Open https://share.streamlit.io/ and sign in with GitHub.
6. Click **Create app**.
7. Choose your repository, branch `main`, and main file path `app.py`.
8. In Advanced settings, select Python 3.12 if available.
9. Click Deploy. Streamlit will install packages from `requirements.txt`.
10. Once deployed, your public URL will look like `https://your-app-name.streamlit.app`.

Official guide: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app

## Update the app

Edit files in your GitHub repository and commit the changes. Streamlit Community Cloud redeploys when the repository changes.

## Optional local test on Windows

1. Install Python 3.11 or 3.12 from https://www.python.org/downloads/windows/.
2. During setup, tick **Add Python to PATH**.
3. Open the extracted folder in File Explorer.
4. Double-click `RUN_LOCAL_WINDOWS.bat`.
5. It creates a temporary virtual environment, installs requirements, and opens the app at http://localhost:8501.

## Public deployment security and operating notes

- This app is public and currently has no login or user-specific data storage.
- Do not add API keys or passwords to source code or public GitHub.
- Public users can make requests to third-party data providers through the app. Heavy use may cause provider throttling or hosting resource limits.
- Do not use it as a high-volume public service without reviewing data provider terms, rate limits, hosting limits, and abuse protection.
- Community Cloud is free for public apps but resource limits and policies can change. It may sleep or throttle apps and is not a guaranteed always-on production host.
