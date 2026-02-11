"""레시피 관리 비즈니스 로직 (식당용)"""
from typing import Dict, List, Optional
from app.db import fetch_one, fetch_all, insert, execute, execute_pos_db
from app.controllers.inventory_controller import process_stock_out


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


def _save_recipe_items(recipe_id: int, items: List[Dict]) -> None:
    """레시피 원재료를 저장합니다."""
    for item in items:
        insert(
            "INSERT INTO stk_recipe_items (recipe_id, product_id, quantity, unit) "
            "VALUES (%s, %s, %s, %s)",
            (recipe_id, item["product_id"], item["quantity"], item.get("unit", "")),
        )
