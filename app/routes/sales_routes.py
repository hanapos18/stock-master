"""자체 판매 관리 라우트 (비POS 사용자용)"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.routes.dashboard_routes import login_required
from app.controllers import sales_controller

sales_bp = Blueprint("sales", __name__, url_prefix="/sales")


@sales_bp.route("/")
@login_required
def list_sales():
    """판매 목록"""
    business_id = session["business"]["id"]
    status = request.args.get("status", "")
    sales = sales_controller.load_sales(business_id, status=status)
    return render_template("sales/list.html", sales=sales, selected_status=status)


@sales_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_sale():
    """판매 생성"""
    business_id = session["business"]["id"]
    store = session.get("store")
    if request.method == "POST":
        data = {
            "business_id": business_id,
            "store_id": store["id"],
            "sale_date": request.form["sale_date"],
            "customer_name": request.form.get("customer_name", ""),
            "memo": request.form.get("memo", ""),
            "created_by": session["user"]["id"],
        }
        items = _extract_sale_items(request.form)
        sale_id = sales_controller.save_sale(data, items)
        flash("Sale created successfully", "success")
        return redirect(url_for("sales.view_sale", sale_id=sale_id))
    return render_template("sales/form.html", sale=None)


@sales_bp.route("/<int:sale_id>")
@login_required
def view_sale(sale_id: int):
    """판매 상세"""
    sale = sales_controller.load_sale(sale_id)
    return render_template("sales/view.html", sale=sale)


@sales_bp.route("/<int:sale_id>/confirm", methods=["POST"])
@login_required
def confirm_sale(sale_id: int):
    """판매 확정 (재고 차감)"""
    result = sales_controller.confirm_sale(sale_id, user_id=session["user"]["id"])
    if result:
        flash("Sale confirmed - inventory updated", "success")
    else:
        flash("Cannot confirm this sale", "danger")
    return redirect(url_for("sales.view_sale", sale_id=sale_id))


@sales_bp.route("/<int:sale_id>/cancel", methods=["POST"])
@login_required
def cancel_sale(sale_id: int):
    """판매 취소"""
    sales_controller.cancel_sale(sale_id)
    flash("Sale cancelled", "warning")
    return redirect(url_for("sales.list_sales"))


@sales_bp.route("/<int:sale_id>/print")
@login_required
def print_delivery(sale_id: int):
    """배송리스트 A4 인쇄용"""
    sale = sales_controller.load_sale(sale_id)
    return render_template("sales/delivery_print.html", sale=sale)


def _extract_sale_items(form) -> list:
    """폼에서 판매 항목을 추출합니다."""
    items = []
    product_ids = form.getlist("item_product_id[]")
    quantities = form.getlist("item_quantity[]")
    prices = form.getlist("item_unit_price[]")
    for i in range(len(product_ids)):
        if product_ids[i] and quantities[i]:
            items.append({
                "product_id": int(product_ids[i]),
                "quantity": float(quantities[i]),
                "unit_price": float(prices[i]) if i < len(prices) else 0,
            })
    return items
