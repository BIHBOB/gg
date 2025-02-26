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
<<<<<<< HEAD
import aiosqlite
import shutil

=======

# Попробуем импортировать зависимости с обработкой ошибок
try:
    import pandas as pd
except ImportError:
    print("Ошибка: 'pandas' не установлен. Установите с помощью 'pip install pandas'.")
    exit(1)

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
    import io
    import json
except ImportError:
    print("Ошибка: библиотеки Google API не установлены. Установите с помощью 'pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client'.")
    exit(1)

>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
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
<<<<<<< HEAD
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-bot-name.onrender.com/webhook")
=======
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-app-name.onrender.com")  # Замените на ваше имя приложения
>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
WEBHOOK_PATH = "/webhook"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

<<<<<<< HEAD
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
=======
# Путь для временного хранения файлов
DOCUMENTS_DIR = "Documents"
DATABASE_FILE = "database.xlsx"
if not os.path.exists(DOCUMENTS_DIR):
    os.makedirs(DOCUMENTS_DIR)

# Инициализация DataFrame
users_df = pd.DataFrame(columns=["user_id", "full_name", "phone", "role", "status"])
documents_df = pd.DataFrame(columns=["id", "user_id", "file_id", "drive_file_id", "upload_date", "role_type", "status"])

# Настройка Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive.file']
DRIVE_FILE_ID = os.getenv("DRIVE_FILE_ID")
TOKEN_JSON = os.getenv("TOKEN_JSON")

# Попытка загрузки токена из переменной окружения или файла
if TOKEN_JSON:
    try:
        creds = Credentials.from_authorized_user_info(json.loads(TOKEN_JSON), SCOPES)
    except Exception as e:
        logger.error(f"Ошибка загрузки TOKEN_JSON из переменной окружения: {e}")
        creds = None
elif os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
else:
    try:
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token_file:
            token_file.write(creds.to_json())
    except FileNotFoundError:
        logger.error("Файл credentials.json не найден. Настройте Google Drive API локально.")
        creds = None

drive_service = build('drive', 'v3', credentials=creds) if creds else None

# Асинхронная загрузка базы данных с Google Drive
async def load_db_from_drive():
    global users_df, documents_df, DRIVE_FILE_ID
    if not drive_service:
        logger.error("Google Drive не доступен для загрузки")
        return
    try:
        if DRIVE_FILE_ID:
            request = drive_service.files().get_media(fileId=DRIVE_FILE_ID)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            fh.seek(0)
            excel_data = pd.ExcelFile(fh)
            users_df = pd.read_excel(excel_data, sheet_name="users", dtype={"user_id": int})
            documents_df = pd.read_excel(excel_data, sheet_name="documents", dtype={"id": int, "user_id": int})
            logger.info("База данных успешно загружена с Google Drive")
        else:
            logger.info("DRIVE_FILE_ID не задан, используется пустая база данных")
    except Exception as e:
        logger.error(f"Ошибка при загрузке базы данных с Google Drive: {e}")

# Асинхронная запись базы данных в Google Drive
async def save_db_to_drive():
    global DRIVE_FILE_ID
    if not drive_service:
        logger.error("Google Drive не доступен для сохранения")
        return
    try:
        writer = pd.ExcelWriter(DATABASE_FILE, engine='xlsxwriter')
        users_df.to_excel(writer, sheet_name="users", index=False)
        documents_df.to_excel(writer, sheet_name="documents", index=False)
        writer.close()

        media = MediaFileUpload(DATABASE_FILE, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        if DRIVE_FILE_ID:
            drive_service.files().update(fileId=DRIVE_FILE_ID, media_body=media).execute()
            logger.info("База данных обновлена на Google Drive")
        else:
            file_metadata = {'name': 'database.xlsx', 'parents': ['root']}
            file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            DRIVE_FILE_ID = file.get('id')
            os.environ["DRIVE_FILE_ID"] = DRIVE_FILE_ID
            logger.info(f"База данных создана на Google Drive с ID: {DRIVE_FILE_ID}")
    except Exception as e:
        logger.error(f"Ошибка сохранения на Google Drive: {e}")

# Асинхронная загрузка файла на Google Drive
async def upload_file_to_drive(file_path: str, file_name: str) -> str:
    if not drive_service:
        logger.error("Google Drive не доступен для загрузки файла")
        return None
    try:
        media = MediaFileUpload(file_path)
        file_metadata = {'name': file_name, 'parents': ['root']}
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        file_id = file.get('id')
        logger.info(f"Файл {file_name} загружен на Google Drive с ID: {file_id}")
        return file_id
    except Exception as e:
        logger.error(f"Ошибка загрузки файла на Google Drive: {e}")
        return None

# Асинхронная загрузка файла с Google Drive
async def download_file_from_drive(file_id: str, local_path: str):
    if not drive_service:
        logger.error("Google Drive не доступен для скачивания файла")
        return False
    try:
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)
        async with aiofiles.open(local_path, 'wb') as f:
            await f.write(fh.read())
        logger.info(f"Файл скачан с Google Drive в {local_path}")
        return True
    except Exception as e:
        logger.error(f"Ошибка скачивания файла с Google Drive: {e}")
        return False
