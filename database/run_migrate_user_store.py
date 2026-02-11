# -*- coding: utf-8 -*-
"""사용자 소속 매장 마이그레이션 실행"""
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

conn = pymysql.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", 3306)),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", ""),
    database=os.getenv("DB_NAME", "stock_master"),
    charset="utf8mb4",
)

try:
    with conn.cursor() as cur:
        # store_id 컬럼 존재 여부 확인
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='stk_users' AND COLUMN_NAME='store_id'",
            (os.getenv("DB_NAME", "stock_master"),),
        )
        exists = cur.fetchone()[0]
        if exists:
            print("store_id 컬럼이 이미 존재합니다. 스킵합니다.")
        else:
            cur.execute(
                "ALTER TABLE stk_users "
                "ADD COLUMN store_id INT NULL DEFAULT NULL AFTER role"
            )
            # FK 추가 시도 (이미 있으면 무시)
            try:
                cur.execute(
                    "ALTER TABLE stk_users "
                    "ADD CONSTRAINT fk_users_store FOREIGN KEY (store_id) "
                    "REFERENCES stk_stores(id) ON DELETE SET NULL"
                )
            except Exception as e:
                print(f"FK 추가 참고: {e}")
            conn.commit()
            print("store_id 컬럼 추가 완료!")

        # 현재 사용자 확인
        cur.execute("SELECT id, username, role, store_id FROM stk_users")
        users = cur.fetchall()
        print(f"\n현재 사용자 목록 ({len(users)}명):")
        for u in users:
            store_label = "전체(본점)" if u[3] is None else f"매장ID={u[3]}"
            print(f"  - {u[1]} (role={u[2]}, {store_label})")
finally:
    conn.close()
