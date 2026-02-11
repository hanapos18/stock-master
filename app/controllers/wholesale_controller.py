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


# ── 결제/잔금 ──

def record_payment(order_id: int, data: Dict) -> int:
    """결제를 등록하고 주문의 결제 상태를 갱신합니다."""
    payment_id = insert(
        "INSERT INTO stk_wholesale_payments "
        "(order_id, business_id, client_id, payment_method, amount, "
        "check_date, check_number, bank_name, bank_ref, memo, paid_by) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (order_id, data["business_id"], data["client_id"],
         data["payment_method"], data["amount"],
         data.get("check_date") or None, data.get("check_number") or None,
         data.get("bank_name") or None, data.get("bank_ref") or None,
         data.get("memo", ""), data.get("paid_by")),
    )
    _update_payment_status(order_id)
    print(f"결제 등록: order_id={order_id}, method={data['payment_method']}, amount={data['amount']}")
    return payment_id


def _update_payment_status(order_id: int) -> None:
    """주문의 결제 상태를 자동 갱신합니다."""
    order = fetch_one(
        "SELECT final_amount FROM stk_wholesale_orders WHERE id = %s",
        (order_id,),
    )
    if not order:
        return
    total_paid = fetch_one(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM stk_wholesale_payments WHERE order_id = %s",
        (order_id,),
    )
    paid = float(total_paid["total"]) if total_paid else 0
    final = float(order["final_amount"])
    if paid <= 0:
        status = "unpaid"
    elif paid >= final:
        status = "paid"
    else:
        status = "partial"
    execute(
        "UPDATE stk_wholesale_orders SET paid_amount = %s, payment_status = %s WHERE id = %s",
        (paid, status, order_id),
    )


def load_order_payments(order_id: int) -> List[Dict]:
    """주문의 결제 내역을 조회합니다."""
    return fetch_all(
        "SELECT wp.*, u.name AS paid_by_name "
        "FROM stk_wholesale_payments wp "
        "LEFT JOIN stk_users u ON wp.paid_by = u.id "
        "WHERE wp.order_id = %s ORDER BY wp.paid_at DESC",
        (order_id,),
    )


def load_client_balance(client_id: int) -> Dict:
    """거래처별 미수금 잔고를 조회합니다."""
    row = fetch_one(
        "SELECT "
        "COALESCE(SUM(wo.final_amount), 0) AS total_order, "
        "COALESCE(SUM(wo.paid_amount), 0) AS total_paid "
        "FROM stk_wholesale_orders wo "
        "WHERE wo.client_id = %s AND wo.status NOT IN ('cancelled','draft')",
        (client_id,),
    )
    total_order = float(row["total_order"]) if row else 0
    total_paid = float(row["total_paid"]) if row else 0
    return {
        "total_order": total_order,
        "total_paid": total_paid,
        "balance": total_order - total_paid,
    }


def load_client_balances(business_id: int) -> List[Dict]:
    """사업장 전체 거래처별 미수금 요약을 조회합니다."""
    return fetch_all(
        "SELECT wc.id, wc.name, wc.phone, "
        "COALESCE(SUM(wo.final_amount), 0) AS total_order, "
        "COALESCE(SUM(wo.paid_amount), 0) AS total_paid, "
        "COALESCE(SUM(wo.final_amount), 0) - COALESCE(SUM(wo.paid_amount), 0) AS balance, "
        "COUNT(wo.id) AS order_count "
        "FROM stk_wholesale_clients wc "
        "LEFT JOIN stk_wholesale_orders wo ON wo.client_id = wc.id "
        "AND wo.status NOT IN ('cancelled','draft') "
        "WHERE wc.business_id = %s AND wc.is_active = 1 "
        "GROUP BY wc.id ORDER BY balance DESC",
        (business_id,),
    )


def load_client_payment_history(client_id: int) -> List[Dict]:
    """거래처의 전체 결제 내역을 조회합니다."""
    return fetch_all(
        "SELECT wp.*, wo.order_number, wo.order_date, wo.final_amount AS order_final, "
        "u.name AS paid_by_name "
        "FROM stk_wholesale_payments wp "
        "JOIN stk_wholesale_orders wo ON wp.order_id = wo.id "
        "LEFT JOIN stk_users u ON wp.paid_by = u.id "
        "WHERE wp.client_id = %s ORDER BY wp.paid_at DESC",
        (client_id,),
    )


def load_client_orders_with_balance(client_id: int) -> List[Dict]:
    """거래처의 주문 목록을 잔금 포함하여 조회합니다."""
    return fetch_all(
        "SELECT wo.*, "
        "(wo.final_amount - wo.paid_amount) AS balance "
        "FROM stk_wholesale_orders wo "
        "WHERE wo.client_id = %s AND wo.status NOT IN ('cancelled','draft') "
        "ORDER BY wo.order_date DESC",
        (client_id,),
    )


def load_check_schedule(business_id: int) -> List[Dict]:
    """수표 만기 스케줄을 조회합니다."""
    return fetch_all(
        "SELECT wp.*, wo.order_number, wc.name AS client_name "
        "FROM stk_wholesale_payments wp "
        "JOIN stk_wholesale_orders wo ON wp.order_id = wo.id "
        "JOIN stk_wholesale_clients wc ON wp.client_id = wc.id "
        "WHERE wp.business_id = %s AND wp.payment_method = 'check' "
        "AND wp.check_date IS NOT NULL "
        "ORDER BY wp.check_date ASC",
        (business_id,),
    )


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
