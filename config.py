"""StockMaster 앱 설정"""
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY: str = os.getenv("SECRET_KEY", "stockmaster-default-secret")
DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
DB_USER: str = os.getenv("DB_USER", "root")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
DB_NAME: str = os.getenv("DB_NAME", "stock_master")
POS_DB_NAME: str = os.getenv("POS_DB_NAME", "order_sys")
APP_PORT: int = int(os.getenv("APP_PORT", "5555"))
APP_DEBUG: bool = os.getenv("APP_DEBUG", "true").lower() == "true"
