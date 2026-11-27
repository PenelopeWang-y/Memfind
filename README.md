# MemFind 2.0 可运行原型

## 当前实现
- Streamlit网页交互界面
- SQLite空间语义记忆库（物品、别名、颜色、紧急程度、库位、批次、库存）
- Master Agent规则路由
- 空间记忆、智能排产、设备运维、质量检测、供应链优化五类Agent入口
- 模拟订单、设备、质量和库存数据
- Agent调用过程与运行日志

## 重要说明
当前版本是可运行的规则型模拟原型，不是已接入真实大模型的生产系统。
没有接入真实MES/ERP/WMS、真实传感器或Arduino小车。
页面中的制造业务数据为演示数据，不能在答辩中称为真实工厂数据。

## Windows本地运行
1. 安装 Python 3.10 或更新版本。
2. 解压项目文件。
3. 在项目文件夹地址栏输入 cmd，回车。
4. 执行：
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   streamlit run app.py
5. 浏览器打开终端显示的本地地址，通常为 http://localhost:8501

## 公网发布（Streamlit Community Cloud）
1. 将本项目上传到 GitHub 仓库。
2. 打开 https://share.streamlit.io/ 并登录。
3. 选择仓库、分支 main、入口文件 app.py。
4. 部署成功后会获得一个 *.streamlit.app 的公网链接。
5. 用手机流量或无痕窗口测试评委访问权限。

官方文档：
https://docs.streamlit.io/deploy/streamlit-community-cloud

## 数据持久化提醒
Community Cloud 的本地文件系统不适合作为长期可靠数据库。比赛演示可使用初始化演示数据；若需要长期保存用户写入数据，后续应迁移到托管数据库。
