"""재고 관리 라우트"""
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app.routes.dashboard_routes import login_required
from app.controllers import inventory_controller, category_controller, attachment_controller, transfer_controller

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
                           selected_category=category_id, low_stock=low_stock,
                           today=date.today())


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
    """출고 처리 (로트 선택 방식)"""
    store = session.get("store")
    if request.method == "POST":
        lot_ids = request.form.getlist("lot_id[]")
        lot_qtys = request.form.getlist("lot_qty[]")
        reason = request.form.get("reason", "")
        lot_deductions = []
        for inv_id, qty in zip(lot_ids, lot_qtys):
            if inv_id and qty and float(qty) > 0:
                lot_deductions.append({"inventory_id": int(inv_id), "quantity": float(qty)})
        if lot_deductions:
            inventory_controller.process_lot_stock_out(
                lot_deductions=lot_deductions,
                store_id=store["id"],
                reason=reason,
                user_id=session["user"]["id"],
            )
            flash("Stock Out processed successfully", "success")
        else:
            flash("No lots selected for stock out", "warning")
        return redirect(url_for("inventory.list_inventory"))
    return render_template("inventory/stock_out.html", locations=LOCATION_LABELS)


@inventory_bp.route("/adjust", methods=["POST"])
@login_required
def stock_adjust():
    """재고 조정 (특정 로트)"""
    store = session.get("store")
    inventory_id = request.form.get("inventory_id", type=int)
    inventory_controller.process_stock_adjust(
        product_id=int(request.form["product_id"]),
        store_id=store["id"],
        new_quantity=float(request.form["new_quantity"]),
        location=request.form.get("location", "warehouse"),
        reason=request.form.get("reason", ""),
        user_id=session["user"]["id"],
        inventory_id=inventory_id,
    )
    flash("Stock adjusted successfully", "success")
    return redirect(url_for("inventory.list_inventory"))


@inventory_bp.route("/discard", methods=["POST"])
@login_required
def stock_discard():
    """폐기 처리 (특정 로트)"""
    store = session.get("store")
    inventory_id = request.form.get("inventory_id", type=int)
    inventory_controller.process_stock_discard(
        product_id=int(request.form["product_id"]),
        store_id=store["id"],
        quantity=float(request.form["quantity"]),
        location=request.form.get("location", "warehouse"),
        reason=request.form.get("reason", ""),
        user_id=session["user"]["id"],
        inventory_id=inventory_id,
    )
    flash("Stock discarded", "warning")
    return redirect(url_for("inventory.list_inventory"))


@inventory_bp.route("/move", methods=["GET", "POST"])
@login_required
def stock_move():
    """위치 이동 (로트 선택 방식)"""
    store = session.get("store")
    if request.method == "GET":
        return render_template("inventory/stock_move.html", locations=LOCATION_LABELS)
    to_location = request.form["to_location"]
    lot_ids = request.form.getlist("lot_id[]")
    lot_qtys = request.form.getlist("lot_qty[]")
    lot_deductions = []
    for inv_id, qty in zip(lot_ids, lot_qtys):
        if inv_id and qty and float(qty) > 0:
            lot_deductions.append({"inventory_id": int(inv_id), "quantity": float(qty)})
    if lot_deductions:
        inventory_controller.process_lot_stock_move(
            lot_deductions=lot_deductions,
            store_id=store["id"],
            to_location=to_location,
            user_id=session["user"]["id"],
        )
        flash("Stock moved successfully", "success")
    else:
        flash("No lots selected for move", "warning")
    return redirect(url_for("inventory.list_inventory"))


@inventory_bp.route("/api/lots/<int:product_id>")
@login_required
def api_product_lots(product_id: int):
    """상품의 로트 목록 API (유통기한별 재고)"""
    store = session.get("store")
    location = request.args.get("location", "")
    lots = inventory_controller.load_product_lots(product_id, store["id"], location=location)
    result = []
    today = date.today()
    for lot in lots:
        expiry = lot.get("expiry_date")
        days_left = (expiry - today).days if expiry else None
        result.append({
            "id": lot["id"],
            "quantity": float(lot["quantity"]),
            "expiry_date": str(expiry) if expiry else None,
            "days_left": days_left,
            "location": lot["location"],
        })
    return jsonify(result)


@inventory_bp.route("/all-stores")
@login_required
def all_stores_inventory():
    """전 매장 합산 재고"""
    business_id = session["business"]["id"]
    search = request.args.get("search", "")
    category_id = request.args.get("category_id", type=int)
    items = transfer_controller.load_all_stores_inventory(
        business_id, search=search, category_id=category_id,
    )
    categories = category_controller.load_categories(business_id)
    store_summary = transfer_controller.load_store_inventory_summary(business_id)
    return render_template(
        "inventory/all_stores.html",
        items=items,
        categories=categories,
        store_summary=store_summary,
        search=search,
        selected_category=category_id,
    )


@inventory_bp.route("/api/store-breakdown/<int:product_id>")
@login_required
def api_store_breakdown(product_id: int):
    """상품의 매장별 재고 분포 API"""
    business_id = session["business"]["id"]
    breakdown = transfer_controller.load_store_breakdown(business_id, product_id)
    result = []
    for s in breakdown:
        result.append({
            "store_id": s["store_id"],
            "store_name": s["store_name"],
            "is_warehouse": bool(s["is_warehouse"]),
            "quantity": float(s["quantity"]),
        })
    return jsonify(result)


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
