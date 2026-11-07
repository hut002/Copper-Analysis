Copper Quant Cloud V6.0.1 修复说明

原因：backtest.py 引用了旧版 paper_engine.py，但云端项目仅有 cloud_paper.py。

最小修复：把本补丁 backtest.py 上传覆盖 GitHub 仓库根目录中的同名文件（必须与 app.py 同一目录）；提交后在 Streamlit Cloud Reboot app，或者等待自动重新部署。

也可直接在 GitHub 编辑 backtest.py：
from paper_engine import SPECS
改为
from cloud_paper import SPECS

无需修改 DATABASE_URL、账户密码或数据库。
