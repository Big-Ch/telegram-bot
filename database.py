import aiosqlite
import json
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
        
        # Таблица для хранения состояния сценария целеполагания
        await db.execute("""
            CREATE TABLE IF NOT EXISTS goal_scenarios (
                user_id INTEGER PRIMARY KEY,
                stage TEXT NOT NULL,
                all_goals TEXT,
                selected_goals TEXT,
                current_goal_index INTEGER DEFAULT 0,
                conversation_history TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
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


# Функции для работы со сценарием целеполагания
async def save_scenario_state(user_id: int, state_data: Dict):
    """Сохранение состояния сценария целеполагания"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO goal_scenarios 
            (user_id, stage, all_goals, selected_goals, current_goal_index, conversation_history, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                stage = excluded.stage,
                all_goals = excluded.all_goals,
                selected_goals = excluded.selected_goals,
                current_goal_index = excluded.current_goal_index,
                conversation_history = excluded.conversation_history,
                updated_at = excluded.updated_at
        """, (
            user_id,
            state_data.get("stage"),
            json.dumps(state_data.get("all_goals", []), ensure_ascii=False),
            json.dumps(state_data.get("selected_goals", []), ensure_ascii=False),
            state_data.get("current_goal_index", 0),
            json.dumps(state_data.get("conversation_history", []), ensure_ascii=False),
            datetime.now()
        ))
        await db.commit()


async def get_scenario_state(user_id: int) -> Optional[Dict]:
    """Получение состояния сценария целеполагания"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM goal_scenarios WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                state = dict(row)
                # Десериализация JSON полей
                state["all_goals"] = json.loads(state["all_goals"] or "[]")
                state["selected_goals"] = json.loads(state["selected_goals"] or "[]")
                state["conversation_history"] = json.loads(state["conversation_history"] or "[]")
                return state
            return None


async def delete_scenario_state(user_id: int):
    """Удаление состояния сценария целеполагания"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM goal_scenarios WHERE user_id = ?", (user_id,))
        await db.commit()

