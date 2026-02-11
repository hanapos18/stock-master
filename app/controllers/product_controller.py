"""상품/식자재 비즈니스 로직"""
from typing import Dict, List, Optional
from app.db import fetch_one, fetch_all, insert, execute


def load_products(business_id: int, category_id: Optional[int] = None,
                  search: str = "", active_only: bool = True) -> List[Dict]:
    """상품 목록을 조회합니다."""
    sql = (
        "SELECT p.*, c.name AS category_name, s.name AS supplier_name "
        "FROM stk_products p "
        "LEFT JOIN stk_categories c ON p.category_id = c.id "
        "LEFT JOIN stk_suppliers s ON p.supplier_id = s.id "
        "WHERE p.business_id = %s"
    )
    params: list = [business_id]
    if active_only:
        sql += " AND p.is_active = 1"
    if category_id:
        sql += " AND p.category_id = %s"
        params.append(category_id)
    if search:
        sql += " AND (p.name LIKE %s OR p.code LIKE %s OR p.barcode LIKE %s)"
        like = f"%{search}%"
        params.extend([like, like, like])
    sql += " ORDER BY p.name"
    return fetch_all(sql, tuple(params))


def load_product(product_id: int) -> Optional[Dict]:
    """상품 상세 정보를 조회합니다."""
    return fetch_one(
        "SELECT p.*, c.name AS category_name, s.name AS supplier_name "
        "FROM stk_products p "
        "LEFT JOIN stk_categories c ON p.category_id = c.id "
        "LEFT JOIN stk_suppliers s ON p.supplier_id = s.id "
        "WHERE p.id = %s",
        (product_id,),
    )


def save_product(data: Dict) -> int:
    """상품을 생성합니다."""
    return insert(
        "INSERT INTO stk_products "
        "(business_id, category_id, supplier_id, code, barcode, name, description, "
        "storage_location, unit, unit_price, sell_price, min_stock, max_stock) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (data["business_id"], data.get("category_id") or None,
         data.get("supplier_id") or None, data["code"], data.get("barcode", ""),
         data["name"], data.get("description", ""),
         data.get("storage_location", ""), data.get("unit", "ea"),
         data.get("unit_price", 0), data.get("sell_price", 0),
         data.get("min_stock", 0), data.get("max_stock") or None),
    )


def update_product(product_id: int, data: Dict) -> int:
    """상품 정보를 수정합니다."""
    return execute(
        "UPDATE stk_products SET category_id=%s, supplier_id=%s, code=%s, barcode=%s, "
        "name=%s, description=%s, storage_location=%s, unit=%s, unit_price=%s, "
        "sell_price=%s, min_stock=%s, max_stock=%s WHERE id=%s",
        (data.get("category_id") or None, data.get("supplier_id") or None,
         data["code"], data.get("barcode", ""), data["name"],
         data.get("description", ""), data.get("storage_location", ""),
         data.get("unit", "ea"), data.get("unit_price", 0),
         data.get("sell_price", 0), data.get("min_stock", 0),
         data.get("max_stock") or None, product_id),
    )


def delete_product(product_id: int) -> int:
    """상품을 비활성화합니다."""
    return execute("UPDATE stk_products SET is_active = 0 WHERE id = %s", (product_id,))


def generate_product_code(business_id: int) -> str:
    """다음 상품 코드를 자동 생성합니다."""
    row = fetch_one(
        "SELECT MAX(CAST(SUBSTRING(code, 2) AS UNSIGNED)) AS max_num "
        "FROM stk_products WHERE business_id = %s AND code REGEXP '^P[0-9]+$'",
        (business_id,),
    )
    next_num = (row["max_num"] or 0) + 1 if row else 1
    return f"P{next_num:04d}"
