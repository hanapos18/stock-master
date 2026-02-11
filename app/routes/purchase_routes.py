"""매입 관리 라우트"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app.routes.dashboard_routes import login_required
from app.controllers import purchase_controller, supplier_controller, attachment_controller

purchase_bp = Blueprint("purchase", __name__, url_prefix="/purchases")


@purchase_bp.route("/")
@login_required
def list_purchases():
    """매입 목록"""
    business_id = session["business"]["id"]
    status = request.args.get("status", "")
    purchases = purchase_controller.load_purchases(business_id, status=status)
    return render_template("purchase/list.html", purchases=purchases, selected_status=status)


@purchase_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_purchase():
    """매입 생성"""
    business_id = session["business"]["id"]
    store = session.get("store")
    if request.method == "POST":
        data = {
            "business_id": business_id,
            "store_id": store["id"],
            "supplier_id": request.form.get("supplier_id") or None,
            "purchase_date": request.form["purchase_date"],
            "memo": request.form.get("memo", ""),
            "created_by": session["user"]["id"],
        }
        items = _extract_items(request.form)
        purchase_id = purchase_controller.save_purchase(data, items)
        receipt_file = request.files.get("receipt_file")
        if receipt_file and receipt_file.filename:
            attachment_controller.save_attachment(
                business_id=business_id,
                reference_type="purchase",
                reference_id=purchase_id,
                file=receipt_file,
                user_id=session["user"]["id"],
            )
        flash("Purchase created successfully", "success")
        return redirect(url_for("purchase.view_purchase", purchase_id=purchase_id))
    suppliers = supplier_controller.load_suppliers(business_id)
    return render_template("purchase/form.html", purchase=None, suppliers=suppliers)


@purchase_bp.route("/<int:purchase_id>")
@login_required
def view_purchase(purchase_id: int):
    """매입 상세"""
    purchase = purchase_controller.load_purchase(purchase_id)
    attachments = attachment_controller.load_attachments("purchase", purchase_id)
    return render_template("purchase/view.html", purchase=purchase, attachments=attachments)


@purchase_bp.route("/<int:purchase_id>/receive", methods=["POST"])
@login_required
def receive_purchase(purchase_id: int):
    """매입 입고 처리"""
    result = purchase_controller.receive_purchase(purchase_id, user_id=session["user"]["id"])
    if result:
        flash("Purchase received - inventory updated", "success")
    else:
        flash("Cannot receive this purchase", "danger")
    return redirect(url_for("purchase.view_purchase", purchase_id=purchase_id))


@purchase_bp.route("/<int:purchase_id>/cancel", methods=["POST"])
@login_required
def cancel_purchase(purchase_id: int):
    """매입 취소"""
    purchase_controller.cancel_purchase(purchase_id)
    flash("Purchase cancelled", "warning")
    return redirect(url_for("purchase.list_purchases"))


def _extract_items(form) -> list:
    """폼에서 매입 항목들을 추출합니다."""
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
