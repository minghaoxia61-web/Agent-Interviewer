"""pytest 全局夹具：测试期间把数据目录重定向到临时目录、关闭访问令牌。

注意：环境变量必须在导入 app.* 之前设置（conftest 先于测试模块加载）。
"""
import os
import tempfile

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="rai_test_data_"))
os.environ.setdefault("ACCESS_TOKEN", "")
