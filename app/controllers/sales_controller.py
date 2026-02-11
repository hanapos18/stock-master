"""자체 판매 관리 비즈니스 로직 (비POS 사용자용)"""
from typing import Dict, List, Optional
from app.db import fetch_one, fetch_all, insert, execute
from app.controllers.inventory_controller import process_stock_out


def load_sales(business_id: int, status: str = "") -> List[Dict]:
    """판매 목록을 조회합니다."""
    sql = (
        "SELECT sa.*, st.name AS store_name, u.name AS created_by_name "
        "FROM stk_sales sa "
        "JOIN stk_stores st ON sa.store_id = st.id "
        "LEFT JOIN stk_users u ON sa.created_by = u.id "
        "WHERE sa.business_id = %s"
    )
    params: list = [business_id]
    if status:
        sql += " AND sa.status = %s"
        params.append(status)
    sql += " ORDER BY sa.sale_date DESC, sa.id DESC"
    return fetch_all(sql, tuple(params))


def load_sale(sale_id: int) -> Optional[Dict]:
    """판매 상세를 조회합니다."""
    sale = fetch_one(
        "SELECT sa.*, st.name AS store_name "
        "FROM stk_sales sa JOIN stk_stores st ON sa.store_id = st.id "
        "WHERE sa.id = %s",
        (sale_id,),
    )
    if sale:
        sale["line_items"] = fetch_all(
            "SELECT si.*, p.name AS product_name, p.code AS product_code, p.unit "
            "FROM stk_sale_items si JOIN stk_products p ON si.product_id = p.id "
            "WHERE si.sale_id = %s",
            (sale_id,),
        )
    return sale


def save_sale(data: Dict, items: List[Dict]) -> int:
    """판매를 생성합니다."""
    sale_number = _generate_sale_number(data["business_id"])
    sale_id = insert(
        "INSERT INTO stk_sales "
        "(business_id, store_id, sale_number, sale_date, customer_name, memo, created_by) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (data["business_id"], data["store_id"], sale_number,
         data["sale_date"], data.get("customer_name", ""),
         data.get("memo", ""), data.get("created_by")),
    )
    total = _save_sale_items(sale_id, items)
    execute("UPDATE stk_sales SET total_amount = %s WHERE id = %s", (total, sale_id))
    return sale_id


def confirm_sale(sale_id: int, user_id: Optional[int] = None) -> bool:
    """판매를 확정하고 재고를 차감합니다."""
    sale = load_sale(sale_id)
    if not sale or sale["status"] != "draft":
        return False
    for item in sale["line_items"]:
        process_stock_out(
            product_id=item["product_id"], store_id=sale["store_id"],
            quantity=float(item["quantity"]), unit_price=float(item["unit_price"]),
            reason=f"Sale #{sale['sale_number']}",
            user_id=user_id, reference_id=sale_id, reference_type="sale",
        )
    execute("UPDATE stk_sales SET status = 'confirmed' WHERE id = %s", (sale_id,))
    return True


def cancel_sale(sale_id: int) -> int:
    """판매를 취소합니다."""
    return execute("UPDATE stk_sales SET status = 'cancelled' WHERE id = %s", (sale_id,))


def _save_sale_items(sale_id: int, items: List[Dict]) -> float:
    """판매 상세를 저장하고 합계를 반환합니다."""
    total = 0.0
    for item in items:
        qty = float(item["quantity"])
        price = float(item["unit_price"])
        amount = qty * price
        total += amount
        insert(
            "INSERT INTO stk_sale_items (sale_id, product_id, quantity, unit_price, amount) "
            "VALUES (%s, %s, %s, %s, %s)",
            (sale_id, item["product_id"], qty, price, amount),
        )
    return total


def _generate_sale_number(business_id: int) -> str:
    """판매 번호를 생성합니다."""
    from datetime import date
    today = date.today().strftime("%Y%m%d")
    row = fetch_one(
        "SELECT COUNT(*) AS cnt FROM stk_sales WHERE business_id = %s AND sale_number LIKE %s",
        (business_id, f"SA-{today}%"),
    )
    seq = (row["cnt"] or 0) + 1
    return f"SA-{today}-{seq:03d}"