>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19

# Обработчики маршрутов
async def handle_webhook(request):
    logger.info("Получен запрос на /webhook")
    data = await request.json()
    logger.info(f"Полученные данные: {data}")
    await dp.feed_raw_update(bot, data)
    logger.info("Обновление обработано")
    return web.Response(text="OK")

async def handle_root(request):
    logger.info("Получен запрос на /")
    return web.Response(text="Бот жив")

# Самопингование
async def keep_alive():
    await asyncio.sleep(10)
<<<<<<< HEAD
    ping_url = f"{WEBHOOK_URL}/"
=======
>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(ping_url) as response:
                    if response.status == 200:
                        logger.info("Сервис активен")
                    else:
                        logger.warning(f"Ошибка самопингования: статус {response.status}")
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

class DocumentRequest(StatesGroup):
    user_selection = State()

# Вспомогательные функции
<<<<<<< HEAD
async def check_user(user_id: int) -> tuple[bool, str]:
    user = await get_user(user_id)
    if user and user[4] == "approved":  # status — пятый столбец (индекс 4)
        return True, user[3]  # role — четвертый столбец (индекс 3)
    return False, ""

async def get_all_approved_users():
    async with aiosqlite.connect(DATABASE_FILE) as conn:
        cursor = await conn.execute('SELECT user_id, role FROM users WHERE status = ?', ('approved',))
        users = await cursor.fetchall()
        return users

=======
async def get_all_approved_users():
    return users_df[users_df["status"] == "approved"][["user_id", "role"]].values.tolist()

async def check_user(user_id: int) -> tuple[bool, str]:
    user = users_df[users_df["user_id"] == user_id]
    if not user.empty and user["status"].iloc[0] == "approved":
        return True, user["role"].iloc[0]
    return False, ""

>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
# Обработчики
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    logger.info(f"Получена команда /start от {message.from_user.id}")
    await message.answer("Привет! Введите ваше ФИО для регистрации:")
    await state.set_state(UserRegistration.full_name)

@dp.message(UserRegistration.full_name)
async def process_full_name(message: types.Message, state: FSMContext):
    logger.info(f"Получено ФИО: {message.text}")
    if not message.text or message.text.strip() == "":
        await message.answer("ФИО не может быть пустым. Пожалуйста, введите ваше ФИО:")
        return
    await state.update_data(full_name=message.text.strip())
    await message.answer("Поделитесь контактом:", reply_markup=get_contact_keyboard())
    await state.set_state(UserRegistration.phone)

