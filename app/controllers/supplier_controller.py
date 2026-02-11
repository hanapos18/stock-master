"""거래처(납품업체) 비즈니스 로직"""
from typing import Dict, List, Optional
from app.db import fetch_one, fetch_all, insert, execute


def load_suppliers(business_id: int) -> List[Dict]:
    """거래처 목록을 조회합니다."""
    return fetch_all(
        "SELECT s.*, "
        "(SELECT COUNT(*) FROM stk_products p WHERE p.supplier_id = s.id) AS product_count "
        "FROM stk_suppliers s WHERE s.business_id = %s AND s.is_active = 1 ORDER BY s.name",
        (business_id,),
    )


def load_supplier(supplier_id: int) -> Optional[Dict]:
    """거래처 상세를 조회합니다."""
    return fetch_one("SELECT * FROM stk_suppliers WHERE id = %s", (supplier_id,))


def save_supplier(data: Dict) -> int:
    """거래처를 생성합니다."""
    return insert(
        "INSERT INTO stk_suppliers (business_id, name, contact_person, phone, email, address, memo) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (data["business_id"], data["name"], data.get("contact_person", ""),
         data.get("phone", ""), data.get("email", ""), data.get("address", ""),
         data.get("memo", "")),
    )


def update_supplier(supplier_id: int, data: Dict) -> int:
    """거래처를 수정합니다."""
    return execute(
        "UPDATE stk_suppliers SET name=%s, contact_person=%s, phone=%s, "
        "email=%s, address=%s, memo=%s WHERE id=%s",
        (data["name"], data.get("contact_person", ""), data.get("phone", ""),
         data.get("email", ""), data.get("address", ""), data.get("memo", ""),
         supplier_id),
    )


def delete_supplier(supplier_id: int) -> int:
    """거래처를 비활성화합니다."""
    return execute("UPDATE stk_suppliers SET is_active = 0 WHERE id = %s", (supplier_id,))
