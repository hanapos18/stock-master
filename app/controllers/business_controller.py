"""사업장/매장 비즈니스 로직"""
from typing import Dict, List, Optional
from app.db import fetch_one, fetch_all, insert, execute


def load_businesses() -> List[Dict]:
    """모든 사업장 목록을 조회합니다."""
    return fetch_all(
        "SELECT b.*, (SELECT COUNT(*) FROM stk_stores s WHERE s.business_id = b.id) AS store_count "
        "FROM stk_businesses b ORDER BY b.id"
    )


def load_business(business_id: int) -> Optional[Dict]:
    """사업장 상세 정보를 조회합니다."""
    return fetch_one("SELECT * FROM stk_businesses WHERE id = %s", (business_id,))


def save_business(data: Dict) -> int:
    """사업장을 생성합니다."""
    return insert(
        "INSERT INTO stk_businesses (name, type, owner_name, business_number, address, phone, memo, pos_db_name) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (data["name"], data["type"], data.get("owner_name", ""),
         data.get("business_number", ""), data.get("address", ""),
         data.get("phone", ""), data.get("memo", ""), data.get("pos_db_name")),
    )


def update_business(business_id: int, data: Dict) -> int:
    """사업장 정보를 수정합니다."""
    return execute(
        "UPDATE stk_businesses SET name=%s, type=%s, owner_name=%s, business_number=%s, "
        "address=%s, phone=%s, memo=%s, pos_db_name=%s WHERE id=%s",
        (data["name"], data["type"], data.get("owner_name", ""),
         data.get("business_number", ""), data.get("address", ""),
         data.get("phone", ""), data.get("memo", ""), data.get("pos_db_name"),
         business_id),
    )


def delete_business(business_id: int) -> int:
    """사업장을 삭제합니다."""
    return execute("DELETE FROM stk_businesses WHERE id = %s", (business_id,))


# ── 매장 관련 ──

def load_stores(business_id: int) -> List[Dict]:
    """사업장의 매장 목록을 조회합니다."""
    return fetch_all(
        "SELECT * FROM stk_stores WHERE business_id = %s ORDER BY id",
        (business_id,),
    )


def load_store(store_id: int) -> Optional[Dict]:
    """매장 상세 정보를 조회합니다."""
    return fetch_one("SELECT * FROM stk_stores WHERE id = %s", (store_id,))


def save_store(data: Dict) -> int:
    """매장을 생성합니다."""
    return insert(
        "INSERT INTO stk_stores (business_id, name, address, phone, is_warehouse) VALUES (%s, %s, %s, %s, %s)",
        (data["business_id"], data["name"], data.get("address", ""),
         data.get("phone", ""), data.get("is_warehouse", 0)),
    )


def update_store(store_id: int, data: Dict) -> int:
    """매장 정보를 수정합니다."""
    return execute(
        "UPDATE stk_stores SET name=%s, address=%s, phone=%s, is_warehouse=%s WHERE id=%s",
        (data["name"], data.get("address", ""), data.get("phone", ""),
         data.get("is_warehouse", 0), store_id),
    )


def delete_store(store_id: int) -> int:
    """매장을 삭제합니다."""
    return execute("DELETE FROM stk_stores WHERE id = %s", (store_id,))
