from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_version: str = "1.0.0"
    app_secret_key: str = "development-only"
    public_base_url: str = "http://localhost:3000"
    demo_mode: bool = True
    demo_user_id: str = "demo-user"
    database_url: str = "sqlite:///./memento.db"
    event_ingest_api_key: str = ""

    dashscope_api_key: str = ""
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_compiler_model: str = "qwen3.7-plus"
    qwen_adjudicator_model: str = "qwen3.6-flash"
    qwen_explanation_model: str = "qwen3.6-flash"
    qwen_request_timeout_seconds: int = 30
    demo_daily_token_limit: int = 250000

    alibaba_cloud_access_key_id: str = ""
    alibaba_cloud_access_key_secret: str = ""
    alibaba_cloud_oss_region: str = ""
    alibaba_cloud_oss_endpoint: str = ""
    alibaba_cloud_oss_bucket: str = ""
    alibaba_cloud_oss_prefix: str = "mementovm/replays"

    @property
    def qwen_configured(self) -> bool:
        return bool(self.dashscope_api_key)

    @property
    def oss_configured(self) -> bool:
        return all(
            [
                self.alibaba_cloud_access_key_id,
                self.alibaba_cloud_access_key_secret,
                self.alibaba_cloud_oss_endpoint,
                self.alibaba_cloud_oss_bucket,
            ]
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

