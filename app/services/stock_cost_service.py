"""이동평균원가 계산 서비스 (Moving Average Cost)

입고 시 매입 품목(purchase_variant)의 환산 비율을 적용하여
재고 품목(stk_products)의 avg_unit_cost를 갱신한다.

사용 예:
    from app.services.stock_cost_service import process_variant_stock_in

    process_variant_stock_in(
        variant_id=3,          # stk_purchase_variants.id (해표 식용유 18L)
        store_id=1,
        purchase_qty=2,        # 2통
        total_cost=72000,      # 72,000원 (선택 입력, None 가능)
        user_id=1,
    )
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from app.db import fetch_one, execute, insert


def process_variant_stock_in(
    variant_id: int,
    store_id: int,
    purchase_qty: float,
    total_cost: Optional[float] = None,
    user_id: Optional[int] = None,
    reason: str = "",
    expiry_date: Optional[str] = None,
) -> dict:
    """매입 품목(variant) 기반 입고 처리 + 이동평균원가 갱신.

    Args:
        variant_id: stk_purchase_variants.id
        store_id: 입고 매장
        purchase_qty: 매입 단위 수량 (예: 2통)
        total_cost: 총 구매 금액 (None이면 원가 갱신 안 함)
        user_id: 처리자
        reason: 사유
        expiry_date: 유통기한 (YYYY-MM-DD or None)

    Returns:
        dict: {base_qty, new_avg_cost, product_id, transaction_id}
    """
    variant = fetch_one(
        "SELECT pv.*, p.avg_unit_cost, p.total_stock_value, p.name AS product_name "
        "FROM stk_purchase_variants pv "
        "JOIN stk_products p ON pv.product_id = p.id "
        "WHERE pv.id = %s",
        (variant_id,),
    )
    if not variant:
        raise ValueError(f"매입 품목을 찾을 수 없습니다: variant_id={variant_id}")
    product_id = variant["product_id"]
    conversion_rate = Decimal(str(variant["conversion_rate"]))
    base_qty = Decimal(str(purchase_qty)) * conversion_rate
    current_avg_cost = Decimal(str(variant["avg_unit_cost"] or 0))
    current_total_value = Decimal(str(variant["total_stock_value"] or 0))
    current_total_qty = _get_total_inventory_qty(product_id)
    new_avg_cost = current_avg_cost
    if total_cost is not None and total_cost > 0:
        incoming_value = Decimal(str(total_cost))
        new_total_value = current_total_value + incoming_value
        new_total_qty = current_total_qty + base_qty
        if new_total_qty > 0:
            new_avg_cost = (new_total_value / new_total_qty).quantize(
                Decimal("0.000001"), rounding=ROUND_HALF_UP
            )
        _update_product_cost(product_id, new_avg_cost, new_total_value)
        _update_variant_last_price(variant_id, total_cost / float(purchase_qty))
    else:
        added_value = current_avg_cost * base_qty
        new_total_value = current_total_value + added_value
        _update_product_cost(product_id, current_avg_cost, new_total_value)
    _upsert_inventory(product_id, store_id, float(base_qty), expiry_date)
    unit_price = float(new_avg_cost) if total_cost else 0
    tx_id = _record_transaction(
        product_id=product_id,
        store_id=store_id,
        quantity=float(base_qty),
        unit_price=unit_price,
        total_amount=float(total_cost) if total_cost else 0,
        reason=reason or f"입고: {variant['name']} x {purchase_qty}",
        user_id=user_id,
        variant_id=variant_id,
    )
    print(f"📦 입고 완료: {variant['product_name']} +{base_qty}{variant.get('purchase_unit','')} "
          f"(원가: {new_avg_cost}/unit)")
    return {
        "product_id": product_id,
        "base_qty": float(base_qty),
        "new_avg_cost": float(new_avg_cost),
        "transaction_id": tx_id,
    }


def get_product_cost_info(product_id: int) -> dict:
    """상품의 현재 원가 정보를 조회한다."""
    product = fetch_one(
        "SELECT id, name, unit, avg_unit_cost, total_stock_value "
        "FROM stk_products WHERE id = %s",
        (product_id,),
    )
    if not product:
        return {}
    total_qty = _get_total_inventory_qty(product_id)
    return {
        "product_id": product_id,
        "name": product["name"],
        "unit": product["unit"],
        "avg_unit_cost": float(product["avg_unit_cost"] or 0),
        "total_stock_value": float(product["total_stock_value"] or 0),
        "total_quantity": float(total_qty),
    }


def recalculate_product_cost(product_id: int) -> dict:
    """총 재고량과 장부가치를 기반으로 이동평균원가를 재계산한다 (실사 후 보정용)."""
    total_qty = _get_total_inventory_qty(product_id)
    product = fetch_one(
        "SELECT avg_unit_cost, total_stock_value FROM stk_products WHERE id = %s",
        (product_id,),
    )
    if not product or total_qty <= 0:
        execute(
            "UPDATE stk_products SET total_stock_value = 0 WHERE id = %s",
            (product_id,),
        )
        return {"avg_unit_cost": 0, "total_quantity": 0}
    current_avg = Decimal(str(product["avg_unit_cost"] or 0))
    corrected_value = current_avg * total_qty
    execute(
        "UPDATE stk_products SET total_stock_value = %s WHERE id = %s",
        (float(corrected_value), product_id),
    )
    return {
        "avg_unit_cost": float(current_avg),
        "total_stock_value": float(corrected_value),
        "total_quantity": float(total_qty),
    }


def _get_total_inventory_qty(product_id: int) -> Decimal:
    """전 매장 합산 재고 수량을 조회한다."""
    row = fetch_one(
        "SELECT COALESCE(SUM(quantity), 0) AS total "
        "FROM stk_inventory WHERE product_id = %s",
        (product_id,),
    )
    return Decimal(str(row["total"])) if row else Decimal("0")


def _update_product_cost(product_id: int, avg_cost: Decimal, total_value: Decimal) -> None:
    """stk_products의 이동평균원가와 총 장부가치를 갱신한다."""
    execute(
        "UPDATE stk_products SET avg_unit_cost = %s, total_stock_value = %s WHERE id = %s",
        (float(avg_cost), float(total_value), product_id),
    )


def _update_variant_last_price(variant_id: int, price_per_unit: float) -> None:
    """매입 품목의 최근 매입가를 갱신한다."""
    execute(
        "UPDATE stk_purchase_variants SET last_purchase_price = %s WHERE id = %s",
        (price_per_unit, variant_id),
    )


def _upsert_inventory(product_id: int, store_id: int, qty: float,
                      expiry_date: Optional[str] = None) -> None:
    """재고를 증가시킨다 (로트별 관리)."""
    if expiry_date:
        existing = fetch_one(
            "SELECT id FROM stk_inventory "
            "WHERE product_id=%s AND store_id=%s AND expiry_date=%s",
            (product_id, store_id, expiry_date),
        )
    else:
        existing = fetch_one(
            "SELECT id FROM stk_inventory "
            "WHERE product_id=%s AND store_id=%s AND expiry_date IS NULL",
            (product_id, store_id),
        )
    if existing:
        execute(
            "UPDATE stk_inventory SET quantity = quantity + %s WHERE id = %s",
            (qty, existing["id"]),
        )
    else:
        insert(
            "INSERT INTO stk_inventory (product_id, store_id, location, quantity, expiry_date) "
            "VALUES (%s, %s, %s, %s, %s)",
            (product_id, store_id, "warehouse", max(0, qty), expiry_date),
        )


def _record_transaction(product_id: int, store_id: int, quantity: float,
                        unit_price: float = 0, total_amount: float = 0,
                        reason: str = "", user_id: Optional[int] = None,
                        variant_id: Optional[int] = None) -> int:
    """입고 트랜잭션을 기록한다."""
    return insert(
        "INSERT INTO stk_transactions "
        "(product_id, store_id, type, to_location, quantity, unit_price, total_amount, reason, user_id) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (product_id, store_id, "in", "warehouse", quantity, unit_price, total_amount, reason, user_id),
    )
