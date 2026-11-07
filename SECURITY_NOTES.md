# Security notes

- Do not store database connection strings, passwords, cloud authentication secrets or brokerage tokens in Git.
- All DB queries for account/order/valuation data include the authenticated `user_id`. The application uses a server-side connection string and does not expose DB access in the browser.
- Passwords use random salts with PBKDF2-SHA256 (600,000 rounds); six failed logins lock that username for 15 minutes.
- The app uses Streamlit session state for login (not organization-grade SSO). Existing logged-in sessions may stay valid after a password change until sessions end or app restarts.
- System avoids broker integration. Forward paper trades use user-entered observed prices; historical replay uses next-bar execution assumptions.
- DB roles used in `DATABASE_URL` require schema creation and normal CRUD privileges. For larger teams, apply restricted DB roles, centralized identity management, audit logs, secret rotation and backups.
- Streamlit Community Cloud may sleep and is not recommended for continuous live trading systems.
