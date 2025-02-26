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
import pandas as pd
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io
import json

# Логирование
logging.basicConfig(level=logging.INFO)
logging.getLogger('aiohttp.access').setLevel(logging.WARNING)  # Уменьшаем логи от aiohttp
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
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-app-name.onrender.com")  # Замените на ваше имя приложения
WEBHOOK_PATH = "/webhook"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

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

if TOKEN_JSON:
    try:
        creds = Credentials.from_authorized_user_info(json.loads(TOKEN_JSON), SCOPES)
    except Exception as e:
        logger.error(f"Ошибка загрузки TOKEN_JSON: {e}")
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
        logger.error("Файл credentials.json не найден.")
        creds = None

drive_service = build('drive', 'v3', credentials=creds) if creds else None

# Асинхронные функции для Google Drive
async def load_db_from_drive():
    global users_df, documents_df, DRIVE_FILE_ID
    if not drive_service:
        logger.error("Google Drive не доступен")
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
            logger.info("База данных загружена с Google Drive")
        else:
            logger.info("DRIVE_FILE_ID не задан, используется пустая база")
    except Exception as e:
        logger.error(f"Ошибка загрузки базы: {e}")

async def save_db_to_drive():
    global DRIVE_FILE_ID
    if not drive_service:
        logger.error("Google Drive не доступен")
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
            logger.info(f"База данных создана на Google Drive: {DRIVE_FILE_ID}")
    except Exception as e:
        logger.error(f"Ошибка сохранения на Google Drive: {e}")

async def upload_file_to_drive(file_path: str, file_name: str) -> str:
    if not drive_service:
        logger.error("Google Drive не доступен")
        return None
    try:
        media = MediaFileUpload(file_path)
        file_metadata = {'name': file_name, 'parents': ['root']}
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')
    except Exception as e:
        logger.error(f"Ошибка загрузки файла: {e}")
        return None

async def download_file_from_drive(file_id: str, local_path: str):
    if not drive_service:
        logger.error("Google Drive не доступен")
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
        return True
    except Exception as e:
        logger.error(f"Ошибка скачивания файла: {e}")
        return False

# Обработчики маршрутов
async def handle_webhook(request):
    data = await request.json()
    logger.info(f"Получен webhook: {data}")
    await dp.feed_raw_update(bot, data)
    return web.Response(text="OK")

async def handle_root(request):
    return web.Response(text="Бот жив")

# Самопингование
async def keep_alive():
    await asyncio.sleep(10)
    ping_url = f"{WEBHOOK_URL}/"
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(ping_url) as response:
                    if response.status == 200:
                        logger.info("Сервис активен")
                    else:
                        logger.warning(f"Ошибка самопингования: {response.status}")
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
        return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Админ-панель")]], resize_keyboard=True)
    elif role in ["официант", "бармен", "повар"]:
        return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Отправить чек")]], resize_keyboard=True)
    elif role in ["бухгалтер", "смм"]:
        return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Отправить документ")]], resize_keyboard=True)
    return None

