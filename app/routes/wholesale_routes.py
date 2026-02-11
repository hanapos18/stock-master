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
    client_balances = wholesale_controller.load_client_balances(business_id)
    balance_map = {b["id"]: float(b["balance"]) for b in client_balances}
    return render_template("wholesale/clients.html", clients=clients, balance_map=balance_map)


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
    payments = wholesale_controller.load_order_payments(order_id)
    balance = float(order["final_amount"]) - float(order["paid_amount"]) if order else 0
    return render_template("wholesale/order_view.html", order=order, payments=payments, balance=balance)


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


@wholesale_bp.route("/orders/<int:order_id>/pay", methods=["POST"])
@login_required
def pay_order(order_id: int):
    """도매 주문 결제 등록"""
    order = wholesale_controller.load_wholesale_order(order_id)
    if not order:
        flash("Order not found", "danger")
        return redirect(url_for("wholesale.list_orders"))
    data = {
        "business_id": order["business_id"],
        "client_id": order["client_id"],
        "payment_method": request.form["payment_method"],
        "amount": float(request.form["amount"]),
        "check_date": request.form.get("check_date") or None,
        "check_number": request.form.get("check_number") or None,
        "bank_name": request.form.get("bank_name") or None,
        "bank_ref": request.form.get("bank_ref") or None,
        "memo": request.form.get("memo", ""),
        "paid_by": session["user"]["id"],
    }
    wholesale_controller.record_payment(order_id, data)
    flash("Payment recorded successfully", "success")
    return redirect(url_for("wholesale.view_order", order_id=order_id))


@wholesale_bp.route("/orders/<int:order_id>/payments")
@login_required
def api_order_payments(order_id: int):
    """주문별 결제 내역 (JSON API)"""
    payments = wholesale_controller.load_order_payments(order_id)
    result = []
    for p in payments:
        result.append({
            "id": p["id"],
            "payment_method": p["payment_method"],
            "amount": float(p["amount"]),
            "check_date": str(p["check_date"]) if p.get("check_date") else None,
            "check_number": p.get("check_number"),
            "bank_name": p.get("bank_name"),
            "bank_ref": p.get("bank_ref"),
            "memo": p.get("memo"),
            "paid_at": str(p["paid_at"]),
            "paid_by_name": p.get("paid_by_name", ""),
        })
    return jsonify(result)


@wholesale_bp.route("/balances")
@login_required
def balances():
    """거래처별 미수금 현황"""
    business_id = session["business"]["id"]
    client_balances = wholesale_controller.load_client_balances(business_id)
    check_schedule = wholesale_controller.load_check_schedule(business_id)
    total_balance = sum(float(c["balance"]) for c in client_balances)
    return render_template(
        "wholesale/balances.html",
        client_balances=client_balances,
        check_schedule=check_schedule,
        total_balance=total_balance,
    )


@wholesale_bp.route("/clients/<int:client_id>/statement")
@login_required
def client_statement(client_id: int):
    """거래처 거래명세서"""
    client = wholesale_controller.load_wholesale_client(client_id)
    if not client:
        flash("Client not found", "danger")
        return redirect(url_for("wholesale.list_clients"))
    orders = wholesale_controller.load_client_orders_with_balance(client_id)
    payments = wholesale_controller.load_client_payment_history(client_id)
    balance_info = wholesale_controller.load_client_balance(client_id)
    return render_template(
        "wholesale/client_statement.html",
        client=client,
        orders=orders,
        payments=payments,
        balance_info=balance_info,
    )


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
