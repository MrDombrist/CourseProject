# UniSite API

Простое API на FastAPI с подключением к PostgreSQL для изучения основ веб-разработки.

## Структура проекта

```
UniSite/
├── server/
│   ├── api/
│   │   ├── __init__.py
│   │   └── api_implementation.py  # CRUD операции
│   ├── __init__.py
│   └── main.py                    # Запуск сервера
├── database.py                    # Подключение к БД
├── .env                          # Переменные окружения
├── pyproject.toml               # Зависимости
└── README.md
```

## Установка и настройка

### 1. Установка зависимостей

```bash
# Установка Poetry (если не установлен)
curl -sSL https://install.python-poetry.org | python3 -

# Установка зависимостей проекта
poetry install
```

### 2. Настройка базы данных PostgreSQL

Убедитесь, что PostgreSQL установлен и запущен. Создайте базу данных:

```sql
-- Подключитесь к PostgreSQL
psql -U postgres

-- Создайте базу данных
CREATE DATABASE unisite_db;

-- Создайте пользователя (опционально)
CREATE USER unisite_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE unisite_db TO unisite_user;
```

### 3. Настройка переменных окружения

Скопируйте и настройте файл `.env`:

```bash
cp .env.example .env
```

Отредактируйте `.env` файл, указав правильные данные для подключения к вашей базе данных.

### 4. Запуск сервера

```bash
# Активация виртуального окружения Poetry
poetry shell

# Запуск сервера
python main.py

# Или с помощью uvicorn напрямую
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## API Эндпоинты

### Основные

- `GET /` - Главная страница API
- `GET /status` - Статус сервера
- `GET /docs` - Swagger UI документация
- `GET /redoc` - ReDoc документация

### Пользователи (Users)

- `GET /api/users` - Получить всех пользователей
- `GET /api/users/{user_id}` - Получить пользователя по ID
- `POST /api/users` - Создать нового пользователя
- `PUT /api/users/{user_id}` - Обновить пользователя
- `DELETE /api/users/{user_id}` - Удалить пользователя
- `DELETE /api/users` - Удалить всех пользователей

### Служебные

- `GET /api/health` - Проверка состояния API и БД

## Примеры запросов

### Создание пользователя

```bash
curl -X POST "http://127.0.0.1:8000/api/users" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Иван Петров",
       "email": "ivan@example.com",
       "age": 25
     }'
```

### Получение всех пользователей

```bash
curl -X GET "http://127.0.0.1:8000/api/users"
```

### Обновление пользователя

```bash
curl -X PUT "http://127.0.0.1:8000/api/users/1" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Иван Иванов",
       "age": 26
     }'
```

### Удаление пользователя

```bash
curl -X DELETE "http://127.0.0.1:8000/api/users/1"
```

## Структура базы данных

### Таблица `users`

| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL | Первичный ключ |
| name | VARCHAR(255) | Имя пользователя |
| email | VARCHAR(255) | Email (уникальный) |
| age | INTEGER | Возраст (0-150) |
| created_at | TIMESTAMP | Время создания |
| updated_at | TIMESTAMP | Время обновления |

## Разработка

### Форматирование кода

```bash
# Форматирование с Black
poetry run black .

# Сортировка импортов
poetry run isort .

# Проверка стиля кода
poetry run flake8 .
```

### Тестирование

```bash
# Запуск тестов
poetry run pytest

# Запуск с покрытием
poetry run pytest --cov=.
```

## Логи

Логи сохраняются в файл `unisite.log` и выводятся в консоль. Уровень логирования можно настроить в `.env` файле.

## Полезные команды

```bash
# Проверка статуса сервера
curl http://127.0.0.1:8000/status

# Проверка здоровья API и БД
curl http://127.0.0.1:8000/api/health

# Просмотр логов в реальном времени
tail -f unisite.log

# Остановка сервера
# Ctrl+C в терминале где запущен сервер
```

## Устранение проблем

### Проблемы с подключением к базе данных

1. Убедитесь, что PostgreSQL запущен:
   ```bash
   # Ubuntu/Debian
   sudo systemctl status postgresql
   
   # macOS с Homebrew
   brew services list | grep postgresql
   
   # Windows
   # Проверьте в Services или Task Manager
   ```

2. Проверьте настройки в `.env` файле
3. Убедитесь, что база данных `unisite_db` существует
4. Проверьте права доступа пользователя к базе данных

### Ошибки при запуске

1. **ModuleNotFoundError**: Убедитесь, что все зависимости установлены:
   ```bash
   poetry install
   ```

2. **Port already in use**: Измените порт в `.env` или остановите процесс:
   ```bash
   # Найти процесс на порту 8000
   lsof -i :8000
   
   # Остановить процесс
   kill -9 <PID>
   ```

3. **Permission denied**: Проверьте права на файлы и директории

### Очистка данных

```bash
# Удаление всех пользователей через API
curl -X DELETE "http://127.0.0.1:8000/api/users"

# Или напрямую в PostgreSQL
psql -U postgres -d unisite_db -c "DELETE FROM users;"
```

## Следующие шаги

После того как базовый API заработает, вы можете:

1. **Добавить аутентификацию** - JWT токены, сессии
2. **Создать ORM модели** - SQLAlchemy или Tortoise ORM
3. **Добавить валидацию** - более сложные Pydantic модели
4. **Создать тесты** - pytest для тестирования эндпоинтов
5. **Добавить миграции** - Alembic для управления схемой БД
6. **Создать фронтенд** - React, Vue.js или обычный HTML/JS
7. **Добавить документацию** - расширить Swagger/OpenAPI
8. **Настроить CI/CD** - GitHub Actions, Docker

## Дополнительные ресурсы

- [Документация FastAPI](https://fastapi.tiangolo.com/)
- [Документация asyncpg](https://magicstack.github.io/asyncpg/)
- [PostgreSQL Tutorial](https://www.postgresql.org/docs/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

## Контакты

Если у вас есть вопросы или предложения, создайте issue в репозитории проекта.