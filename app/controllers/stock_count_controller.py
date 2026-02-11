"""실사 재고 보고 비즈니스 로직"""
from typing import Dict, List, Optional
from app.db import fetch_one, fetch_all, insert, execute
from app.controllers.inventory_controller import process_stock_adjust


def load_stock_counts(business_id: int) -> List[Dict]:
    """실사 보고 목록을 조회합니다."""
    return fetch_all(
        "SELECT sc.*, s.name AS store_name, c.name AS category_name, "
        "u.name AS created_by_name, "
        "(SELECT COUNT(*) FROM stk_stock_count_items sci WHERE sci.stock_count_id = sc.id) AS item_count "
        "FROM stk_stock_counts sc "
        "JOIN stk_stores s ON sc.store_id = s.id "
        "LEFT JOIN stk_categories c ON sc.category_id = c.id "
        "LEFT JOIN stk_users u ON sc.created_by = u.id "
        "WHERE sc.business_id = %s ORDER BY sc.count_date DESC",
        (business_id,),
    )


def load_stock_count(count_id: int) -> Optional[Dict]:
    """실사 보고 상세를 조회합니다."""
    count = fetch_one(
        "SELECT sc.*, s.name AS store_name, c.name AS category_name "
        "FROM stk_stock_counts sc "
        "JOIN stk_stores s ON sc.store_id = s.id "
        "LEFT JOIN stk_categories c ON sc.category_id = c.id "
        "WHERE sc.id = %s",
        (count_id,),
    )
    if count:
        count["line_items"] = fetch_all(
            "SELECT sci.*, p.name AS product_name, p.code AS product_code, p.unit "
            "FROM stk_stock_count_items sci "
            "JOIN stk_products p ON sci.product_id = p.id "
            "WHERE sci.stock_count_id = %s ORDER BY p.name",
            (count_id,),
        )
    return count


def create_stock_count(data: Dict) -> int:
    """실사 보고를 생성합니다 (시스템 재고 자동 로드)."""
    count_id = insert(
        "INSERT INTO stk_stock_counts (business_id, store_id, count_date, category_id, memo, created_by) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (data["business_id"], data["store_id"], data["count_date"],
         data.get("category_id") or None, data.get("memo", ""), data.get("created_by")),
    )
    _load_system_quantities(count_id, data["store_id"], data.get("category_id"))
    return count_id


def update_stock_count_items(count_id: int, items: List[Dict]) -> None:
    """실사 수량을 업데이트합니다."""
    for item in items:
        execute(
            "UPDATE stk_stock_count_items SET actual_quantity=%s, "
            "difference = %s - system_quantity, memo=%s WHERE id=%s",
            (item["actual_quantity"], item["actual_quantity"], item.get("memo", ""), item["id"]),
        )


def approve_stock_count(count_id: int, user_id: Optional[int] = None) -> bool:
    """실사를 승인하고 재고를 조정합니다."""
    count = load_stock_count(count_id)
    if not count or count["status"] == "approved":
        return False
    for item in count["line_items"]:
        diff = float(item["actual_quantity"]) - float(item["system_quantity"])
        if diff != 0:
            process_stock_adjust(
                product_id=item["product_id"], store_id=count["store_id"],
                new_quantity=float(item["actual_quantity"]),
                reason=f"Stock count #{count_id}: {item.get('memo', '')}",
                user_id=user_id,
            )
    execute("UPDATE stk_stock_counts SET status = 'approved' WHERE id = %s", (count_id,))
    return True


def _load_system_quantities(count_id: int, store_id: int, category_id: Optional[int] = None) -> None:
    """시스템 재고를 실사 항목에 로드합니다."""
    sql = (
        "SELECT i.product_id, SUM(i.quantity) AS total_qty "
        "FROM stk_inventory i "
        "JOIN stk_products p ON i.product_id = p.id "
        "WHERE i.store_id = %s AND p.is_active = 1"
    )
    params: list = [store_id]
    if category_id:
        sql += " AND p.category_id = %s"
        params.append(category_id)
    sql += " GROUP BY i.product_id"
    rows = fetch_all(sql, tuple(params))
    for row in rows:
        insert(
            "INSERT INTO stk_stock_count_items "
            "(stock_count_id, product_id, system_quantity, actual_quantity, difference) "
            "VALUES (%s, %s, %s, %s, 0)",
            (count_id, row["product_id"], row["total_qty"], row["total_qty"]),
        )
