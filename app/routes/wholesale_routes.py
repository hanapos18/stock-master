"""도매 관리 라우트 (마트용)"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app.routes.dashboard_routes import login_required
from app.controllers import wholesale_controller

wholesale_bp = Blueprint("wholesale", __name__, url_prefix="/wholesale")


@wholesale_bp.route("/clients")
@login_required
def list_clients():
    """도매 거래처 목록"""
    business_id = session["business"]["id"]
    clients = wholesale_controller.load_wholesale_clients(business_id)
    return render_template("wholesale/clients.html", clients=clients)


@wholesale_bp.route("/clients/create", methods=["GET", "POST"])
@login_required
def create_client():
    """도매 거래처 생성"""
    if request.method == "POST":
        data = {
            "business_id": session["business"]["id"],
            "name": request.form["name"],
            "contact_person": request.form.get("contact_person", ""),
            "phone": request.form.get("phone", ""),
            "email": request.form.get("email", ""),
            "address": request.form.get("address", ""),
            "default_discount_rate": request.form.get("default_discount_rate", 0),
            "memo": request.form.get("memo", ""),
        }
        wholesale_controller.save_wholesale_client(data)
        flash("Wholesale client created successfully", "success")
        return redirect(url_for("wholesale.list_clients"))
    return render_template("wholesale/client_form.html", client=None)


@wholesale_bp.route("/clients/<int:client_id>/edit", methods=["GET", "POST"])
@login_required
def edit_client(client_id: int):
    """도매 거래처 수정"""
    client = wholesale_controller.load_wholesale_client(client_id)
    if request.method == "POST":
        data = {
            "name": request.form["name"],
            "contact_person": request.form.get("contact_person", ""),
            "phone": request.form.get("phone", ""),
            "email": request.form.get("email", ""),
            "address": request.form.get("address", ""),
            "default_discount_rate": request.form.get("default_discount_rate", 0),
            "memo": request.form.get("memo", ""),
        }
        wholesale_controller.update_wholesale_client(client_id, data)
        flash("Wholesale client updated successfully", "success")
        return redirect(url_for("wholesale.list_clients"))
    return render_template("wholesale/client_form.html", client=client)


@wholesale_bp.route("/clients/<int:client_id>/pricing", methods=["POST"])
@login_required
def set_pricing(client_id: int):
    """업체별 할인가 설정"""
    product_id = int(request.form["product_id"])
    data = {
        "discount_type": request.form.get("discount_type", "rate"),
        "discount_rate": request.form.get("discount_rate", 0),
        "fixed_price": request.form.get("fixed_price") or None,
    }
    wholesale_controller.save_wholesale_pricing(client_id, product_id, data)
    flash("Pricing updated", "success")
    return redirect(url_for("wholesale.edit_client", client_id=client_id))


# ── 도매 주문 ──

@wholesale_bp.route("/orders")
@login_required
def list_orders():
    """도매 주문 목록"""
    business_id = session["business"]["id"]
    status = request.args.get("status", "")
    orders = wholesale_controller.load_wholesale_orders(business_id, status=status)
    return render_template("wholesale/orders.html", orders=orders, selected_status=status)


@wholesale_bp.route("/orders/create", methods=["GET", "POST"])
@login_required
def create_order():
    """도매 주문 생성"""
    business_id = session["business"]["id"]
    store = session.get("store")
    if request.method == "POST":
        data = {
            "business_id": business_id,
            "store_id": store["id"],
            "client_id": int(request.form["client_id"]),
            "order_date": request.form["order_date"],
            "delivery_date": request.form.get("delivery_date") or None,
            "memo": request.form.get("memo", ""),
            "created_by": session["user"]["id"],
        }
        items = _extract_order_items(request.form)
        order_id = wholesale_controller.save_wholesale_order(data, items)
        flash("Wholesale order created", "success")
        return redirect(url_for("wholesale.view_order", order_id=order_id))
    clients = wholesale_controller.load_wholesale_clients(business_id)
    return render_template("wholesale/order_form.html", order=None, clients=clients)


@wholesale_bp.route("/orders/<int:order_id>")
@login_required
def view_order(order_id: int):
    """도매 주문 상세 / 배송리스트"""
    order = wholesale_controller.load_wholesale_order(order_id)
    return render_template("wholesale/order_view.html", order=order)


@wholesale_bp.route("/orders/<int:order_id>/ship", methods=["POST"])
@login_required
def ship_order(order_id: int):
    """도매 주문 출고 처리"""
    result = wholesale_controller.ship_wholesale_order(order_id, user_id=session["user"]["id"])
    if result:
        flash("Order shipped - inventory updated", "success")
    else:
        flash("Cannot ship this order", "danger")
    return redirect(url_for("wholesale.view_order", order_id=order_id))


@wholesale_bp.route("/orders/<int:order_id>/print")
@login_required
def print_delivery_list(order_id: int):
    """배송리스트 A4 인쇄용"""
    order = wholesale_controller.load_wholesale_order(order_id)
    return render_template("wholesale/delivery_print.html", order=order)


def _extract_order_items(form) -> list:
    """폼에서 주문 항목을 추출합니다."""
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
