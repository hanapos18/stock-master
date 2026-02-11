"""매입 관리 비즈니스 로직"""
from typing import Dict, List, Optional
from app.db import fetch_one, fetch_all, insert, execute
from app.controllers.inventory_controller import process_stock_in


def load_purchases(business_id: int, status: str = "") -> List[Dict]:
    """매입 목록을 조회합니다."""
    sql = (
        "SELECT p.*, s.name AS store_name, sp.name AS supplier_name, "
        "u.name AS created_by_name "
        "FROM stk_purchases p "
        "JOIN stk_stores s ON p.store_id = s.id "
        "LEFT JOIN stk_suppliers sp ON p.supplier_id = sp.id "
        "LEFT JOIN stk_users u ON p.created_by = u.id "
        "WHERE p.business_id = %s"
    )
    params: list = [business_id]
    if status:
        sql += " AND p.status = %s"
        params.append(status)
    sql += " ORDER BY p.purchase_date DESC, p.id DESC"
    return fetch_all(sql, tuple(params))


def load_purchase(purchase_id: int) -> Optional[Dict]:
    """매입 상세를 조회합니다."""
    purchase = fetch_one(
        "SELECT p.*, s.name AS store_name, sp.name AS supplier_name "
        "FROM stk_purchases p "
        "JOIN stk_stores s ON p.store_id = s.id "
        "LEFT JOIN stk_suppliers sp ON p.supplier_id = sp.id "
        "WHERE p.id = %s",
        (purchase_id,),
    )
    if purchase:
        purchase["line_items"] = fetch_all(
            "SELECT pi.*, pr.name AS product_name, pr.code AS product_code, pr.unit "
            "FROM stk_purchase_items pi "
            "JOIN stk_products pr ON pi.product_id = pr.id "
            "WHERE pi.purchase_id = %s",
            (purchase_id,),
        )
    return purchase


def save_purchase(data: Dict, items: List[Dict]) -> int:
    """매입을 생성합니다."""
    purchase_number = _generate_purchase_number(data["business_id"])
    purchase_id = insert(
        "INSERT INTO stk_purchases "
        "(business_id, store_id, supplier_id, purchase_number, purchase_date, memo, created_by) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (data["business_id"], data["store_id"], data.get("supplier_id") or None,
         purchase_number, data["purchase_date"], data.get("memo", ""),
         data.get("created_by")),
    )
    total = _save_purchase_items(purchase_id, items)
    execute("UPDATE stk_purchases SET total_amount = %s WHERE id = %s", (total, purchase_id))
    return purchase_id


def receive_purchase(purchase_id: int, user_id: Optional[int] = None) -> bool:
    """매입을 입고 처리합니다 (재고에 반영)."""
    purchase = load_purchase(purchase_id)
    if not purchase or purchase["status"] == "received":
        return False
    for item in purchase["line_items"]:
        process_stock_in(
            product_id=item["product_id"], store_id=purchase["store_id"],
            quantity=float(item["quantity"]), unit_price=float(item["unit_price"]),
            reason=f"Purchase #{purchase['purchase_number']}",
            user_id=user_id, reference_id=purchase_id, reference_type="purchase",
        )
    execute("UPDATE stk_purchases SET status = 'received' WHERE id = %s", (purchase_id,))
    return True


def cancel_purchase(purchase_id: int) -> int:
    """매입을 취소합니다."""
    return execute("UPDATE stk_purchases SET status = 'cancelled' WHERE id = %s", (purchase_id,))


def _save_purchase_items(purchase_id: int, items: List[Dict]) -> float:
    """매입 상세 항목을 저장하고 합계를 반환합니다."""
    total = 0.0
    for item in items:
        qty = float(item["quantity"])
        price = float(item["unit_price"])
        amount = qty * price
        total += amount
        insert(
            "INSERT INTO stk_purchase_items (purchase_id, product_id, quantity, unit_price, amount) "
            "VALUES (%s, %s, %s, %s, %s)",
            (purchase_id, item["product_id"], qty, price, amount),
        )
    return total


def _generate_purchase_number(business_id: int) -> str:
    """매입 번호를 생성합니다."""
    from datetime import date
    today = date.today().strftime("%Y%m%d")
    row = fetch_one(
        "SELECT COUNT(*) AS cnt FROM stk_purchases "
        "WHERE business_id = %s AND purchase_number LIKE %s",
        (business_id, f"PO-{today}%"),
    )
    seq = (row["cnt"] or 0) + 1
    return f"PO-{today}-{seq:03d}"
