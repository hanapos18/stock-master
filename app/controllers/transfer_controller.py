"""매장 간 이동(Inter-Store Transfer) 비즈니스 로직"""
from datetime import datetime
from typing import Dict, List, Optional
from app.db import fetch_one, fetch_all, insert, execute


def create_transfer(business_id: int, from_store_id: int, to_store_id: int,
                    items: List[Dict], user_id: int, memo: str = "") -> int:
    """매장 간 이동 요청을 생성합니다 (status=pending)."""
    transfer_id = insert(
        "INSERT INTO stk_transfers "
        "(business_id, from_store_id, to_store_id, requested_by, memo) "
        "VALUES (%s, %s, %s, %s, %s)",
        (business_id, from_store_id, to_store_id, user_id, memo),
    )
    for item in items:
        inv = fetch_one(
            "SELECT product_id, expiry_date, location FROM stk_inventory WHERE id = %s",
            (item["inventory_id"],),
        )
        if not inv:
            continue
        insert(
            "INSERT INTO stk_transfer_items "
            "(transfer_id, product_id, inventory_id, quantity, expiry_date, location) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (transfer_id, inv["product_id"], item["inventory_id"],
             item["quantity"],
             str(inv["expiry_date"]) if inv["expiry_date"] else None,
             inv["location"]),
        )
    print(f"📦 이동 요청 생성: transfer_id={transfer_id}, 출발={from_store_id}, 도착={to_store_id}")
    return transfer_id


def ship_transfer(transfer_id: int, user_id: int) -> bool:
    """이동 요청을 발송 처리합니다 (pending -> shipped, 출발매장 재고 차감)."""
    transfer = fetch_one(
        "SELECT * FROM stk_transfers WHERE id = %s", (transfer_id,),
    )
    if not transfer or transfer["status"] != "pending":
        return False
    items = fetch_all(
        "SELECT * FROM stk_transfer_items WHERE transfer_id = %s", (transfer_id,),
    )
    for item in items:
        if item["inventory_id"]:
            execute(
                "UPDATE stk_inventory SET quantity = quantity - %s WHERE id = %s",
                (item["quantity"], item["inventory_id"]),
            )
        _record_transfer_transaction(
            product_id=item["product_id"],
            store_id=transfer["from_store_id"],
            tx_type="transfer_out",
            from_location=item["location"],
            quantity=item["quantity"],
            user_id=user_id,
            reference_id=transfer_id,
        )
    execute(
        "UPDATE stk_transfers SET status='shipped', shipped_by=%s, shipped_at=NOW() "
        "WHERE id=%s",
        (user_id, transfer_id),
    )
    for item in items:
        _sync_to_pos(item["product_id"], transfer["from_store_id"])
    print(f"🚚 이동 발송 완료: transfer_id={transfer_id}")
    return True


def receive_transfer(transfer_id: int, user_id: int,
                     received_items: Optional[List[Dict]] = None) -> bool:
    """이동 요청을 수령 처리합니다 (shipped -> received, 도착매장 재고 증가)."""
    transfer = fetch_one(
        "SELECT * FROM stk_transfers WHERE id = %s", (transfer_id,),
    )
    if not transfer or transfer["status"] != "shipped":
        return False
    items = fetch_all(
        "SELECT * FROM stk_transfer_items WHERE transfer_id = %s", (transfer_id,),
    )
    received_map = {}
    if received_items:
        for ri in received_items:
            received_map[int(ri["item_id"])] = float(ri["received_quantity"])
    for item in items:
        recv_qty = received_map.get(item["id"], float(item["quantity"]))
        execute(
            "UPDATE stk_transfer_items SET received_quantity = %s WHERE id = %s",
            (recv_qty, item["id"]),
        )
        if recv_qty > 0:
            _upsert_inventory_for_transfer(
                product_id=item["product_id"],
                store_id=transfer["to_store_id"],
                location=item["location"],
                quantity=recv_qty,
                expiry_date=str(item["expiry_date"]) if item["expiry_date"] else None,
            )
            _record_transfer_transaction(
                product_id=item["product_id"],
                store_id=transfer["to_store_id"],
                tx_type="transfer_in",
                to_location=item["location"],
                quantity=recv_qty,
                user_id=user_id,
                reference_id=transfer_id,
            )
    execute(
        "UPDATE stk_transfers SET status='received', received_by=%s, received_at=NOW() "
        "WHERE id=%s",
        (user_id, transfer_id),
    )
    for item in items:
        recv_qty = received_map.get(item["id"], float(item["quantity"]))
        if recv_qty > 0:
            _sync_to_pos(item["product_id"], transfer["to_store_id"])
    print(f"✅ 이동 수령 완료: transfer_id={transfer_id}")
    return True


