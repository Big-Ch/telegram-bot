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
import goal_scenario
from goal_scenario import ScenarioStage, ScenarioState, Goal
from typing import Optional

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


# Состояния для сценария целеполагания
class GoalScenario(StatesGroup):
    collecting_goals = State()
    selecting_goals = State()
    defining_success_criteria = State()
    finalization = State()


# Клавиатура главного меню
def get_main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Мой профиль"), KeyboardButton(text="✏️ Редактировать профиль")],
            [KeyboardButton(text="🎯 Целеполагание на 12 недель")],
            [KeyboardButton(text="ℹ️ Информация"), KeyboardButton(text="❓ Помощь")],
            [KeyboardButton(text="📊 Статистика бота")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите пункт меню..."
    )
    return keyboard


# Инициализация сценария целеполагания (ленивая загрузка)
_scenario_manager: Optional[goal_scenario.GoalSettingScenario] = None

def get_scenario_manager() -> goal_scenario.GoalSettingScenario:
    """Получить экземпляр менеджера сценария (ленивая инициализация)"""
    global _scenario_manager
    if _scenario_manager is None:
        try:
            _scenario_manager = goal_scenario.GoalSettingScenario()
        except Exception as e:
            logger.warning(f"Не удалось инициализировать LLM клиент: {e}. "
                          "Сценарий будет работать без LLM функций.")
            # Создаем менеджер, он сам обработает отсутствие LLM
            _scenario_manager = goal_scenario.GoalSettingScenario()
    return _scenario_manager


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
        "• 🎯 Целеполагание на 12 недель - цифровой ассистент для постановки и достижения целей\n"
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
        "🎯 <b>Целеполагание на 12 недель</b> - Начать сценарий постановки и планирования целей\n"
        "ℹ️ <b>Информация</b> - Информация о боте\n"
        "❓ <b>Помощь</b> - Это сообщение\n"
        "📊 <b>Статистика бота</b> - Общая статистика\n\n"
        "<b>О сценарии целеполагания:</b>\n"
        "Сценарий поможет тебе:\n"
        "• Сформулировать до 10 целей на 12 недель\n"
        "• Выбрать 3 самые важные\n"
        "• Определить критерии успеха\n"
        "• Получить инструкцию по планированию\n\n"
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


# ========== Обработчики сценария целеполагания ==========

async def load_scenario_state(user_id: int) -> Optional[ScenarioState]:
    """Загрузка состояния сценария из БД"""
    state_data = await database.get_scenario_state(user_id)
    if state_data:
        return ScenarioState.from_dict(state_data)
    return None


async def save_scenario_state_to_db(state: ScenarioState):
    """Сохранение состояния сценария в БД"""
    await database.save_scenario_state(state.user_id, state.to_dict())


