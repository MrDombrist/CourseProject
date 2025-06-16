"""Конфигурация приложения и загрузка переменных окружения"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    # Поиск .env файла в текущей директории и родительских
    env_path = Path('.') / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Загружен .env файл: {env_path.absolute()}")
    else:
        print("⚠️  .env файл не найден, используются системные переменные окружения")

except ImportError:
    print("⚠️  python-dotenv не установлен, используются системные переменные окружения")


class Settings:
    """Класс для управления настройками приложения"""

    # Настройки базы данных
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "password")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME", "unisite_db")

    # Настройки сервера
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")

    # Настройки безопасности
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

    # Настройки логирования
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")

    @property
    def database_url(self) -> str:
        """Получить URL для подключения к базе данных"""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    def __repr__(self) -> str:
        return f"Settings(host={self.HOST}, port={self.PORT}, db_name={self.DB_NAME})"


# Создание глобального экземпляра настроек
settings = Settings()


# Функция для проверки обязательных переменных
def validate_required_env_vars():
    """Проверка наличия обязательных переменных окружения"""
    required_vars = {
        "DB_PASSWORD": settings.DB_PASSWORD,
        "SECRET_KEY": settings.SECRET_KEY,
    }

    missing_vars = []
    default_vars = []

    for var_name, var_value in required_vars.items():
        if var_name == "DB_PASSWORD" and var_value == "password":
            default_vars.append(var_name)
        elif var_name == "SECRET_KEY" and "change-in-production" in var_value:
            default_vars.append(var_name)

    if default_vars:
        print(f"⚠️  Используются значения по умолчанию для: {', '.join(default_vars)}")
        print("   Рекомендуется изменить их в .env файле для безопасности")

    if missing_vars:
        print(f"❌ Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
        return False

    return True


if __name__ == "__main__":
    # Проверка настроек при прямом запуске
    print("🔧 Текущие настройки приложения:")
    print(f"   Сервер: {settings.HOST}:{settings.PORT}")
    print(f"   База данных: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    print(f"   Пользователь БД: {settings.DB_USER}")
    print(f"   Режим отладки: {settings.DEBUG}")
    print(f"   Уровень логирования: {settings.LOG_LEVEL}")

    validate_required_env_vars()