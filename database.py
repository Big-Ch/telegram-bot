import aiosqlite
from datetime import datetime
from typing import Optional, Dict


DB_NAME = "bot_database.db"


async def init_db():
    """Инициализация базы данных"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                city TEXT NOT NULL,
                interests TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def add_user(user_id: int, username: str, name: str, age: int, city: str, interests: str):
    """Добавление или обновление пользователя"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, name, age, city, interests, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                name = excluded.name,
                age = excluded.age,
                city = excluded.city,
                interests = excluded.interests,
                updated_at = excluded.updated_at
        """, (user_id, username, name, age, city, interests, datetime.now()))
        await db.commit()


async def get_user(user_id: int) -> Optional[Dict]:
    """Получение пользователя по ID"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None


async def get_total_users() -> int:
    """Получение общего количества пользователей"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def delete_user(user_id: int):
    """Удаление пользователя"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.commit()

