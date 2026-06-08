"""실사 재고 보고 비즈니스 로직"""
from typing import Dict, List, Optional
from app.db import fetch_one, fetch_all, insert, execute
from app.controllers.inventory_controller import process_stock_adjust


def load_stock_counts(business_id: int, store_id: int = None) -> List[Dict]:
    """실사 보고 목록을 조회합니다."""
    sql = (
        "SELECT sc.*, s.name AS store_name, c.name AS category_name, "
        "u.name AS created_by_name, "
        "(SELECT COUNT(*) FROM stk_stock_count_items sci WHERE sci.stock_count_id = sc.id) AS item_count "
        "FROM stk_stock_counts sc "
        "JOIN stk_stores s ON sc.store_id = s.id "
        "LEFT JOIN stk_categories c ON sc.category_id = c.id "
        "LEFT JOIN stk_users u ON sc.created_by = u.id "
        "WHERE sc.business_id = %s"
    )
    params: list = [business_id]
    if store_id:
        sql += " AND sc.store_id = %s"
        params.append(store_id)
    sql += " ORDER BY sc.count_date DESC"
    return fetch_all(sql, tuple(params))


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
            "SELECT sci.*, p.name AS product_name, p.code AS product_code, p.unit, "
            "p.category_id, COALESCE(c.name, 'Uncategorized') AS category_name "
            "FROM stk_stock_count_items sci "
            "JOIN stk_products p ON sci.product_id = p.id "
            "LEFT JOIN stk_categories c ON p.category_id = c.id "
            "WHERE sci.stock_count_id = %s ORDER BY c.name, p.name",
            (count_id,),
        )
    return count


STOCK_LOCATIONS = [
    ("kitchen", "Kitchen"),
    ("warehouse", "Warehouse"),
]


def create_stock_count(data: Dict) -> int:
    """실사 보고를 생성합니다 (시스템 재고 자동 로드, 위치별 가능)."""
    location = data.get("location") or None
    count_id = insert(
        "INSERT INTO stk_stock_counts "
        "(business_id, store_id, location, count_date, category_id, memo, created_by) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (data["business_id"], data["store_id"], location, data["count_date"],
         data.get("category_id") or None, data.get("memo", ""), data.get("created_by")),
    )
    _load_system_quantities(count_id, data["store_id"], data.get("category_id"), location)
    return count_id


ADJUST_REASONS = [
    ("overuse", "Over-use"),
    ("spoilage", "Spoilage"),
    ("staff_meal", "Staff Meal"),
    ("loss", "Loss / Unknown"),
    ("measurement", "Measurement Error"),
    ("unrecorded_in", "Unrecorded Stock-In"),
    ("other", "Other"),
]


def update_stock_count_items(count_id: int, items: List[Dict]) -> None:
    """실사 수량을 업데이트합니다 (사유 분류 포함)."""
    for item in items:
        reason = item.get("adjust_reason", "")
        memo = item.get("memo", "")
        combined_memo = f"[{reason}] {memo}".strip() if reason else memo
        execute(
            "UPDATE stk_stock_count_items SET actual_quantity=%s, "
            "difference = %s - system_quantity, memo=%s WHERE id=%s",
            (item["actual_quantity"], item["actual_quantity"], combined_memo, item["id"]),
        )


def approve_stock_count(count_id: int, user_id: Optional[int] = None) -> bool:
    """실사를 승인하고 재고를 조정합니다 (사유 포함)."""
    from app.services.stock_cost_service import recalculate_product_cost
    count = load_stock_count(count_id)
    if not count or count["status"] == "approved":
        return False
    adjusted_products = set()
    for item in count["line_items"]:
        diff = float(item["actual_quantity"]) - float(item["system_quantity"])
        if diff != 0:
            memo = item.get("memo", "")
            reason = f"Stock count #{count_id}: {memo}" if memo else f"Stock count #{count_id}"
            process_stock_adjust(
                product_id=item["product_id"], store_id=count["store_id"],
                new_quantity=float(item["actual_quantity"]),
                reason=reason,
                user_id=user_id,
            )
            adjusted_products.add(item["product_id"])
    for product_id in adjusted_products:
        recalculate_product_cost(product_id)
    execute("UPDATE stk_stock_counts SET status = 'approved' WHERE id = %s", (count_id,))
    return True


def create_full_stock_count(data: Dict) -> int:
    """식당용: 전체 상품 실사를 생성합니다 (재고 0인 상품 포함, 위치별 가능)."""
    location = data.get("location") or None
    count_id = insert(
        "INSERT INTO stk_stock_counts "
        "(business_id, store_id, location, count_date, category_id, memo, created_by) "
        "VALUES (%s, %s, %s, %s, NULL, %s, %s)",
        (data["business_id"], data["store_id"], location, data["count_date"],
         data.get("memo", "Full inventory count"), data.get("created_by")),
    )
    _load_all_products(count_id, data["business_id"], data["store_id"], location)
    return count_id


