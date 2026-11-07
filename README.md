# Copper Quant Cloud V6 | 铜期货量化云端版

A deployable bilingual Streamlit application for SHFE Copper and LME 3M copper quantitative analysis, hedging scenarios, historical replay, paper trading and backtesting.

- **App entrypoint:** `app.py`
- **Storage:** external PostgreSQL, e.g. Supabase (required)
- **Authentication:** username/password with salted PBKDF2, lockout, no public sign-up
- **Fixed URL:** choose an available `*.streamlit.app` subdomain when deploying
- **Real-money trading:** none; research/paper trading only

Start with [中文云部署指南](README_中文_云部署.md) or [English Cloud Deployment Guide](README_EN_CLOUD.md).

**Not live yet:** The included package is deployment-ready source. It does not include a cloud account, database URL, deployed site, or trading data. You must deploy it using your own GitHub, Streamlit Cloud and PostgreSQL accounts.
