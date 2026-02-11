"""매장 간 이동(Inter-Store Transfer) DB 마이그레이션 실행 스크립트"""
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
    print("=== 매장 간 이동 마이그레이션 시작 ===\n")

    # 1. stk_stores에 is_warehouse 컬럼 추가
    print("1. stk_stores.is_warehouse 컬럼 추가...")
    try:
        cur.execute("ALTER TABLE stk_stores ADD COLUMN is_warehouse TINYINT(1) DEFAULT 0")
        print("   ✅ is_warehouse 컬럼 추가 완료")
    except pymysql.err.OperationalError as e:
        if "Duplicate column" in str(e):
            print("   ⏭️ is_warehouse 컬럼 이미 존재")
        else:
            raise

    # 2. stk_transactions type ENUM 확장
    print("2. stk_transactions type ENUM 확장 (transfer_out, transfer_in)...")
    cur.execute(
        "ALTER TABLE stk_transactions "
        "MODIFY COLUMN type ENUM('in','out','adjust','discard','move','sale','transfer_out','transfer_in') NOT NULL"
    )
    print("   ✅ ENUM 확장 완료")

    # 3. stk_transfers 테이블 생성
    print("3. stk_transfers 테이블 생성...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stk_transfers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            business_id INT NOT NULL,
            from_store_id INT NOT NULL,
            to_store_id INT NOT NULL,
            status ENUM('pending','shipped','received','cancelled') DEFAULT 'pending',
            requested_by INT NULL,
            shipped_by INT NULL,
            received_by INT NULL,
            shipped_at DATETIME NULL,
            received_at DATETIME NULL,
            memo TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES stk_businesses(id),
            FOREIGN KEY (from_store_id) REFERENCES stk_stores(id),
            FOREIGN KEY (to_store_id) REFERENCES stk_stores(id)
        ) ENGINE=InnoDB
    """)
    print("   ✅ stk_transfers 테이블 생성 완료")

    # 4. stk_transfer_items 테이블 생성
    print("4. stk_transfer_items 테이블 생성...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stk_transfer_items (
            id INT AUTO_INCREMENT PRIMARY KEY,
            transfer_id INT NOT NULL,
            product_id INT NOT NULL,
            inventory_id INT NULL COMMENT 'source lot inventory ID',
            quantity DECIMAL(10,4) NOT NULL,
            received_quantity DECIMAL(10,4) NULL COMMENT 'actual received qty',
            expiry_date DATE NULL,
            location VARCHAR(50) DEFAULT 'warehouse',
            FOREIGN KEY (transfer_id) REFERENCES stk_transfers(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES stk_products(id)
        ) ENGINE=InnoDB
    """)
    print("   ✅ stk_transfer_items 테이블 생성 완료")

    # 검증
    print("\n=== 검증 ===")
    cur.execute("SHOW COLUMNS FROM stk_stores LIKE 'is_warehouse'")
    row = cur.fetchone()
    print(f"  stk_stores.is_warehouse: {'✅ 존재' if row else '❌ 없음'}")

    cur.execute("SHOW COLUMNS FROM stk_transactions LIKE 'type'")
    row = cur.fetchone()
    print(f"  stk_transactions.type: {row[1] if row else '❌ 없음'}")

    cur.execute("SHOW TABLES LIKE 'stk_transfers'")
    print(f"  stk_transfers: {'✅ 존재' if cur.fetchone() else '❌ 없음'}")

    cur.execute("SHOW TABLES LIKE 'stk_transfer_items'")
    print(f"  stk_transfer_items: {'✅ 존재' if cur.fetchone() else '❌ 없음'}")

    cur.close()
    conn.close()
    print("\n=== 마이그레이션 완료 ===")


if __name__ == "__main__":
    run_migration()
