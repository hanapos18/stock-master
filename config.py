"""Hana StockMaster 앱 설정"""
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
POS_API_KEY: str = os.getenv("POS_API_KEY", "")

# ESC/POS Receipt Printer (IP Socket)
PRINTER_IP: str = os.getenv("PRINTER_IP", "")
PRINTER_PORT: int = int(os.getenv("PRINTER_PORT", "9100"))
PRINTER_WIDTH: int = int(os.getenv("PRINTER_WIDTH", "40"))  # 20 or 40 chars
PRINTER_ENCODING: str = os.getenv("PRINTER_ENCODING", "euc-kr")  # euc-kr for Korean

# Baekwon POS (Firebird 1.5) Bridge
BAEKWON_POS_API_KEY: str = os.getenv("BAEKWON_POS_API_KEY", "baekwon-bridge-key")
BAEKWON_SYNC_ENABLED: bool = os.getenv("BAEKWON_SYNC_ENABLED", "true").lower() == "true"
