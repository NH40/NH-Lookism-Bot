from pydantic_settings import BaseSettings
from typing import List
 
 
class Settings(BaseSettings):
    BOT_TOKEN: str
    POSTGRES_USER: str = "lookism"
    POSTGRES_PASSWORD: str = "lookism_secret"
    POSTGRES_DB: str = "lookism_db"
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    DEBUG: bool = False
    ADMIN_IDS: str = ""
 
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
 
    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
 
    @property
    def admin_ids_list(self) -> List[int]:
        if not self.ADMIN_IDS:
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]
 
    class Config:
        env_file = ".env"
        extra = "ignore"
 
 
settings = Settings()
