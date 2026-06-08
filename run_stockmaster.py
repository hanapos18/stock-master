"""Hana StockMaster 앱 실행 진입점"""
import sys
import io
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import config
from app import create_app

app = create_app()

if __name__ == "__main__":
    print("=" * 50)
    print("  Hana StockMaster - 재고 관리 시스템")
    print("=" * 50)
    print(f"  주소: http://localhost:{config.APP_PORT}")
    print(f"  DB:   {config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}")
    print("=" * 50)
    app.run(
        host="0.0.0.0",
        port=config.APP_PORT,
        debug=config.APP_DEBUG,
    )
