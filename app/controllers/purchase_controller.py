"""매입 관리 비즈니스 로직"""
from typing import Dict, List, Optional
from io import BytesIO
from app.db import fetch_one, fetch_all, insert, execute
from app.controllers.inventory_controller import process_stock_in
from app.services.excel_service import parse_purchase_excel


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


def import_purchases_from_excel(business_id: int, store_id: int,
                                user_id: int, file_stream: BytesIO) -> Dict:
    """엑셀 파일에서 매입을 일괄 등록합니다. 같은 날짜+공급처+메모를 그룹핑."""
    rows, parse_errors = parse_purchase_excel(file_stream)
    result = {"created": 0, "items": 0, "skipped": 0, "errors": list(parse_errors)}
    if parse_errors and not rows:
        return result
    product_map = _build_product_code_map(business_id)
    supplier_map = _build_supplier_name_map(business_id)
    groups = _group_purchase_rows(rows)
    for group_key, group_items in groups.items():
        try:
            _process_purchase_group(
                business_id, store_id, user_id,
                group_key, group_items, product_map, supplier_map, result)
        except Exception as e:
            result["errors"].append(f"Purchase '{group_key}': {str(e)}")
            result["skipped"] += 1
    print(f"📊 매입 엑셀 가져오기 완료 - 매입: {result['created']}, "
          f"항목: {result['items']}, 오류: {len(result['errors'])}")
    return result


def _build_product_code_map(business_id: int) -> Dict[str, int]:
    """상품 코드 → ID 매핑."""
    products = fetch_all(
        "SELECT id, code FROM stk_products WHERE business_id = %s AND is_active = 1",
        (business_id,))
    return {p["code"].strip().upper(): p["id"] for p in products}


def _build_supplier_name_map(business_id: int) -> Dict[str, int]:
    """공급처 이름 → ID 매핑."""
    suppliers = fetch_all(
        "SELECT id, name FROM stk_suppliers WHERE business_id = %s", (business_id,))
    return {s["name"].strip().lower(): s["id"] for s in suppliers}


def _group_purchase_rows(rows: List[Dict]) -> Dict[str, List[Dict]]:
    """같은 날짜+공급처+메모를 하나의 매입으로 그룹핑."""
    from collections import OrderedDict
    groups: OrderedDict = OrderedDict()
    for row in rows:
        key = f"{row.get('purchase_date', '')}|{row.get('supplier_name', '')}|{row.get('memo', '')}"
        if key not in groups:
            groups[key] = []
        groups[key].append(row)
    return groups


def _process_purchase_group(business_id: int, store_id: int, user_id: int,
                            group_key: str, items: List[Dict],
                            product_map: Dict, supplier_map: Dict,
                            result: Dict) -> None:
    """매입 그룹을 처리하여 하나의 매입을 생성합니다."""
    from datetime import date
    first = items[0]
    purchase_date = first.get("purchase_date") or date.today().isoformat()
    supplier_name = first.get("supplier_name", "")
    supplier_id = supplier_map.get(supplier_name.strip().lower()) if supplier_name else None
    valid_items = []
    for item in items:
        code = item["product_code"].strip().upper()
        product_id = product_map.get(code)
        if not product_id:
            result["errors"].append(f"Product code '{item['product_code']}' not found")
            continue
        valid_items.append({
            "product_id": product_id,
            "quantity": item["quantity"],
            "unit_price": item["unit_price"],
        })
    if not valid_items:
        result["skipped"] += 1
        return
    data = {
        "business_id": business_id,
        "store_id": store_id,
        "supplier_id": supplier_id,
        "purchase_date": purchase_date,
        "memo": first.get("memo", ""),
        "created_by": user_id,
    }
    save_purchase(data, valid_items)
    result["created"] += 1
    result["items"] += len(valid_items)


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
