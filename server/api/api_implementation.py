"""Обновленная реализация API для академической витрины UniSite"""
import logging
import time
from datetime import datetime as dt
from typing import Optional, List
import hashlib
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
import bcrypt
from passlib.context import CryptContext
import asyncpg
from pydantic import BaseModel, EmailStr, validator

from ..database.db_con import get_db_connection, fetchrow_query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Pydantic модели для API
class StudentRegister(BaseModel):
    name: str
    email: EmailStr
    password: str
    student_id: str
    faculty: str
    degree_level: str  # бакалавр, магистр, аспирант

    @validator('email')
    def validate_kpfu_email(cls, v):
        if not v.endswith('@stud.kpfu.ru'):
            raise ValueError('Разрешены только корпоративные email @stud.kpfu.ru')
        return v

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Пароль должен содержать минимум 8 символов')
        return v

class StudentLogin(BaseModel):
    email: EmailStr
    password: str

class StudentProfile(BaseModel):
    id: int
    name: str
    email: str
    student_id: str
    faculty: str
    degree_level: str
    avatar_url: Optional[str] = None
    created_at: dt
    works_count: int

class WorkCreate(BaseModel):
    title: str
    description: str
    category: str  # НИР, ВКР, диссертация, статья, etc
    keywords: List[str]
    year: int
    supervisor: Optional[str] = None

    @validator('title')
    def validate_title(cls, v):
        if len(v) < 10:
            raise ValueError('Название работы должно содержать минимум 10 символов')
        return v

class WorkResponse(BaseModel):
    id: int
    title: str
    description: str
    category: str
    keywords: List[str]
    year: int
    supervisor: Optional[str]
    ai_generated_image: Optional[str]
    file_path: Optional[str]
    views_count: int
    likes_count: int
    created_at: dt
    updated_at: dt
    author: dict

class WorkSearch(BaseModel):
    query: Optional[str] = None
    category: Optional[str] = None
    faculty: Optional[str] = None
    year: Optional[int] = None
    degree_level: Optional[str] = None


class WorkSubmissionCreate(BaseModel):
    title: str
    description: str
    category: str
    keywords: List[str]
    year: int
    supervisor: Optional[str] = None

    @validator('title')
    def validate_title(cls, v):
        if len(v) < 10:
            raise ValueError('Название работы должно содержать минимум 10 символов')
        return v

class WorkSubmissionResponse(BaseModel):
    id: int
    title: str
    description: str
    category: str
    keywords: List[str]
    year: int
    supervisor: Optional[str]
    status: str
    file_path: Optional[str]
    moderator_comment: Optional[str]
    submitted_at: dt
    reviewed_at: Optional[dt]
    author: dict

class ModerationAction(BaseModel):
    action: str  # approve, reject, return_for_revision
    comment: Optional[str] = None
    moderator_id: int

class ModeratorProfile(BaseModel):
    id: int
    student_info: dict
    permissions: List[str]
    appointed_at: dt
    is_active: bool
    stats: dict

# Утилиты
def generate_ai_prompt_from_work(title: str, description: str, keywords: List[str]) -> str:
    """Генерация промпта для ИИ на основе работы"""
    keywords_str = ", ".join(keywords[:5])  # Берем первые 5 ключевых слов

    prompt = f"""
    Создай академическое изображение для научной работы:
    Название: {title[:100]}
    Описание: {description[:200]}
    Ключевые слова: {keywords_str}
    
    Стиль: современный, профессиональный, академический
    Цвета: сдержанные, научные
    Элементы: абстрактные символы, связанные с темой исследования
    """
    return prompt.strip()

def simulate_ai_image_generation(prompt: str) -> str:
    """Симуляция генерации изображения ИИ (заглушка)"""
    # В реальном проекте здесь будет интеграция с DALL-E, Midjourney или Stable Diffusion
    hash_object = hashlib.md5(prompt.encode())
    image_hash = hash_object.hexdigest()
    return f"/static/ai_images/{image_hash}.jpg"

