from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    kilopass_api_key: str = ""
    kilopass_base_url: str = ""
    kilopass_model: str = ""
    kilopass_embedding_model: str = ""
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str
    mysql_password: str
    mysql_database: str
    mysql_test_database: str = ""
    mysql_ssl_ca: str = ""
    secret_key: str
    chroma_path: str = "./data/chroma"

    def database_url(self, test: bool = False) -> str:
        if test:
            if not self.mysql_test_database:
                raise RuntimeError("MYSQL_TEST_DATABASE está vacío: las pruebas requieren una base propia")
            base = self.mysql_test_database
        else:
            base = self.mysql_database
        return (
            f"mysql+pymysql://{quote_plus(self.mysql_user)}:{quote_plus(self.mysql_password)}"
            f"@{self.mysql_host}:{self.mysql_port}/{base}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
