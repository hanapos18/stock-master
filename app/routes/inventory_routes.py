"""재고 관리 라우트"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app.routes.dashboard_routes import login_required
from app.controllers import inventory_controller, category_controller, attachment_controller

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")

LOCATION_LABELS = {
    "warehouse": "Warehouse", "kitchen": "Kitchen", "prep_area": "Prep Area",
    "cold_storage": "Cold Storage", "freezer": "Freezer", "dry_storage": "Dry Storage",
    "bar": "Bar", "display": "Display", "display_fresh": "Fresh Display",
    "display_frozen": "Frozen Display", "display_refrigerated": "Refrigerated",
    "backroom": "Backroom",
}


@inventory_bp.route("/")
@login_required
def list_inventory():
    """재고 현황"""
    store = session.get("store")
    if not store:
        flash("Please select a store first", "warning")
        return redirect(url_for("dashboard.index"))
    category_id = request.args.get("category_id", type=int)
    search = request.args.get("search", "")
    low_stock = request.args.get("low_stock", "") == "1"
    items = inventory_controller.load_inventory(
        store["id"], category_id=category_id, search=search, low_stock_only=low_stock,
    )
    business_id = session["business"]["id"]
    categories = category_controller.load_categories(business_id)
    return render_template("inventory/list.html", items=items, categories=categories,
                           locations=LOCATION_LABELS, search=search,
                           selected_category=category_id, low_stock=low_stock)


@inventory_bp.route("/stock-in", methods=["GET", "POST"])
@login_required
def stock_in():
    """입고 처리"""
    store = session.get("store")
    if request.method == "POST":
        tx_id = inventory_controller.process_stock_in(
            product_id=int(request.form["product_id"]),
            store_id=store["id"],
            quantity=float(request.form["quantity"]),
            location=request.form.get("location", "warehouse"),
            unit_price=float(request.form.get("unit_price", 0)),
            reason=request.form.get("reason", ""),
            user_id=session["user"]["id"],
        )
        receipt_file = request.files.get("receipt_file")
        if receipt_file and receipt_file.filename:
            attachment_controller.save_attachment(
                business_id=session["business"]["id"],
                reference_type="transaction",
                reference_id=tx_id,
                file=receipt_file,
                user_id=session["user"]["id"],
            )
        flash("Stock In processed successfully", "success")
        return redirect(url_for("inventory.list_inventory"))
    return render_template("inventory/stock_in.html", locations=LOCATION_LABELS)


@inventory_bp.route("/stock-out", methods=["GET", "POST"])
@login_required
def stock_out():
    """출고 처리"""
    store = session.get("store")
    if request.method == "POST":
        inventory_controller.process_stock_out(
            product_id=int(request.form["product_id"]),
            store_id=store["id"],
            quantity=float(request.form["quantity"]),
            location=request.form.get("location", "warehouse"),
            reason=request.form.get("reason", ""),
            user_id=session["user"]["id"],
        )
        flash("Stock Out processed successfully", "success")
        return redirect(url_for("inventory.list_inventory"))
    return render_template("inventory/stock_out.html", locations=LOCATION_LABELS)


@inventory_bp.route("/adjust", methods=["POST"])
@login_required
def stock_adjust():
    """재고 조정"""
    store = session.get("store")
    inventory_controller.process_stock_adjust(
        product_id=int(request.form["product_id"]),
        store_id=store["id"],
        new_quantity=float(request.form["new_quantity"]),
        location=request.form.get("location", "warehouse"),
        reason=request.form.get("reason", ""),
        user_id=session["user"]["id"],
    )
    flash("Stock adjusted successfully", "success")
    return redirect(url_for("inventory.list_inventory"))


@inventory_bp.route("/discard", methods=["POST"])
@login_required
def stock_discard():
    """폐기 처리"""
    store = session.get("store")
    inventory_controller.process_stock_discard(
        product_id=int(request.form["product_id"]),
        store_id=store["id"],
        quantity=float(request.form["quantity"]),
        location=request.form.get("location", "warehouse"),
        reason=request.form.get("reason", ""),
        user_id=session["user"]["id"],
    )
    flash("Stock discarded", "warning")
    return redirect(url_for("inventory.list_inventory"))


@inventory_bp.route("/move", methods=["POST"])
@login_required
def stock_move():
    """위치 이동"""
    store = session.get("store")
    inventory_controller.process_stock_move(
        product_id=int(request.form["product_id"]),
        store_id=store["id"],
        from_location=request.form["from_location"],
        to_location=request.form["to_location"],
        quantity=float(request.form["quantity"]),
        user_id=session["user"]["id"],
    )
    flash("Stock moved successfully", "success")
    return redirect(url_for("inventory.list_inventory"))


@inventory_bp.route("/transactions")
@login_required
def transactions():
    """입출고 내역"""
    store = session.get("store")
    tx_type = request.args.get("type", "")
    txs = inventory_controller.load_transactions(store["id"], limit=100, tx_type=tx_type)
    tx_ids = [tx["id"] for tx in txs]
    attach_map = attachment_controller.load_attachment_ids_for_references("transaction", tx_ids)
    return render_template("inventory/transactions.html", transactions=txs,
                           selected_type=tx_type, attach_map=attach_map)
