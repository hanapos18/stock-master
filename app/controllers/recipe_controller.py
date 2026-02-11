"""레시피 관리 비즈니스 로직 (식당용)"""
from typing import Dict, List, Optional
from io import BytesIO
from app.db import fetch_one, fetch_all, insert, execute, execute_pos_db
from app.controllers.inventory_controller import process_stock_out
from app.services.excel_service import parse_recipe_excel


def load_recipes(business_id: int) -> List[Dict]:
    """레시피 목록을 조회합니다."""
    return fetch_all(
        "SELECT r.*, "
        "(SELECT COUNT(*) FROM stk_recipe_items ri WHERE ri.recipe_id = r.id) AS ingredient_count "
        "FROM stk_recipes r WHERE r.business_id = %s AND r.is_active = 1 ORDER BY r.name",
        (business_id,),
    )


def load_recipe(recipe_id: int) -> Optional[Dict]:
    """레시피 상세를 조회합니다."""
    recipe = fetch_one("SELECT * FROM stk_recipes WHERE id = %s", (recipe_id,))
    if recipe:
        recipe["ingredients"] = fetch_all(
            "SELECT ri.*, p.name AS product_name, p.code AS product_code, p.unit AS product_unit "
            "FROM stk_recipe_items ri JOIN stk_products p ON ri.product_id = p.id "
            "WHERE ri.recipe_id = %s",
            (recipe_id,),
        )
    return recipe


def save_recipe(data: Dict, items: List[Dict]) -> int:
    """레시피를 생성합니다."""
    recipe_id = insert(
        "INSERT INTO stk_recipes (business_id, name, pos_menu_id, description, yield_quantity, yield_unit) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (data["business_id"], data["name"], data.get("pos_menu_id") or None,
         data.get("description", ""), data.get("yield_quantity", 1),
         data.get("yield_unit", "ea")),
    )
    _save_recipe_items(recipe_id, items)
    return recipe_id


def update_recipe(recipe_id: int, data: Dict, items: List[Dict]) -> None:
    """레시피를 수정합니다."""
    execute(
        "UPDATE stk_recipes SET name=%s, pos_menu_id=%s, description=%s, "
        "yield_quantity=%s, yield_unit=%s WHERE id=%s",
        (data["name"], data.get("pos_menu_id") or None, data.get("description", ""),
         data.get("yield_quantity", 1), data.get("yield_unit", "ea"), recipe_id),
    )
    execute("DELETE FROM stk_recipe_items WHERE recipe_id = %s", (recipe_id,))
    _save_recipe_items(recipe_id, items)


def delete_recipe(recipe_id: int) -> int:
    """레시피를 비활성화합니다."""
    return execute("UPDATE stk_recipes SET is_active = 0 WHERE id = %s", (recipe_id,))


def deduct_by_recipe(recipe_id: int, sold_quantity: float,
                     store_id: int, user_id: Optional[int] = None) -> List[Dict]:
    """레시피 기반으로 재고를 차감합니다."""
    recipe = load_recipe(recipe_id)
    if not recipe:
        return []
    results = []
    for item in recipe["ingredients"]:
        deduct_qty = float(item["quantity"]) * sold_quantity
        tx_id = process_stock_out(
            product_id=item["product_id"], store_id=store_id,
            quantity=deduct_qty, location="kitchen",
            reason=f"Recipe: {recipe['name']} x{sold_quantity}",
            user_id=user_id,
        )
        results.append({"product_id": item["product_id"], "quantity": deduct_qty, "tx_id": tx_id})
    return results


def load_pos_menu_items(pos_db_name: str) -> List[Dict]:
    """POS DB에서 메뉴 아이템 목록을 조회합니다."""
    try:
        return execute_pos_db(
            "SELECT id, item_name AS name, item_price AS price "
            "FROM menu_items WHERE is_active = 1 ORDER BY item_name",
            db_name=pos_db_name,
        )
    except Exception as e:
        print(f"POS 메뉴 조회 실패: {e}")
        return []


