"""대시보드 라우트"""
from functools import wraps
from flask import Blueprint, render_template, session, redirect, url_for, request
from app.controllers.inventory_controller import load_inventory_summary, load_expiry_alerts
from app.controllers.report_controller import load_low_stock_products
from app.controllers.pos_sync_controller import load_sync_status
from app.controllers.transfer_controller import load_pending_transfer_counts, load_store_inventory_summary
from app.db import fetch_one, fetch_all

dashboard_bp = Blueprint("dashboard", __name__)


def login_required(f):
    """로그인 필수 데코레이터"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session or "business" not in session:
            has_user = "user" in session
            has_biz = "business" in session
            keys = list(session.keys())
            print(f"🔒 세션 무효 [{request.path}]: user={has_user}, business={has_biz}, keys={keys}")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


@dashboard_bp.route("/")
@login_required
def index():
    """대시보드 메인 페이지 (매장별 필터 적용)"""
    business_id = session["business"]["id"]
    store = session.get("store")
    is_hq = session.get("is_hq", True)
    store_id = store["id"] if store else None
    # 본점/관리자: 전체, 지점 직원: 자기 매장만
    if is_hq:
        summary = load_inventory_summary(business_id)
        low_stock = load_low_stock_products(business_id)
        product_count = fetch_one(
            "SELECT COUNT(*) AS cnt FROM stk_products WHERE business_id=%s AND is_active=1",
            (business_id,),
        )
        recent_tx = fetch_all(
            "SELECT t.*, p.name AS product_name, p.code AS product_code "
            "FROM stk_transactions t "
            "JOIN stk_products p ON t.product_id = p.id "
            "JOIN stk_stores s ON t.store_id = s.id "
            "WHERE s.business_id = %s ORDER BY t.created_at DESC LIMIT 10",
            (business_id,),
        )
    else:
        summary = load_inventory_summary(business_id, store_id=store_id)
        low_stock = load_low_stock_products(business_id, store_id=store_id)
        product_count = fetch_one(
            "SELECT COUNT(DISTINCT i.product_id) AS cnt FROM stk_inventory i "
            "WHERE i.store_id=%s AND i.quantity > 0",
            (store_id,),
        )
        recent_tx = fetch_all(
            "SELECT t.*, p.name AS product_name, p.code AS product_code "
            "FROM stk_transactions t "
            "JOIN stk_products p ON t.product_id = p.id "
            "WHERE t.store_id = %s ORDER BY t.created_at DESC LIMIT 10",
            (store_id,),
        )
    expiry_alerts = load_expiry_alerts(business_id, store_id=None if is_hq else store_id)
    pos_sync = load_sync_status(business_id)
    has_pos = bool(session.get("business", {}).get("pos_db_name"))
    transfer_counts = load_pending_transfer_counts(business_id, store_id) if store_id else {"outgoing": 0, "incoming": 0}
    store_inventory = load_store_inventory_summary(business_id)
    has_multi_stores = len(store_inventory) > 1
    return render_template(
        "dashboard.html",
        summary=summary,
        low_stock=low_stock[:10],
        product_count=product_count["cnt"] if product_count else 0,
        recent_transactions=recent_tx,
        expiry_alerts=expiry_alerts,
        pos_sync=pos_sync,
        has_pos=has_pos,
        transfer_counts=transfer_counts,
        store_inventory=store_inventory,
        has_multi_stores=has_multi_stores,
        is_hq=is_hq,
    )
