"""Private app login for Streamlit: persistent salted password verifier, DB-backed lockout."""
import hashlib,hmac,secrets
from datetime import datetime,timezone,timedelta
from cloud_db import connect,init_db

ITERATIONS=600_000

def password_hash(password,salt):
    return hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),bytes.fromhex(salt),ITERATIONS).hex()

def create_user(username,password,url=None):
    username=username.strip().lower()
    if not 3<=len(username)<=64 or not username.replace('_','').replace('-','').isalnum():
        raise ValueError('Username: 3-64 letters, digits, hyphens or underscores')
    if len(password)<14: raise ValueError('Password must contain at least 14 characters')
    salt=secrets.token_hex(32)
    with connect(url) as c:
        c.execute('INSERT INTO users(username,password_salt,password_hash) VALUES(%s,%s,%s)',(username,salt,password_hash(password,salt)))
        c.commit()

def authenticate(username,password,url=None):
    username=username.strip().lower()
    if len(username)>64 or len(password)>1024: return None
    with connect(url) as c:
        # Serialize attempts for the username, prevents races between parallel sessions
        c.execute('INSERT INTO login_attempts(username) VALUES(%s) ON CONFLICT DO NOTHING',(username,))
        a=c.execute('SELECT * FROM login_attempts WHERE username=%s FOR UPDATE',(username,)).fetchone()
        now=datetime.now(timezone.utc)
        if a['locked_until'] and a['locked_until']>now: return None
        u=c.execute('SELECT * FROM users WHERE username=%s',(username,)).fetchone()
        salt=u['password_salt'] if u else '00'*32
        expected=u['password_hash'] if u else '00'*32
        valid=hmac.compare_digest(password_hash(password,salt),expected)
        if valid:
            c.execute('UPDATE login_attempts SET failures=0,locked_until=NULL,last_failed=NULL WHERE username=%s',(username,))
            c.commit()
            return {'id':u['id'],'username':u['username']}
        failures=a['failures']+1
        locked_until=now+timedelta(minutes=15) if failures>=6 else None
        c.execute('UPDATE login_attempts SET failures=%s,last_failed=now(),locked_until=%s WHERE username=%s',(failures,locked_until,username))
        c.commit()
        return None

def change_credentials(user_id,old_password,new_username,new_password,url=None):
    new_username=new_username.strip().lower()
    if len(new_password)<14: raise ValueError('New password must have at least 14 characters')
    if not 3<=len(new_username)<=64 or not new_username.replace('_','').replace('-','').isalnum(): raise ValueError('Invalid username')
    with connect(url) as c:
        u=c.execute('SELECT * FROM users WHERE id=%s FOR UPDATE',(user_id,)).fetchone()
        if not u or not hmac.compare_digest(password_hash(old_password,u['password_salt']),u['password_hash']):
            raise ValueError('Current password incorrect')
        salt=secrets.token_hex(32)
        c.execute('UPDATE users SET username=%s,password_salt=%s,password_hash=%s WHERE id=%s',(new_username,salt,password_hash(new_password,salt),user_id))
        c.execute('DELETE FROM login_attempts WHERE username IN (%s,%s)',(u['username'],new_username))
        c.commit()

def gate():
    import streamlit as st
    if 'auth_user' in st.session_state:
        return st.session_state['auth_user']
    st.title('🔒 Copper Quant · 安全登录 / Secure Sign In')
    st.caption('Persistent cloud account / 云端持久化账户')
    with st.form('cloud_sign_in'):
        username=st.text_input('Username / 用户名',max_chars=64)
        password=st.text_input('Password / 密码',type='password')
        submit=st.form_submit_button('Sign In / 登录',type='primary')
    if submit:
        try: user=authenticate(username,password)
        except Exception:
            st.error('Authentication service unavailable. Check database configuration. / 登录服务不可用，请检查数据库。')
            st.stop()
        if user:
            st.session_state['auth_user']=user
            st.rerun()
        else:st.error('Invalid credentials or temporarily locked (6 failures / 15 min). / 账户或密码错误，或暂时锁定。')
    st.caption('No public registration. Account owner provisions the first user privately. / 不允许公开注册。')
    st.stop()