def load_uncounted_categories(business_id: int, store_id: int,
                              count_date: str = "") -> List[Dict]:
    """마트용: 미실시 카테고리 목록을 조회합니다."""
    if not count_date:
        from datetime import date
        count_date = date.today().strftime("%Y-%m-%d")
    all_cats = fetch_all(
        "SELECT c.id, c.name, "
        "COUNT(DISTINCT p.id) AS product_count "
        "FROM stk_categories c "
        "JOIN stk_products p ON p.category_id = c.id AND p.business_id = %s AND p.is_active = 1 "
        "GROUP BY c.id, c.name ORDER BY c.name",
        (business_id,),
    )
    counted_cats = fetch_all(
        "SELECT sc.category_id, sc.status, sc.id AS count_id, sc.count_date, "
        "u.name AS created_by_name, "
        "(SELECT COUNT(*) FROM stk_stock_count_items sci WHERE sci.stock_count_id = sc.id) AS item_count "
        "FROM stk_stock_counts sc "
        "LEFT JOIN stk_users u ON sc.created_by = u.id "
        "WHERE sc.business_id = %s AND sc.store_id = %s AND sc.count_date = %s "
        "AND sc.category_id IS NOT NULL",
        (business_id, store_id, count_date),
    )
    counted_map = {}
    for cc in counted_cats:
        counted_map[cc["category_id"]] = cc
    result = []
    for cat in all_cats:
        info = counted_map.get(cat["id"])
        result.append({
            "id": cat["id"],
            "name": cat["name"],
            "product_count": cat["product_count"],
            "is_counted": info is not None,
            "count_id": info["count_id"] if info else None,
            "count_status": info["status"] if info else None,
            "counted_items": info["item_count"] if info else 0,
            "counted_by": info["created_by_name"] if info else None,
        })
    return result


def load_count_coverage_summary(business_id: int, store_id: int,
                                count_date: str = "") -> Dict:
    """마트용: 실사 커버리지 요약을 조회합니다."""
    categories = load_uncounted_categories(business_id, store_id, count_date)
    total = len(categories)
    counted = sum(1 for c in categories if c["is_counted"])
    return {
        "total_categories": total,
        "counted_categories": counted,
        "uncounted_categories": total - counted,
        "coverage_pct": round(counted / total * 100, 1) if total > 0 else 0,
        "categories": categories,
    }


def _load_system_quantities(count_id: int, store_id: int,
                            category_id: Optional[int] = None,
                            location: Optional[str] = None) -> None:
    """시스템 재고를 실사 항목에 로드합니다 (위치별 필터 가능)."""
    sql = (
        "SELECT i.product_id, SUM(i.quantity) AS total_qty "
        "FROM stk_inventory i "
        "JOIN stk_products p ON i.product_id = p.id "
        "WHERE i.store_id = %s AND p.is_active = 1"
    )
    params: list = [store_id]
    if location:
        sql += " AND i.location = %s"
        params.append(location)
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


def _load_all_products(count_id: int, business_id: int, store_id: int,
                       location: Optional[str] = None) -> None:
    """식당용: 전체 상품을 로드합니다 (재고 0인 상품 포함, 위치별 가능)."""
    if location:
        rows = fetch_all(
            "SELECT p.id AS product_id, "
            "COALESCE(SUM(i.quantity), 0) AS total_qty "
            "FROM stk_products p "
            "LEFT JOIN stk_inventory i ON p.id = i.product_id "
            "  AND i.store_id = %s AND i.location = %s "
            "WHERE p.business_id = %s AND p.is_active = 1 "
            "GROUP BY p.id ORDER BY p.category_id, p.name",
            (store_id, location, business_id),
        )
    else:
        rows = fetch_all(
            "SELECT p.id AS product_id, "
            "COALESCE(SUM(i.quantity), 0) AS total_qty "
            "FROM stk_products p "
            "LEFT JOIN stk_inventory i ON p.id = i.product_id AND i.store_id = %s "
            "WHERE p.business_id = %s AND p.is_active = 1 "
            "GROUP BY p.id ORDER BY p.category_id, p.name",
            (store_id, business_id),
        )
    for row in rows:
        insert(
            "INSERT INTO stk_stock_count_items "
            "(stock_count_id, product_id, system_quantity, actual_quantity, difference) "
            "VALUES (%s, %s, %s, %s, 0)",
            (count_id, row["product_id"], row["total_qty"], row["total_qty"]),
        )


# ─────────────────────────────────────────────
# 합산 리뷰 + 일괄 승인 (위치별 실사 → 합산 확인)
# ─────────────────────────────────────────────

