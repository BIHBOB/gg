import asyncio
import os
from datetime import datetime
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv
import logging
import aiofiles
import aiosqlite
import shutil

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загружаем переменные из .env
load_dotenv()

# Инициализация бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Токен бота не найден.")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
if not ADMIN_ID:
    raise ValueError("ID администратора не найден.")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-bot-name.onrender.com")
WEBHOOK_PATH = "/webhook"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Путь для временного хранения файлов и базы данных
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCUMENTS_DIR = os.path.join(BASE_DIR, "Documents")
DATABASE_FILE = os.path.join(BASE_DIR, "database.db")

if not os.path.exists(DOCUMENTS_DIR):
    os.makedirs(DOCUMENTS_DIR)

# Инициализация базы данных SQLite
async def init_db():
    async with aiosqlite.connect(DATABASE_FILE) as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                role TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                file_path TEXT NOT NULL,
                upload_date TEXT NOT NULL,
                role_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        await conn.commit()
    logger.info(f"База данных SQLite инициализирована в {DATABASE_FILE}")

async def save_user(user_id, full_name, phone, role):
    async with aiosqlite.connect(DATABASE_FILE) as conn:
        await conn.execute('''
            INSERT OR REPLACE INTO users (user_id, full_name, phone, role, status)
            VALUES (?, ?, ?, ?, 'pending')
        ''', (user_id, full_name, phone, role))
        await conn.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DATABASE_FILE) as conn:
        cursor = await conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = await cursor.fetchone()
        return user

async def update_user_status(user_id, status):
    async with aiosqlite.connect(DATABASE_FILE) as conn:
        await conn.execute('UPDATE users SET status = ? WHERE user_id = ?', (status, user_id))
        await conn.commit()

async def save_document(user_id, file_path, role_type):
    current_date = datetime.now().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DATABASE_FILE) as conn:
        await conn.execute('''
            INSERT INTO documents (user_id, file_path, upload_date, role_type, status)
            VALUES (?, ?, ?, ?, 'pending')
        ''', (user_id, file_path, current_date, role_type))
        await conn.commit()

async def get_pending_users():
    async with aiosqlite.connect(DATABASE_FILE) as conn:
        cursor = await conn.execute('SELECT user_id, full_name, role FROM users WHERE status = ?', ('pending',))
        users = await cursor.fetchall()
        return users

async def get_document_by_id(doc_id):
    async with aiosqlite.connect(DATABASE_FILE) as conn:
        cursor = await conn.execute('SELECT * FROM documents WHERE id = ?', (doc_id,))
        doc = await cursor.fetchone()
        return doc

async def update_document_status(doc_id, status):
    async with aiosqlite.connect(DATABASE_FILE) as conn:
        await conn.execute('UPDATE documents SET status = ? WHERE id = ?', (status, doc_id))
        await conn.commit()

# Обработчики маршрутов
async def handle_webhook(request):
    data = await request.json()
    await dp.feed_raw_update(bot, data)
    return web.Response(text="OK")

async def handle_root(request):
    return web.Response(text="Бот жив")

# Самопингование
async def keep_alive():
    await asyncio.sleep(10)
    ping_url = WEBHOOK_URL  # Используем WEBHOOK_URL без лишнего слеша
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(ping_url) as response:
                    if response.status == 200:
                        logger.info("Сервис активен")
                    else:
                        logger.warning(f"Ошибка пинга: статус {response.status}")
        except Exception as e:
            logger.error(f"Ошибка самопингования: {e}")
        await asyncio.sleep(600)

# Клавиатуры
def get_role_keyboard():
    roles = ["Официант", "Администратор", "Бармен", "Менеджер", "Бухгалтер", "СММ", "Повар"]
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=role)] for role in roles], resize_keyboard=True, one_time_keyboard=True)

def get_contact_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Поделиться контактом", request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)

def get_role_action_keyboard(role):
    role = role.lower()
    if role == "администратор":
        return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Админ-панель")], [KeyboardButton(text="Экспорт базы данных")]], resize_keyboard=True)
    elif role in ["официант", "бармен", "повар"]:
        return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Отправить чек")]], resize_keyboard=True)
    elif role in ["бухгалтер", "смм"]:
        return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Отправить документ")]], resize_keyboard=True)
    return None

