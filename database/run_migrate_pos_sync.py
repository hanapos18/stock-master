"""POS 연동 마이그레이션 실행"""
import pymysql

DB_PASS = "manila72"
conn = pymysql.connect(host="localhost", port=3306, user="root", password=DB_PASS,
                       database="stock_master", cursorclass=pymysql.cursors.DictCursor,
                       autocommit=True)

with conn.cursor() as cur:
    # 1) 상품코드 M 접두어 제거
    cur.execute("SELECT COUNT(*) AS cnt FROM stk_products WHERE code LIKE 'M%%'")
    cnt = cur.fetchone()["cnt"]
    print(f"M 접두어 상품 수: {cnt}")
    if cnt > 0:
        cur.execute("UPDATE stk_products SET code = SUBSTRING(code, 2) WHERE code LIKE 'M%%'")
        print(f"  [OK] M 접두어 제거 완료 ({cnt}건)")

    # 2) POS 동기화 로그 테이블
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stk_pos_sync_log (
            id INT AUTO_INCREMENT PRIMARY KEY,
            business_id INT NOT NULL,
            pos_table VARCHAR(50) NOT NULL COMMENT 'sale_items or stock_transactions',
            pos_last_id INT NOT NULL DEFAULT 0 COMMENT 'last synced POS record id',
            synced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            record_count INT DEFAULT 0 COMMENT 'records synced in this batch',
            FOREIGN KEY (business_id) REFERENCES stk_businesses(id) ON DELETE CASCADE
        ) ENGINE=InnoDB
    """)
    print("  [OK] stk_pos_sync_log 테이블 생성")

    # 3) POS 동기화 상세 로그
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stk_pos_sync_detail (
            id INT AUTO_INCREMENT PRIMARY KEY,
            business_id INT NOT NULL,
            pos_table VARCHAR(50) NOT NULL,
            pos_record_id INT NOT NULL,
            sync_type VARCHAR(20) NOT NULL COMMENT 'sale, stock_in, loss',
            menu_code VARCHAR(50),
            quantity DECIMAL(10,2),
            status VARCHAR(20) DEFAULT 'success' COMMENT 'success, skipped, error',
            error_message TEXT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_pos_record (pos_table, pos_record_id),
            INDEX idx_business_date (business_id, created_at)
        ) ENGINE=InnoDB
    """)
    print("  [OK] stk_pos_sync_detail 테이블 생성")

# 확인
with conn.cursor() as cur:
    cur.execute("SELECT code FROM stk_products LIMIT 10")
    rows = cur.fetchall()
    print(f"\n상품코드 샘플:")
    for r in rows:
        print(f"  code: {r['code']}")

    cur.execute("SHOW TABLES LIKE 'stk_pos_sync%%'")
    tables = cur.fetchall()
    print(f"\n동기화 테이블:")
    for t in tables:
        print(f"  {list(t.values())[0]}")

conn.close()
print("\n마이그레이션 완료")
