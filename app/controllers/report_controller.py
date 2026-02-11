"""리포트 비즈니스 로직"""
from typing import Dict, List
from app.db import fetch_all, fetch_one


def load_inventory_report(business_id: int, store_id: int = 0) -> List[Dict]:
    """재고 현황 리포트를 생성합니다."""
    sql = (
        "SELECT p.code, p.name, p.unit, p.unit_price, p.sell_price, p.min_stock, "
        "c.name AS category_name, s.name AS store_name, "
        "COALESCE(SUM(i.quantity), 0) AS total_qty, "
        "COALESCE(SUM(i.quantity), 0) * p.unit_price AS stock_value "
        "FROM stk_products p "
        "LEFT JOIN stk_inventory i ON p.id = i.product_id "
        "LEFT JOIN stk_stores s ON i.store_id = s.id "
        "LEFT JOIN stk_categories c ON p.category_id = c.id "
        "WHERE p.business_id = %s AND p.is_active = 1"
    )
    params: list = [business_id]
    if store_id:
        sql += " AND i.store_id = %s"
        params.append(store_id)
    sql += " GROUP BY p.id, s.id ORDER BY c.name, p.name"
    return fetch_all(sql, tuple(params))


def load_purchase_report(business_id: int, start_date: str, end_date: str) -> List[Dict]:
    """매입 리포트를 생성합니다."""
    return fetch_all(
        "SELECT p.purchase_date, p.purchase_number, sp.name AS supplier_name, "
        "p.total_amount, p.status, s.name AS store_name "
        "FROM stk_purchases p "
        "JOIN stk_stores s ON p.store_id = s.id "
        "LEFT JOIN stk_suppliers sp ON p.supplier_id = sp.id "
        "WHERE p.business_id = %s AND p.purchase_date BETWEEN %s AND %s "
        "ORDER BY p.purchase_date DESC",
        (business_id, start_date, end_date),
    )


def load_sales_report(business_id: int, start_date: str, end_date: str) -> List[Dict]:
    """매출 리포트를 생성합니다."""
    return fetch_all(
        "SELECT sa.sale_date, sa.sale_number, sa.customer_name, "
        "sa.total_amount, sa.status, s.name AS store_name "
        "FROM stk_sales sa "
        "JOIN stk_stores s ON sa.store_id = s.id "
        "WHERE sa.business_id = %s AND sa.sale_date BETWEEN %s AND %s "
        "ORDER BY sa.sale_date DESC",
        (business_id, start_date, end_date),
    )


def load_wholesale_report(business_id: int, start_date: str, end_date: str) -> List[Dict]:
    """도매 리포트를 생성합니다."""
    return fetch_all(
        "SELECT wo.order_date, wo.order_number, wc.name AS client_name, "
        "wo.total_amount, wo.discount_amount, wo.final_amount, wo.status "
        "FROM stk_wholesale_orders wo "
        "JOIN stk_wholesale_clients wc ON wo.client_id = wc.id "
        "WHERE wo.business_id = %s AND wo.order_date BETWEEN %s AND %s "
        "ORDER BY wo.order_date DESC",
        (business_id, start_date, end_date),
    )


def load_transaction_summary(business_id: int, start_date: str, end_date: str) -> Dict:
    """기간별 입출고 요약을 반환합니다."""
    rows = fetch_all(
        "SELECT t.type, COUNT(*) AS count, COALESCE(SUM(t.total_amount), 0) AS total "
        "FROM stk_transactions t "
        "JOIN stk_stores s ON t.store_id = s.id "
        "WHERE s.business_id = %s AND DATE(t.created_at) BETWEEN %s AND %s "
        "GROUP BY t.type",
        (business_id, start_date, end_date),
    )
    return {row["type"]: {"count": row["count"], "total": float(row["total"])} for row in rows}


def load_low_stock_products(business_id: int) -> List[Dict]:
    """최소 재고 이하 상품 목록을 조회합니다."""
    return fetch_all(
        "SELECT p.code, p.name, p.unit, p.min_stock, "
        "COALESCE(SUM(i.quantity), 0) AS current_stock, "
        "s.name AS store_name "
        "FROM stk_products p "
        "LEFT JOIN stk_inventory i ON p.id = i.product_id "
        "LEFT JOIN stk_stores s ON i.store_id = s.id "
        "WHERE p.business_id = %s AND p.is_active = 1 AND p.min_stock > 0 "
        "GROUP BY p.id, s.id "
        "HAVING COALESCE(SUM(i.quantity), 0) <= p.min_stock "
        "ORDER BY COALESCE(SUM(i.quantity), 0) / p.min_stock ASC",
        (business_id,),
    )
