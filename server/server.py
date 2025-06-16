"""Основной файл запуска FastAPI сервера"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from starlette.responses import JSONResponse


from .config import settings, validate_required_env_vars
from .api.api_implementation import router
from server.database.db_con import init_database, close_database_pool

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("unisite.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    logger.info("🚀 Запуск UniSite API...")

    # Инициализация базы данных при запуске
    try:
        await init_database()
        logger.info("✅ База данных успешно инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации базы данных: {e}")
        raise

    yield

    # Закрытие соединений при остановке
    logger.info("🛑 Остановка UniSite API...")
    try:
        await close_database_pool()
        logger.info("✅ Соединения с базой данных закрыты")
    except Exception as e:
        logger.error(f"❌ Ошибка при закрытии соединений: {e}")


# Создание FastAPI приложения
app = FastAPI(
    title="UniSite API",
    description="API для проекта UniSite - учебная система управления",
    version="0.1.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc
    lifespan=lifespan
)

# Настройка CORS (для фронтенда)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(router)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Корневой эндпоинт
@app.get("/", response_class=HTMLResponse)
async def root():
    """Главная страница"""
    try:
        # Получаем абсолютный путь к файлу index.html
        current_dir = os.path.dirname(__file__)
        html_path = os.path.join(current_dir, "..", "client", "index.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>UniSite API</h1><p>index.html not found</p>")
    except Exception as e:
        return HTMLResponse(content=f"<h1>UniSite API</h1><p>Error: {e}</p>")


@app.get("/register", response_class=HTMLResponse)
async def register_page():
    """Страница регистрации"""
    try:
        # Получаем абсолютный путь к файлу register.html
        current_dir = os.path.dirname(__file__)
        html_path = os.path.join(current_dir, "..", "client", "register.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>UniSite API</h1><p>register.html not found</p>")
    except Exception as e:
        return HTMLResponse(content=f"<h1>UniSite API</h1><p>Error: {e}</p>")



@app.get("/login", response_class=HTMLResponse)
async def login_page():
    """Страница входа"""
    try:
        # Получаем абсолютный путь к файлу login.html
        current_dir = os.path.dirname(__file__)
        html_path = os.path.join(current_dir, "..", "client", "login.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>UniSite API</h1><p>login.html not found</p>")
    except Exception as e:
        return HTMLResponse(content=f"<h1>UniSite API</h1><p>Error: {e}</p>")

# @app.get('/favicon.ico', include_in_schema=False)
# async def favicon():
#     return FileResponse(os.path.join("client", "favicon.ico"))

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    """Личный кабинет (требует аутентификации)"""
    try:
        # Получаем абсолютный путь к файлу login.html
        current_dir = os.path.dirname(__file__)
        html_path = os.path.join(current_dir, "..", "client", "dashboard.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>UniSite API</h1><p>dashboard.html not found</p>")
    except Exception as e:
        return HTMLResponse(content=f"<h1>UniSite API</h1><p>Error: {e}</p>")

@app.get("/addWork", response_class=HTMLResponse)
async def addWork_page():
    """Страница добавления работы"""
    try:
        # Получаем абсолютный путь к файлу addWorks.html
        current_dir = os.path.dirname(__file__)
        html_path = os.path.join(current_dir, "..", "client", "addWork.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>UniSite API</h1><p>addWorks.html not found</p>")
    except Exception as e:
        return HTMLResponse(content=f"<h1>UniSite API</h1><p>Error: {e}</p>")



@app.get("/works/{work_id}", response_class=HTMLResponse)
async def view_work_page(work_id: int):
    """Страница просмотра отдельной научной работы"""
    try:
        # Получаем абсолютный путь к файлу viewWork.html
        current_dir = os.path.dirname(__file__)
        html_path = os.path.join(current_dir, "..", "client", "viewWork.html")

        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Можно добавить work_id в HTML как метатег для использования в JavaScript
        # Добавляем скрипт с work_id в head секцию
        work_id_script = f'<script>window.WORK_ID = {work_id};</script>'

        # Вставляем скрипт перед закрывающим тегом </head>
        if '</head>' in html_content:
            html_content = html_content.replace('</head>', f'{work_id_script}\n</head>')
        else:
            # Если нет тега head, добавляем в начало body
            html_content = html_content.replace('<body>', f'<body>\n{work_id_script}')

        return HTMLResponse(content=html_content)

    except FileNotFoundError:
        return HTMLResponse(
            content=f"<h1>UniSite API</h1><p>viewWork.html not found</p><p>Work ID: {work_id}</p>",
            status_code=404
        )
    except Exception as e:
        return HTMLResponse(
            content=f"<h1>UniSite API</h1><p>Error: {e}</p><p>Work ID: {work_id}</p>",
            status_code=500
        )

@app.get("/edit-profile", response_class=HTMLResponse)
async def edit_profile_page():
    """Страница редактирования профиля"""
    try:
        # Получаем абсолютный путь к файлу editProfile.html
        current_dir = os.path.dirname(__file__)
        html_path = os.path.join(current_dir, "..", "client", "editProfile.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>UniSite API</h1><p>editProfile.html not found</p>")
    except Exception as e:
        return HTMLResponse(content=f"<h1>UniSite API</h1><p>Error: {e}</p>")


@app.get("/moderation", response_class=HTMLResponse)
async def moderation_page():
    """Страница модерации (только для модераторов)"""
    try:
        # Получаем абсолютный путь к файлу moderation.html
        current_dir = os.path.dirname(__file__)
        html_path = os.path.join(current_dir, "..", "client", "moderation.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>UniSite API</h1><p>moderation.html not found</p>")
    except Exception as e:
        return HTMLResponse(content=f"<h1>UniSite API</h1><p>Error: {e}</p>")


@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    """Страница администратора (управление модераторами)"""
    try:
        # Получаем абсолютный путь к файлу admin.html
        current_dir = os.path.dirname(__file__)
        html_path = os.path.join(current_dir, "..", "client", "admin.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>UniSite API</h1><p>admin.html not found</p>")
    except Exception as e:
        return HTMLResponse(content=f"<h1>UniSite API</h1><p>Error: {e}</p>")

# Эндпоинт для проверки статуса
@app.get("/status")
async def get_status():
    """Проверка статуса сервера"""
    return {
        "status": "running",
        "service": "UniSite API",
        "version": "0.1.0"
    }


# Обработчик ошибок
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Эндпоинт не найден",
            "message": "Проверьте правильность URL",
            "available_endpoints": [
                "/",
                "/status",
                "/api",
                "/docs",
                "/redoc"
            ]
        }
    )


if __name__ == "__main__":
    # Проверка переменных окружения
    if not validate_required_env_vars():
        logger.error("❌ Проверьте настройки в .env файле")
        exit(1)

    logger.info(f"🌐 Запуск сервера на http://{settings.HOST}:{settings.PORT}")
    logger.info(f"📊 Режим отладки: {settings.DEBUG}")
    logger.info(f"🗃️  База данных: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")

    uvicorn.run(
        "server.server:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,  # Автоперезагрузка в режиме разработки
        log_level=settings.LOG_LEVEL.lower()
    )
