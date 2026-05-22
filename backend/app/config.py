from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    backend_port: int = 8010
    frontend_port: int = 3010
    database_url: str = "postgresql://ai_soc:ai_soc_dev_password@postgres:5432/ai_soc_assistant"
    splunk_mcp_enabled: bool = False
    splunk_mcp_base_url: str = ""
    splunk_mcp_token: str = ""
    llm_enabled: bool = False
    foundation_sec_instruct_url: str = ""
    foundation_sec_reasoning_url: str = ""
    reasoning_enabled: bool = False
    routing_mode: str = "llm_primary"
    debug_trace_enabled: bool = True
    app_auth_enabled: bool = True
    app_auth_user: str = "analyst"
    app_auth_password: str = ""
    app_auth_session_secret: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
