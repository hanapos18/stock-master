"""상품/식자재 비즈니스 로직"""
from typing import Dict, List, Optional, Tuple
from io import BytesIO
from app.db import fetch_one, fetch_all, insert, execute
from app.services.excel_service import parse_product_excel


def load_products(business_id: int, category_id: Optional[int] = None,
                  search: str = "", active_only: bool = True) -> List[Dict]:
    """상품 목록을 조회합니다."""
    sql = (
        "SELECT p.*, c.name AS category_name, s.name AS supplier_name "
        "FROM stk_products p "
        "LEFT JOIN stk_categories c ON p.category_id = c.id "
        "LEFT JOIN stk_suppliers s ON p.supplier_id = s.id "
        "WHERE p.business_id = %s"
    )
    params: list = [business_id]
    if active_only:
        sql += " AND p.is_active = 1"
    if category_id:
        sql += " AND p.category_id = %s"
        params.append(category_id)
    if search:
        sql += " AND (p.name LIKE %s OR p.code LIKE %s OR p.barcode LIKE %s)"
        like = f"%{search}%"
        params.extend([like, like, like])
    sql += " ORDER BY p.name"
    return fetch_all(sql, tuple(params))


def load_product(product_id: int) -> Optional[Dict]:
    """상품 상세 정보를 조회합니다."""
    return fetch_one(
        "SELECT p.*, c.name AS category_name, s.name AS supplier_name "
        "FROM stk_products p "
        "LEFT JOIN stk_categories c ON p.category_id = c.id "
        "LEFT JOIN stk_suppliers s ON p.supplier_id = s.id "
        "WHERE p.id = %s",
        (product_id,),
    )


def save_product(data: Dict) -> int:
    """상품을 생성합니다."""
    return insert(
        "INSERT INTO stk_products "
        "(business_id, category_id, supplier_id, code, barcode, name, description, "
        "storage_location, unit, unit_price, sell_price, min_stock, max_stock) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (data["business_id"], data.get("category_id") or None,
         data.get("supplier_id") or None, data["code"], data.get("barcode", ""),
         data["name"], data.get("description", ""),
         data.get("storage_location", ""), data.get("unit", "ea"),
         data.get("unit_price", 0), data.get("sell_price", 0),
         data.get("min_stock", 0), data.get("max_stock") or None),
    )


def update_product(product_id: int, data: Dict) -> int:
    """상품 정보를 수정합니다."""
    return execute(
        "UPDATE stk_products SET category_id=%s, supplier_id=%s, code=%s, barcode=%s, "
        "name=%s, description=%s, storage_location=%s, unit=%s, unit_price=%s, "
        "sell_price=%s, min_stock=%s, max_stock=%s WHERE id=%s",
        (data.get("category_id") or None, data.get("supplier_id") or None,
         data["code"], data.get("barcode", ""), data["name"],
         data.get("description", ""), data.get("storage_location", ""),
         data.get("unit", "ea"), data.get("unit_price", 0),
         data.get("sell_price", 0), data.get("min_stock", 0),
         data.get("max_stock") or None, product_id),
    )


def delete_product(product_id: int) -> int:
    """상품을 비활성화합니다."""
    return execute("UPDATE stk_products SET is_active = 0 WHERE id = %s", (product_id,))


def generate_product_code(business_id: int) -> str:
    """다음 상품 코드를 자동 생성합니다."""
    row = fetch_one(
        "SELECT MAX(CAST(SUBSTRING(code, 2) AS UNSIGNED)) AS max_num "
        "FROM stk_products WHERE business_id = %s AND code REGEXP '^P[0-9]+$'",
        (business_id,),
    )
    next_num = (row["max_num"] or 0) + 1 if row else 1
    return f"P{next_num:04d}"


def import_products_from_excel(business_id: int, file_stream: BytesIO) -> Dict:
    """엑셀 파일에서 상품을 일괄 등록/수정합니다.
    Returns: {"created": int, "updated": int, "skipped": int, "errors": List[str]}
    """
    rows, parse_errors = parse_product_excel(file_stream)
    result = {"created": 0, "updated": 0, "skipped": 0, "errors": list(parse_errors)}
    if parse_errors and not rows:
        return result
    category_map = _build_category_map(business_id)
    supplier_map = _build_supplier_map(business_id)
    for row_data in rows:
        try:
            _process_import_row(business_id, row_data, category_map, supplier_map, result)
        except Exception as e:
            result["errors"].append(f"Code '{row_data.get('code', '?')}': {str(e)}")
            result["skipped"] += 1
    print(f"📊 엑셀 가져오기 완료 - 생성: {result['created']}, 수정: {result['updated']}, "
          f"건너뜀: {result['skipped']}, 오류: {len(result['errors'])}")
    return result


def _build_category_map(business_id: int) -> Dict[str, int]:
    """카테고리 이름 → ID 매핑을 생성합니다."""
    categories = fetch_all(
        "SELECT id, name FROM stk_categories WHERE business_id = %s", (business_id,))
    return {c["name"].strip().lower(): c["id"] for c in categories}


def _build_supplier_map(business_id: int) -> Dict[str, int]:
    """공급업체 이름 → ID 매핑을 생성합니다."""
    suppliers = fetch_all(
        "SELECT id, name FROM stk_suppliers WHERE business_id = %s", (business_id,))
    return {s["name"].strip().lower(): s["id"] for s in suppliers}


def _process_import_row(business_id: int, row_data: Dict,
                        category_map: Dict[str, int],
                        supplier_map: Dict[str, int],
                        result: Dict) -> None:
    """엑셀 한 행을 처리하여 상품을 생성 또는 수정합니다."""
    category_id = _resolve_category_id(row_data.get("category_name", ""), category_map)
    supplier_id = _resolve_supplier_id(row_data.get("supplier_name", ""), supplier_map)
    product_data = {
        "business_id": business_id,
        "code": row_data["code"],
        "name": row_data["name"],
        "barcode": row_data.get("barcode", ""),
        "description": row_data.get("description", ""),
        "storage_location": row_data.get("storage_location", ""),
        "category_id": category_id,
        "supplier_id": supplier_id,
        "unit": row_data.get("unit", "ea"),
        "unit_price": row_data.get("unit_price", 0),
        "sell_price": row_data.get("sell_price", 0),
        "min_stock": row_data.get("min_stock", 0),
        "max_stock": row_data.get("max_stock"),
    }
    existing = fetch_one(
        "SELECT id FROM stk_products WHERE business_id = %s AND code = %s",
        (business_id, row_data["code"]),
    )
    if existing:
        update_product(existing["id"], product_data)
        result["updated"] += 1
    else:
        save_product(product_data)
        result["created"] += 1


def _resolve_category_id(name: str, category_map: Dict[str, int]) -> Optional[int]:
    """카테고리 이름으로 ID를 조회합니다."""
    if not name:
        return None
    return category_map.get(name.strip().lower())


def _resolve_supplier_id(name: str, supplier_map: Dict[str, int]) -> Optional[int]:
    """공급업체 이름으로 ID를 조회합니다."""
    if not name:
        return None
    return supplier_map.get(name.strip().lower())
