# Copper Quant Cloud V6.1 — 云端完整版

## 与 V6.0.1 的区别
- 保留中英双语、SHFE / LME 3M、风险指标、VaR/CVaR、蒙特卡洛、套保分析、历史回放与模拟交易。
- 修复 PostgreSQL 错误笼统显示为 OperationalError 的问题。提供不会输出数据库密码的诊断码。
- **推荐独立 Secret 字段**，解决连接字符串中 `@`、`#`、`%` 等字符的编码问题。
- 持续通过 PostgreSQL 保存模拟交易；不再需要 ngrok / Cloudflare 本地隧道。

## 1. 安全操作（优先）
你之前的截图曾暴露数据库凭据。请在 Supabase 先重置数据库密码，然后使用新密码。不要在 GitHub、对话、截图中展示。

## 2. 用 GitHub 替换代码
将 ZIP 中项目文件上传到现有 `copper-analysis` 仓库根目录（`app.py` 应位于根目录）；保留原 GitHub 仓库名与 Streamlit 应用 URL。
不要上传 `.streamlit/secrets.toml`、 `.env` 或真实密码。

## 3. Streamlit Cloud → Manage app → Settings → Secrets
删除之前的 `DATABASE_URL`，改为以下 **5 个独立字段**（同一个 TOML 编辑框，示例没有真实密码）：
```toml
DB_HOST = "aws-0-ap-northeast-1.pooler.supabase.com"
DB_PORT = 5432
DB_NAME = "postgres"
DB_USER = "postgres.ofljdadmotifjhenfcvj"
DB_PASSWORD = "在此填写重置后的真实数据库密码"
```
本方案不需要对密码进行 URL 百分号编码；直接粘贴原始数据库密码。若密码中有 `"` 或 `\` 等 TOML 特殊字符，需要按 TOML 规则转义；也可选择字面量单引号字符串（密码含单引号时除外）。建议生成不包含引号和反斜杠的强密码。
保存 Secrets 后在 Streamlit Cloud 重启应用。

## 4. 诊断
- `DB_AUTH`: 检查数据库密码、Pooler 用户名。
- `DB_POOLER_USER`: 检查项目 ID 与数据库用户。
- `DB_DNS`: 连接主机错误。
- `DB_TIMEOUT`: 数据库暂停、网络、连接超时。
- `DB_TLS`: TLS 链路失败。
- `DB_PERMISSION`: 数据库账户缺少建表权限。
- `DB_CONFIG`: Secrets 字段缺失或不完整。

提示：本版本没有访问你的真实 Supabase；不能保证你的账户设置正确。出现问题时只发送错误**代码**，不要发送任何 Secrets。

## 5. 初始化管理员
如果已经创建过管理员账户，不要重复创建。
若尚未创建，运行 `Setup_Cloud_Admin_Windows.bat`。按提示粘贴**完整 PostgreSQL URL** 并输入管理员密码；该步骤仍通过 getpass 不回显密码。如不希望制作 URL，可在自己的电脑上临时设置环境变量 `DB_HOST`、`DB_PORT`、`DB_NAME`、`DB_USER`、`DB_PASSWORD` 后执行 `python provision_admin.py --username YOUR_USER`，不要将环境变量保存到代码仓库。数据库账号与网站管理员账号不是同一个账号。

## 6. 云端运行范围
这是研究与模拟交易平台，不包含券商/期货交易所实盘下单接口；云端行情抓取依赖公开第三方源、可能受连接限制。历史回测和蒙特卡洛不能视为实际成交价格。

## 7. 推荐 Python 版本
目前云端日志采用 Python 3.14；如遇第三方行情兼容问题，可在 Streamlit Cloud 的部署设置中选择 Python 3.12（如果平台当前提供）。不能仅修改 requirements.txt 来切换解释器版本。
