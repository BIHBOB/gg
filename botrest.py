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

# Попытка загрузки токена
creds = None
if TOKEN_JSON:
    try:
        creds = Credentials.from_authorized_user_info(json.loads(TOKEN_JSON), SCOPES)
    except Exception as e:
        logger.error(f"Ошибка загрузки TOKEN_JSON: {e}")
elif os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
else:
    logger.warning("Файл token.json не найден, Google Drive API недоступен.")

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
            logger.info("База данных загружена с Google Drive")
        else:
            logger.info("DRIVE_FILE_ID не задан, используется пустая база")
    except Exception as e:
        logger.error(f"Ошибка загрузки базы с Google Drive: {e}")

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
            logger.info("База данных обновлена на Google...
