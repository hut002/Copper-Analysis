# Changes in V6.1
- New safe connection options: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` (preferred), or legacy `DATABASE_URL`.
- Consistent TLS-required PostgreSQL connection.
- Safe error classification without printing raw psycopg exceptions.
- App renders diagnostic codes without revealing secrets.
- `db_check.py` interactive private diagnostic CLI.
- No change to quant/hedge/backtest/paper trading business logic.