def cancel_transfer(transfer_id: int, user_id: int) -> bool:
    """이동 요청을 취소합니다 (pending 상태만 가능)."""
    transfer = fetch_one(
        "SELECT * FROM stk_transfers WHERE id = %s", (transfer_id,),
    )
    if not transfer or transfer["status"] != "pending":
        return False
    execute(
        "UPDATE stk_transfers SET status='cancelled' WHERE id=%s",
        (transfer_id,),
    )
    print(f"❌ 이동 취소: transfer_id={transfer_id}")
    return True


def load_transfers(business_id: int, store_id: Optional[int] = None,
                   status_filter: str = "") -> List[Dict]:
    """이동 목록을 조회합니다."""
    sql = (
        "SELECT t.*, "
        "fs.name AS from_store_name, ts.name AS to_store_name, "
        "u.name AS requested_by_name, "
        "(SELECT COUNT(*) FROM stk_transfer_items ti WHERE ti.transfer_id = t.id) AS item_count, "
        "(SELECT COALESCE(SUM(ti.quantity), 0) FROM stk_transfer_items ti WHERE ti.transfer_id = t.id) AS total_quantity "
        "FROM stk_transfers t "
        "JOIN stk_stores fs ON t.from_store_id = fs.id "
        "JOIN stk_stores ts ON t.to_store_id = ts.id "
        "LEFT JOIN stk_users u ON t.requested_by = u.id "
        "WHERE t.business_id = %s"
    )
    params: list = [business_id]
    if store_id:
        sql += " AND (t.from_store_id = %s OR t.to_store_id = %s)"
        params.extend([store_id, store_id])
    if status_filter:
        sql += " AND t.status = %s"
        params.append(status_filter)
    sql += " ORDER BY t.created_at DESC"
    return fetch_all(sql, tuple(params))


def load_transfer_detail(transfer_id: int) -> Optional[Dict]:
    """이동 상세 정보를 조회합니다."""
    transfer = fetch_one(
        "SELECT t.*, "
        "fs.name AS from_store_name, ts.name AS to_store_name, "
        "u1.name AS requested_by_name, "
        "u2.name AS shipped_by_name, "
        "u3.name AS received_by_name "
        "FROM stk_transfers t "
        "JOIN stk_stores fs ON t.from_store_id = fs.id "
        "JOIN stk_stores ts ON t.to_store_id = ts.id "
        "LEFT JOIN stk_users u1 ON t.requested_by = u1.id "
        "LEFT JOIN stk_users u2 ON t.shipped_by = u2.id "
        "LEFT JOIN stk_users u3 ON t.received_by = u3.id "
        "WHERE t.id = %s",
        (transfer_id,),
    )
    if not transfer:
        return None
    items = fetch_all(
        "SELECT ti.*, p.name AS product_name, p.code AS product_code, p.unit "
        "FROM stk_transfer_items ti "
        "JOIN stk_products p ON ti.product_id = p.id "
        "WHERE ti.transfer_id = %s ORDER BY ti.id",
        (transfer_id,),
    )
    transfer["items"] = items
    return transfer


def load_pending_transfer_counts(business_id: int, store_id: int) -> Dict:
    """현재 매장 기준 대기 중인 이동 건수를 조회합니다."""
    outgoing = fetch_one(
        "SELECT COUNT(*) AS cnt FROM stk_transfers "
        "WHERE business_id = %s AND from_store_id = %s AND status IN ('pending', 'shipped')",
        (business_id, store_id),
    )
    incoming = fetch_one(
        "SELECT COUNT(*) AS cnt FROM stk_transfers "
        "WHERE business_id = %s AND to_store_id = %s AND status = 'shipped'",
        (business_id, store_id),
    )
    return {
        "outgoing": outgoing["cnt"] if outgoing else 0,
        "incoming": incoming["cnt"] if incoming else 0,
    }