@dp.message(UserRegistration.phone, F.contact)
async def process_contact(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number
    logger.info(f"Получен телефон: {phone}")
    await state.update_data(phone=phone)
    await message.answer("Выберите роль:", reply_markup=get_role_keyboard())
    await state.set_state(UserRegistration.role)

@dp.message(UserRegistration.role, F.text.in_(["Официант", "Администратор", "Бармен", "Менеджер", "Бухгалтер", "СММ", "Повар"]))
async def process_role(message: types.Message, state: FSMContext):
    logger.info(f"Получена роль: {message.text}")
    user_data = await state.get_data()
    logger.info(f"Данные состояния: {user_data}")
    user_id = message.from_user.id
    role = message.text.strip().lower()

    if "full_name" not in user_data or "phone" not in user_data:
        await message.answer("Ошибка: не все данные заполнены. Начните регистрацию заново с /start.")
        await state.clear()
        return

    full_name = user_data["full_name"]
    phone = user_data["phone"]

<<<<<<< HEAD
    user = await get_user(user_id)
    if user:
=======
    global users_df
    if user_id in users_df["user_id"].values:
>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
        await message.answer("Вы уже зарегистрированы. Обратитесь к администратору.")
        await state.clear()
        return

<<<<<<< HEAD
    await save_user(user_id, full_name, phone, role.capitalize())
=======
    new_user = pd.DataFrame({
        "user_id": [user_id],
        "full_name": [full_name],
        "phone": [phone],
        "role": [role.capitalize()],
        "status": ["pending"]
    })
    users_df = pd.concat([users_df, new_user], ignore_index=True)
    await save_db_to_drive()

>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
    await message.answer(f"Роль: {role.capitalize()}. Ожидайте подтверждения.", reply_markup=ReplyKeyboardRemove())
    try:
        await bot.send_message(ADMIN_ID, f"Новая заявка:\nФИО: {full_name}\nТелефон: {phone}\nРоль: {role.capitalize()}\nID: {user_id}\n/approve {user_id} или /reject {user_id}")
    except Exception as e:
        logger.error(f"Ошибка уведомления: {e}")
    await state.clear()

@dp.callback_query(F.data.startswith("approve_"))
async def approve_user(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split("_")[1])
<<<<<<< HEAD
    await update_user_status(user_id, "approved")
    user = await get_user(user_id)
    if user:
        role = user[3].lower()  # role — четвертый столбец
        await bot.send_message(user_id, "Регистрация подтверждена!", reply_markup=get_role_action_keyboard(role))
        await bot.send_message(callback_query.from_user.id, f"{user[1]} ({user[3]}) подтвержден.")  # full_name и role
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
        await bot.send_message(callback_query.from_user.id, f"{user[1]} отклонен.")  # full_name
    await bot.answer_callback_query(callback_query.id)
    pending_users = await get_pending_users()
=======
    global users_df
    user = users_df[users_df["user_id"] == user_id]
    if not user.empty:
        users_df.loc[users_df["user_id"] == user_id, "status"] = "approved"
        await save_db_to_drive()
        role = user["role"].iloc[0].lower()
        await bot.send_message(user_id, "Регистрация подтверждена!", reply_markup=get_role_action_keyboard(role))
        await bot.send_message(callback_query.from_user.id, f"{user['full_name'].iloc[0]} ({user['role'].iloc[0]}) подтвержден.")
    await bot.answer_callback_query(callback_query.id)
    pending_users = users_df[users_df["status"] == "pending"][["user_id", "full_name", "role"]].values.tolist()
>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
    await bot.edit_message_reply_markup(chat_id=callback_query.from_user.id, message_id=callback_query.message.message_id, reply_markup=get_admin_panel(pending_users))

@dp.message(Command("my_actions"))
async def show_role_actions(message: types.Message):
    user_id = message.from_user.id
    is_registered, role = await check_user(user_id)
    if not is_registered:
        await message.answer("Вы не зарегистрированы или не подтверждены.")
        return
    keyboard = get_role_action_keyboard(role)
    await message.answer("Выберите действие:", reply_markup=keyboard) if keyboard else await message.answer("Нет действий для вашей роли.")

@dp.message(F.text == "Админ-панель", F.from_user.id == ADMIN_ID)
async def cmd_admin_panel(message: types.Message):
<<<<<<< HEAD
    pending_users = await get_pending_users()
=======
    pending_users = users_df[users_df["status"] == "pending"][["user_id", "full_name", "role"]].values.tolist()
>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
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

    # Загружаем файл на Google Drive
    drive_file_id = await upload_file_to_drive(local_path, file_name)
    if not drive_file_id:
        await message.answer("Ошибка загрузки файла на Google Drive.")
        return

    role_type = "чек" if role.lower() in ["официант", "бармен", "повар"] else "документ" if role.lower() in ["бухгалтер", "смм"] else "другое"
<<<<<<< HEAD
    await save_document(user_id, local_path, role_type)

    try:
        user = await get_user(user_id)
        user_name = user[1] if user else "Неизвестный пользователь"  # full_name — второй столбец
        await bot.send_message(ADMIN_ID, f"Новый {role_type} от {user_name} ({role.capitalize()}):\nID: {user_id}\nДата: {current_date}\nПуть: {local_path}")
=======
    global documents_df
    new_doc = pd.DataFrame({
        "id": [documents_df["id"].max() + 1 if not documents_df.empty else 1],
        "user_id": [user_id],
        "file_id": [file_id],
        "drive_file_id": [drive_file_id],
        "upload_date": [current_date],
        "role_type": [role_type],
        "status": ["pending"]
    })
    documents_df = pd.concat([documents_df, new_doc], ignore_index=True)
    await save_db_to_drive()

    try:
        user_name = users_df[users_df["user_id"] == user_id]["full_name"].iloc[0]
        await bot.send_message(ADMIN_ID, f"Новый {role_type} от {user_name} ({role.capitalize()}):\nID: {user_id}\nДата: {current_date}")
>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
    except Exception as e:
        logger.error(f"Ошибка уведомления: {e}")
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

@dp.callback_query(F.data.startswith("send_check_") | F.data.startswith("send_document_"))
async def handle_role_action(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    is_registered, role = await check_user(user_id)
    if not is_registered:
        await bot.send_message(user_id, "Вы не зарегистрированы или не подтверждены.")
        await bot.answer_callback_query(callback_query.id)
        return
    action_type = "чек" if "send_check_" in callback_query.data else "документ"
    await bot.send_message(user_id, f"Отправьте {action_type}:")
    await bot.answer_callback_query(callback_query.id)

@dp.message(Command("admin_panel"), F.from_user.id == ADMIN_ID)
async def cmd_admin_panel_command(message: types.Message):
<<<<<<< HEAD
    pending_users = await get_pending_users()
=======
    pending_users = users_df[users_df["status"] == "pending"][["user_id", "full_name", "role"]].values.tolist()
>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
    await message.answer("Админ-панель:", reply_markup=get_admin_panel(pending_users))

@dp.callback_query(F.data.startswith("user_info_"))
async def show_user_info(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split("_")[2])
<<<<<<< HEAD
    user = await get_user(user_id)
    if user:
        await bot.send_message(callback_query.from_user.id, f"ФИО: {user[1]}\nРоль: {user[3]}\nСтатус: {user[4]}")  # full_name, role, status
=======
    user = users_df[users_df["user_id"] == user_id]
    if not user.empty:
        await bot.send_message(callback_query.from_user.id, f"ФИО: {user['full_name'].iloc[0]}\nРоль: {user['role'].iloc[0]}\nСтатус: {user['status'].iloc[0]}")
>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
    else:
        await bot.send_message(callback_query.from_user.id, "Пользователь не найден.")
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query(F.data == "all_users")
async def process_all_users(callback_query: types.CallbackQuery):
<<<<<<< HEAD
    async with aiosqlite.connect(DATABASE_FILE) as conn:
        cursor = await conn.execute('SELECT * FROM users')
        users = await cursor.fetchall()
    if not users:
        await bot.send_message(callback_query.from_user.id, "Список пользователей пуст.")
    else:
        response = "Все пользователи:\n" + "\n".join(f"ID: {row[0]}, ФИО: {row[1]}, Роль: {row[3]}, Статус: {row[4]}" for row in users)
=======
    if users_df.empty:
        await bot.send_message(callback_query.from_user.id, "Список пользователей пуст.")
    else:
        response = "Все пользователи:\n" + "\n".join(f"ID: {row['user_id']}, ФИО: {row['full_name']}, Роль: {row['role']}, Статус: {row['status']}" for _, row in users_df.iterrows())
>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
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
<<<<<<< HEAD
            doc_id = int(message.text)
            doc = await get_document_by_id(doc_id)
            if doc:
                if doc[6] == "approved":  # status — седьмой столбец
                    local_path = doc[2]  # file_path — третий столбец
                    if os.path.exists(local_path):
                        document = FSInputFile(local_path)
                        await bot.send_document(message.chat.id, document)
                    else:
                        await message.answer("Файл документа не найден локально.")
=======
            file_id = int(message.text)
            doc = documents_df[documents_df["id"] == file_id]
            if not doc.empty:
                if doc["status"].iloc[0] == "approved":
                    local_path = os.path.join(DOCUMENTS_DIR, f"temp_{file_id}{os.path.splitext(doc['file_id'].iloc[0])[1]}")
                    if await download_file_from_drive(doc["drive_file_id"].iloc[0], local_path):
                        document = FSInputFile(local_path)
                        await bot.send_document(message.chat.id, document)
                        os.remove(local_path)  # Удаляем временный файл
                    else:
                        await message.answer("Ошибка скачивания документа.")
>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
                else:
                    await message.answer("Документ не подтвержден.")
            else:
                await message.answer("Документ не найден.")
            return
        date = message.text.strip()
        datetime.strptime(date, "%Y-%m-%d")
<<<<<<< HEAD
        async with aiosqlite.connect(DATABASE_FILE) as conn:
            cursor = await conn.execute('SELECT * FROM documents WHERE upload_date = ?', (date,))
            files = await cursor.fetchall()
        if not files:
            await message.answer(f"Документы за {date} не найдены.")
            return
        response = f"Документы за {date}:\n"
        for file in files:
            user = await get_user(file[1])  # user_id — второй столбец
            user_name = user[1] if user else "Неизвестный пользователь"  # full_name
            response += f"ID: {file[0]}, Путь: {file[2]}, Сотрудник: {user_name}, Тип: {file[5]}, Статус: {file[6]}\n"  # id, file_path, role_type, status
=======
        files = documents_df[documents_df["upload_date"] == date]
        if files.empty:
            await message.answer(f"Документы за {date} не найдены.")
            return
        response = f"Документы за {date}:\n"
        for _, file in files.iterrows():
            user_name = users_df[users_df["user_id"] == file["user_id"]]["full_name"].iloc[0]
            response += f"ID: {file['id']}, Drive ID: {file['drive_file_id']}, Сотрудник: {user_name}, Тип: {file['role_type']}, Статус: {file['status']}\n"
>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
        await message.answer(response)
    except ValueError:
        await message.answer("Неверный формат. Используйте ГГГГ-ММ-ДД или ID документа.")

@dp.callback_query(F.data == "documents_by_user")
async def process_documents_by_user(callback_query: types.CallbackQuery):
<<<<<<< HEAD
    approved_users = await get_all_approved_users()
    if not approved_users:
        await bot.send_message(callback_query.from_user.id, "Нет сотрудников.")
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{row[1]}", callback_data=f"user_docs_{row[0]}")] for row in approved_users])  # full_name, user_id
=======
    approved_users = users_df[users_df["status"] == "approved"]
    if approved_users.empty:
        await bot.send_message(callback_query.from_user.id, "Нет сотрудников.")
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=row["full_name"], callback_data=f"user_docs_{row['user_id']}")] for _, row in approved_users.iterrows()])
>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
        await bot.send_message(callback_query.from_user.id, "Выберите сотрудника:", reply_markup=keyboard)
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query(F.data.startswith("user_docs_"))
async def process_user_documents(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split("_")[2])
<<<<<<< HEAD
    user = await get_user(user_id)
    if not user:
        await bot.send_message(callback_query.from_user.id, "Сотрудник не найден.")
        await bot.answer_callback_query(callback_query.id)
        return
    user_name = user[1]  # full_name
    async with aiosqlite.connect(DATABASE_FILE) as conn:
        cursor = await conn.execute('SELECT * FROM documents WHERE user_id = ?', (user_id,))
        files = await cursor.fetchall()
    if not files:
        await bot.send_message(callback_query.from_user.id, f"У {user_name} нет документов.")
    else:
        response = f"Документы {user_name}:\n" + "\n".join(f"ID: {row[0]}, Путь: {row[2]}, Дата: {row[4]}, Тип: {row[5]}, Статус: {row[6]}" for row in files)  # id, file_path, upload_date, role_type, status