# Запуск сценария целеполагания
@router.message(F.text == "🎯 Целеполагание на 12 недель")
async def start_goal_scenario(message: Message, state: FSMContext) -> None:
    """Начало сценария целеполагания"""
    user_id = message.from_user.id
    
    # Проверяем, есть ли незавершенный сценарий
    existing_state = await load_scenario_state(user_id)
    if existing_state and existing_state.stage != ScenarioStage.COMPLETED:
        await message.answer(
            "⚠️ У тебя есть незавершенный сценарий. Хочешь продолжить с того места, где остановился, "
            "или начать заново?\n\n"
            "Напиши <b>\"Продолжить\"</b> или <b>\"Начать заново\"</b>",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(GoalScenario.collecting_goals)
        await state.update_data(action="continue_or_restart")
        return
    
    # Начинаем новый сценарий
    scenario_state = ScenarioState(
        user_id=user_id,
        stage=ScenarioStage.COLLECTING_GOALS,
        all_goals=[],
        selected_goals=[],
        current_goal_index=0,
        conversation_history=[]
    )
    
    await save_scenario_state_to_db(scenario_state)
    await state.set_state(GoalScenario.collecting_goals)
    
    scenario_manager = get_scenario_manager()
    intro_message = scenario_manager.get_introduction_message()
    await message.answer(intro_message, reply_markup=ReplyKeyboardRemove())


# Обработка ввода целей
@router.message(GoalScenario.collecting_goals)
async def handle_goals_collection(message: Message, state: FSMContext) -> None:
    """Обработка этапа сбора целей"""
    user_id = message.from_user.id
    scenario_state = await load_scenario_state(user_id)
    
    if not scenario_state:
        await message.answer("❌ Произошла ошибка. Начни сценарий заново с помощью кнопки меню.")
        await state.clear()
        return
    
    # Проверка на продолжение или перезапуск
    state_data = await state.get_data()
    if state_data.get("action") == "continue_or_restart":
        user_input_lower = message.text.lower().strip()
        if user_input_lower in ["продолжить", "продолжать"]:
            # Восстанавливаем состояние
            await message.answer(
                "✅ Продолжаем сценарий с того места, где остановились!",
                reply_markup=ReplyKeyboardRemove()
            )
            await state.update_data(action=None)
            # Продолжаем с текущего этапа
            await continue_scenario_from_stage(message, scenario_state, state)
            return
        elif user_input_lower in ["начать заново", "заново", "новый"]:
            # Удаляем старое состояние
            await database.delete_scenario_state(user_id)
            scenario_state = ScenarioState(
                user_id=user_id,
                stage=ScenarioStage.COLLECTING_GOALS,
                all_goals=[],
                selected_goals=[],
                current_goal_index=0,
                conversation_history=[]
            )
            await save_scenario_state_to_db(scenario_state)
            scenario_manager = get_scenario_manager()
            await message.answer(
                scenario_manager.get_introduction_message(),
                reply_markup=ReplyKeyboardRemove()
            )
            await state.update_data(action=None)
            return
    
    # Обработка ввода целей
    scenario_manager = get_scenario_manager()
    response_msg, updated_goals, finished = await scenario_manager.process_goals_input(
        message.text,
        scenario_state.all_goals
    )
    
    scenario_state.all_goals = updated_goals
    await save_scenario_state_to_db(scenario_state)
    
    await message.answer(response_msg)
    
    if finished:
        # Переход к выбору целей
        scenario_state.stage = ScenarioStage.SELECTING_GOALS
        await save_scenario_state_to_db(scenario_state)
        await state.set_state(GoalScenario.selecting_goals)
        scenario_manager = get_scenario_manager()
        selection_message = scenario_manager.get_goals_selection_message(scenario_state.all_goals)
        await message.answer(selection_message)


# Обработка выбора целей
@router.message(GoalScenario.selecting_goals)
async def handle_goals_selection(message: Message, state: FSMContext) -> None:
    """Обработка этапа выбора целей"""
    user_id = message.from_user.id
    scenario_state = await load_scenario_state(user_id)
    
    if not scenario_state:
        await message.answer("❌ Произошла ошибка. Начни сценарий заново.")
        await state.clear()
        return
    
    scenario_manager = get_scenario_manager()
    response_msg, selected_goals_list, success = await scenario_manager.process_goals_selection(
        message.text,
        scenario_state.all_goals
    )
    
    await message.answer(response_msg)
    
    if success:
        # Сохраняем выбранные цели
        scenario_state.selected_goals = [Goal(text=goal) for goal in selected_goals_list]
        scenario_state.current_goal_index = 0
        scenario_state.stage = ScenarioStage.DEFINING_SUCCESS_CRITERIA
        await save_scenario_state_to_db(scenario_state)
        await state.set_state(GoalScenario.defining_success_criteria)
        
        # Запрашиваем критерий успеха для первой цели
        current_goal = scenario_state.selected_goals[0]
        scenario_manager = get_scenario_manager()
        criteria_prompt = await scenario_manager.get_success_criteria_prompt(
            current_goal.text,
            1,
            len(scenario_state.selected_goals)
        )
        await message.answer(criteria_prompt)


# Обработка определения критериев успеха
@router.message(GoalScenario.defining_success_criteria)
async def handle_success_criteria(message: Message, state: FSMContext) -> None:
    """Обработка этапа определения критериев успеха"""
    user_id = message.from_user.id
    scenario_state = await load_scenario_state(user_id)
    
    if not scenario_state:
        await message.answer("❌ Произошла ошибка. Начни сценарий заново.")
        await state.clear()
        return
    
    # Сохраняем критерий успеха для текущей цели
    current_goal = scenario_state.selected_goals[scenario_state.current_goal_index]
    current_goal.success_criteria = message.text
    scenario_state.selected_goals[scenario_state.current_goal_index] = current_goal
    
    scenario_state.current_goal_index += 1
    
    # Проверяем, все ли цели обработаны
    if scenario_state.current_goal_index < len(scenario_state.selected_goals):
        # Запрашиваем критерий для следующей цели
        next_goal = scenario_state.selected_goals[scenario_state.current_goal_index]
        await save_scenario_state_to_db(scenario_state)
        
        scenario_manager = get_scenario_manager()
        criteria_prompt = await scenario_manager.get_success_criteria_prompt(
            next_goal.text,
            scenario_state.current_goal_index + 1,
            len(scenario_state.selected_goals)
        )
        await message.answer(f"✅ Критерий успеха сохранен!\n\n{criteria_prompt}")
    else:
        # Все цели обработаны, переходим к инструкции по планированию
        scenario_state.stage = ScenarioStage.PLANNING_INSTRUCTION
        await save_scenario_state_to_db(scenario_state)
        
        scenario_manager = get_scenario_manager()
        planning_message = scenario_manager.get_planning_instruction_message()
        await message.answer(planning_message)
        
        # Переходим к финализации
        await asyncio.sleep(2)
        scenario_state.stage = ScenarioStage.FINALIZATION
        await save_scenario_state_to_db(scenario_state)
        await state.set_state(GoalScenario.finalization)
        
        final_message = scenario_manager.get_finalization_message(scenario_state.selected_goals)
        await message.answer(final_message)


# Обработка финализации
@router.message(GoalScenario.finalization)
async def handle_finalization(message: Message, state: FSMContext) -> None:
    """Обработка финального этапа"""
    user_id = message.from_user.id
    scenario_state = await load_scenario_state(user_id)
    
    if not scenario_state:
        await message.answer("❌ Произошла ошибка.")
        await state.clear()
        return
    
    user_input_lower = message.text.lower().strip()
    
    # Проверка на запрос декомпозиции целей
    if any(word in user_input_lower for word in ["декомпозир", "задания", "разбить", "план", "задачи"]):
        await message.answer(
            "🎯 Отличная идея! Декомпозиция целей поможет тебе создать конкретный план действий.\n\n"
            "В разработке: функция автоматической декомпозиции целей на задания. "
            "Пока ты можешь сделать это самостоятельно, следуя инструкции выше.\n\n"
            "Если нужна помощь, напиши мне!",
            reply_markup=get_main_menu()
        )
        scenario_state.stage = ScenarioStage.COMPLETED
        await save_scenario_state_to_db(scenario_state)
        await state.clear()
        return
    
    # Проверка на запрос консультации коуча
    if any(word in user_input_lower for word in ["коуч", "консультац", "помощь", "поддержка"]):
        await message.answer(
            "💼 Консультация коуча - это отличный следующий шаг!\n\n"
            "В разработке: функция подключения к профессиональным коучам. "
            "Следи за обновлениями!\n\n"
            "А пока используй инструкцию выше для самостоятельного планирования. "
            "Ты справишься! 💪",
            reply_markup=get_main_menu()
        )
        scenario_state.stage = ScenarioStage.COMPLETED
        await save_scenario_state_to_db(scenario_state)
        await state.clear()
        return
    
    # Другое сообщение
    await message.answer(
        "Если у тебя есть вопросы или нужна помощь, используй кнопки меню или напиши /help.",
        reply_markup=get_main_menu()
    )
    scenario_state.stage = ScenarioStage.COMPLETED
    await save_scenario_state_to_db(scenario_state)
    await state.clear()


async def continue_scenario_from_stage(message: Message, scenario_state: ScenarioState, state: FSMContext):
    """Продолжение сценария с текущего этапа"""
    if scenario_state.stage == ScenarioStage.COLLECTING_GOALS:
        await state.set_state(GoalScenario.collecting_goals)
        if scenario_state.all_goals:
            await message.answer(
                f"Ты уже ввел {len(scenario_state.all_goals)} {'целей' if len(scenario_state.all_goals) > 1 else 'цель'}. "
                "Продолжай вводить цели или напиши <b>\"Готово\"</b>.",
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            scenario_manager = get_scenario_manager()
            await message.answer(
                scenario_manager.get_introduction_message(),
                reply_markup=ReplyKeyboardRemove()
            )
    elif scenario_state.stage == ScenarioStage.SELECTING_GOALS:
        await state.set_state(GoalScenario.selecting_goals)
        scenario_manager = get_scenario_manager()
        await message.answer(
            scenario_manager.get_goals_selection_message(scenario_state.all_goals),
            reply_markup=ReplyKeyboardRemove()
        )
    elif scenario_state.stage == ScenarioStage.DEFINING_SUCCESS_CRITERIA:
        await state.set_state(GoalScenario.defining_success_criteria)
        current_goal = scenario_state.selected_goals[scenario_state.current_goal_index]
        scenario_manager = get_scenario_manager()
        criteria_prompt = await scenario_manager.get_success_criteria_prompt(
            current_goal.text,
            scenario_state.current_goal_index + 1,
            len(scenario_state.selected_goals)
        )
        await message.answer(criteria_prompt, reply_markup=ReplyKeyboardRemove())
    elif scenario_state.stage == ScenarioStage.PLANNING_INSTRUCTION:
        await state.set_state(GoalScenario.finalization)
        scenario_manager = get_scenario_manager()
        await message.answer(
            scenario_manager.get_finalization_message(scenario_state.selected_goals),
            reply_markup=ReplyKeyboardRemove()
        )
    elif scenario_state.stage == ScenarioStage.FINALIZATION:
        await state.set_state(GoalScenario.finalization)
        scenario_manager = get_scenario_manager()
        await message.answer(
            scenario_manager.get_finalization_message(scenario_state.selected_goals),
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        # Сценарий завершен или ошибка
        await message.answer(
            "Сценарий уже завершен. Хочешь начать новый? Нажми кнопку в меню.",
            reply_markup=get_main_menu()
        )
        await state.clear()


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