def hash_password(password: str) -> str:
    """Хеширование пароля"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

# === ЭНДПОИНТЫ АУТЕНТИФИКАЦИИ ===

@router.post("/auth/register")
async def register_student(student: StudentRegister, db: asyncpg.Connection = Depends(get_db_connection)):
    """Регистрация нового студента"""
    try:

        hashed_password = pwd_context.hash(student.password)
        # Проверяем уникальность email и student_id
        check_query = """
            SELECT id FROM students 
            WHERE email = $1 OR student_id = $2
        """
        existing = await db.fetchrow(check_query, student.email, student.student_id)

        if existing:
            raise HTTPException(status_code=400, detail="Студент уже зарегистрирован")

        # Создаем нового студента
        insert_query = """
            INSERT INTO students (name, email, password_hash, student_id, faculty, degree_level, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            RETURNING id, name, email, student_id, faculty, degree_level, created_at
        """
        row = await db.fetchrow(insert_query,
                               student.name, student.email, hashed_password, student.student_id,
                               student.faculty, student.degree_level)

        return {
            "message": "Регистрация успешна",
            "student": {
                "id": row["id"],
                "name": row["name"],
                "email": row["email"],
                "student_id": row["student_id"],
                "faculty": row["faculty"],
                "degree_level": row["degree_level"],
                "created_at": row["created_at"]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка регистрации: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при регистрации")

@router.post("/auth/login")
async def login_student(credentials: StudentLogin, db: asyncpg.Connection = Depends(get_db_connection)):
    """Вход в систему"""
    try:
        # В реальном проекте здесь должна быть проверка пароля
        query = """
            SELECT s.*, COUNT(w.id) as works_count
            FROM students s
            LEFT JOIN works w ON s.id = w.author_id
            WHERE s.email = $1
            GROUP BY s.id
        """
        row = await db.fetchrow(query, credentials.email)

        if not row:
            raise HTTPException(status_code=401, detail="Неверные учетные данные")

        if not pwd_context.verify(credentials.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Неверные учетные данные")

        return {
            "message": "Вход выполнен успешно",
            "student": {
                "id": row["id"],
                "name": row["name"],
                "email": row["email"],
                "student_id": row["student_id"],
                "faculty": row["faculty"],
                "degree_level": row["degree_level"],
                "works_count": row["works_count"]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка входа: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при входе")

# === ЭНДПОИНТЫ ПРОФИЛЯ ===

@router.get("/profile/{student_id}")
async def get_student_profile(student_id: int, db: asyncpg.Connection = Depends(get_db_connection)):
    """Получение профиля студента"""
    try:
        query = """
            SELECT s.*, COUNT(w.id) as works_count
            FROM students s
            LEFT JOIN works w ON s.id = w.author_id
            WHERE s.id = $1
            GROUP BY s.id
        """
        row = await db.fetchrow(query, student_id)

        if not row:
            raise HTTPException(status_code=404, detail="Студент не найден")

        return {
            "id": row["id"],
            "name": row["name"],
            "email": row["email"],
            "student_id": row["student_id"],
            "faculty": row["faculty"],
            "degree_level": row["degree_level"],
            "avatar_url": row.get("avatar_url"),
            "created_at": row["created_at"],
            "works_count": row["works_count"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения профиля: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении профиля")


@router.put("/profile/{student_id}")
async def update_student_profile(
        student_id: int,
        name: str = Form(...),
        faculty: str = Form(...),
        degree_level: str = Form(...),
        phone: str = Form(None),
        birth_date: str = Form(None),
        current_password: str = Form(None),
        new_password: str = Form(None),
        avatar: UploadFile = File(None),
        db: asyncpg.Connection = Depends(get_db_connection)
):
    """Обновление профиля студента"""
    try:
        # Проверяем существование студента
        student = await db.fetchrow("SELECT * FROM students WHERE id = $1", student_id)
        if not student:
            raise HTTPException(status_code=404, detail="Студент не найден")

        # Подготавливаем данные для обновления (только поля, которые есть в БД)
        update_data = {
            "name": name.strip(),
            "faculty": faculty,
            "degree_level": degree_level,
        }

        # Обработка аватара
        if avatar and avatar.filename:
            # Проверяем тип файла
            if not avatar.content_type.startswith('image/'):
                raise HTTPException(status_code=400, detail="Можно загружать только изображения")

            # Проверяем размер файла (5MB)
            content = await avatar.read()
            if len(content) > 5 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="Размер файла не должен превышать 5MB")

            # Создаем директорию для аватаров если не существует
            avatar_dir = Path("static/avatars")
            avatar_dir.mkdir(parents=True, exist_ok=True)

            # Генерируем уникальное имя файла
            file_extension = avatar.filename.split('.')[-1]
            filename = f"{student_id}_{int(time.time())}.{file_extension}"
            file_path = avatar_dir / filename

            # Сохраняем файл
            with open(file_path, 'wb') as f:
                f.write(content)

            avatar_url = f"/static/avatars/{filename}"
            update_data["avatar_url"] = avatar_url

        # Обработка смены пароля
        if new_password:
            if not current_password:
                raise HTTPException(status_code=400, detail="Необходимо указать текущий пароль")

            # Проверяем текущий пароль
            if not verify_password(current_password, student["password_hash"]):
                raise HTTPException(status_code=400, detail="Неверный текущий пароль")

            # Валидация нового пароля
            if len(new_password) < 8:
                raise HTTPException(status_code=400, detail="Новый пароль должен содержать минимум 8 символов")

            # Хешируем новый пароль
            update_data["password_hash"] = hash_password(new_password)

        # Валидация данных
        if len(update_data["name"]) < 2:
            raise HTTPException(status_code=400, detail="Имя должно содержать минимум 2 символа")

        # Формируем SQL запрос для обновления
        set_clauses = []
        values = []
        param_counter = 1

        for key, value in update_data.items():
            if value is not None:
                set_clauses.append(f"{key} = ${param_counter}")
                values.append(value)
                param_counter += 1

        if not set_clauses:
            raise HTTPException(status_code=400, detail="Нет данных для обновления")

        # Добавляем updated_at
        set_clauses.append(f"updated_at = ${param_counter}")
        values.append(dt.now())
        param_counter += 1

        # ID студента для WHERE
        values.append(student_id)

        query = f"""
            UPDATE students 
            SET {', '.join(set_clauses)}
            WHERE id = ${param_counter}
            RETURNING id, name, email, student_id, faculty, degree_level, 
                     avatar_url, created_at, updated_at
        """

        updated_student = await db.fetchrow(query, *values)

        if not updated_student:
            raise HTTPException(status_code=500, detail="Ошибка при обновлении профиля")

        # Возвращаем обновленные данные (только поля из БД)
        return {
            "message": "Профиль успешно обновлен",
            "user": {
                "id": updated_student["id"],
                "name": updated_student["name"],
                "email": updated_student["email"],
                "student_id": updated_student["student_id"],
                "faculty": updated_student["faculty"],
                "degree_level": updated_student["degree_level"],
                "avatar_url": updated_student["avatar_url"],
                "created_at": updated_student["created_at"].isoformat(),
                "updated_at": updated_student["updated_at"].isoformat(),
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обновления профиля: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при обновлении профиля")


@router.get("/works")
async def get_all_works(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    category: Optional[str] = Query(None),
    faculty: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    """Получение всех работ с фильтрацией и пагинацией"""
    try:
        offset = (page - 1) * limit

        # Базовый запрос
        base_query = """
            FROM works w
            JOIN students s ON w.author_id = s.id
            WHERE 1=1
        """

        params = []
        param_count = 0

        # Фильтры
        if category:
            param_count += 1
            base_query += f" AND w.category = ${param_count}"
            params.append(category)

        if faculty:
            param_count += 1
            base_query += f" AND s.faculty = ${param_count}"
            params.append(faculty)

        if search:
            param_count += 1
            base_query += f" AND (w.title ILIKE ${param_count} OR w.description ILIKE ${param_count})"
            params.append(f"%{search}%")

        # Получаем общее количество
        count_query = f"SELECT COUNT(*) {base_query}"
        total_count = await db.fetchval(count_query, *params)

        # Получаем работы
        works_query = f"""
            SELECT w.*, s.name as author_name, s.faculty, s.degree_level
            {base_query}
            ORDER BY w.created_at DESC
            LIMIT ${param_count + 1} OFFSET ${param_count + 2}
        """
        params.extend([limit, offset])

        rows = await db.fetch(works_query, *params)

        works = []
        for row in rows:
            works.append({
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "category": row["category"],
                "keywords": row["keywords"],
                "year": row["year"],
                "supervisor": row["supervisor"],
                "ai_generated_image": row["ai_generated_image"],
                "views_count": row["views_count"],
                "likes_count": row["likes_count"],
                "created_at": row["created_at"],
                "author": {
                    "name": row["author_name"],
                    "faculty": row["faculty"],
                    "degree_level": row["degree_level"]
                }
            })

        return {
            "works": works,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "pages": (total_count + limit - 1) // limit
            }
        }

    except Exception as e:
        logger.error(f"Ошибка получения работ: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении работ")

@router.get("/works/{work_id}")
async def get_work_detail(work_id: int, db: asyncpg.Connection = Depends(get_db_connection)):
    """Получение детальной информации о работе"""
    try:
        # Увеличиваем счетчик просмотров
        await db.execute("UPDATE works SET views_count = views_count + 1 WHERE id = $1", work_id)

        # Получаем работу
        query = """
            SELECT w.*, s.name as author_name, s.faculty, s.degree_level, s.email
            FROM works w
            JOIN students s ON w.author_id = s.id
            WHERE w.id = $1
        """
        row = await db.fetchrow(query, work_id)

        if not row:
            raise HTTPException(status_code=404, detail="Работа не найдена")

        return {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "category": row["category"],
            "keywords": row["keywords"],
            "year": row["year"],
            "supervisor": row["supervisor"],
            "ai_generated_image": row["ai_generated_image"],
            "file_path": row["file_path"],
            "views_count": row["views_count"],
            "likes_count": row["likes_count"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "author": {
                "name": row["author_name"],
                "faculty": row["faculty"],
                "degree_level": row["degree_level"],
                "email": row["email"]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения работы: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении работы")

@router.post("/works/{work_id}/like")
async def toggle_like_work(work_id: int, student_id: int = Form(...), db: asyncpg.Connection = Depends(get_db_connection)):
    """Поставить/убрать лайк работе"""
    try:
        # Проверяем, есть ли уже лайк
        check_query = "SELECT id FROM work_likes WHERE work_id = $1 AND student_id = $2"
        existing_like = await db.fetchrow(check_query, work_id, student_id)

        if existing_like:
            # Убираем лайк
            await db.execute("DELETE FROM work_likes WHERE work_id = $1 AND student_id = $2", work_id, student_id)
            await db.execute("UPDATE works SET likes_count = likes_count - 1 WHERE id = $1", work_id)
            action = "removed"
        else:
            # Добавляем лайк
            await db.execute("INSERT INTO work_likes (work_id, student_id, created_at) VALUES ($1, $2, NOW())", work_id, student_id)
            await db.execute("UPDATE works SET likes_count = likes_count + 1 WHERE id = $1", work_id)
            action = "added"

        # Получаем обновленное количество лайков
        likes_count = await db.fetchval("SELECT likes_count FROM works WHERE id = $1", work_id)

        return {
            "message": f"Лайк {action}",
            "likes_count": likes_count,
            "action": action
        }

    except Exception as e:
        logger.error(f"Ошибка лайка: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при обработке лайка")

# === СТАТИСТИКА И ПОИСК ===

@router.get("/stats/dashboard")
async def get_dashboard_stats(db: asyncpg.Connection = Depends(get_db_connection)):
    """Получение статистики для дашборда"""
    try:
        stats = {}

        # Общее количество студентов
        stats["total_students"] = await db.fetchval("SELECT COUNT(*) FROM students")

        # Общее количество работ
        stats["total_works"] = await db.fetchval("SELECT COUNT(*) FROM works")

        # Общее количество модераторов
        stats["total_moderators"] = await db.fetchval("SELECT COUNT(*) FROM moderators")

        # Работы по категориям
        categories_query = """
            SELECT category, COUNT(*) as count 
            FROM works 
            GROUP BY category 
            ORDER BY count DESC
        """
        categories = await db.fetch(categories_query)
        stats["works_by_category"] = [{"category": row["category"], "count": row["count"]} for row in categories]

        # Работы по факультетам
        faculties_query = """
            SELECT s.faculty, COUNT(w.id) as count
            FROM students s
            LEFT JOIN works w ON s.id = w.author_id
            WHERE w.id IS NOT NULL
            GROUP BY s.faculty
            ORDER BY count DESC
        """
        faculties = await db.fetch(faculties_query)
        stats["works_by_faculty"] = [{"faculty": row["faculty"], "count": row["count"]} for row in faculties]

        # Самые популярные работы
        popular_query = """
            SELECT w.title, w.views_count, w.likes_count, s.name as author
            FROM works w
            JOIN students s ON w.author_id = s.id
            ORDER BY (w.views_count + w.likes_count * 5) DESC
            LIMIT 5
        """
        popular = await db.fetch(popular_query)
        stats["popular_works"] = [
            {
                "title": row["title"],
                "author": row["author"],
                "views": row["views_count"],
                "likes": row["likes_count"]
            } for row in popular
        ]

        return stats

    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении статистики")

@router.get("/search")
async def search_works(
    q: str = Query(..., min_length=2),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    """Поиск работ по ключевым словам"""
    try:
        offset = (page - 1) * limit

        search_query = """
            SELECT w.*, s.name as author_name, s.faculty, s.degree_level,
                   ts_rank(to_tsvector('russian', w.title || ' ' || w.description), plainto_tsquery('russian', $1)) as rank
            FROM works w
            JOIN students s ON w.author_id = s.id
            WHERE to_tsvector('russian', w.title || ' ' || w.description) @@ plainto_tsquery('russian', $1)
               OR w.title ILIKE $2
               OR w.description ILIKE $2
               OR EXISTS (
                   SELECT 1 FROM unnest(w.keywords) as keyword 
                   WHERE keyword ILIKE $2
               )
            ORDER BY rank DESC, w.created_at DESC
            LIMIT $3 OFFSET $4
        """

        search_param = f"%{q}%"
        rows = await db.fetch(search_query, q, search_param, limit, offset)

        works = []
        for row in rows:
            works.append({
                "id": row["id"],
                "title": row["title"],
                "description": row["description"][:200] + "..." if len(row["description"]) > 200 else row["description"],
                "category": row["category"],
                "keywords": row["keywords"],
                "year": row["year"],
                "ai_generated_image": row["ai_generated_image"],
                "views_count": row["views_count"],
                "likes_count": row["likes_count"],
                "author": {
                    "name": row["author_name"],
                    "faculty": row["faculty"],
                    "degree_level": row["degree_level"]
                }
            })

        return {
            "query": q,
            "results": works,
            "count": len(works)
        }

    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при поиске")


# === ЭНДПОИНТЫ ЗАЯВОК НА ПУБЛИКАЦИЮ ===

@router.post("/submissions")
async def submit_work(
        title: str = Form(...),
        description: str = Form(...),
        category: str = Form(...),
        keywords: str = Form(...),
        year: int = Form(...),
        supervisor: str = Form(None),
        author_id: int = Form(...),
        file: UploadFile = File(None),
        db: asyncpg.Connection = Depends(get_db_connection)
):
    """Подача заявки на публикацию работы"""
    try:
        keywords_list = [kw.strip() for kw in keywords.split(',') if kw.strip()]

        # Сохраняем файл если предоставлен
        file_path = None
        if file:
            upload_dir = Path("uploads/submissions")
            upload_dir.mkdir(parents=True, exist_ok=True)

            file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'pdf'
            file_name = f"submission_{dt.now().strftime('%Y%m%d_%H%M%S')}_{author_id}.{file_extension}"
            file_path = upload_dir / file_name

            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            file_path = str(file_path)

        # Создаем заявку
        insert_query = """
            INSERT INTO work_submissions (
                title, description, category, keywords, year, supervisor, 
                author_id, file_path, submitted_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
            RETURNING id, title, status, submitted_at
        """

        row = await db.fetchrow(insert_query,
                                title, description, category, keywords_list, year,
                                supervisor, author_id, file_path)

        return {
            "message": "Заявка на публикацию подана успешно",
            "submission": {
                "id": row["id"],
                "title": row["title"],
                "status": row["status"],
                "submitted_at": row["submitted_at"]
            }
        }

    except Exception as e:
        logger.error(f"Ошибка подачи заявки: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при подаче заявки")


@router.get("/submissions/my/{author_id}")
async def get_my_submissions(
        author_id: int,
        page: int = Query(1, ge=1),
        limit: int = Query(10, ge=1, le=50),
        db: asyncpg.Connection = Depends(get_db_connection)
):
    """Получение заявок пользователя"""
    try:
        offset = (page - 1) * limit

        query = """
            SELECT ws.*, s.name as author_name
            FROM work_submissions ws
            JOIN students s ON ws.author_id = s.id
            WHERE ws.author_id = $1
            ORDER BY ws.submitted_at DESC
            LIMIT $2 OFFSET $3
        """

        rows = await db.fetch(query, author_id, limit, offset)

        submissions = []
        for row in rows:
            submissions.append({
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "category": row["category"],
                "status": row["status"],
                "moderator_comment": row["moderator_comment"],
                "submitted_at": row["submitted_at"],
                "reviewed_at": row["reviewed_at"]
            })

        return {"submissions": submissions}

    except Exception as e:
        logger.error(f"Ошибка получения заявок: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении заявок")


# === ЭНДПОИНТЫ МОДЕРАЦИИ ===

@router.get("/moderation/submissions")
async def get_pending_submissions(
        page: int = Query(1, ge=1),
        limit: int = Query(10, ge=1, le=50),
        status: str = Query("pending"),
        moderator_id: int = Query(...),
        db: asyncpg.Connection = Depends(get_db_connection)
):
    """Получение заявок для модерации"""
    try:
        # Проверяем права модератора
        mod_check = await db.fetchrow(
            "SELECT id FROM moderators WHERE student_id = $1 AND is_active = TRUE",
            moderator_id
        )
        if not mod_check:
            raise HTTPException(status_code=403, detail="Нет прав модератора")

        offset = (page - 1) * limit

        query = """
            SELECT ws.*, s.name as author_name, s.faculty, s.degree_level, s.email
            FROM work_submissions ws
            JOIN students s ON ws.author_id = s.id
            WHERE ws.status = $1
            ORDER BY ws.submitted_at ASC
            LIMIT $2 OFFSET $3
        """

        rows = await db.fetch(query, status, limit, offset)

        submissions = []
        for row in rows:
            submissions.append({
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "category": row["category"],
                "keywords": row["keywords"],
                "year": row["year"],
                "supervisor": row["supervisor"],
                "file_path": row["file_path"],
                "status": row["status"],
                "submitted_at": row["submitted_at"],
                "author": {
                    "name": row["author_name"],
                    "faculty": row["faculty"],
                    "degree_level": row["degree_level"],
                    "email": row["email"]
                }
            })

        return {"submissions": submissions}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения заявок для модерации: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении заявок")


@router.post("/moderation/submissions/{submission_id}/action")
async def moderate_submission(
        submission_id: int,
        action_data: ModerationAction,  # Принимаем весь объект как JSON
        db: asyncpg.Connection = Depends(get_db_connection)
):
    """Модерация заявки (одобрение/отклонение)"""
    try:
        # Проверяем права модератора
        moderator = await db.fetchrow(
            "SELECT id FROM moderators WHERE student_id = $1 AND is_active = TRUE",
            action_data.moderator_id
        )
        if not moderator:
            raise HTTPException(status_code=403, detail="Нет прав модератора")

        # Получаем заявку
        submission = await db.fetchrow(
            "SELECT * FROM work_submissions WHERE id = $1 AND status = 'pending'",
            submission_id
        )
        if not submission:
            raise HTTPException(status_code=404, detail="Заявка не найдена или уже обработана")

        approved_work_id = None

        if action_data.action == "approve":
            # Создаем работу в основной таблице
            ai_prompt = generate_ai_prompt_from_work(
                submission["title"],
                submission["description"],
                submission["keywords"]
            )
            ai_image_url = simulate_ai_image_generation(ai_prompt)

            # Перемещаем файл в папку для одобренных работ
            new_file_path = None
            if submission["file_path"]:
                old_path = Path(submission["file_path"])
                if old_path.exists():
                    new_dir = Path("uploads/works")
                    new_dir.mkdir(parents=True, exist_ok=True)
                    new_file_path = new_dir / old_path.name
                    old_path.rename(new_file_path)
                    new_file_path = str(new_file_path)

            work_insert = """
                INSERT INTO works (
                    title, description, category, keywords, year, supervisor, 
                    author_id, ai_generated_image, file_path, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())
                RETURNING id
            """

            approved_work_id = await db.fetchval(work_insert,
                                                 submission["title"], submission["description"], submission["category"],
                                                 submission["keywords"], submission["year"], submission["supervisor"],
                                                 submission["author_id"], ai_image_url, new_file_path
                                                 )

        # Обновляем статус заявки
        update_query = """
            UPDATE work_submissions 
            SET status = $1, moderator_id = $2, moderator_comment = $3, 
                reviewed_at = NOW(), approved_work_id = $4
            WHERE id = $5
        """
        await db.execute(update_query, action_data.action, moderator["id"],
                         action_data.comment, approved_work_id, submission_id)

        # Записываем в лог модерации
        log_query = """
            INSERT INTO moderation_logs (moderator_id, submission_id, action, comment, created_at)
            VALUES ($1, $2, $3, $4, NOW())
        """
        await db.execute(log_query, moderator["id"], submission_id, action_data.action, action_data.comment)

        return {
            "message": f"Заявка {'одобрена' if action_data.action == 'approve' else 'отклонена'}",
            "submission_id": submission_id,
            "action": action_data.action,
            "work_id": approved_work_id if approved_work_id else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка модерации: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при модерации заявки")


@router.get("/moderation/check/{student_id}")
async def check_moderator_access(student_id: int):
    # Проверяем, есть ли запись в таблице moderators для данного студента
    query = """
    SELECT m.id, m.is_active, s.name
    FROM moderators m
    JOIN students s ON m.student_id = s.id
    WHERE m.student_id = $1 AND m.is_active = true
    """

    moderator = await fetchrow_query(query, student_id)

    if moderator:
        return {
            "is_moderator": True,
            "is_active": True,
            "moderator_id": moderator['id'],
            "name": moderator['name']
        }
    else:
        return {
            "is_moderator": False,
            "is_active": False
        }

# === УПРАВЛЕНИЕ МОДЕРАТОРАМИ ===

@router.post("/admin/moderators")
async def appoint_moderator(
        student_id: int = Form(...),
        appointed_by: int = Form(...),  # ID студента, который назначает
        db: asyncpg.Connection = Depends(get_db_connection)
):
    """Назначение модератора (только для супер-администраторов)"""
    try:
        # Проверяем, что назначающий является модератором
        appointer = await db.fetchrow(
            "SELECT id FROM moderators WHERE student_id = $1 AND is_active = TRUE",
            appointed_by
        )
        if not appointer:
            raise HTTPException(status_code=403, detail="Нет прав для назначения модераторов")

        # Проверяем, что студент существует
        student = await db.fetchrow("SELECT id, name FROM students WHERE id = $1", student_id)
        if not student:
            raise HTTPException(status_code=404, detail="Студент не найден")

        # Проверяем, что он еще не модератор
        existing = await db.fetchrow("SELECT id FROM moderators WHERE student_id = $1", student_id)
        if existing:
            raise HTTPException(status_code=400, detail="Студент уже является модератором")

        # Назначаем модератора
        insert_query = """
            INSERT INTO moderators (student_id, appointed_by, appointed_at, is_active)
            VALUES ($1, $2, NOW(), TRUE)
            RETURNING id
        """
        mod_id = await db.fetchval(insert_query, student_id, appointer["id"])

        return {
            "message": "Модератор назначен успешно",
            "moderator_id": mod_id,
            "student_name": student["name"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка назначения модератора: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при назначении модератора")


@router.get("/admin/moderators")
async def get_moderators(db: asyncpg.Connection = Depends(get_db_connection)):
    """Получение списка всех модераторов"""
    try:
        query = """
            SELECT 
                m.id,
                m.student_id,
                s.name,
                s.faculty,
                s.degree_level,
                m.appointed_at,
                m.is_active,
                appointer.name as appointed_by_name
            FROM moderators m
            JOIN students s ON m.student_id = s.id
            LEFT JOIN moderators appointer_mod ON m.appointed_by = appointer_mod.id
            LEFT JOIN students appointer ON appointer_mod.student_id = appointer.id
            ORDER BY m.appointed_at DESC
        """

        moderators = await db.fetch(query)

        # Преобразуем результат в список словарей
        moderators_list = []
        for mod in moderators:
            moderators_list.append({
                "id": mod["id"],
                "student_id": mod["student_id"],
                "name": mod["name"],
                "faculty": mod["faculty"],
                "degree_level": mod["degree_level"],
                "appointed_at": mod["appointed_at"].isoformat() if mod["appointed_at"] else None,
                "is_active": mod["is_active"],
                "appointed_by_name": mod["appointed_by_name"]
            })

        return {"moderators": moderators_list}

    except Exception as e:
        logger.error(f"Ошибка получения списка модераторов: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении списка модераторов")

@router.get("/moderators")
async def get_all_moderators(
        db: asyncpg.Connection = Depends(get_db_connection),
):
    """Получение списка всех модераторов"""
    try:
        # Базовый запрос
        query = """
            SELECT m.id, m.student_id, m.is_active, m.appointed_at, 
                   s.name, s.faculty, s.degree_level
            FROM moderators m
            JOIN students s ON m.student_id = s.id
        """

        rows = await db.fetch(query)

        moderators = []
        for row in rows:
            moderators.append({
                "id": row["id"],
                "student_id": row["student_id"],
                "name": row["name"],
                "faculty": row["faculty"],
                "degree_level": row["degree_level"],
                "is_active": row["is_active"],
                "appointed_at": row["appointed_at"]
            })

        return {"moderators": moderators}

    except Exception as e:
        logger.error(f"Ошибка получения списка модераторов: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении списка модераторов")

@router.get("/moderation/stats/{moderator_id}")
async def get_moderation_stats(moderator_id: int, db: asyncpg.Connection = Depends(get_db_connection)):
    """Статистика модерации"""
    try:
        # Проверяем права модератора
        moderator = await db.fetchrow(
            "SELECT id FROM moderators WHERE student_id = $1 AND is_active = TRUE",
            moderator_id
        )
        if not moderator:
            raise HTTPException(status_code=403, detail="Нет прав модератора")

        stats = {}

        # Общая статистика заявок
        stats["total_pending"] = await db.fetchval(
            "SELECT COUNT(*) FROM work_submissions WHERE status = 'pending'"
        )
        stats["total_approved"] = await db.fetchval(
            "SELECT COUNT(*) FROM work_submissions WHERE status = 'approve'"
        )
        stats["total_rejected"] = await db.fetchval(
            "SELECT COUNT(*) FROM work_submissions WHERE status = 'reject'"
        )

        # Статистика модератора
        moderator_stats = await db.fetchrow("""
            SELECT 
                COUNT(CASE WHEN ml.action = 'approve' THEN 1 END) as approved_by_me,
                COUNT(CASE WHEN ml.action = 'reject' THEN 1 END) as rejected_by_me,
                COUNT(*) as total_reviewed
            FROM moderation_logs ml
            WHERE ml.moderator_id = $1
        """, moderator["id"])

        stats["my_approved"] = moderator_stats["approved_by_me"] or 0
        stats["my_rejected"] = moderator_stats["rejected_by_me"] or 0
        stats["my_total"] = moderator_stats["total_reviewed"] or 0

        return stats

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении статистики")

# === ФАЙЛЫ ===

@router.get("/files/download/{work_id}")
async def download_work_file(work_id: int, db: asyncpg.Connection = Depends(get_db_connection)):
    """Скачивание файла работы"""
    try:
        query = "SELECT file_path, title FROM works WHERE id = $1"
        row = await db.fetchrow(query, work_id)

        if not row or not row["file_path"]:
            raise HTTPException(status_code=404, detail="Файл не найден")

        file_path = Path(row["file_path"])
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Файл не существует")

        return FileResponse(
            path=str(file_path),
            filename=f"{row['title']}.pdf",
            media_type='application/pdf'
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка скачивания файла: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при скачивании файла")

# === ЗДОРОВЬЕ СИСТЕМЫ ===

@router.get("/health")
async def health_check(db: asyncpg.Connection = Depends(get_db_connection)):
    """Проверка состояния API и базы данных"""
    try:
        # Проверяем подключение к БД
        await db.fetchval("SELECT 1")

        # Проверяем основные таблицы
        tables_check = await db.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('students', 'works', 'work_likes')
        """)

        return {
            "status": "healthy",
            "database": "connected",
            "tables": len(tables_check),
            "timestamp": dt .now()
        }
    except Exception as e:
        logger.error(f"Ошибка при проверке здоровья: {e}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": dt.now()
        }