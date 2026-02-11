"""재고 관리 비즈니스 로직 (유통기한/FEFO 지원)"""
from datetime import date
from typing import Dict, List, Optional
from app.db import fetch_one, fetch_all, insert, execute


def load_inventory(store_id: int, category_id: Optional[int] = None,
                   search: str = "", low_stock_only: bool = False) -> List[Dict]:
    """매장별 재고 현황을 조회합니다 (유통기한별 로트 포함)."""
    sql = (
        "SELECT i.*, p.name AS product_name, p.code AS product_code, "
        "p.unit, p.min_stock, p.unit_price, p.sell_price, "
        "c.name AS category_name "
        "FROM stk_inventory i "
        "JOIN stk_products p ON i.product_id = p.id "
        "LEFT JOIN stk_categories c ON p.category_id = c.id "
        "WHERE i.store_id = %s AND p.is_active = 1"
    )
    params: list = [store_id]
    if category_id:
        sql += " AND p.category_id = %s"
        params.append(category_id)
    if search:
        sql += " AND (p.name LIKE %s OR p.code LIKE %s)"
        like = f"%{search}%"
        params.extend([like, like])
    if low_stock_only:
        sql += " AND i.quantity <= p.min_stock"
    sql += " ORDER BY p.name, i.expiry_date ASC"
    return fetch_all(sql, tuple(params))


def load_inventory_summary(business_id: int, store_id: int = None) -> Dict:
    """사업장(또는 특정 매장) 재고 요약을 조회합니다."""
    if store_id:
        total = fetch_one(
            "SELECT COUNT(DISTINCT i.product_id) AS product_count, "
            "COALESCE(SUM(i.quantity), 0) AS total_quantity "
            "FROM stk_inventory i "
            "JOIN stk_products p ON i.product_id = p.id "
            "WHERE i.store_id = %s AND p.is_active = 1",
            (store_id,),
        )
    else:
        total = fetch_one(
            "SELECT COUNT(DISTINCT i.product_id) AS product_count, "
            "COALESCE(SUM(i.quantity), 0) AS total_quantity "
            "FROM stk_inventory i "
            "JOIN stk_products p ON i.product_id = p.id "
            "JOIN stk_stores s ON i.store_id = s.id "
            "WHERE s.business_id = %s AND p.is_active = 1",
            (business_id,),
        )
    return {
        "product_count": total["product_count"] if total else 0,
        "total_quantity": float(total["total_quantity"]) if total else 0,
        "low_stock_count": 0,
    }


def load_expiry_alerts(business_id: int, days: int = 30, store_id: int = None) -> Dict:
    """유통기한 임박/만료 요약을 조회합니다 (매장별 필터 지원)."""
    today = date.today()
    if store_id:
        where = "WHERE i.store_id = %s AND p.is_active = 1"
        base_params = (store_id,)
    else:
        where = "WHERE s.business_id = %s AND p.is_active = 1"
        base_params = (business_id,)
    join_store = "" if store_id else "JOIN stk_stores s ON i.store_id = s.id "
    expired = fetch_one(
        f"SELECT COUNT(*) AS cnt FROM stk_inventory i "
        f"JOIN stk_products p ON i.product_id = p.id "
        f"{join_store}"
        f"{where} "
        f"AND i.expiry_date IS NOT NULL AND i.expiry_date < %s AND i.quantity > 0",
        base_params + (today,),
    )
    expiring = fetch_one(
        f"SELECT COUNT(*) AS cnt FROM stk_inventory i "
        f"JOIN stk_products p ON i.product_id = p.id "
        f"{join_store}"
        f"{where} "
        f"AND i.expiry_date IS NOT NULL AND i.expiry_date >= %s "
        f"AND i.expiry_date <= DATE_ADD(%s, INTERVAL %s DAY) AND i.quantity > 0",
        base_params + (today, today, days),
    )
    return {
        "expired_count": expired["cnt"] if expired else 0,
        "expiring_count": expiring["cnt"] if expiring else 0,
    }


