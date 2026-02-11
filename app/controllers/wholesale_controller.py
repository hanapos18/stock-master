"""도매 관리 비즈니스 로직 (마트용)"""
from typing import Dict, List, Optional
from app.db import fetch_one, fetch_all, insert, execute
from app.controllers.inventory_controller import process_stock_out


# ── 도매 거래처 ──

def load_wholesale_clients(business_id: int) -> List[Dict]:
    """도매 거래처 목록을 조회합니다."""
    return fetch_all(
        "SELECT * FROM stk_wholesale_clients "
        "WHERE business_id = %s AND is_active = 1 ORDER BY name",
        (business_id,),
    )


def load_wholesale_client(client_id: int) -> Optional[Dict]:
    """도매 거래처 상세를 조회합니다."""
    client = fetch_one("SELECT * FROM stk_wholesale_clients WHERE id = %s", (client_id,))
    if client:
        client["pricing"] = fetch_all(
            "SELECT wp.*, p.name AS product_name, p.code AS product_code, p.sell_price "
            "FROM stk_wholesale_pricing wp "
            "JOIN stk_products p ON wp.product_id = p.id "
            "WHERE wp.client_id = %s",
            (client_id,),
        )
    return client


def save_wholesale_client(data: Dict) -> int:
    """도매 거래처를 생성합니다."""
    return insert(
        "INSERT INTO stk_wholesale_clients "
        "(business_id, name, contact_person, phone, email, address, default_discount_rate, memo) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (data["business_id"], data["name"], data.get("contact_person", ""),
         data.get("phone", ""), data.get("email", ""), data.get("address", ""),
         data.get("default_discount_rate", 0), data.get("memo", "")),
    )


def update_wholesale_client(client_id: int, data: Dict) -> int:
    """도매 거래처를 수정합니다."""
    return execute(
        "UPDATE stk_wholesale_clients SET name=%s, contact_person=%s, phone=%s, "
        "email=%s, address=%s, default_discount_rate=%s, memo=%s WHERE id=%s",
        (data["name"], data.get("contact_person", ""), data.get("phone", ""),
         data.get("email", ""), data.get("address", ""),
         data.get("default_discount_rate", 0), data.get("memo", ""), client_id),
    )


# ── 업체별 할인가 ──

def save_wholesale_pricing(client_id: int, product_id: int, data: Dict) -> int:
    """업체별 상품 할인가를 설정합니다."""
    return insert(
        "INSERT INTO stk_wholesale_pricing "
        "(client_id, product_id, discount_type, discount_rate, fixed_price) "
        "VALUES (%s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE discount_type=%s, discount_rate=%s, fixed_price=%s",
        (client_id, product_id, data.get("discount_type", "rate"),
         data.get("discount_rate", 0), data.get("fixed_price"),
         data.get("discount_type", "rate"), data.get("discount_rate", 0),
         data.get("fixed_price")),
    )


# ── 도매 주문 ──

def load_wholesale_orders(business_id: int, status: str = "") -> List[Dict]:
    """도매 주문 목록을 조회합니다."""
    sql = (
        "SELECT wo.*, wc.name AS client_name, s.name AS store_name "
        "FROM stk_wholesale_orders wo "
        "JOIN stk_wholesale_clients wc ON wo.client_id = wc.id "
        "JOIN stk_stores s ON wo.store_id = s.id "
        "WHERE wo.business_id = %s"
    )
    params: list = [business_id]
    if status:
        sql += " AND wo.status = %s"
        params.append(status)
    sql += " ORDER BY wo.order_date DESC, wo.id DESC"
    return fetch_all(sql, tuple(params))


