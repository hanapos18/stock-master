"""소분/리패키징 관리 비즈니스 로직 (마트용)"""
from typing import Dict, List, Optional
from app.db import fetch_one, fetch_all, insert, execute
from app.controllers.inventory_controller import process_stock_out, process_stock_in


def load_repackaging_rules(business_id: int) -> List[Dict]:
    """소분 규칙 목록을 조회합니다."""
    return fetch_all(
        "SELECT r.*, "
        "sp.name AS source_name, sp.code AS source_code, sp.unit AS source_unit, "
        "tp.name AS target_name, tp.code AS target_code, tp.unit AS target_unit "
        "FROM stk_repackaging r "
        "JOIN stk_products sp ON r.source_product_id = sp.id "
        "JOIN stk_products tp ON r.target_product_id = tp.id "
        "WHERE r.business_id = %s AND r.is_active = 1 ORDER BY sp.name",
        (business_id,),
    )


def load_repackaging_rule(rule_id: int) -> Optional[Dict]:
    """소분 규칙 상세를 조회합니다."""
    return fetch_one(
        "SELECT r.*, "
        "sp.name AS source_name, sp.code AS source_code, sp.unit AS source_unit, "
        "tp.name AS target_name, tp.code AS target_code, tp.unit AS target_unit "
        "FROM stk_repackaging r "
        "JOIN stk_products sp ON r.source_product_id = sp.id "
        "JOIN stk_products tp ON r.target_product_id = tp.id "
        "WHERE r.id = %s",
        (rule_id,),
    )


def save_repackaging_rule(data: Dict) -> int:
    """소분 규칙을 생성합니다."""
    return insert(
        "INSERT INTO stk_repackaging (business_id, source_product_id, target_product_id, ratio) "
        "VALUES (%s, %s, %s, %s)",
        (data["business_id"], data["source_product_id"],
         data["target_product_id"], data["ratio"]),
    )


def update_repackaging_rule(rule_id: int, data: Dict) -> int:
    """소분 규칙을 수정합니다."""
    return execute(
        "UPDATE stk_repackaging SET source_product_id=%s, target_product_id=%s, ratio=%s WHERE id=%s",
        (data["source_product_id"], data["target_product_id"], data["ratio"], rule_id),
    )


def delete_repackaging_rule(rule_id: int) -> int:
    """소분 규칙을 비활성화합니다."""
    return execute("UPDATE stk_repackaging SET is_active = 0 WHERE id = %s", (rule_id,))


def execute_repackaging(rule_id: int, source_quantity: float,
                        store_id: int, user_id: Optional[int] = None) -> Dict:
    """소분을 실행합니다 (원재료 출고 → 소분 상품 입고)."""
    rule = load_repackaging_rule(rule_id)
    if not rule:
        return {"success": False, "message": "Rule not found"}
    target_quantity = source_quantity * float(rule["ratio"])
    process_stock_out(
        product_id=rule["source_product_id"], store_id=store_id,
        quantity=source_quantity, location="warehouse",
        reason=f"Repackaging: {rule['source_name']} → {rule['target_name']}",
        user_id=user_id,
    )
    process_stock_in(
        product_id=rule["target_product_id"], store_id=store_id,
        quantity=target_quantity, location="warehouse",
        reason=f"Repackaging: {rule['source_name']} → {rule['target_name']}",
        user_id=user_id,
    )
    return {
        "success": True,
        "source_qty": source_quantity,
        "target_qty": target_quantity,
        "source_name": rule["source_name"],
        "target_name": rule["target_name"],
    }
