# Copper Quant Cloud V6 — Deployment Guide

**Architecture:** Streamlit Community Cloud (stable `*.streamlit.app` subdomain) + Supabase PostgreSQL + in-app username/password authentication. No ngrok, no Cloudflare Tunnel, no Windows PC needed to host the site.

1. Create your own Supabase PostgreSQL project and copy a suitable pooled connection URL. Ensure `sslmode=require`. Keep the URL secret.
2. Push this source folder (not the ZIP and not actual `.streamlit/secrets.toml`) to a GitHub repo you control.
3. Provision the initial login account on your own PC: `pip install "psycopg[binary]>=3.2,<4"`, then `python provision_admin.py --username your_username`. Enter your database URL and a strong password at hidden prompts. This initializes tables and a salted PBKDF2 verifier; there is no public registration.
4. At https://share.streamlit.io/ create an app from your repository, entrypoint `app.py`. Pick an available custom `streamlit.app` subdomain.
5. Set Advanced settings → Secrets to `DATABASE_URL = "postgresql://...?...sslmode=require"`; use Python 3.12. Deploy.
6. Sign in. Your paper account, orders, valuation marks, and cached histories persist in PostgreSQL and are isolated by account.
7. Optional: import an existing V5 SQLite ledger with `python migrate_local_sqlite.py --sqlite "path/to/paper_accounts.sqlite3" --username your_username` **before** writing new cloud trade records. Keep a local backup.

Caveats: Community Cloud may sleep after inactivity and is not a continuously running trading server. Data-source availability is not guaranteed, LME benchmark needs licensed data for production, and this system never routes live orders. Cloud app login sessions are in-memory; password rotation does not forcibly terminate other live browser sessions. No preconfigured domain/database/account is included; you must authorize GitHub, Supabase, and Streamlit setup yourself.