def calculate_recipe_cost(recipe_id: int) -> Dict:
    """레시피 원가를 계산합니다."""
    recipe = load_recipe(recipe_id)
    if not recipe:
        return {"total_cost": 0, "items": []}
    items_with_cost = []
    total_cost = 0.0
    for item in recipe["ingredients"]:
        product = fetch_one("SELECT unit_price FROM stk_products WHERE id = %s", (item["product_id"],))
        cost = float(item["quantity"]) * float(product["unit_price"]) if product else 0
        total_cost += cost
        items_with_cost.append({**item, "cost": cost})
    return {"total_cost": total_cost, "items": items_with_cost}


def import_recipes_from_excel(business_id: int, file_stream: BytesIO) -> Dict:
    """엑셀 파일에서 레시피를 일괄 등록/수정합니다. 같은 Recipe Name을 그룹핑."""
    rows, parse_errors = parse_recipe_excel(file_stream)
    result = {"created": 0, "updated": 0, "items": 0, "skipped": 0, "errors": list(parse_errors)}
    if parse_errors and not rows:
        return result
    product_map = _build_product_code_map(business_id)
    groups = _group_recipe_rows(rows)
    for recipe_name, ingredients in groups.items():
        try:
            _process_recipe_group(business_id, recipe_name, ingredients, product_map, result)
        except Exception as e:
            result["errors"].append(f"Recipe '{recipe_name}': {str(e)}")
            result["skipped"] += 1
    print(f"📊 레시피 엑셀 가져오기 완료 - 생성: {result['created']}, "
          f"수정: {result['updated']}, 원재료: {result['items']}, 오류: {len(result['errors'])}")
    return result


def _build_product_code_map(business_id: int) -> Dict[str, int]:
    """상품 코드 → ID 매핑."""
    products = fetch_all(
        "SELECT id, code FROM stk_products WHERE business_id = %s AND is_active = 1",
        (business_id,))
    return {p["code"].strip().upper(): p["id"] for p in products}


def _group_recipe_rows(rows: List[Dict]) -> Dict[str, List[Dict]]:
    """같은 레시피명을 그룹핑."""
    from collections import OrderedDict
    groups: OrderedDict = OrderedDict()
    for row in rows:
        name = row.get("recipe_name", "")
        if name not in groups:
            groups[name] = []
        groups[name].append(row)
    return groups


def _process_recipe_group(business_id: int, recipe_name: str,
                          ingredients: List[Dict], product_map: Dict,
                          result: Dict) -> None:
    """레시피 그룹을 처리하여 레시피를 생성 또는 수정합니다."""
    first = ingredients[0]
    valid_items = []
    for item in ingredients:
        code = item["product_code"].strip().upper()
        product_id = product_map.get(code)
        if not product_id:
            result["errors"].append(f"Recipe '{recipe_name}': product '{item['product_code']}' not found")
            continue
        valid_items.append({
            "product_id": product_id,
            "quantity": item["quantity"],
            "unit": item.get("unit", ""),
        })
    if not valid_items:
        result["skipped"] += 1
        return
    existing = fetch_one(
        "SELECT id FROM stk_recipes WHERE business_id = %s AND name = %s AND is_active = 1",
        (business_id, recipe_name))
    if existing:
        data = {
            "name": recipe_name,
            "description": first.get("description", ""),
            "yield_quantity": first.get("yield_quantity", 1),
            "yield_unit": first.get("yield_unit", "ea"),
        }
        update_recipe(existing["id"], data, valid_items)
        result["updated"] += 1
    else:
        data = {
            "business_id": business_id,
            "name": recipe_name,
            "description": first.get("description", ""),
            "yield_quantity": first.get("yield_quantity", 1),
            "yield_unit": first.get("yield_unit", "ea"),
        }
        save_recipe(data, valid_items)
        result["created"] += 1
    result["items"] += len(valid_items)


def _save_recipe_items(recipe_id: int, items: List[Dict]) -> None:
    """레시피 원재료를 저장합니다."""
    for item in items:
        insert(
            "INSERT INTO stk_recipe_items (recipe_id, product_id, quantity, unit) "
            "VALUES (%s, %s, %s, %s)",
            (recipe_id, item["product_id"], item["quantity"], item.get("unit", "")),
        )
