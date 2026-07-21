"""Support Request System 마이그레이션 실행"""
import pymysql
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "stock_master")

conn = pymysql.connect(
    host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS,
    database=DB_NAME, cursorclass=pymysql.cursors.DictCursor, autocommit=True
)

with conn.cursor() as cur:
    # 1) 접수 기록 테이블
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stk_support_requests (
            id INT AUTO_INCREMENT PRIMARY KEY,
            store_code VARCHAR(20) NOT NULL COMMENT 'POS 매장코드',
            store_name VARCHAR(100) DEFAULT '' COMMENT '매장명',
            terminal_id VARCHAR(20) DEFAULT '' COMMENT 'POS 터미널 ID',
            request_type ENUM('ORDER','AS') NOT NULL COMMENT '주문 또는 A/S',
            items JSON COMMENT '주문 품목 또는 장비 정보',
            memo TEXT COMMENT '요청 메모/증상 설명',
            status ENUM('PENDING','PROCESSING','DONE','REJECTED') DEFAULT 'PENDING',
            admin_note TEXT COMMENT '관리자 메모',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_store (store_code),
            INDEX idx_status (status),
            INDEX idx_created (created_at DESC)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("[OK] stk_support_requests 테이블 생성")

    # 2) 소모품 카탈로그
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stk_support_catalog (
            id INT AUTO_INCREMENT PRIMARY KEY,
            category ENUM('PAPER','RIBBON','PART','OTHER') NOT NULL DEFAULT 'OTHER',
            name VARCHAR(100) NOT NULL COMMENT '상품명',
            description VARCHAR(500) DEFAULT '' COMMENT '상품 설명',
            unit_price DECIMAL(10,2) DEFAULT 0 COMMENT '단가',
            image_url VARCHAR(500) DEFAULT '' COMMENT '상품 이미지 URL',
            is_active TINYINT(1) DEFAULT 1,
            sort_order INT DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_category (category),
            INDEX idx_active_sort (is_active, sort_order)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("[OK] stk_support_catalog 테이블 생성")

    # 3) 자가해결 유튜브 동영상
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stk_support_videos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            category ENUM('PRINTER','POS','MONITOR','DRAWER','NETWORK','OTHER') NOT NULL DEFAULT 'OTHER',
            title VARCHAR(200) NOT NULL COMMENT '동영상 제목',
            youtube_url VARCHAR(500) NOT NULL COMMENT '유튜브 URL',
            description VARCHAR(500) DEFAULT '' COMMENT '설명',
            sort_order INT DEFAULT 0,
            is_active TINYINT(1) DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_category (category),
            INDEX idx_active_sort (is_active, sort_order)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("[OK] stk_support_videos 테이블 생성")

    # 샘플 데이터 삽입 (이미 있으면 skip)
    cur.execute("SELECT COUNT(*) AS cnt FROM stk_support_catalog")
    if cur.fetchone()["cnt"] == 0:
        cur.execute("""
            INSERT INTO stk_support_catalog (category, name, description, unit_price, sort_order) VALUES
            ('PAPER', 'Thermal Paper 57mm (50 rolls)', 'Standard receipt paper for 57mm printers', 850.00, 1),
            ('PAPER', 'Thermal Paper 80mm (50 rolls)', 'Standard receipt paper for 80mm printers', 1200.00, 2),
            ('RIBBON', 'Ribbon Cartridge (Black)', 'Compatible ribbon for dot-matrix printers', 350.00, 3),
            ('PART', 'Cash Drawer Key (Spare)', 'Replacement key for standard cash drawer', 150.00, 4),
            ('PART', 'Barcode Scanner Cable (USB)', 'Replacement USB cable for barcode scanner', 250.00, 5)
        """)
        print("[OK] 카탈로그 샘플 데이터 삽입 (5건)")

    cur.execute("SELECT COUNT(*) AS cnt FROM stk_support_videos")
    if cur.fetchone()["cnt"] == 0:
        cur.execute("""
            INSERT INTO stk_support_videos (category, title, youtube_url, description, sort_order) VALUES
            ('PRINTER', 'Receipt Printer Paper Jam Fix', 'https://www.youtube.com/watch?v=example1', 'How to clear paper jam on thermal printer', 1),
            ('PRINTER', 'Printer Not Printing - Troubleshoot', 'https://www.youtube.com/watch?v=example2', 'Check connections, driver, and settings', 2),
            ('NETWORK', 'POS Network Connection Issue', 'https://www.youtube.com/watch?v=example3', 'Resolve common network problems between POS devices', 3),
            ('DRAWER', 'Cash Drawer Not Opening', 'https://www.youtube.com/watch?v=example4', 'Manual release and cable check guide', 4)
        """)
        print("[OK] 유튜브 샘플 데이터 삽입 (4건)")

# 발신자/신청자 정보 컬럼 추가
with conn.cursor() as cur:
    cur.execute("""
        ALTER TABLE stk_support_requests
            ADD COLUMN IF NOT EXISTS store_address VARCHAR(200) DEFAULT NULL COMMENT '매장 주소',
            ADD COLUMN IF NOT EXISTS store_phone VARCHAR(50) DEFAULT NULL COMMENT '매장 전화번호',
            ADD COLUMN IF NOT EXISTS requester_name VARCHAR(100) DEFAULT NULL COMMENT '신청자 이름',
            ADD COLUMN IF NOT EXISTS requester_phone VARCHAR(50) DEFAULT NULL COMMENT '신청자 연락처'
    """)
    print("[OK] requester/store contact columns added")

# 확인
with conn.cursor() as cur:
    cur.execute("SHOW TABLES LIKE 'stk_support%%'")
    tables = cur.fetchall()
    print(f"\nSupport 테이블 목록:")
    for t in tables:
        print(f"  {list(t.values())[0]}")

conn.close()
print("\nSupport 마이그레이션 완료!")
