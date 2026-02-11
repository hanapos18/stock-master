"""인증 비즈니스 로직"""
from typing import Optional, Dict
from werkzeug.security import check_password_hash, generate_password_hash
from app.db import fetch_one, fetch_all, insert


def verify_login(username: str, password: str) -> Optional[Dict]:
    """사용자 로그인을 검증합니다."""
    user = fetch_one(
        "SELECT u.*, b.name AS business_name, b.type AS business_type "
        "FROM stk_users u JOIN stk_businesses b ON u.business_id = b.id "
        "WHERE u.username = %s AND u.is_active = 1",
        (username,),
    )
    if not user:
        return None
    if not check_password_hash(user["password_hash"], password):
        return None
    return user


def create_initial_admin(username: str, password: str, business_name: str, business_type: str) -> Dict:
    """초기 설정 시 관리자 계정과 사업장을 생성합니다."""
    business_id = insert(
        "INSERT INTO stk_businesses (name, type, owner_name) VALUES (%s, %s, %s)",
        (business_name, business_type, "Admin"),
    )
    insert(
        "INSERT INTO stk_stores (business_id, name) VALUES (%s, %s)",
        (business_id, "Main Store"),
    )
    password_hash = generate_password_hash(password)
    user_id = insert(
        "INSERT INTO stk_users (business_id, username, password_hash, name, role) "
        "VALUES (%s, %s, %s, %s, %s)",
        (business_id, username, password_hash, "Administrator", "admin"),
    )
    return {"user_id": user_id, "business_id": business_id}


def has_any_user() -> bool:
    """사용자가 존재하는지 확인합니다."""
    row = fetch_one("SELECT COUNT(*) AS cnt FROM stk_users")
    return row["cnt"] > 0 if row else False


def load_user_session_data(user_id: int) -> Dict:
    """세션에 저장할 사용자 정보를 로드합니다."""
    user = fetch_one(
        "SELECT u.id, u.username, u.name, u.role, u.business_id, "
        "b.name AS business_name, b.type AS business_type, b.pos_db_name "
        "FROM stk_users u JOIN stk_businesses b ON u.business_id = b.id "
        "WHERE u.id = %s",
        (user_id,),
    )
    stores = fetch_all(
        "SELECT id, name FROM stk_stores WHERE business_id = %s AND is_active = 1",
        (user["business_id"],),
    )
    return {"user": user, "stores": stores}
