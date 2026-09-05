"""全局配置：所有可调参数集中在 Settings，通过 .env 覆盖。"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # LLM 配置：任何 OpenAI 兼容接口均可（Zhipu / DeepSeek / OpenAI / Moonshot ...）
    llm_api_key: str = ""  # 为空时进入 Mock 模式（无需 API Key 即可完整跑通流程）
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.6
    llm_timeout: float = 60.0

    # 面试节奏控制（AgentX 原则：确定性规则可调，不依赖 LLM 自觉）
    max_followup_depth: int = 3      # 单个漏洞点最多追问层数（3-5 层深挖）
    max_probe_weaknesses: int = 3    # 项目深挖环节最多覆盖的漏洞点数
    max_drill_rounds: int = 4        # 技术基础环节题量
    max_stress_rounds: int = 2       # 压力测试环节题量

    data_dir: Path = BASE_DIR / "data"
    static_dir: Path = ""            # 生产模式下前端构建产物目录，留空自动探测
    cors_origins: str = "*"

    # 公网部署护栏（AgentX 演示模式）
    access_token: str = ""           # 非空时所有 API 需携带 X-API-Token（或 ?token=）
    rate_limit_daily: int = 300      # 每客户端 IP 每日 API 调用上限

    # 检索后端：auto（优先 Chroma，未安装则 BM25）/ bm25 / ngram
    retriever_mode: str = "auto"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def traces_dir(self) -> Path:
        return self.data_dir / "traces"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "reports"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def knowledge_dir(self) -> Path:
        return self.data_dir / "knowledge"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "rai.db"


settings = Settings()
