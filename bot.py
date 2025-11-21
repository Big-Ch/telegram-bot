import asyncio
import logging
import sys
from os import getenv

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

import database

# Загрузка переменных окружения
load_dotenv()
TOKEN = getenv("BOT_TOKEN")

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())
router = Router()


# Состояния для сбора информации о пользователе
class UserRegistration(StatesGroup):
    waiting_for_name = State()
    waiting_for_age = State()
    waiting_for_city = State()
    waiting_for_interests = State()


# Клавиатура главного меню
def get_main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Мой профиль"), KeyboardButton(text="✏️ Редактировать профиль")],
            [KeyboardButton(text="ℹ️ Информация"), KeyboardButton(text="❓ Помощь")],
            [KeyboardButton(text="📊 Статистика бота")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите пункт меню..."
    )
    return keyboard


# Команда /start
@router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    
    # Проверяем, зарегистрирован ли пользователь
    user = await database.get_user(user_id)
    
    if user:
        # Пользователь уже зарегистрирован
        await message.answer(
            f"👋 С возвращением, <b>{user['name']}</b>!\n\n"
            f"Рад снова видеть тебя! Используй меню ниже для навигации.",
            reply_markup=get_main_menu()
        )
    else:
        # Новый пользователь - начинаем регистрацию
        await message.answer(
            f"👋 Привет, <b>{message.from_user.full_name}</b>!\n\n"
            f"🎉 Добро пожаловать в наш бот!\n\n"
            f"Я помогу тебе познакомиться с нашим сообществом. "
            f"Для начала давай соберем немного информации о тебе.\n\n"
            f"<b>Как тебя зовут?</b> (Введи свое имя)",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(UserRegistration.waiting_for_name)


# Обработчик имени
@router.message(UserRegistration.waiting_for_name)
async def process_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)
    await message.answer(
        f"Приятно познакомиться, <b>{message.text}</b>! 😊\n\n"
        f"<b>Сколько тебе лет?</b> (Введи число)"
    )
    await state.set_state(UserRegistration.waiting_for_age)


# Обработчик возраста
@router.message(UserRegistration.waiting_for_age)
async def process_age(message: Message, state: FSMContext) -> None:
    if not message.text.isdigit():
        await message.answer("❌ Пожалуйста, введи возраст числом (например, 25)")
        return
    
    age = int(message.text)
    if age < 5 or age > 120:
        await message.answer("❌ Пожалуйста, введи корректный возраст (от 5 до 120 лет)")
        return
    
    await state.update_data(age=age)
    await message.answer(
        f"Отлично! 👍\n\n"
        f"<b>Из какого ты города?</b> (Введи название города)"
    )
    await state.set_state(UserRegistration.waiting_for_city)


# Обработчик города
@router.message(UserRegistration.waiting_for_city)
async def process_city(message: Message, state: FSMContext) -> None:
    await state.update_data(city=message.text)
    await message.answer(
        f"Замечательно! 🌆\n\n"
        f"<b>Расскажи о своих интересах или хобби</b>\n"
        f"(Например: программирование, спорт, музыка)"
    )
    await state.set_state(UserRegistration.waiting_for_interests)


# Обработчик интересов и завершение регистрации
@router.message(UserRegistration.waiting_for_interests)
async def process_interests(message: Message, state: FSMContext) -> None:
    await state.update_data(interests=message.text)
    
    # Получаем все данные пользователя
    user_data = await state.get_data()
    user_id = message.from_user.id
    username = message.from_user.username or "Не указан"
    
    # Сохраняем пользователя в базу данных
    await database.add_user(
        user_id=user_id,
        username=username,
        name=user_data['name'],
        age=user_data['age'],
        city=user_data['city'],
        interests=user_data['interests']
    )
    
    # Завершаем регистрацию
    await message.answer(
        f"✅ <b>Регистрация завершена!</b>\n\n"
        f"📝 <b>Твой профиль:</b>\n"
        f"👤 Имя: {user_data['name']}\n"
        f"🎂 Возраст: {user_data['age']} лет\n"
        f"🌆 Город: {user_data['city']}\n"
        f"💫 Интересы: {user_data['interests']}\n\n"
        f"Теперь ты можешь пользоваться всеми функциями бота! 🚀",
        reply_markup=get_main_menu()
    )
    
    await state.clear()


# Обработчик кнопки "Мой профиль"
@router.message(F.text == "📋 Мой профиль")
async def show_profile(message: Message) -> None:
    user_id = message.from_user.id
    user = await database.get_user(user_id)
    
    if user:
        await message.answer(
            f"👤 <b>Твой профиль</b>\n\n"
            f"📛 Имя: {user['name']}\n"
            f"🎂 Возраст: {user['age']} лет\n"
            f"🌆 Город: {user['city']}\n"
            f"💫 Интересы: {user['interests']}\n"
            f"🆔 Telegram ID: {user['user_id']}\n"
            f"📅 Дата регистрации: {user['created_at']}"
        )
    else:
        await message.answer("❌ Профиль не найден. Используй /start для регистрации.")


# Обработчик кнопки "Редактировать профиль"
@router.message(F.text == "✏️ Редактировать профиль")
async def edit_profile(message: Message, state: FSMContext) -> None:
    await message.answer(
        "🔄 Начинаем обновление профиля!\n\n"
        "<b>Как тебя зовут?</b> (Введи новое имя)",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(UserRegistration.waiting_for_name)


# Обработчик кнопки "Информация"
@router.message(F.text == "ℹ️ Информация")
async def show_info(message: Message) -> None:
    await message.answer(
        "ℹ️ <b>О боте</b>\n\n"
        "Этот бот создан для управления сообществом и общения с участниками.\n\n"
        "<b>Возможности:</b>\n"
        "• Регистрация новых участников\n"
        "• Управление профилем\n"
        "• Просмотр статистики\n"
        "• Получение помощи\n\n"
        "💡 Используй меню для навигации по боту!"
    )


# Обработчик кнопки "Помощь"
@router.message(F.text == "❓ Помощь")
async def show_help(message: Message) -> None:
    await message.answer(
        "❓ <b>Помощь</b>\n\n"
        "<b>Доступные команды:</b>\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать это сообщение\n"
        "/menu - Показать главное меню\n\n"
        "<b>Кнопки меню:</b>\n"
        "📋 <b>Мой профиль</b> - Просмотр твоего профиля\n"
        "✏️ <b>Редактировать профиль</b> - Изменение данных профиля\n"
        "ℹ️ <b>Информация</b> - Информация о боте\n"
        "❓ <b>Помощь</b> - Это сообщение\n"
        "📊 <b>Статистика бота</b> - Общая статистика\n\n"
        "❔ Если у тебя есть вопросы, обратись к администратору."
    )


# Обработчик кнопки "Статистика бота"
@router.message(F.text == "📊 Статистика бота")
async def show_stats(message: Message) -> None:
    total_users = await database.get_total_users()
    await message.answer(
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"🤖 Версия бота: 1.0.0\n"
        f"⚡ Статус: Активен"
    )


# Команда /help
@router.message(Command("help"))
async def command_help(message: Message) -> None:
    await show_help(message)


# Команда /menu
@router.message(Command("menu"))
async def command_menu(message: Message) -> None:
    await message.answer(
        "📱 Главное меню открыто!",
        reply_markup=get_main_menu()
    )


async def main() -> None:
    # Инициализация базы данных
    await database.init_db()
    
    # Регистрация роутера
    dp.include_router(router)
    
    # Запуск бота
    logger.info("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен!")