=======
    user_name = users_df[users_df["user_id"] == user_id]["full_name"].iloc[0]
    files = documents_df[documents_df["user_id"] == user_id]
    if files.empty:
        await bot.send_message(callback_query.from_user.id, f"У {user_name} нет документов.")
    else:
        response = f"Документы {user_name}:\n" + "\n".join(f"ID: {row['id']}, Drive ID: {row['drive_file_id']}, Дата: {row['upload_date']}, Тип: {row['role_type']}, Статус: {row['status']}" for _, row in files.iterrows())
>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
        await bot.send_message(callback_query.from_user.id, response)
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query(F.data == "close_menu")
async def close_menu(callback_query: types.CallbackQuery):
    await bot.send_message(callback_query.from_user.id, "Меню закрыто.", reply_markup=ReplyKeyboardRemove())
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query(F.data == "request_documents")
async def request_documents(callback_query: types.CallbackQuery):
<<<<<<< HEAD
    approved_users = await get_all_approved_users()
    if not approved_users:
        await bot.send_message(callback_query.from_user.id, "Нет сотрудников.")
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{row[1]}", callback_data=f"request_docs_{row[0]}")] for row in approved_users])  # full_name, user_id
=======
    approved_users = users_df[users_df["status"] == "approved"]
    if approved_users.empty:
        await bot.send_message(callback_query.from_user.id, "Нет сотрудников.")
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=row["full_name"], callback_data=f"request_docs_{row['user_id']}")] for _, row in approved_users.iterrows()])
>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
        await bot.send_message(callback_query.from_user.id, "Выберите сотрудника:", reply_markup=keyboard)
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query(F.data.startswith("request_docs_"))
async def process_request_documents(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split("_")[2])
<<<<<<< HEAD
    user = await get_user(user_id)
    if not user:
        await bot.send_message(callback_query.from_user.id, "Сотрудник не найден.")
        await bot.answer_callback_query(callback_query.id)
        return
    await bot.send_message(user_id, "Администратор запросил документы.", reply_markup=get_role_action_keyboard(user[3].lower()))  # role
    await bot.send_message(callback_query.from_user.id, f"Запрос отправлен {user[1]}.")  # full_name
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query(F.data.startswith("approve_doc_"))
async def approve_document(callback_query: types.CallbackQuery):
    doc_id = int(callback_query.data.split("_")[2])
    doc = await get_document_by_id(doc_id)
    if doc:
        await update_document_status(doc_id, "approved")
        user = await get_user(doc[1])  # user_id
        if user:
            user_name = user[1]  # full_name
            role_type = doc[5]  # role_type
            await bot.send_message(user[0], f"Ваш {role_type} подтвержден!")  # user_id
            await bot.send_message(callback_query.from_user.id, f"Документ от {user_name} подтвержден.")
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query(F.data.startswith("reject_doc_"))
async def reject_document(callback_query: types.CallbackQuery):
    doc_id = int(callback_query.data.split("_")[2])
    doc = await get_document_by_id(doc_id)
    if doc:
        await update_document_status(doc_id, "rejected")
        user = await get_user(doc[1])  # user_id
        if user:
            user_name = user[1]  # full_name
            role_type = doc[5]  # role_type
            await bot.send_message(user[0], f"Ваш {role_type} отклонен.")  # user_id
            await bot.send_message(callback_query.from_user.id, f"Документ от {user_name} отклонен.")
