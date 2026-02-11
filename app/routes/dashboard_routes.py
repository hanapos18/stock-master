"""대시보드 라우트"""
from functools import wraps
from flask import Blueprint, render_template, session, redirect, url_for
from app.controllers.inventory_controller import load_inventory_summary
from app.controllers.report_controller import load_low_stock_products
from app.db import fetch_one, fetch_all

dashboard_bp = Blueprint("dashboard", __name__)


def login_required(f):
    """로그인 필수 데코레이터"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


@dashboard_bp.route("/")
@login_required
def index():
    """대시보드 메인 페이지"""
    business_id = session["business"]["id"]
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
    return render_template(
        "dashboard.html",
        summary=summary,
        low_stock=low_stock[:10],
        product_count=product_count["cnt"] if product_count else 0,
        recent_transactions=recent_tx,
    )
