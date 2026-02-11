"""소분/리패키징 관리 비즈니스 로직 (1:N 지원)"""
from typing import Dict, List, Optional
from app.db import fetch_one, fetch_all, insert, execute
from app.controllers.inventory_controller import process_stock_out, process_stock_in


def load_repackaging_rules(business_id: int) -> List[Dict]:
    """소분 규칙 목록을 조회합니다 (타겟 목록 포함)."""
    rules = fetch_all(
        "SELECT r.id, r.name, r.source_product_id, r.is_active, r.created_at, "
        "sp.name AS source_name, sp.code AS source_code, sp.unit AS source_unit "
        "FROM stk_repackaging r "
        "JOIN stk_products sp ON r.source_product_id = sp.id "
        "WHERE r.business_id = %s AND r.is_active = 1 ORDER BY r.name, sp.name",
        (business_id,),
    )
    for rule in rules:
        rule["targets"] = _load_rule_targets(rule["id"])
    return rules


def load_repackaging_rule(rule_id: int) -> Optional[Dict]:
    """소분 규칙 상세를 조회합니다 (타겟 목록 포함)."""
    rule = fetch_one(
        "SELECT r.id, r.name, r.business_id, r.source_product_id, r.is_active, "
        "sp.name AS source_name, sp.code AS source_code, sp.unit AS source_unit "
        "FROM stk_repackaging r "
        "JOIN stk_products sp ON r.source_product_id = sp.id "
        "WHERE r.id = %s",
        (rule_id,),
    )
    if rule:
        rule["targets"] = _load_rule_targets(rule_id)
    return rule


def _load_rule_targets(repackaging_id: int) -> List[Dict]:
    """소분 규칙의 타겟 목록을 조회합니다."""
    return fetch_all(
        "SELECT rt.id, rt.target_product_id, rt.ratio, "
        "tp.name AS target_name, tp.code AS target_code, tp.unit AS target_unit "
        "FROM stk_repackaging_targets rt "
        "JOIN stk_products tp ON rt.target_product_id = tp.id "
        "WHERE rt.repackaging_id = %s ORDER BY rt.id",
        (repackaging_id,),
    )


def save_repackaging_rule(data: Dict) -> int:
    """소분 규칙을 생성합니다 (1:N 타겟 포함)."""
    rule_id = insert(
        "INSERT INTO stk_repackaging (business_id, name, source_product_id) "
        "VALUES (%s, %s, %s)",
        (data["business_id"], data["name"], data["source_product_id"]),
    )
    _save_targets(rule_id, data.get("targets", []))
    return rule_id


def update_repackaging_rule(rule_id: int, data: Dict) -> int:
    """소분 규칙을 수정합니다 (타겟 삭제 후 재입력)."""
    execute(
        "UPDATE stk_repackaging SET name=%s, source_product_id=%s WHERE id=%s",
        (data["name"], data["source_product_id"], rule_id),
    )
    execute("DELETE FROM stk_repackaging_targets WHERE repackaging_id = %s", (rule_id,))
    _save_targets(rule_id, data.get("targets", []))
    return rule_id


def _save_targets(repackaging_id: int, targets: List[Dict]) -> None:
    """타겟 목록을 저장합니다."""
    for target in targets:
        insert(
            "INSERT INTO stk_repackaging_targets (repackaging_id, target_product_id, ratio) "
            "VALUES (%s, %s, %s)",
            (repackaging_id, target["target_product_id"], target["ratio"]),
        )


def delete_repackaging_rule(rule_id: int) -> int:
    """소분 규칙을 비활성화합니다."""
    return execute("UPDATE stk_repackaging SET is_active = 0 WHERE id = %s", (rule_id,))


def execute_repackaging(rule_id: int, source_quantity: float,
                        store_id: int, user_id: Optional[int] = None) -> Dict:
    """소분을 실행합니다 (원재료 1 출고 → 타겟 N 입고)."""
    rule = load_repackaging_rule(rule_id)
    if not rule:
        return {"success": False, "message": "Rule not found"}
    targets = rule.get("targets", [])
    if not targets:
        return {"success": False, "message": "No target products defined"}
    process_stock_out(
        product_id=rule["source_product_id"], store_id=store_id,
        quantity=source_quantity, location="warehouse",
        reason=f"소분출고: {rule['name'] or rule['source_name']}",
        user_id=user_id,
    )
    result_targets = []
    for target in targets:
        target_qty = source_quantity * float(target["ratio"])
        process_stock_in(
            product_id=target["target_product_id"], store_id=store_id,
            quantity=target_qty, location="warehouse",
            reason=f"소분입고: {rule['name'] or rule['source_name']} → {target['target_name']}",
            user_id=user_id,
        )
        result_targets.append({
            "name": target["target_name"],
            "qty": target_qty,
            "unit": target["target_unit"],
        })
    return {
        "success": True,
        "source_qty": source_quantity,
        "source_name": rule["source_name"],
        "targets": result_targets,
    }
