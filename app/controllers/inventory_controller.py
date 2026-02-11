"""재고 관리 비즈니스 로직"""
from typing import Dict, List, Optional
from app.db import fetch_one, fetch_all, insert, execute


def load_inventory(store_id: int, category_id: Optional[int] = None,
                   search: str = "", low_stock_only: bool = False) -> List[Dict]:
    """매장별 재고 현황을 조회합니다."""
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
    sql += " ORDER BY p.name"
    return fetch_all(sql, tuple(params))


def load_inventory_summary(business_id: int) -> Dict:
    """사업장 전체 재고 요약을 조회합니다."""
    total = fetch_one(
        "SELECT COUNT(DISTINCT i.product_id) AS product_count, "
        "COALESCE(SUM(i.quantity), 0) AS total_quantity "
        "FROM stk_inventory i "
        "JOIN stk_products p ON i.product_id = p.id "
        "JOIN stk_stores s ON i.store_id = s.id "
        "WHERE s.business_id = %s AND p.is_active = 1",
        (business_id,),
    )
    low_stock = fetch_one(
        "SELECT COUNT(*) AS cnt FROM stk_inventory i "
        "JOIN stk_products p ON i.product_id = p.id "
        "JOIN stk_stores s ON i.store_id = s.id "
        "WHERE s.business_id = %s AND p.is_active = 1 AND i.quantity <= p.min_stock AND p.min_stock > 0",
        (business_id,),
    )
    return {
        "product_count": total["product_count"] if total else 0,
        "total_quantity": float(total["total_quantity"]) if total else 0,
        "low_stock_count": low_stock["cnt"] if low_stock else 0,
    }


def process_stock_in(product_id: int, store_id: int, quantity: float,
                     location: str = "warehouse", unit_price: float = 0,
                     reason: str = "", user_id: Optional[int] = None,
                     reference_id: Optional[int] = None, reference_type: str = "") -> int:
    """입고를 처리합니다."""
    _upsert_inventory(product_id, store_id, location, quantity)
    return _record_transaction(
        product_id=product_id, store_id=store_id, tx_type="in",
        to_location=location, quantity=quantity, unit_price=unit_price,
        reason=reason, user_id=user_id, reference_id=reference_id,
        reference_type=reference_type,
    )


def process_stock_out(product_id: int, store_id: int, quantity: float,
                      location: str = "warehouse", unit_price: float = 0,
                      reason: str = "", user_id: Optional[int] = None,
                      reference_id: Optional[int] = None, reference_type: str = "") -> int:
    """출고를 처리합니다."""
    _upsert_inventory(product_id, store_id, location, -quantity)
    return _record_transaction(
        product_id=product_id, store_id=store_id, tx_type="out",
        from_location=location, quantity=quantity, unit_price=unit_price,
        reason=reason, user_id=user_id, reference_id=reference_id,
        reference_type=reference_type,
    )


def process_stock_adjust(product_id: int, store_id: int, new_quantity: float,
                         location: str = "warehouse", reason: str = "",
                         user_id: Optional[int] = None) -> int:
    """재고를 조정합니다."""
    current = fetch_one(
        "SELECT quantity FROM stk_inventory WHERE product_id=%s AND store_id=%s AND location=%s",
        (product_id, store_id, location),
    )
    current_qty = float(current["quantity"]) if current else 0
    diff = new_quantity - current_qty
    _set_inventory(product_id, store_id, location, new_quantity)
    return _record_transaction(
        product_id=product_id, store_id=store_id, tx_type="adjust",
        to_location=location, quantity=diff, reason=reason, user_id=user_id,
    )


def process_stock_discard(product_id: int, store_id: int, quantity: float,
                          location: str = "warehouse", reason: str = "",
                          user_id: Optional[int] = None) -> int:
    """폐기를 처리합니다."""
    _upsert_inventory(product_id, store_id, location, -quantity)
    return _record_transaction(
        product_id=product_id, store_id=store_id, tx_type="discard",
        from_location=location, quantity=quantity, reason=reason, user_id=user_id,
    )


def process_stock_move(product_id: int, store_id: int,
                       from_location: str, to_location: str,
                       quantity: float, user_id: Optional[int] = None) -> int:
    """위치 간 재고를 이동합니다."""
    _upsert_inventory(product_id, store_id, from_location, -quantity)
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

def _upsert_inventory(product_id: int, store_id: int, location: str, qty_delta: float) -> None:
    """재고를 증감합니다 (없으면 생성)."""
    existing = fetch_one(
        "SELECT id, quantity FROM stk_inventory "
        "WHERE product_id=%s AND store_id=%s AND location=%s",
        (product_id, store_id, location),
    )
    if existing:
        execute(
            "UPDATE stk_inventory SET quantity = quantity + %s WHERE id = %s",
            (qty_delta, existing["id"]),
        )
    else:
        insert(
            "INSERT INTO stk_inventory (product_id, store_id, location, quantity) "
            "VALUES (%s, %s, %s, %s)",
            (product_id, store_id, location, max(0, qty_delta)),
        )


def _set_inventory(product_id: int, store_id: int, location: str, quantity: float) -> None:
    """재고를 특정 수량으로 설정합니다."""
    existing = fetch_one(
        "SELECT id FROM stk_inventory WHERE product_id=%s AND store_id=%s AND location=%s",
        (product_id, store_id, location),
    )
    if existing:
        execute("UPDATE stk_inventory SET quantity = %s WHERE id = %s", (quantity, existing["id"]))
    else:
        insert(
            "INSERT INTO stk_inventory (product_id, store_id, location, quantity) "
            "VALUES (%s, %s, %s, %s)",
            (product_id, store_id, location, quantity),
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