def load_expiry_report(business_id: int, filter_type: str = "all") -> List[Dict]:
    """유통기한 리포트를 조회합니다."""
    today = date.today()
    sql = (
        "SELECT i.id, i.quantity, i.expiry_date, i.location, "
        "p.name AS product_name, p.code AS product_code, p.unit, "
        "s.name AS store_name, c.name AS category_name, "
        "DATEDIFF(i.expiry_date, %s) AS days_left "
        "FROM stk_inventory i "
        "JOIN stk_products p ON i.product_id = p.id "
        "JOIN stk_stores s ON i.store_id = s.id "
        "LEFT JOIN stk_categories c ON p.category_id = c.id "
        "WHERE s.business_id = %s AND p.is_active = 1 "
        "AND i.expiry_date IS NOT NULL AND i.quantity > 0"
    )
    params: list = [today, business_id]
    if filter_type == "expired":
        sql += " AND i.expiry_date < %s"
        params.append(today)
    elif filter_type == "week":
        sql += " AND i.expiry_date >= %s AND i.expiry_date <= DATE_ADD(%s, INTERVAL 7 DAY)"
        params.extend([today, today])
    elif filter_type == "month":
        sql += " AND i.expiry_date >= %s AND i.expiry_date <= DATE_ADD(%s, INTERVAL 30 DAY)"
        params.extend([today, today])
    sql += " ORDER BY i.expiry_date ASC, p.name"
    return fetch_all(sql, tuple(params))


def load_product_lots(product_id: int, store_id: int,
                      location: str = "") -> List[Dict]:
    """상품의 로트 목록을 조회합니다 (유통기한순)."""
    sql = (
        "SELECT i.id, i.product_id, i.quantity, i.expiry_date, i.location "
        "FROM stk_inventory i "
        "WHERE i.product_id = %s AND i.store_id = %s AND i.quantity > 0"
    )
    params: list = [product_id, store_id]
    if location:
        sql += " AND i.location = %s"
        params.append(location)
    sql += " ORDER BY i.expiry_date IS NULL, i.expiry_date ASC"
    return fetch_all(sql, tuple(params))


# ── 입고 ──

def process_stock_in(product_id: int, store_id: int, quantity: float,
                     location: str = "warehouse", unit_price: float = 0,
                     reason: str = "", user_id: Optional[int] = None,
                     reference_id: Optional[int] = None, reference_type: str = "",
                     expiry_date: Optional[str] = None) -> int:
    """입고를 처리합니다 (유통기한별 로트 관리)."""
    _upsert_inventory(product_id, store_id, location, quantity, expiry_date=expiry_date)
    return _record_transaction(
        product_id=product_id, store_id=store_id, tx_type="in",
        to_location=location, quantity=quantity, unit_price=unit_price,
        reason=reason, user_id=user_id, reference_id=reference_id,
        reference_type=reference_type,
    )


# ── 출고 (FEFO) ──

def process_stock_out(product_id: int, store_id: int, quantity: float,
                      location: str = "warehouse", unit_price: float = 0,
                      reason: str = "", user_id: Optional[int] = None,
                      reference_id: Optional[int] = None, reference_type: str = "") -> int:
    """출고를 처리합니다 (FEFO: 유통기한 빠른 것부터 차감)."""
    _fefo_deduct(product_id, store_id, location, quantity)
    return _record_transaction(
        product_id=product_id, store_id=store_id, tx_type="out",
        from_location=location, quantity=quantity, unit_price=unit_price,
        reason=reason, user_id=user_id, reference_id=reference_id,
        reference_type=reference_type,
    )


def process_lot_stock_out(lot_deductions: List[Dict], store_id: int,
                          reason: str = "", user_id: Optional[int] = None,
                          reference_id: Optional[int] = None,
                          reference_type: str = "") -> List[int]:
    """로트 지정 출고: 사용자가 선택한 로트별로 차감합니다."""
    tx_ids = []
    for lot in lot_deductions:
        inv_id = lot["inventory_id"]
        qty = float(lot["quantity"])
        if qty <= 0:
            continue
        inv = fetch_one("SELECT product_id, location FROM stk_inventory WHERE id = %s", (inv_id,))
        if not inv:
            continue
        execute(
            "UPDATE stk_inventory SET quantity = quantity - %s WHERE id = %s",
            (qty, inv_id),
        )
        tx_id = _record_transaction(
            product_id=inv["product_id"], store_id=store_id, tx_type="out",
            from_location=inv["location"], quantity=qty,
            reason=reason, user_id=user_id,
            reference_id=reference_id, reference_type=reference_type,
        )
        tx_ids.append(tx_id)
    return tx_ids


