"""자체 판매 관리 비즈니스 로직 (비POS 사용자용)"""
from typing import Dict, List, Optional, Tuple
from app.db import fetch_one, fetch_all, insert, execute
from app.controllers.inventory_controller import process_stock_out


def load_sales(business_id: int, status: str = "",
               date_from: str = "", date_to: str = "",
               store_id: int = None) -> List[Dict]:
    """판매 목록을 조회합니다 (날짜/상태/매장 필터 지원)."""
    sql = (
        "SELECT sa.*, st.name AS store_name, u.name AS created_by_name "
        "FROM stk_sales sa "
        "JOIN stk_stores st ON sa.store_id = st.id "
        "LEFT JOIN stk_users u ON sa.created_by = u.id "
        "WHERE sa.business_id = %s"
    )
    params: list = [business_id]
    if store_id:
        sql += " AND sa.store_id = %s"
        params.append(store_id)
    if status:
        sql += " AND sa.status = %s"
        params.append(status)
    if date_from:
        sql += " AND sa.sale_date >= %s"
        params.append(date_from)
    if date_to:
        sql += " AND sa.sale_date <= %s"
        params.append(date_to)
    sql += " ORDER BY sa.sale_date DESC, sa.id DESC"
    return fetch_all(sql, tuple(params))


def load_sales_summary(business_id: int, date_from: str = "",
                       date_to: str = "", store_id: int = None) -> Dict:
    """기간별 판매 정산 요약을 조회합니다 (매장별 필터 지원)."""
    where = "WHERE sa.business_id = %s"
    params: list = [business_id]
    if store_id:
        where += " AND sa.store_id = %s"
        params.append(store_id)
    if date_from:
        where += " AND sa.sale_date >= %s"
        params.append(date_from)
    if date_to:
        where += " AND sa.sale_date <= %s"
        params.append(date_to)
    row = fetch_one(
        f"SELECT "
        f"COUNT(*) AS total_count, "
        f"COALESCE(SUM(sa.total_amount), 0) AS total_amount, "
        f"SUM(CASE WHEN sa.status='confirmed' THEN 1 ELSE 0 END) AS confirmed_count, "
        f"COALESCE(SUM(CASE WHEN sa.status='confirmed' THEN sa.total_amount ELSE 0 END), 0) AS confirmed_amount, "
        f"SUM(CASE WHEN sa.status='draft' THEN 1 ELSE 0 END) AS draft_count, "
        f"COALESCE(SUM(CASE WHEN sa.status='draft' THEN sa.total_amount ELSE 0 END), 0) AS draft_amount, "
        f"SUM(CASE WHEN sa.status='cancelled' THEN 1 ELSE 0 END) AS cancelled_count "
        f"FROM stk_sales sa {where}",
        tuple(params),
    )
    return row or {}


def load_daily_settlement(business_id: int, date_from: str = "",
                          date_to: str = "", store_id: int = None) -> List[Dict]:
    """일별 정산 내역을 조회합니다 (매장별 필터 지원)."""
    where = "WHERE sa.business_id = %s AND sa.status != 'cancelled'"
    params: list = [business_id]
    if store_id:
        where += " AND sa.store_id = %s"
        params.append(store_id)
    if date_from:
        where += " AND sa.sale_date >= %s"
        params.append(date_from)
    if date_to:
        where += " AND sa.sale_date <= %s"
        params.append(date_to)
    return fetch_all(
        f"SELECT sa.sale_date, "
        f"COUNT(*) AS sale_count, "
        f"COALESCE(SUM(sa.total_amount), 0) AS day_total, "
        f"SUM(CASE WHEN sa.status='confirmed' THEN 1 ELSE 0 END) AS confirmed, "
        f"SUM(CASE WHEN sa.status='draft' THEN 1 ELSE 0 END) AS draft "
        f"FROM stk_sales sa {where} "
        f"GROUP BY sa.sale_date ORDER BY sa.sale_date DESC",
        tuple(params),
    )


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


def resolve_sales_items(rows: List[Dict], business_id: int) -> Tuple[List[Dict], List[str]]:
    """엑셀 파싱 결과를 product_id로 해석하고, 날짜+고객+메모 기준 그룹핑합니다."""
    errors: List[str] = []
    resolved: List[Dict] = []
    for i, row in enumerate(rows):
        product = fetch_one(
            "SELECT id, name, sell_price, unit FROM stk_products WHERE code = %s AND business_id = %s",
            (row["product_code"], business_id),
        )
        if not product:
            errors.append(f"Row {i+2}: Product code '{row['product_code']}' not found")
            continue
        price = row["unit_price"] if row["unit_price"] > 0 else float(product["sell_price"])
        resolved.append({
            "sale_date": row["sale_date"],
            "customer_name": row["customer_name"],
            "product_code": row["product_code"],
            "product_name": product["name"],
            "product_id": product["id"],
            "quantity": row["quantity"],
            "unit_price": price,
            "unit": product["unit"],
            "amount": row["quantity"] * price,
            "memo": row["memo"],
        })
    return resolved, errors


def group_sales_from_rows(resolved_rows: List[Dict]) -> List[Dict]:
    """해석된 행들을 날짜+고객명+메모 기준으로 판매 단위로 그룹핑합니다."""
    groups: Dict[str, Dict] = {}
    for row in resolved_rows:
        key = f"{row['sale_date']}|{row['customer_name']}|{row['memo']}"
        if key not in groups:
            groups[key] = {
                "sale_date": row["sale_date"],
                "customer_name": row["customer_name"],
                "memo": row["memo"],
                "line_items": [],
                "total_amount": 0.0,
            }
        groups[key]["line_items"].append(row)
        groups[key]["total_amount"] += row["amount"]
    return list(groups.values())


def batch_create_sales(grouped_sales: List[Dict], business_id: int,
                       store_id: int, user_id: int,
                       auto_confirm: bool = False) -> Tuple[List[int], List[str]]:
    """그룹핑된 판매를 일괄 생성합니다. auto_confirm=True이면 FEFO로 재고 차감."""
    created_ids: List[int] = []
    errors: List[str] = []
    for sale_group in grouped_sales:
        data = {
            "business_id": business_id,
            "store_id": store_id,
            "sale_date": sale_group["sale_date"],
            "customer_name": sale_group["customer_name"],
            "memo": sale_group.get("memo", "") + " [Excel Upload]",
            "created_by": user_id,
        }
        items = [
            {"product_id": item["product_id"], "quantity": item["quantity"], "unit_price": item["unit_price"]}
            for item in sale_group["line_items"]
        ]
        try:
            sale_id = save_sale(data, items)
            if auto_confirm:
                confirm_sale(sale_id, user_id)
            created_ids.append(sale_id)
            print(f"판매 일괄 생성: sale_id={sale_id}, items={len(items)}, confirm={auto_confirm}")
        except Exception as e:
            errors.append(f"Sale '{sale_group['customer_name']}' ({sale_group['sale_date']}): {str(e)}")
    return created_ids, errors


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
