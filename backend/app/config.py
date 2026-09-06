from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_name: str = "StorServer"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_origin: str = "http://localhost:3000"

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    admin_email: str = "admin@hoststorm.cloud"
    admin_password: str

    database_url: str
    redis_url: str = "redis://redis:6379/0"

    agent_shared_token: str
    agent_url: str = "http://agent:9000"
    node_name: str = "storserver-local"
    node_region: str = "lab"

    public_base_domain: str = "hoststorm.cloud"
    panel_host: str = "panel.hoststorm.cloud"


settings = Settings()