def process_lot_stock_move(lot_deductions: List[Dict], store_id: int,
                           to_location: str, user_id: Optional[int] = None) -> List[int]:
    """로트 지정 이동: 사용자가 선택한 로트별로 이동합니다."""
    tx_ids = []
    for lot in lot_deductions:
        inv_id = lot["inventory_id"]
        qty = float(lot["quantity"])
        if qty <= 0:
            continue
        inv = fetch_one(
            "SELECT product_id, location, expiry_date FROM stk_inventory WHERE id = %s",
            (inv_id,),
        )
        if not inv:
            continue
        execute(
            "UPDATE stk_inventory SET quantity = quantity - %s WHERE id = %s",
            (qty, inv_id),
        )
        expiry_str = str(inv["expiry_date"]) if inv["expiry_date"] else None
        _upsert_inventory(inv["product_id"], store_id, to_location, qty, expiry_date=expiry_str)
        tx_id = _record_transaction(
            product_id=inv["product_id"], store_id=store_id, tx_type="move",
            from_location=inv["location"], to_location=to_location,
            quantity=qty, user_id=user_id,
        )
        tx_ids.append(tx_id)
    return tx_ids


def process_stock_adjust(product_id: int, store_id: int, new_quantity: float,
                         location: str = "warehouse", reason: str = "",
                         user_id: Optional[int] = None,
                         inventory_id: Optional[int] = None) -> int:
    """재고를 조정합니다 (특정 로트 지정 가능)."""
    if inventory_id:
        row = fetch_one("SELECT quantity FROM stk_inventory WHERE id = %s", (inventory_id,))
        current_qty = float(row["quantity"]) if row else 0
        diff = new_quantity - current_qty
        execute("UPDATE stk_inventory SET quantity = %s WHERE id = %s", (new_quantity, inventory_id))
    else:
        rows = fetch_all(
            "SELECT id, quantity FROM stk_inventory "
            "WHERE product_id=%s AND store_id=%s AND location=%s",
            (product_id, store_id, location),
        )
        current_qty = sum(float(r["quantity"]) for r in rows)
        diff = new_quantity - current_qty
        if rows:
            execute(
                "UPDATE stk_inventory SET quantity = quantity + %s WHERE id = %s",
                (diff, rows[0]["id"]),
            )
        else:
            _set_inventory(product_id, store_id, location, new_quantity)
    return _record_transaction(
        product_id=product_id, store_id=store_id, tx_type="adjust",
        to_location=location, quantity=diff, reason=reason, user_id=user_id,
    )


def process_stock_discard(product_id: int, store_id: int, quantity: float,
                          location: str = "warehouse", reason: str = "",
                          user_id: Optional[int] = None,
                          expiry_date: Optional[str] = None,
                          inventory_id: Optional[int] = None) -> int:
    """폐기를 처리합니다 (특정 로트 지정 가능)."""
    if inventory_id:
        execute(
            "UPDATE stk_inventory SET quantity = quantity - %s WHERE id = %s",
            (quantity, inventory_id),
        )
    elif expiry_date:
        _upsert_inventory(product_id, store_id, location, -quantity, expiry_date=expiry_date)
    else:
        _fefo_deduct(product_id, store_id, location, quantity)
    return _record_transaction(
        product_id=product_id, store_id=store_id, tx_type="discard",
        from_location=location, quantity=quantity, reason=reason, user_id=user_id,
    )


def process_stock_move(product_id: int, store_id: int,
                       from_location: str, to_location: str,
                       quantity: float, user_id: Optional[int] = None) -> int:
    """위치 간 재고를 이동합니다."""
    _fefo_deduct(product_id, store_id, from_location, quantity)
    _upsert_inventory(product_id, store_id, to_location, quantity)
    return _record_transaction(
        product_id=product_id, store_id=store_id, tx_type="move",
        from_location=from_location, to_location=to_location,
        quantity=quantity, user_id=user_id,
    )


