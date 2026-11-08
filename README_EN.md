# Copper Quant & Paper Trading Terminal V5 — Bilingual Local Website

Run on Windows 10/11 with Python **3.11–3.13** (3.12 recommended). Extract the ZIP into a short English path, e.g. `D:\Copper_V5`, and double-click `Start_Windows.bat`. The launcher builds a private virtual environment, installs requirements, starts the Streamlit service, and opens `http://127.0.0.1:8501`. Select **中文 / English** in the sidebar.

The dashboard supports SHFE copper main-continuous and third-party LME Copper 3M history, technical analysis, historical VaR/CVaR, rolling volatility, drawdown, 20-day Monte Carlo, hedge-tenor scenarios, historical day-by-day paper orders, manually confirmed forward paper quotes, a next-open SMA-cross backtest and read-only uploads of external simulator trade CSVs.

Replay orders entered after today's close fill at the NEXT observed bar open (for market orders) or, for limit orders, only if price touches the limit on the next bar. Replay requires observed OHLC. Forward paper quotes are **manual, timestamped observations** and **not an automatic real-time feed**. A simulated Monte Carlo trajectory is never used as a genuine future quote. Both paper accounts are local SQLite ledgers with independent SHFE CNY and LME USD balances; no actual broker/API connectivity, authenticated external accounts, or live orders are implemented. Never type brokerage credentials into this app.

Historical data should be actual observed daily data with `date,open,high,low,close` headers (Chinese aliases supported). Files are validated for date span and row count. SHFE continuous contracts must not be treated as directly tradable historical contracts; LME 3M rolling benchmark requires careful date/quote definition and proper licensed data for production. Real exchange clearing, night sessions, contract rollover, bid/ask slippage, forced liquidation and funding are not simulated in this educational version.

Market data sources: https://www.lme.com/Market-data ; https://www.lme.com/en/Market-data/Accessing-market-data/Historical-data ; https://edu.shfe.com.cn/home/simulate/simnow.html .