def load_combined_review(business_id: int, store_id: int, count_date: str) -> Dict:
    """같은 날짜/매장의 위치별 실사를 합산하여 리뷰 데이터를 생성합니다."""
    counts = fetch_all(
        "SELECT sc.id, sc.location, sc.status, sc.memo, u.name AS created_by_name "
        "FROM stk_stock_counts sc "
        "LEFT JOIN stk_users u ON sc.created_by = u.id "
        "WHERE sc.business_id = %s AND sc.store_id = %s AND sc.count_date = %s "
        "ORDER BY sc.location",
        (business_id, store_id, count_date),
    )
    if not counts:
        return {"counts": [], "combined_items": [], "total_system": 0,
                "total_actual": 0, "total_diff": 0, "is_all_ready": False}
    all_items = fetch_all(
        "SELECT sci.product_id, p.name AS product_name, p.code AS product_code, "
        "p.unit, COALESCE(c.name, 'Uncategorized') AS category_name, "
        "sc.location, sci.system_quantity, sci.actual_quantity, sci.difference, sci.memo "
        "FROM stk_stock_count_items sci "
        "JOIN stk_stock_counts sc ON sci.stock_count_id = sc.id "
        "JOIN stk_products p ON sci.product_id = p.id "
        "LEFT JOIN stk_categories c ON p.category_id = c.id "
        "WHERE sc.business_id = %s AND sc.store_id = %s AND sc.count_date = %s "
        "ORDER BY c.name, p.name, sc.location",
        (business_id, store_id, count_date),
    )
    product_map = {}
    for item in all_items:
        pid = item["product_id"]
        if pid not in product_map:
            product_map[pid] = {
                "product_id": pid,
                "product_name": item["product_name"],
                "product_code": item["product_code"],
                "unit": item["unit"],
                "category_name": item["category_name"],
                "locations": {},
                "total_system": 0,
                "total_actual": 0,
            }
        loc = item["location"] or "all"
        product_map[pid]["locations"][loc] = {
            "system_quantity": float(item["system_quantity"]),
            "actual_quantity": float(item["actual_quantity"]),
            "difference": float(item["difference"]),
            "memo": item["memo"] or "",
        }
        product_map[pid]["total_system"] += float(item["system_quantity"])
        product_map[pid]["total_actual"] += float(item["actual_quantity"])
    combined_items = []
    for p in product_map.values():
        p["total_diff"] = p["total_actual"] - p["total_system"]
        combined_items.append(p)
    total_system = sum(p["total_system"] for p in combined_items)
    total_actual = sum(p["total_actual"] for p in combined_items)
    is_all_ready = all(c["status"] == "draft" for c in counts) and len(counts) > 0
    has_approved = any(c["status"] == "approved" for c in counts)
    return {
        "counts": counts,
        "combined_items": combined_items,
        "total_system": total_system,
        "total_actual": total_actual,
        "total_diff": total_actual - total_system,
        "is_all_ready": is_all_ready,
        "has_approved": has_approved,
        "count_date": count_date,
        "location_list": [c["location"] or "all" for c in counts],
    }


def approve_combined_counts(business_id: int, store_id: int, count_date: str,
                            user_id: Optional[int] = None) -> bool:
    """같은 날짜/매장의 모든 위치별 실사를 일괄 승인합니다."""
    from app.services.stock_cost_service import recalculate_product_cost
    counts = fetch_all(
        "SELECT id, location FROM stk_stock_counts "
        "WHERE business_id = %s AND store_id = %s AND count_date = %s AND status = 'draft'",
        (business_id, store_id, count_date),
    )
    if not counts:
        return False
    adjusted_products = set()
    for count_row in counts:
        count = load_stock_count(count_row["id"])
        if not count:
            continue
        location = count_row["location"] or "warehouse"
        for item in count["line_items"]:
            diff = float(item["actual_quantity"]) - float(item["system_quantity"])
            if diff != 0:
                memo = item.get("memo", "")
                reason = (f"Stock count [{location}] #{count_row['id']}: {memo}"
                          if memo else f"Stock count [{location}] #{count_row['id']}")
                _adjust_inventory_by_location(
                    product_id=item["product_id"],
                    store_id=store_id,
                    location=location,
                    new_quantity=float(item["actual_quantity"]),
                    reason=reason,
                    user_id=user_id,
                )
                adjusted_products.add(item["product_id"])
        execute("UPDATE stk_stock_counts SET status = 'approved' WHERE id = %s",
                (count_row["id"],))
    for product_id in adjusted_products:
        recalculate_product_cost(product_id)
    print(f"📋 일괄 승인 완료: {count_date} / {len(counts)}건 / 조정 상품 {len(adjusted_products)}건")
    return True


def _adjust_inventory_by_location(product_id: int, store_id: int, location: str,
                                  new_quantity: float, reason: str = "",
                                  user_id: Optional[int] = None) -> None:
    """특정 위치의 재고를 실사 수량으로 직접 조정합니다."""
    existing = fetch_one(
        "SELECT id, quantity FROM stk_inventory "
        "WHERE product_id = %s AND store_id = %s AND location = %s",
        (product_id, store_id, location),
    )
    old_qty = float(existing["quantity"]) if existing else 0
    diff = new_quantity - old_qty
    if existing:
        execute(
            "UPDATE stk_inventory SET quantity = %s WHERE id = %s",
            (new_quantity, existing["id"]),
        )
    else:
        insert(
            "INSERT INTO stk_inventory (product_id, store_id, location, quantity) "
            "VALUES (%s, %s, %s, %s)",
            (product_id, store_id, location, new_quantity),
        )
    insert(
        "INSERT INTO stk_transactions "
        "(product_id, store_id, type, quantity, reason, user_id) "
        "VALUES (%s, %s, 'adjust', %s, %s, %s)",
        (product_id, store_id, diff, reason, user_id),
    )
