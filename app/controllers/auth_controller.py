"""인증 비즈니스 로직"""
from typing import Optional, Dict, List
from werkzeug.security import check_password_hash, generate_password_hash
from app.db import fetch_one, fetch_all, insert


def verify_login(username: str, password: str) -> Optional[Dict]:
    """사용자 로그인을 검증합니다."""
    user = fetch_one(
        "SELECT u.*, b.name AS business_name, b.type AS business_type, b.pos_db_name "
        "FROM stk_users u JOIN stk_businesses b ON u.business_id = b.id "
        "WHERE u.username = %s AND u.is_active = 1",
        (username,),
    )
    if not user:
        return None
    if not check_password_hash(user["password_hash"], password):
        return None
    return user


def can_access_all_stores(user: Dict) -> bool:
    """사용자가 전체 매장에 접근 가능한지 확인합니다.
    - admin 역할: 항상 전체 접근
    - store_id가 NULL: 본점/관리자 (전체 접근)
    - store_id가 있으면: 해당 지점만
    """
    if user.get("role") == "admin":
        return True
    if user.get("store_id") is None:
        return True
    return False


def get_accessible_stores(user: Dict, all_stores: List[Dict]) -> List[Dict]:
    """사용자가 접근 가능한 매장 목록을 반환합니다."""
    if can_access_all_stores(user):
        return all_stores
    user_store_id = user.get("store_id")
    return [s for s in all_stores if s["id"] == user_store_id]


def get_default_store(user: Dict, accessible_stores: List[Dict]) -> Optional[Dict]:
    """로그인 시 자동 선택할 기본 매장을 반환합니다."""
    if not accessible_stores:
        return None
    user_store_id = user.get("store_id")
    if user_store_id:
        for s in accessible_stores:
            if s["id"] == user_store_id:
                return s
    return accessible_stores[0]


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
        "SELECT u.id, u.username, u.name, u.role, u.store_id, u.business_id, "
        "b.name AS business_name, b.type AS business_type, b.pos_db_name "
        "FROM stk_users u JOIN stk_businesses b ON u.business_id = b.id "
        "WHERE u.id = %s",
        (user_id,),
    )
    all_stores = fetch_all(
        "SELECT id, name, is_warehouse FROM stk_stores "
        "WHERE business_id = %s AND is_active = 1",
        (user["business_id"],),
    )
    accessible = get_accessible_stores(user, all_stores)
    default_store = get_default_store(user, accessible)
    is_hq = can_access_all_stores(user)
    return {
        "user": user,
        "stores": accessible,
        "all_stores": all_stores,
        "default_store": default_store,
        "is_hq": is_hq,
    }
