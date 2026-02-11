"""카테고리 비즈니스 로직"""
from typing import Dict, List, Optional
from app.db import fetch_one, fetch_all, insert, execute


def load_categories(business_id: int) -> List[Dict]:
    """카테고리 목록을 조회합니다."""
    return fetch_all(
        "SELECT c.*, p.name AS parent_name, "
        "(SELECT COUNT(*) FROM stk_products pr WHERE pr.category_id = c.id) AS product_count "
        "FROM stk_categories c "
        "LEFT JOIN stk_categories p ON c.parent_id = p.id "
        "WHERE c.business_id = %s ORDER BY c.display_order, c.name",
        (business_id,),
    )


def load_category(category_id: int) -> Optional[Dict]:
    """카테고리 상세를 조회합니다."""
    return fetch_one("SELECT * FROM stk_categories WHERE id = %s", (category_id,))


def save_category(data: Dict) -> int:
    """카테고리를 생성합니다."""
    return insert(
        "INSERT INTO stk_categories (business_id, name, parent_id, display_order) "
        "VALUES (%s, %s, %s, %s)",
        (data["business_id"], data["name"], data.get("parent_id") or None,
         data.get("display_order", 0)),
    )


def update_category(category_id: int, data: Dict) -> int:
    """카테고리를 수정합니다."""
    return execute(
        "UPDATE stk_categories SET name=%s, parent_id=%s, display_order=%s WHERE id=%s",
        (data["name"], data.get("parent_id") or None, data.get("display_order", 0), category_id),
    )


def delete_category(category_id: int) -> int:
    """카테고리를 삭제합니다."""
    return execute("DELETE FROM stk_categories WHERE id = %s", (category_id,))
