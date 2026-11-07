"""Run in the GitHub repo root before committing; backs up app.py locally."""
from pathlib import Path
import re
p=Path('app.py')
s=p.read_text(encoding='utf-8')
if 'safe_db_diagnose' in s:
    print('Already patched. No changes.')
    raise SystemExit(0)
pattern=r"(?m)^try:\s*\n\s+init_db\(\)\s*\nexcept Exception(?: as \w+)?:\s*\n(?:(?:    |\t).+\n)+?\s+st\.stop\(\)"
m=re.search(pattern,s)
if not m:
    raise SystemExit('Could not find original init_db try/except; edit app.py manually using README snippet.')
replacement='''from db_diagnostic import safe_db_diagnose
try:
    init_db()
except Exception as e:
    # Do not print the raw exception: a driver error may contain connection details.
    try:
        url = st.secrets.get('DATABASE_URL', None)
    except Exception:
        url = None
    code, guidance = safe_db_diagnose(e, url)
    st.error(f'Database connection failed [{code}] / 数据库连接失败：{guidance}')
    st.stop()'''
backup=p.with_suffix('.py.pre_db_diagnostic.bak')
backup.write_text(s,encoding='utf-8')
p.write_text(s[:m.start()]+replacement+s[m.end():],encoding='utf-8')
print('Patched app.py. Backup:',backup)
print('IMPORTANT: keep .bak out of Git; only upload app.py and db_diagnostic.py.')
