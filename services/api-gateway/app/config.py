# services/api-gateway/app/config.py

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Service info
    app_name: str = "PathWise AI API"
    debug: bool = False

    # Redis
    redis_url: str = "redis://redis:6379"

    # Database
    database_url: str = "postgresql://pathwise:pathwise_dev@timescaledb:5432/pathwise"

    # SDN Controller
    odl_url: str = "http://opendaylight:8181"
    odl_username: str = "admin"
    odl_password: str = "admin"

    # Batfish
    batfish_host: str = "batfish"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Prediction Engine
    prediction_engine_url: str = "http://prediction-engine:8001"

    # Steering Service
    steering_service_url: str = "http://traffic-steering:8002"

    # Digital Twin Service
    digital_twin_url: str = "http://digital-twin:8003"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
