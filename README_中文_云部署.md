# Copper Quant Cloud V6 — 云端部署（中文）

## 目标架构

Streamlit Community Cloud（固定 `*.streamlit.app` 地址） → Streamlit 应用内账号登录 → Supabase PostgreSQL（持久化模拟账户、订单、估值、每用户行情缓存）。不使用 ngrok、Cloudflare Tunnel、8501/8502 公网网关或 Windows 常驻电脑。本项目只支持纸面模拟下单，**不接实盘券商、不自动成交真实订单**。

## 准备

1. 注册 GitHub、Streamlit Community Cloud（https://share.streamlit.io/），并在 Supabase（https://supabase.com/dashboard）创建 PostgreSQL 项目。
2. 在 Supabase 的 **Connect** / Database connection string 找到连接字符串，优先使用适合云端 IPv4 网络的 pooler 连接方式（根据项目控制台提示选择），确认包含 `sslmode=require`。连接串含数据库密码，**仅在本机输入与 Streamlit Secrets 中保存，绝不上传 GitHub 或发给聊天**。
3. 将本 ZIP 的**项目文件内容**上传至自己控制的 GitHub 私有仓库。`requirements.txt`、`app.py` 和各模块置于仓库根目录。GitHub 私有仓库权限按 Streamlit 当前产品支持情况确认。`.streamlit/secrets.toml` 必须不上传，已加入 `.gitignore`。
4. 在自己电脑用 Python 3.11/3.12 安装 `psycopg[binary]`；或双击 `Setup_Cloud_Admin_Windows.bat`。按提示输入管理员用户名、数据库 URL（输入时隐藏）和两次新密码（输入时隐藏，至少14字符）。此脚本会自动创建表和第一个账户，凭据不会写到代码中。
5. 打开 https://share.streamlit.io/ → **Create app**，选择 GitHub 仓库、分支、入口 `app.py`。在 **App URL** 填写你喜欢的、尚未被占用的子域名，例如 `copper-quant-yourteam`（这只是名称示例，不保证可用）。
6. 进入 **Advanced settings → Secrets** 粘贴以下内容，并替换为自己的真实 URL：

   ```toml
   DATABASE_URL = "postgresql://USER:PASSWORD@POOLER_HOST:5432/postgres?sslmode=require"
   ```

7. 选择 Python 3.12 并 Deploy。部署成功后在固定网址用步骤4创建的用户名密码登录；进入中英双语量化分析、套保、历史回放和模拟交易。

## 首次数据操作

- 从左侧选择 **在线获取**：通过原版 AKShare 相关公开接口拉取 SHFE/LME 3M 参考历史数据，受源站可用性/授权影响，不保证每次能成功。
- 从左侧选择 **上传 CSV**：推荐在源站不能使用时上传经核对的真实历史数据，必须包含 date/close 及回放所需的 open/high/low。
- **云端缓存**：历史数据按当前用户和市场保存到 PostgreSQL，不依赖 Streamlit 本地硬盘。会带来数据库空间占用。

## 迁移原 Windows 模拟盘

先在云端创建账户，再将原程序文件夹中的 `paper_accounts.sqlite3` 复制到本机安全位置。运行：

```powershell
python -m pip install "psycopg[binary]>=3.2,<4"
python migrate_local_sqlite.py --sqlite "C:\path\paper_accounts.sqlite3" --username 你的用户名
```

会提示输入数据库连接串。迁移脚本只读本地 SQLite，向该登录用户的 PostgreSQL 账户、订单、权益表导入原记录。**在云端有交易记录后不要重复执行**。原数据库不变，先备份。

## 固定 URL、数据与安全边界

- 固定域名属于 Streamlit 云端 `streamlit.app` 子域名，取决于平台命名规则和可用性。**当前压缩包并未自动创建云端网址**；必须你用自己的账户完成 GitHub、Supabase 与 Streamlit 授权配置。
- 这是应用层登录：密码使用随机盐 + PBKDF2-SHA256；失败六次锁定十五分钟；更换密码在侧边栏 **账号管理**。登录后才访问交易数据；数据库按 user_id 隔离。
- Streamlit 进程内会话不保证跨部署保留，重新部署可能需要重新登录。更换密码后，其他已经登录的浏览器会话可能持续有效直到重启或会话结束，当前不是组织级 SSO。
- Streamlit Community Cloud 在无流量时可能休眠、存在资源限额；**不提供保证全天候实时行情、持续自动下单或严格 SLA**。需24小时运行或商业级审计时，应迁移到付费常驻容器/云服务器以及托管 PostgreSQL。
- **不可将密钥/数据库密码或原账户信息提交 GitHub。** 当前项目不提供公众自行注册。模拟盘数据存于 PostgreSQL；历史回测本身仍为研究性简化模型，非交易所精确结算和换月。

## 排障

- 数据库错误：核实 Secrets 中的 `DATABASE_URL`、Supabase 密码、连接串端口与 pooler 地址、IPv4 连接。
- 登录失败：先确认是否成功运行 `provision_admin.py`；连续失败会临时锁定。
- 无数据：试传 CSV；公网行情来源可能限制云服务器 IP。
- 不允许把旧版公网端口 8501 直接暴露，也不需要运行任何 ngrok/cloudflared 客户端。