def load_wholesale_order(order_id: int) -> Optional[Dict]:
    """도매 주문 상세를 조회합니다."""
    order = fetch_one(
        "SELECT wo.*, wc.name AS client_name, wc.address AS client_address, "
        "wc.phone AS client_phone, s.name AS store_name "
        "FROM stk_wholesale_orders wo "
        "JOIN stk_wholesale_clients wc ON wo.client_id = wc.id "
        "JOIN stk_stores s ON wo.store_id = s.id "
        "WHERE wo.id = %s",
        (order_id,),
    )
    if order:
        order["line_items"] = fetch_all(
            "SELECT woi.*, p.name AS product_name, p.code AS product_code, p.unit "
            "FROM stk_wholesale_order_items woi "
            "JOIN stk_products p ON woi.product_id = p.id "
            "WHERE woi.order_id = %s",
            (order_id,),
        )
    return order


def save_wholesale_order(data: Dict, items: List[Dict]) -> int:
    """도매 주문을 생성합니다."""
    order_number = _generate_order_number(data["business_id"])
    order_id = insert(
        "INSERT INTO stk_wholesale_orders "
        "(business_id, store_id, client_id, order_number, order_date, delivery_date, memo, created_by) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (data["business_id"], data["store_id"], data["client_id"],
         order_number, data["order_date"], data.get("delivery_date"),
         data.get("memo", ""), data.get("created_by")),
    )
    totals = _save_order_items(order_id, data["client_id"], items)
    execute(
        "UPDATE stk_wholesale_orders SET total_amount=%s, discount_amount=%s, final_amount=%s WHERE id=%s",
        (totals["total"], totals["discount"], totals["final"], order_id),
    )
    return order_id


def ship_wholesale_order(order_id: int, user_id: Optional[int] = None) -> bool:
    """도매 주문을 출고 처리합니다."""
    order = load_wholesale_order(order_id)
    if not order or order["status"] in ("shipped", "delivered", "cancelled"):
        return False
    for item in order["line_items"]:
        process_stock_out(
            product_id=item["product_id"], store_id=order["store_id"],
            quantity=float(item["quantity"]), unit_price=float(item["unit_price"]),
            reason=f"Wholesale #{order['order_number']} → {order['client_name']}",
            user_id=user_id, reference_id=order_id, reference_type="wholesale_order",
        )
    execute("UPDATE stk_wholesale_orders SET status = 'shipped' WHERE id = %s", (order_id,))
    return True


def _save_order_items(order_id: int, client_id: int, items: List[Dict]) -> Dict:
    """주문 상세를 저장하고 합계를 반환합니다."""
    total = 0.0
    discount_total = 0.0
    for item in items:
        qty = float(item["quantity"])
        price = float(item["unit_price"])
        pricing = fetch_one(
            "SELECT * FROM stk_wholesale_pricing WHERE client_id=%s AND product_id=%s",
            (client_id, item["product_id"]),
        )
        disc_rate = float(pricing["discount_rate"]) if pricing and pricing["discount_type"] == "rate" else 0
        if pricing and pricing["discount_type"] == "fixed_price" and pricing["fixed_price"]:
            price = float(pricing["fixed_price"])
            disc_rate = 0
        disc_amount = qty * price * disc_rate / 100
        amount = qty * price - disc_amount
        total += qty * price
        discount_total += disc_amount
        insert(
            "INSERT INTO stk_wholesale_order_items "
            "(order_id, product_id, quantity, unit_price, discount_rate, discount_amount, amount) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (order_id, item["product_id"], qty, price, disc_rate, disc_amount, amount),
        )
    return {"total": total, "discount": discount_total, "final": total - discount_total}


def _generate_order_number(business_id: int) -> str:
    """도매 주문 번호를 생성합니다."""
    from datetime import date
    today = date.today().strftime("%Y%m%d")
    row = fetch_one(
        "SELECT COUNT(*) AS cnt FROM stk_wholesale_orders "
        "WHERE business_id = %s AND order_number LIKE %s",
        (business_id, f"WO-{today}%"),
    )
    seq = (row["cnt"] or 0) + 1
    return f"WO-{today}-{seq:03d}"
