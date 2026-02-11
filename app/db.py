"""MariaDB 데이터베이스 연결 관리"""
from typing import Optional, Dict, List, Any
import pymysql
import pymysql.cursors
from flask import Flask, g

_db_config: Dict[str, Any] = {}


def init_db(application: Flask) -> None:
    """앱 설정에서 DB 연결 정보를 초기화합니다."""
    import config
    _db_config.update({
        "host": config.DB_HOST,
        "port": config.DB_PORT,
        "user": config.DB_USER,
        "password": config.DB_PASSWORD,
        "database": config.DB_NAME,
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": True,
    })
    application.teardown_appcontext(_close_db)


def get_db() -> pymysql.connections.Connection:
    """현재 요청의 DB 연결을 반환합니다 (없으면 새로 생성, 끊기면 재연결)."""
    if "db" not in g:
        g.db = pymysql.connect(**_db_config)
    else:
        try:
            g.db.ping(reconnect=True)
        except Exception:
            g.db = pymysql.connect(**_db_config)
    return g.db


def _close_db(exception: Optional[Exception] = None) -> None:
    """요청 종료 시 DB 연결을 닫습니다."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def fetch_one(sql: str, params: tuple = ()) -> Optional[Dict]:
    """단일 행을 조회합니다."""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def fetch_all(sql: str, params: tuple = ()) -> List[Dict]:
    """여러 행을 조회합니다."""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def execute(sql: str, params: tuple = ()) -> int:
    """INSERT/UPDATE/DELETE를 실행하고 영향받은 행 수를 반환합니다."""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount


def insert(sql: str, params: tuple = ()) -> int:
    """INSERT를 실행하고 생성된 ID를 반환합니다."""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.lastrowid


def execute_pos_db(sql: str, params: tuple = (), db_name: Optional[str] = None) -> List[Dict]:
    """POS 데이터베이스에서 조회합니다 (읽기 전용)."""
    import config
    pos_db = db_name or config.POS_DB_NAME
    pos_config = {**_db_config, "database": pos_db}
    conn = pymysql.connect(**pos_config)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()