def load_all_stores_inventory(business_id: int, search: str = "",
                              category_id: Optional[int] = None) -> List[Dict]:
    """전 매장 합산 재고를 상품별로 조회합니다."""
    sql = (
        "SELECT p.id AS product_id, p.code AS product_code, p.name AS product_name, "
        "p.unit, c.name AS category_name, "
        "COALESCE(SUM(i.quantity), 0) AS total_quantity "
        "FROM stk_products p "
        "LEFT JOIN stk_inventory i ON i.product_id = p.id "
        "LEFT JOIN stk_categories c ON p.category_id = c.id "
        "WHERE p.business_id = %s AND p.is_active = 1"
    )
    params: list = [business_id]
    if search:
        sql += " AND (p.name LIKE %s OR p.code LIKE %s)"
        like = f"%{search}%"
        params.extend([like, like])
    if category_id:
        sql += " AND p.category_id = %s"
        params.append(category_id)
    sql += " GROUP BY p.id ORDER BY p.name"
    return fetch_all(sql, tuple(params))


def load_store_breakdown(business_id: int, product_id: int) -> List[Dict]:
    """특정 상품의 매장별 재고 분포를 조회합니다."""
    return fetch_all(
        "SELECT s.id AS store_id, s.name AS store_name, s.is_warehouse, "
        "COALESCE(SUM(i.quantity), 0) AS quantity "
        "FROM stk_stores s "
        "LEFT JOIN stk_inventory i ON i.store_id = s.id AND i.product_id = %s "
        "WHERE s.business_id = %s AND s.is_active = 1 "
        "GROUP BY s.id ORDER BY s.is_warehouse DESC, s.name",
        (product_id, business_id),
    )


def load_store_inventory_summary(business_id: int) -> List[Dict]:
    """매장별 재고 요약을 조회합니다."""
    return fetch_all(
        "SELECT s.id, s.name, s.is_warehouse, "
        "COUNT(DISTINCT i.product_id) AS product_count, "
        "COALESCE(SUM(i.quantity), 0) AS total_quantity "
        "FROM stk_stores s "
        "LEFT JOIN stk_inventory i ON i.store_id = s.id "
        "WHERE s.business_id = %s AND s.is_active = 1 "
        "GROUP BY s.id ORDER BY s.is_warehouse DESC, s.name",
        (business_id,),
    )


# ── POS 동기화 헬퍼 ──

def _sync_to_pos(product_id: int, store_id: int) -> None:
    """재고 변동 후 POS menulist 재고를 동기화합니다 (실패 시 무시)."""
    try:
        from app.controllers.pos_sync_controller import sync_inventory_to_pos
        sync_inventory_to_pos(product_id, store_id)
    except Exception as e:
        print(f"POS 동기화 스킵: {e}")


# ── 내부 헬퍼 ──

def _upsert_inventory_for_transfer(product_id: int, store_id: int,
                                   location: str, quantity: float,
                                   expiry_date: Optional[str] = None) -> None:
    """이동 수령 시 도착 매장 재고를 증감합니다."""
    if expiry_date:
        existing = fetch_one(
            "SELECT id FROM stk_inventory "
            "WHERE product_id=%s AND store_id=%s AND location=%s AND expiry_date=%s",
            (product_id, store_id, location, expiry_date),
        )
    else:
        existing = fetch_one(
            "SELECT id FROM stk_inventory "
            "WHERE product_id=%s AND store_id=%s AND location=%s AND expiry_date IS NULL",
            (product_id, store_id, location),
        )
    if existing:
        execute(
            "UPDATE stk_inventory SET quantity = quantity + %s WHERE id = %s",
            (quantity, existing["id"]),
        )
    else:
        insert(
            "INSERT INTO stk_inventory (product_id, store_id, location, quantity, expiry_date) "
            "VALUES (%s, %s, %s, %s, %s)",
            (product_id, store_id, location, max(0, quantity), expiry_date),
        )


def _record_transfer_transaction(product_id: int, store_id: int, tx_type: str,
                                 from_location: str = "", to_location: str = "",
                                 quantity: float = 0, user_id: Optional[int] = None,
                                 reference_id: Optional[int] = None) -> int:
    """이동 트랜잭션을 기록합니다."""
    return insert(
        "INSERT INTO stk_transactions "
        "(product_id, store_id, type, from_location, to_location, quantity, "
        "reason, user_id, reference_id, reference_type) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (product_id, store_id, tx_type, from_location, to_location,
         quantity, "Inter-store transfer", user_id, reference_id, "transfer"),
    )
