# Copper Quant Cloud V6.1.2 — 模拟盘委托记录修复

## 故障
提交虚拟订单后，`app.py` 第219行调用 `rows(...)`，`cloud_paper.py` 旧版第81行在退出数据库 cursor 上下文后读取 `cur.description`。关闭游标后该属性可能为 `None`，触发 `TypeError: 'NoneType' object is not iterable`。

## 修复
`rows()` 改为直接将 psycopg `dict_row` 的记录转换为 pandas DataFrame；不再引用关闭游标的列元数据。对于无历史订单或权益数据，返回带预设列名的空 DataFrame；查询仍严格按 `user_id`、`market`、`mode` 隔离。

## 更新现有 GitHub 仓库（推荐）
1. 备份 GitHub 仓库中现有的 `cloud_paper.py`。
2. 将本补丁里的 `cloud_paper.py` 上传到仓库**根目录**，覆盖同名文件。
3. GitHub 点击 **Commit changes**。Streamlit Community Cloud 会自动重新部署（必要时 Manage app → Reboot app）。
4. 重新登录，查看“委托与成交记录”和“权益变化”。订单已经写入 PostgreSQL，不需要重新下单。

**无需修改** `app.py`、Supabase Secrets、管理员密码或数据库表结构；不要清空任何数据表。

## 验证
本地执行 `python test_journal_fix.py` 可运行不依赖数据库的回归测试；测试使用模拟游标与模拟数据，不会访问或修改云端账户。

注意：本补丁已离线测试，尚未在你的 Streamlit Cloud / Supabase 环境完成在线验证。
