"""pytest 全局夹具：测试期间重定向数据目录、强制 Mock 模式、关闭令牌。

注意：环境变量必须在导入 app.* 之前设置（conftest 先于测试模块加载）。
环境变量优先级高于 .env 文件，因此即使用户本地 .env 配了真实 Key，
测试也会稳定跑在 Mock 模式上（快、零成本、可离线）。
"""
import os
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="rai_test_data_")
os.environ["ACCESS_TOKEN"] = ""
os.environ["LLM_API_KEY"] = ""