=======
    user = users_df[users_df["user_id"] == user_id]
    if not user.empty:
        await bot.send_message(user_id, "Администратор запросил документы.", reply_markup=get_role_action_keyboard(user["role"].iloc[0].lower()))
        await bot.send_message(callback_query.from_user.id, f"Запрос отправлен {user['full_name'].iloc[0]}.")
>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
    await bot.answer_callback_query(callback_query.id)

@dp.message(Command("approve"))
async def cmd_approve(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ только администратору.")
        return
    try:
        user_id = int(message.text.split()[1])
<<<<<<< HEAD
        await update_user_status(user_id, "approved")
        user = await get_user(user_id)
        if user:
            await bot.send_message(user_id, "Регистрация подтверждена.", reply_markup=get_role_action_keyboard(user[3].lower()))  # role
            await message.answer(f"{user[1]} ({user[3]}) подтвержден.")  # full_name, role
=======
        global users_df
        user = users_df[users_df["user_id"] == user_id]
        if not user.empty:
            users_df.loc[users_df["user_id"] == user_id, "status"] = "approved"
            await save_db_to_drive()
            await bot.send_message(user_id, "Регистрация подтверждена.", reply_markup=get_role_action_keyboard(user["role"].iloc[0].lower()))
            await message.answer(f"{user['full_name'].iloc[0]} ({user['role'].iloc[0]}) подтвержден.")
>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
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
<<<<<<< HEAD
        await update_user_status(user_id, "rejected")
        user = await get_user(user_id)
        if user:
            await bot.send_message(user_id, "Регистрация отклонена.")
            await message.answer(f"{user[1]} отклонен.")  # full_name
=======
        global users_df
        user = users_df[users_df["user_id"] == user_id]
        if not user.empty:
            users_df.loc[users_df["user_id"] == user_id, "status"] = "rejected"
            await save_db_to_drive()
            await bot.send_message(user_id, "Регистрация отклонена.")
            await message.answer(f"{user['full_name'].iloc[0]} отклонен.")
>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
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
<<<<<<< HEAD
        doc_id = int(message.text.split()[1])
        doc = await get_document_by_id(doc_id)
        if doc:
            if doc[6] == "approved":  # status
                local_path = doc[2]  # file_path
                if os.path.exists(local_path):
                    document = FSInputFile(local_path)
                    await bot.send_document(message.chat.id, document)
                else:
                    await message.answer("Файл документа не найден локально.")
=======
        file_id = int(message.text.split()[1])
        doc = documents_df[documents_df["id"] == file_id]
        if not doc.empty:
            if doc["status"].iloc[0] == "approved":
                local_path = os.path.join(DOCUMENTS_DIR, f"temp_{file_id}{os.path.splitext(doc['file_id'].iloc[0])[1]}")
                if await download_file_from_drive(doc["drive_file_id"].iloc[0], local_path):
                    document = FSInputFile(local_path)
                    await bot.send_document(message.chat.id, document)
                    os.remove(local_path)  # Удаляем временный файл
                else:
                    await message.answer("Ошибка скачивания документа.")
>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
            else:
                await message.answer("Документ не подтвержден.")
        else:
            await message.answer("Документ не найден.")
    except (IndexError, ValueError):
        await message.answer("Формат: /get_document {id}")

<<<<<<< HEAD
@dp.message(Command("export_db"), F.from_user.id == ADMIN_ID)
async def export_database(message: types.Message):
    try:
        # Создаем копию базы данных для экспорта
        temp_db_path = os.path.join(DOCUMENTS_DIR, f"database_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
        shutil.copy2(DATABASE_FILE, temp_db_path)
        
        # Отправляем файл в чат бота
        db_file = FSInputFile(temp_db_path)
        await bot.send_document(chat_id=message.chat.id, document=db_file, caption="База данных SQLite")
        
        # Удаляем временный файл
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)
        
        await message.answer("База данных экспортирована и отправлена в чат.")
    except Exception as e:
        logger.error(f"Ошибка при экспорте базы данных: {e}")
        await message.answer("Произошла ошибка при экспорте базы данных.")

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
    logger.info("База данных SQLite инициализирована")
=======
# Запуск
async def on_startup():
    await load_db_from_drive()
    logger.info("База данных инициализирована из Google Drive")
>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
    await bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}")
    logger.info(f"Webhook установлен: {WEBHOOK_URL}{WEBHOOK_PATH}")
    me = await bot.get_me()
    logger.info(f"Бот подключен: {me.username}")
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo") as resp:
            webhook_info = await resp.json()
            logger.info(f"Текущий webhook: {webhook_info}")

async def main():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.router.add_get("/", handle_root)
    runner = web.AppRunner(app)
    await runner.setup()
<<<<<<< HEAD
    port = int(os.getenv("PORT", 8080))
=======
    port = int(os.getenv("PORT", 8080))  # Render может переопределить PORT
>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Сервер запущен на порту {port}")
    await on_startup()
<<<<<<< HEAD
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        logger.info("Ресурсы очищены")
=======
    asyncio.create_task(keep_alive())
    await asyncio.Event().wait()
>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
<<<<<<< HEAD
        logger.error(f"Ошибка при запуске бота: {e}")
=======
        logger.error(f"Ошибка при запуске бота: {e}")
>>>>>>> 53ca98fe8f5c931a905566f5af3093b1614a0b19
