"""도매 결제/잔금 관리 DB 마이그레이션 실행 스크립트"""
import os
import sys
import pymysql

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "stock_master")


def run_migration():
    """마이그레이션을 실행합니다."""
    conn = pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER,
        password=DB_PASS, database=DB_NAME,
        charset="utf8mb4", autocommit=True,
    )
    cur = conn.cursor()
    print("=== 도매 결제/잔금 마이그레이션 시작 ===\n")

    # 1. stk_wholesale_orders에 paid_amount 추가
    print("1. stk_wholesale_orders.paid_amount 컬럼 추가...")
    try:
        cur.execute("ALTER TABLE stk_wholesale_orders ADD COLUMN paid_amount DECIMAL(16,6) DEFAULT 0")
        print("   OK paid_amount 추가 완료")
    except pymysql.err.OperationalError as e:
        if "Duplicate column" in str(e):
            print("   -- paid_amount 이미 존재")
        else:
            raise

    # 2. payment_status 추가
    print("2. stk_wholesale_orders.payment_status 컬럼 추가...")
    try:
        cur.execute(
            "ALTER TABLE stk_wholesale_orders "
            "ADD COLUMN payment_status ENUM('unpaid','partial','paid') DEFAULT 'unpaid'"
        )
        print("   OK payment_status 추가 완료")
    except pymysql.err.OperationalError as e:
        if "Duplicate column" in str(e):
            print("   -- payment_status 이미 존재")
        else:
            raise

    # 3. stk_wholesale_payments 테이블 생성
    print("3. stk_wholesale_payments 테이블 생성...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stk_wholesale_payments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            order_id INT NOT NULL,
            business_id INT NOT NULL,
            client_id INT NOT NULL,
            payment_method ENUM('cash','check','bank_transfer','credit') NOT NULL,
            amount DECIMAL(16,6) NOT NULL,
            check_date DATE NULL COMMENT 'check maturity date',
            check_number VARCHAR(50) NULL,
            bank_name VARCHAR(50) NULL,
            bank_ref VARCHAR(100) NULL COMMENT 'bank transfer reference',
            memo TEXT,
            paid_by INT NULL,
            paid_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES stk_wholesale_orders(id) ON DELETE CASCADE,
            FOREIGN KEY (business_id) REFERENCES stk_businesses(id),
            FOREIGN KEY (client_id) REFERENCES stk_wholesale_clients(id)
        ) ENGINE=InnoDB
    """)
    print("   OK stk_wholesale_payments 생성 완료")

    # 검증
    print("\n=== 검증 ===")
    cur.execute("SHOW COLUMNS FROM stk_wholesale_orders LIKE 'paid_amount'")
    print(f"  paid_amount: {'OK' if cur.fetchone() else 'FAIL'}")
    cur.execute("SHOW COLUMNS FROM stk_wholesale_orders LIKE 'payment_status'")
    print(f"  payment_status: {'OK' if cur.fetchone() else 'FAIL'}")
    cur.execute("SHOW TABLES LIKE 'stk_wholesale_payments'")
    print(f"  stk_wholesale_payments: {'OK' if cur.fetchone() else 'FAIL'}")

    cur.close()
    conn.close()
    print("\n=== 마이그레이션 완료 ===")


if __name__ == "__main__":
    run_migration()