def load_transactions(store_id: int, limit: int = 50, tx_type: str = "") -> List[Dict]:
    """입출고 내역을 조회합니다."""
    sql = (
        "SELECT t.*, p.name AS product_name, p.code AS product_code, p.unit "
        "FROM stk_transactions t "
        "JOIN stk_products p ON t.product_id = p.id "
        "WHERE t.store_id = %s"
    )
    params: list = [store_id]
    if tx_type:
        sql += " AND t.type = %s"
        params.append(tx_type)
    sql += " ORDER BY t.created_at DESC LIMIT %s"
    params.append(limit)
    return fetch_all(sql, tuple(params))


# ── 내부 헬퍼 ──

def _upsert_inventory(product_id: int, store_id: int, location: str,
                      qty_delta: float, expiry_date: Optional[str] = None) -> None:
    """재고를 증감합니다 (유통기한별 로트, 없으면 생성)."""
    if expiry_date:
        existing = fetch_one(
            "SELECT id, quantity FROM stk_inventory "
            "WHERE product_id=%s AND store_id=%s AND location=%s AND expiry_date=%s",
            (product_id, store_id, location, expiry_date),
        )
    else:
        existing = fetch_one(
            "SELECT id, quantity FROM stk_inventory "
            "WHERE product_id=%s AND store_id=%s AND location=%s AND expiry_date IS NULL",
            (product_id, store_id, location),
        )
    if existing:
        execute(
            "UPDATE stk_inventory SET quantity = quantity + %s WHERE id = %s",
            (qty_delta, existing["id"]),
        )
    else:
        insert(
            "INSERT INTO stk_inventory (product_id, store_id, location, quantity, expiry_date) "
            "VALUES (%s, %s, %s, %s, %s)",
            (product_id, store_id, location, max(0, qty_delta), expiry_date),
        )


def _fefo_deduct(product_id: int, store_id: int, location: str, quantity: float) -> None:
    """FEFO: 유통기한 빠른 로트부터 차감합니다."""
    lots = fetch_all(
        "SELECT id, quantity, expiry_date FROM stk_inventory "
        "WHERE product_id=%s AND store_id=%s AND location=%s AND quantity > 0 "
        "ORDER BY expiry_date IS NULL, expiry_date ASC",
        (product_id, store_id, location),
    )
    remaining = quantity
    for lot in lots:
        if remaining <= 0:
            break
        lot_qty = float(lot["quantity"])
        deduct = min(lot_qty, remaining)
        execute(
            "UPDATE stk_inventory SET quantity = quantity - %s WHERE id = %s",
            (deduct, lot["id"]),
        )
        remaining -= deduct
    if remaining > 0:
        print(f"⚠️ FEFO 부족: product_id={product_id}, 부족량={remaining}")


def _set_inventory(product_id: int, store_id: int, location: str,
                   quantity: float, expiry_date: Optional[str] = None) -> None:
    """재고를 특정 수량으로 설정합니다."""
    if expiry_date:
        existing = fetch_one(
            "SELECT id FROM stk_inventory WHERE product_id=%s AND store_id=%s AND location=%s AND expiry_date=%s",
            (product_id, store_id, location, expiry_date),
        )
    else:
        existing = fetch_one(
            "SELECT id FROM stk_inventory WHERE product_id=%s AND store_id=%s AND location=%s AND expiry_date IS NULL",
            (product_id, store_id, location),
        )
    if existing:
        execute("UPDATE stk_inventory SET quantity = %s WHERE id = %s", (quantity, existing["id"]))
    else:
        insert(
            "INSERT INTO stk_inventory (product_id, store_id, location, quantity, expiry_date) "
            "VALUES (%s, %s, %s, %s, %s)",
            (product_id, store_id, location, quantity, expiry_date),
        )


def _record_transaction(product_id: int, store_id: int, tx_type: str,
                        from_location: str = "", to_location: str = "",
                        quantity: float = 0, unit_price: float = 0,
                        reason: str = "", user_id: Optional[int] = None,
                        reference_id: Optional[int] = None,
                        reference_type: str = "") -> int:
    """입출고 트랜잭션을 기록합니다."""
    return insert(
        "INSERT INTO stk_transactions "
        "(product_id, store_id, type, from_location, to_location, quantity, "
        "unit_price, total_amount, reason, user_id, reference_id, reference_type) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (product_id, store_id, tx_type, from_location, to_location,
         quantity, unit_price, abs(quantity * unit_price), reason,
         user_id, reference_id, reference_type),
    )
