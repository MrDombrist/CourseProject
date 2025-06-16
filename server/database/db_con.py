"""Конфигурация и управление подключением к PostgreSQL"""
import os
import logging
from typing import Optional
import asyncpg
from asyncpg import Pool

from server.config import settings

logger = logging.getLogger(__name__)

# Глобальный пул соединений
db_pool: Optional[Pool] = None


def get_database_url() -> str:
    """Построение URL подключения к базе данных из переменных окружения"""
    return settings.database_url


async def create_database_pool() -> Pool:
    """Создание пула соединений с базой данных"""
    database_url = get_database_url()

    try:
        pool = await asyncpg.create_pool(
            database_url,
            min_size=1,  # Минимальное количество соединений
            max_size=10,  # Максимальное количество соединений
            command_timeout=60,  # Таймаут команд (секунды)
            server_settings={
                'application_name': 'unisite_api',
            }
        )

        logger.info("✅ Пул соединений с базой данных создан")
        return pool

    except Exception as e:
        logger.error(f"❌ Ошибка создания пула соединений: {e}")
        raise


async def init_database():
    """Инициализация базы данных и создание таблиц"""
    global db_pool

    # Создаем пул соединений
    db_pool = await create_database_pool()

    # Создаем таблицы, если их нет
    async with db_pool.acquire() as connection:
        await create_tables(connection)


async def create_tables(connection: asyncpg.Connection):
    """Создание необходимых таблиц в базе данных"""
    try:
        # Создание таблицы пользователей
        create_users_table = """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            age INTEGER CHECK (age >= 0 AND age <= 150),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """

        create_students_table = """
        CREATE TABLE IF NOT EXISTS students (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        student_id VARCHAR(50) UNIQUE NOT NULL,
        faculty VARCHAR(255) NOT NULL,
        degree_level VARCHAR(50) NOT NULL, -- бакалавр, магистр, аспирант
        avatar_url VARCHAR(500),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );"""

        create_works_table = """
        CREATE TABLE IF NOT EXISTS works (
        id SERIAL PRIMARY KEY,
        title VARCHAR(500) NOT NULL,
        description TEXT NOT NULL,
        category VARCHAR(100) NOT NULL,
        keywords TEXT[], -- массив ключевых слов
        year INTEGER NOT NULL,
        supervisor VARCHAR(255),
        author_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
        ai_generated_image VARCHAR(500), -- URL ИИ-изображения
        file_path VARCHAR(500), -- путь к файлу работы
        views_count INTEGER DEFAULT 0,
        likes_count INTEGER DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """

        create_work_likes_table = """
        CREATE TABLE IF NOT EXISTS work_likes (
        id SERIAL PRIMARY KEY,
        work_id INTEGER NOT NULL REFERENCES works(id) ON DELETE CASCADE,
        student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        UNIQUE(work_id, student_id)
        );
        """

        create_moderators_table = """
        CREATE TABLE IF NOT EXISTS moderators (
            id SERIAL PRIMARY KEY,
            student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            permissions TEXT[] DEFAULT '{"approve_works", "reject_works", "view_stats"}',
            appointed_by INTEGER REFERENCES moderators(id),
            appointed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            is_active BOOLEAN DEFAULT TRUE,
            UNIQUE(student_id)
        );
        """

        create_work_submissions_table = """
        CREATE TABLE IF NOT EXISTS work_submissions (
            id SERIAL PRIMARY KEY,
            title VARCHAR(500) NOT NULL,
            description TEXT NOT NULL,
            category VARCHAR(100) NOT NULL,
            keywords TEXT[],
            year INTEGER NOT NULL,
            supervisor VARCHAR(255),
            author_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            file_path VARCHAR(500),
            status VARCHAR(50) DEFAULT 'pending', -- pending, approved, rejected
            moderator_id INTEGER REFERENCES moderators(id),
            moderator_comment TEXT,
            submitted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            reviewed_at TIMESTAMP WITH TIME ZONE,
            approved_work_id INTEGER REFERENCES works(id) -- ссылка на созданную работу после одобрения
        );
        """

        create_moderation_logs_table = """
        CREATE TABLE IF NOT EXISTS moderation_logs (
            id SERIAL PRIMARY KEY,
            moderator_id INTEGER NOT NULL REFERENCES moderators(id),
            submission_id INTEGER NOT NULL REFERENCES work_submissions(id),
            action VARCHAR(50) NOT NULL, -- approved, rejected, returned_for_revision
            comment TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """

        await connection.execute(create_users_table)
        await connection.execute(create_students_table)
        await connection.execute(create_works_table)
        await connection.execute(create_work_likes_table)
        await connection.execute(create_moderators_table)
        await connection.execute(create_work_submissions_table)
        await connection.execute(create_moderation_logs_table)

        # Создание индексов для оптимизации
        create_email_index = "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);"
        create_created_at_index = "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);"
        await connection.execute("CREATE INDEX IF NOT EXISTS idx_work_submissions_status ON work_submissions(status);")
        await connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_work_submissions_author ON work_submissions(author_id);")
        await connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_moderation_logs_moderator ON moderation_logs(moderator_id);")

        await connection.execute(create_email_index)
        await connection.execute(create_created_at_index)

        # Создание триггера для автоматического обновления updated_at
        create_trigger_function = """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        """

        create_trigger = """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_users_updated_at') THEN
                CREATE TRIGGER update_users_updated_at
                    BEFORE UPDATE ON users
                    FOR EACH ROW
                    EXECUTE FUNCTION update_updated_at_column();
            END IF;
        END$$;
        """

        await connection.execute(create_trigger_function)
        await connection.execute(create_trigger)

        logger.info("✅ Таблицы и индексы созданы успешно")

    except Exception as e:
        logger.error(f"❌ Ошибка создания таблиц: {e}")
        raise


async def get_db_connection():
    """Получение соединения с базой данных для использования в эндпоинтах"""
    global db_pool

    if db_pool is None:
        raise Exception("Пул соединений не инициализирован")

    async with db_pool.acquire() as connection:
        yield connection


async def close_database_pool():
    """Закрытие пула соединений"""
    global db_pool

    if db_pool:
        await db_pool.close()
        db_pool = None
        logger.info("✅ Пул соединений закрыт")


async def check_database_connection() -> bool:
    """Проверка подключения к базе данных"""
    try:
        global db_pool
        if db_pool is None:
            return False

        async with db_pool.acquire() as connection:
            await connection.fetchval("SELECT 1")
            return True

    except Exception as e:
        logger.error(f"❌ Ошибка проверки подключения к БД: {e}")
        return False


# Дополнительные утилиты для работы с БД
async def execute_query(query: str, *args):
    """Выполнение произвольного запроса"""
    global db_pool

    if db_pool is None:
        raise Exception("Пул соединений не инициализирован")

    async with db_pool.acquire() as connection:
        return await connection.execute(query, *args)


async def fetch_query(query: str, *args):
    """Выполнение SELECT запроса с получением результата"""
    global db_pool

    if db_pool is None:
        raise Exception("Пул соединений не инициализирован")

    async with db_pool.acquire() as connection:
        return await connection.fetch(query, *args)


async def fetchrow_query(query: str, *args):
    """Выполнение SELECT запроса с получением одной строки"""
    global db_pool

    if db_pool is None:
        raise Exception("Пул соединений не инициализирован")

    async with db_pool.acquire() as connection:
        return await connection.fetchrow(query, *args)