def get_admin_panel(pending_users=None):
    keyboard = []
    if pending_users and len(pending_users) > 0:
        for _, row in pending_users.iterrows():
            user_id, full_name, role = row["user_id"], row["full_name"], row["role"]
            keyboard.append([
                InlineKeyboardButton(text=f"{full_name} ({role})", callback_data=f"user_info_{user_id}"),
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user_id}")
            ])
    keyboard.extend([
        [InlineKeyboardButton(text="Все пользователи", callback_data="all_users")],
        [InlineKeyboardButton(text="Документы по дате", callback_data="documents_by_date")],
        [InlineKeyboardButton(text="По сотрудникам", callback_data="documents_by_user")],
        [InlineKeyboardButton(text="Запросить документы", callback_data="request_documents")],
        [InlineKeyboardButton(text="Закрыть меню", callback_data="close_menu")]
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Состояния FSM
class UserRegistration(StatesGroup):
    full_name = State()
    phone = State()
    role = State()

# Вспомогательные функции
async def get_all_approved_users():
    return users_df[users_df["status"] == "approved"][["user_id", "role"]].values.tolist()

async def check_user(user_id: int) -> tuple[bool, str]:
    user = users_df[users_df["user_id"] == user_id]
    if not user.empty and user["status"].iloc[0] == "approved":
        return True, user["role"].iloc[0]
    return False, ""

# Обработчики
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    logger.info(f"Команда /start от {message.from_user.id}")
    await message.answer("Привет! Введите ваше ФИО для регистрации:")
    await state.set_state(UserRegistration.full_name)

@dp.message(UserRegistration.full_name)
async def process_full_name(message: types.Message, state: FSMContext):
    if not message.text or message.text.strip() == "":
        await message.answer("ФИО не может быть пустым:")
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
    global users_df
    user_data = await state.get_data()
    user_id = message.from_user.id
    role = message.text.strip().lower()

    if "full_name" not in user_data or "phone" not in user_data:
        await message.answer("Ошибка: не все данные заполнены. Начните заново с /start.")
        await state.clear()
        return

    full_name = user_data["full_name"]
    phone = user_data["phone"]

    if user_id in users_df["user_id"].values:
        await message.answer("Вы уже зарегистрированы. Обратитесь к администратору.")
        await state.clear()
        return

    new_user = pd.DataFrame({
        "user_id": [user_id],
        "full_name": [full_name],
        "phone": [phone],
        "role": [role.capitalize()],
        "status": ["pending"]
    })
    users_df = pd.concat([users_df, new_user], ignore_index=True)
    await save_db_to_drive()

    await message.answer(f"Роль: {role.capitalize()}. Ожидайте подтверждения.", reply_markup=ReplyKeyboardRemove())
    try:
        await bot.send_message(ADMIN_ID, f"Новая заявка:\nФИО: {full_name}\nТелефон: {phone}\nРоль: {role.capitalize()}\nID: {user_id}")
    except Exception as e:
        logger.error(f"Ошибка уведомления: {e}")
    await state.clear()

@dp.callback_query(F.data.startswith("approve_"))
async def approve_user(callback_query: types.CallbackQuery):
    global users_df
    user_id = int(callback_query.data.split("_")[1])
    user = users_df[users_df["user_id"] == user_id]
    if not user.empty:
        users_df.loc[users_df["user_id"] == user_id, "status"] = "approved"
        await save_db_to_drive()
        role = user["role"].iloc[0].lower()
        await bot.send_message(user_id, "Регистрация подтверждена!", reply_markup=get_role_action_keyboard(role))
        await bot.send_message(callback_query.from_user.id, f"{user['full_name'].iloc[0]} ({user['role'].iloc[0]}) подтвержден.")
    pending_users = users_df[users_df["status"] == "pending"]
    await bot.edit_message_text(
        "Админ-панель:",
        chat_id=callback_query.from_user.id,
        message_id=callback_query.message.message_id,
        reply_markup=get_admin_panel(pending_users)
    )
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query(F.data.startswith("reject_"))
async def reject_user(callback_query: types.CallbackQuery):
    global users_df
    user_id = int(callback_query.data.split("_")[1])
    user = users_df[users_df["user_id"] == user_id]
    if not user.empty:
        users_df.loc[users_df["user_id"] == user_id, "status"] = "rejected"
        await save_db_to_drive()
        await bot.send_message(user_id, "Регистрация отклонена.")
        await bot.send_message(callback_query.from_user.id, f"{user['full_name'].iloc[0]} отклонен.")
    pending_users = users_df[users_df["status"] == "pending"]
    await bot.edit_message_text(
        "Админ-панель:",
        chat_id=callback_query.from_user.id,
        message_id=callback_query.message.message_id,
        reply_markup=get_admin_panel(pending_users)
    )
    await bot.answer_callback_query(callback_query.id)

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
    pending_users = users_df[users_df["status"] == "pending"]
    await message.answer("Админ-панель:", reply_markup=get_admin_panel(pending_users))

@dp.message(F.document | F.photo)
async def handle_role_document(message: types.Message):
    global documents_df
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

    drive_file_id = await upload_file_to_drive(local_path, file_name)
    if not drive_file_id:
        await message.answer("Ошибка загрузки файла на Google Drive.")
        return

    role_type = "чек" if role.lower() in ["официант", "бармен", "повар"] else "документ" if role.lower() in ["бухгалтер", "смм"] else "другое"
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

    user_name = users_df[users_df["user_id"] == user_id]["full_name"].iloc[0]
    await bot.send_message(ADMIN_ID, f"Новый {role_type} от {user_name} ({role.capitalize()}):\nID: {user_id}\nДата: {current_date}")
    await message.answer(f"{role_type.capitalize()} загружен.", reply_markup=get_role_action_keyboard(role.lower()))

@dp.message(Command("admin_panel"), F.from_user.id == ADMIN_ID)
async def cmd_admin_panel_command(message: types.Message):
    pending_users = users_df[users_df["status"] == "pending"]
    await message.answer("Админ-панель:", reply_markup=get_admin_panel(pending_users))

@dp.callback_query(F.data.startswith("user_info_"))
async def show_user_info(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split("_")[2])
    user = users_df[users_df["user_id"] == user_id]
    if not user.empty:
        await bot.send_message(callback_query.from_user.id, f"ФИО: {user['full_name'].iloc[0]}\nРоль: {user['role'].iloc[0]}\nСтатус: {user['status'].iloc[0]}")
    else:
        await bot.send_message(callback_query.from_user.id, "Пользователь не найден.")
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query(F.data == "all_users")
async def process_all_users(callback_query: types.CallbackQuery):
    if users_df.empty:
        await bot.send_message(callback_query.from_user.id, "Список пользователей пуст.")
    else:
        response = "Все пользователи:\n" + "\n".join(f"ID: {row['user_id']}, ФИО: {row['full_name']}, Роль: {row['role']}, Статус: {row['status']}" for _, row in users_df.iterrows())
        await bot.send_message(callback_query.from_user.id, response)
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query(F.data == "documents_by_date")
async def process_documents_by_date(callback_query: types.CallbackQuery):
    await bot.send_message(callback_query.from_user.id, "Укажите дату (ГГГГ-ММ-ДД):")
    await bot.answer_callback_query(callback_query.id)

@dp.message(F.text, F.from_user.id == ADMIN_ID)
async def process_date_input(message: types.Message):
    try:
        date = message.text.strip()
        datetime.strptime(date, "%Y-%m-%d")
        files = documents_df[documents_df["upload_date"] == date]
        if files.empty:
            await message.answer(f"Документы за {date} не найдены.")
            return
        response = f"Документы за {date}:\n"
        for _, file in files.iterrows():
            user_name = users_df[users_df["user_id"] == file["user_id"]]["full_name"].iloc[0]
            response += f"ID: {file['id']}, Drive ID: {file['drive_file_id']}, Сотрудник: {user_name}, Тип: {file['role_type']}, Статус: {file['status']}\n"
        await message.answer(response)
    except ValueError:
        await message.answer("Неверный формат. Используйте ГГГГ-ММ-ДД.")

@dp.callback_query(F.data == "documents_by_user")
async def process_documents_by_user(callback_query: types.CallbackQuery):
    approved_users = users_df[users_df["status"] == "approved"]
    if approved_users.empty:
        await bot.send_message(callback_query.from_user.id, "Нет сотрудников.")
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=row["full_name"], callback_data=f"user_docs_{row['user_id']}")] for _, row in approved_users.iterrows()])
        await bot.send_message(callback_query.from_user.id, "Выберите сотрудника:", reply_markup=keyboard)
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query(F.data.startswith("user_docs_"))
async def process_user_documents(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split("_")[2])
    user_name = users_df[users_df["user_id"] == user_id]["full_name"].iloc[0]
    files = documents_df[documents_df["user_id"] == user_id]
    if files.empty:
        await bot.send_message(callback_query.from_user.id, f"У {user_name} нет документов.")
    else:
        response = f"Документы {user_name}:\n" + "\n".join(f"ID: {row['id']}, Drive ID: {row['drive_file_id']}, Дата: {row['upload_date']}, Тип: {row['role_type']}, Статус: {row['status']}" for _, row in files.iterrows())
        await bot.send_message(callback_query.from_user.id, response)
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query(F.data == "close_menu")
async def close_menu(callback_query: types.CallbackQuery):
    await bot.edit_message_text(
        "Меню закрыто.",
        chat_id=callback_query.from_user.id,
        message_id=callback_query.message.message_id,
        reply_markup=None
    )
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query(F.data == "request_documents")
async def request_documents(callback_query: types.CallbackQuery):
    approved_users = users_df[users_df["status"] == "approved"]
    if approved_users.empty:
        await bot.send_message(callback_query.from_user.id, "Нет сотрудников.")
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=row["full_name"], callback_data=f"request_docs_{row['user_id']}")] for _, row in approved_users.iterrows()])
        await bot.send_message(callback_query.from_user.id, "Выберите сотрудника:", reply_markup=keyboard)
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query(F.data.startswith("request_docs_"))
async def process_request_documents(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split("_")[2])
    user = users_df[users_df["user_id"] == user_id]
    if not user.empty:
        await bot.send_message(user_id, "Администратор запросил документы.", reply_markup=get_role_action_keyboard(user["role"].iloc[0].lower()))
        await bot.send_message(callback_query.from_user.id, f"Запрос отправлен {user['full_name'].iloc[0]}.")
    await bot.answer_callback_query(callback_query.id)

# Запуск
async def on_startup():
    await load_db_from_drive()
    await bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}", drop_pending_updates=True)
    logger.info(f"Webhook установлен: {WEBHOOK_URL}{WEBHOOK_PATH}")
    me = await bot.get_me()
    logger.info(f"Бот подключен: {me.username}")

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
        logger.error(f"Ошибка при запуске бота: {e}")