def get_admin_panel(pending_users=None):
    keyboard = []
    if pending_users:
        for user in pending_users:
            user_id, full_name, role = user
            keyboard.append([
                InlineKeyboardButton(text=f"{full_name} ({role})", callback_data=f"user_info_{user_id}"),
                InlineKeyboardButton(text="Подтвердить", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton(text="Отклонить", callback_data=f"reject_{user_id}")
            ])
    keyboard.extend([
        [InlineKeyboardButton(text="Все пользователи", callback_data="all_users")],
        [InlineKeyboardButton(text="Документы по дате", callback_data="documents_by_date")],
        [InlineKeyboardButton(text="По сотрудникам", callback_data="documents_by_user")],
        [InlineKeyboardButton(text="Запросить документы", callback_data="request_documents")],
        [InlineKeyboardButton(text="Экспорт базы данных", callback_data="export_db")],
        [InlineKeyboardButton(text="Закрыть меню", callback_data="close_menu")]
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Состояния FSM
class UserRegistration(StatesGroup):
    full_name = State()
    phone = State()
    role = State()

# Вспомогательные функции
async def check_user(user_id: int) -> tuple[bool, str]:
    user = await get_user(user_id)
    if user and user[4] == "approved":  # Индекс 4 — status
        return True, user[3]  # Индекс 3 — role
    return False, ""

async def get_all_approved_users():
    async with aiosqlite.connect(DATABASE_FILE) as conn:
        cursor = await conn.execute('SELECT user_id, role FROM users WHERE status = ?', ('approved',))
        users = await cursor.fetchall()
        return users

# Обработчики
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("Привет! Введите ваше ФИО для регистрации:")
    await state.set_state(UserRegistration.full_name)

@dp.message(UserRegistration.full_name)
async def process_full_name(message: types.Message, state: FSMContext):
    if not message.text or message.text.strip() == "":
        await message.answer("ФИО не может быть пустым. Введите ваше ФИО:")
        return
    await state.update_data(full_name=message.text.strip())
    await message.answer("Поделитесь контактом:", reply_markup=get_contact_keyboard())
    await state.set_state(UserRegistration.phone)

@dp.message(UserRegistration.phone, F.contact)
async def process_contact(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number
    await state.update_data(phone=phone)
    await message.answer("Выберите роль:", reply_markup=get_role_keyboard())
    await state.set_state(UserRegistration.role)

@dp.message(UserRegistration.role, F.text.in_(["Официант", "Администратор", "Бармен", "Менеджер", "Бухгалтер", "СММ", "Повар"]))
async def process_role(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    user_id = message.from_user.id
    role = message.text.strip().lower()

    if "full_name" not in user_data or "phone" not in user_data:
        await message.answer("Ошибка: не все данные заполнены. Начните заново с /start.")
        await state.clear()
        return

    full_name = user_data["full_name"]
    phone = user_data["phone"]

    user = await get_user(user_id)
    if user:
        await message.answer("Вы уже зарегистрированы. Обратитесь к администратору.")
        await state.clear()
        return

    await save_user(user_id, full_name, phone, role.capitalize())
    await message.answer(f"Роль: {role.capitalize()}. Ожидайте подтверждения.", reply_markup=ReplyKeyboardRemove())
    try:
        await bot.send_message(ADMIN_ID, f"Новая заявка:\nФИО: {full_name}\nТелефон: {phone}\nРоль: {role.capitalize()}\nID: {user_id}\n/approve {user_id} или /reject {user_id}")
    except Exception as e:
        logger.error(f"Ошибка уведомления: {e}")
    await state.clear()

@dp.callback_query(F.data.startswith("approve_"))
async def approve_user(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split("_")[1])
    await update_user_status(user_id, "approved")
    user = await get_user(user_id)
    if user:
        role = user[3].lower()
        await bot.send_message(user_id, "Регистрация подтверждена!", reply_markup=get_role_action_keyboard(role))
        await bot.send_message(callback_query.from_user.id, f"{user[1]} ({user[3]}) подтвержден.")
    await bot.answer_callback_query(callback_query.id)
    pending_users = await get_pending_users()
    await bot.edit_message_reply_markup(chat_id=callback_query.from_user.id, message_id=callback_query.message.message_id, reply_markup=get_admin_panel(pending_users))

@dp.callback_query(F.data.startswith("reject_"))
async def reject_user(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split("_")[1])
    await update_user_status(user_id, "rejected")
    user = await get_user(user_id)
    if user:
        await bot.send_message(user_id, "Регистрация отклонена.")
        await bot.send_message(callback_query.from_user.id, f"{user[1]} отклонен.")
    await bot.answer_callback_query(callback_query.id)
    pending_users = await get_pending_users()
    await bot.edit_message_reply_markup(chat_id=callback_query.from_user.id, message_id=callback_query.message.message_id, reply_markup=get_admin_panel(pending_users))

@dp.message(Command("my_actions"))
async def show_role_actions(message: types.Message):
    user_id = message.from_user.id
    is_registered, role = await check_user(user_id)
    if not is_registered:
        await message.answer("Вы не зарегистрированы или не подтверждены.")
        return
    keyboard = get_role_action_keyboard(role)
    if keyboard:
        await message.answer("Выберите действие:", reply_markup=keyboard)
    else:
        await message.answer("Нет действий для вашей роли.")

@dp.message(F.text == "Админ-панель", F.from_user.id == ADMIN_ID)
async def cmd_admin_panel(message: types.Message):
    pending_users = await get_pending_users()
    await message.answer("Админ-панель:", reply_markup=get_admin_panel(pending_users))

@dp.message(F.document | F.photo)
async def handle_role_document(message: types.Message):
    user_id = message.from_user.id
    is_registered, role = await check_user(user_id)
    if not is_registered:
        await message.answer("Вы не зарегистрированы или не подтверждены.")
        return

    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    file = await bot.get_file(file_id)
    downloaded_file = await bot.download_file(file.file_path)

    current_date = datetime.now().strftime("%Y-%m-%d")
    date_dir = os.path.join(DOCUMENTS_DIR, current_date)
    if not os.path.exists(date_dir):
        os.makedirs(date_dir)

    file_extension = ".jpg" if message.photo else os.path.splitext(message.document.file_name)[1]
    file_name = f"{datetime.now().strftime('%H-%M-%S')}_{user_id}{file_extension}"
    local_path = os.path.join(date_dir, file_name)
    with open(local_path, "wb") as f:
        f.write(await downloaded_file.read())

    role_type = "чек" if role.lower() in ["официант", "бармен", "повар"] else "документ" if role.lower() in ["бухгалтер", "смм"] else "другое"
    await save_document(user_id, local_path, role_type)

    user = await get_user(user_id)
    user_name = user[1] if user else "Неизвестный пользователь"
    await bot.send_message(ADMIN_ID, f"Новый {role_type} от {user_name} ({role.capitalize()}):\nID: {user_id}\nДата: {current_date}\nПуть: {local_path}")
    await message.answer(f"{role_type.capitalize()} загружен.", reply_markup=get_role_action_keyboard(role.lower()))

@dp.message(F.text.in_(["Отправить чек", "Отправить документ"]))
async def handle_role_action_message(message: types.Message):
    user_id = message.from_user.id
    is_registered, role = await check_user(user_id)
    if not is_registered:
        await message.answer("Вы не зарегистрированы или не подтверждены.")
        return
    action = message.text.lower()
    if action == "отправить чек" and role.lower() in ["официант", "бармен", "повар"]:
        await message.answer("Отправьте чек:")
    elif action == "отправить документ" and role.lower() in ["бухгалтер", "смм"]:
        await message.answer("Отправьте документ:")
    else:
        await message.answer("Действие недоступно.")

@dp.message(Command("admin_panel"), F.from_user.id == ADMIN_ID)
async def cmd_admin_panel_command(message: types.Message):
    pending_users = await get_pending_users()
    await message.answer("Админ-панель:", reply_markup=get_admin_panel(pending_users))

@dp.callback_query(F.data.startswith("user_info_"))
async def show_user_info(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split("_")[2])
    user = await get_user(user_id)
    if user:
        await bot.send_message(callback_query.from_user.id, f"ФИО: {user[1]}\nРоль: {user[3]}\nСтатус: {user[4]}")
    else:
        await bot.send_message(callback_query.from_user.id, "Пользователь не найден.")
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query(F.data == "all_users")
async def process_all_users(callback_query: types.CallbackQuery):
    async with aiosqlite.connect(DATABASE_FILE) as conn:
        cursor = await conn.execute('SELECT * FROM users')
        users = await cursor.fetchall()
    if not users:
        await bot.send_message(callback_query.from_user.id, "Список пользователей пуст.")
    else:
        response = "Все пользователи:\n" + "\n".join(f"ID: {row[0]}, ФИО: {row[1]}, Роль: {row[3]}, Статус: {row[4]}" for row in users)
        await bot.send_message(callback_query.from_user.id, response)
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query(F.data == "documents_by_date")
async def process_documents_by_date(callback_query: types.CallbackQuery):
    await bot.send_message(callback_query.from_user.id, "Укажите дату (ГГГГ-ММ-ДД):")
    await bot.answer_callback_query(callback_query.id)

@dp.message(F.text, F.from_user.id == ADMIN_ID)
async def process_date_input(message: types.Message):
    try:
        if message.text.strip().isdigit():
            doc_id = int(message.text)
            doc = await get_document_by_id(doc_id)
            if doc:
                if doc[6] == "approved":
                    local_path = doc[2]
                    if os.path.exists(local_path):
                        document = FSInputFile(local_path)
                        await bot.send_document(message.chat.id, document)
                    else:
                        await message.answer("Файл документа не найден локально.")
                else:
                    await message.answer("Документ не подтвержден.")
            else:
                await message.answer("Документ не найден.")
            return
        date = message.text.strip()
        datetime.strptime(date, "%Y-%m-%d")
        async with aiosqlite.connect(DATABASE_FILE) as conn:
            cursor = await conn.execute('SELECT * FROM documents WHERE upload_date = ?', (date,))
            files = await cursor.fetchall()
        if not files:
            await message.answer(f"Документы за {date} не найдены.")
            return
        response = f"Документы за {date}:\n"
        for file in files:
            user = await get_user(file[1])
            user_name = user[1] if user else "Неизвестный пользователь"
            response += f"ID: {file[0]}, Путь: {file[2]}, Сотрудник: {user_name}, Тип: {file[5]}, Статус: {file[6]}\n"
        await message.answer(response)
    except ValueError:
        await message.answer("Неверный формат. Используйте ГГГГ-ММ-ДД или ID документа.")

@dp.callback_query(F.data == "documents_by_user")
async def process_documents_by_user(callback_query: types.CallbackQuery):
    approved_users = await get_all_approved_users()
    if not approved_users:
        await bot.send_message(callback_query.from_user.id, "Нет сотрудников.")
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{row[1]}", callback_data=f"user_docs_{row[0]}")] for row in approved_users])
        await bot.send_message(callback_query.from_user.id, "Выберите сотрудника:", reply_markup=keyboard)
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query(F.data.startswith("user_docs_"))
async def process_user_documents(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split("_")[2])
    user = await get_user(user_id)
    if not user:
        await bot.send_message(callback_query.from_user.id, "Сотрудник не найден.")
        await bot.answer_callback_query(callback_query.id)
        return
    user_name = user[1]
    async with aiosqlite.connect(DATABASE_FILE) as conn:
        cursor = await conn.execute('SELECT * FROM documents WHERE user_id = ?', (user_id,))
        files = await cursor.fetchall()
    if not files:
        await bot.send_message(callback_query.from_user.id, f"У {user_name} нет документов.")
    else:
        response = f"Документы {user_name}:\n" + "\n".join(f"ID: {row[0]}, Путь: {row[2]}, Дата: {row[4]}, Тип: {row[5]}, Статус: {row[6]}" for row in files)
        await bot.send_message(callback_query.from_user.id, response)
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query(F.data == "close_menu")
async def close_menu(callback_query: types.CallbackQuery):
    await bot.send_message(callback_query.from_user.id, "Меню закрыто.", reply_markup=ReplyKeyboardRemove())
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query(F.data == "request_documents")
async def request_documents(callback_query: types.CallbackQuery):
    approved_users = await get_all_approved_users()
    if not approved_users:
        await bot.send_message(callback_query.from_user.id, "Нет сотрудников.")
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{row[1]}", callback_data=f"request_docs_{row[0]}")] for row in approved_users])
        await bot.send_message(callback_query.from_user.id, "Выберите сотрудника:", reply_markup=keyboard)
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query(F.data.startswith("request_docs_"))
async def process_request_documents(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split("_")[2])
    user = await get_user(user_id)
    if not user:
        await bot.send_message(callback_query.from_user.id, "Сотрудник не найден.")
        await bot.answer_callback_query(callback_query.id)
        return
    await bot.send_message(user_id, "Администратор запросил документы.", reply_markup=get_role_action_keyboard(user[3].lower()))
    await bot.send_message(callback_query.from_user.id, f"Запрос отправлен {user[1]}.")
    await bot.answer_callback_query(callback_query.id)

@dp.message(Command("approve"))
async def cmd_approve(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ только администратору.")
        return
    try:
        user_id = int(message.text.split()[1])
        await update_user_status(user_id, "approved")
        user = await get_user(user_id)
        if user:
            await bot.send_message(user_id, "Регистрация подтверждена.", reply_markup=get_role_action_keyboard(user[3].lower()))
            await message.answer(f"{user[1]} ({user[3]}) подтвержден.")
        else:
            await message.answer("Пользователь не найден.")
    except (IndexError, ValueError):
        await message.answer("Формат: /approve {user_id}")

@dp.message(Command("reject"))
async def cmd_reject(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ только администратору.")
        return
    try:
        user_id = int(message.text.split()[1])
        await update_user_status(user_id, "rejected")
        user = await get_user(user_id)
        if user:
            await bot.send_message(user_id, "Регистрация отклонена.")
            await message.answer(f"{user[1]} отклонен.")
        else:
            await message.answer("Пользователь не найден.")
    except (IndexError, ValueError):
        await message.answer("Формат: /reject {user_id}")

@dp.message(Command("get_document"))
async def cmd_get_document(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ только администратору.")
        return
    try:
        doc_id = int(message.text.split()[1])
        doc = await get_document_by_id(doc_id)
        if doc:
            if doc[6] == "approved":
                local_path = doc[2]
                if os.path.exists(local_path):
                    document = FSInputFile(local_path)
                    await bot.send_document(message.chat.id, document)
                else:
                    await message.answer("Файл документа не найден локально.")
            else:
                await message.answer("Документ не подтвержден.")
        else:
            await message.answer("Документ не найден.")
    except (IndexError, ValueError):
        await message.answer("Формат: /get_document {id}")

@dp.message(Command("export_db"), F.from_user.id == ADMIN_ID)
async def export_database(message: types.Message):
    try:
        temp_db_path = os.path.join(DOCUMENTS_DIR, f"database_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
        shutil.copy2(DATABASE_FILE, temp_db_path)
        db_file = FSInputFile(temp_db_path)
        await bot.send_document(chat_id=message.chat.id, document=db_file, caption="База данных SQLite")
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)
        await message.answer("База данных экспортирована.")
    except Exception as e:
        logger.error(f"Ошибка экспорта: {e}")
        await message.answer("Ошибка при экспорте базы данных.")

@dp.callback_query(F.data == "export_db")
async def export_database_callback(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await bot.send_message(callback_query.from_user.id, "Доступ только администратору.")
        await bot.answer_callback_query(callback_query.id)
        return
    await export_database(types.Message(chat=callback_query.message.chat, from_user=callback_query.from_user, text="/export_db"))
    await bot.answer_callback_query(callback_query.id)

# Запуск
async def on_startup():
    await init_db()
    await bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}")
    logger.info(f"Webhook установлен: {WEBHOOK_URL}{WEBHOOK_PATH}")

async def main():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.router.add_get("/", handle_root)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Сервер запущен на порту {port}")
    await on_startup()
    asyncio.create_task(keep_alive())
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Ошибка при запуске: {e}")
