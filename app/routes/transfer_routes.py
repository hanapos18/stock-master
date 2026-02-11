"""매장 간 이동(Inter-Store Transfer) 라우트"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app.routes.dashboard_routes import login_required
from app.controllers import transfer_controller
from app.db import fetch_all

transfer_bp = Blueprint("transfer", __name__, url_prefix="/transfer")


@transfer_bp.route("/")
@login_required
def list_transfers():
    """이동 목록"""
    business_id = session["business"]["id"]
    store = session.get("store")
    status_filter = request.args.get("status", "")
    view_mode = request.args.get("view", "my")
    store_id = store["id"] if view_mode == "my" and store else None
    transfers = transfer_controller.load_transfers(
        business_id, store_id=store_id, status_filter=status_filter,
    )
    return render_template(
        "transfer/list.html",
        transfers=transfers,
        selected_status=status_filter,
        view_mode=view_mode,
        current_store_id=store["id"] if store else None,
    )


@transfer_bp.route("/new", methods=["GET", "POST"])
@login_required
def create_transfer():
    """새 이동 생성"""
    business_id = session["business"]["id"]
    store = session.get("store")
    stores = fetch_all(
        "SELECT id, name, is_warehouse FROM stk_stores "
        "WHERE business_id = %s AND is_active = 1 ORDER BY is_warehouse DESC, name",
        (business_id,),
    )
    if request.method == "POST":
        from_store_id = int(request.form["from_store_id"])
        to_store_id = int(request.form["to_store_id"])
        memo = request.form.get("memo", "")
        lot_ids = request.form.getlist("lot_id[]")
        lot_qtys = request.form.getlist("lot_qty[]")
        items = []
        for inv_id, qty in zip(lot_ids, lot_qtys):
            if inv_id and qty and float(qty) > 0:
                items.append({"inventory_id": int(inv_id), "quantity": float(qty)})
        if not items:
            flash("No items selected for transfer", "warning")
            return redirect(url_for("transfer.create_transfer"))
        if from_store_id == to_store_id:
            flash("Source and destination store cannot be the same", "warning")
            return redirect(url_for("transfer.create_transfer"))
        transfer_id = transfer_controller.create_transfer(
            business_id=business_id,
            from_store_id=from_store_id,
            to_store_id=to_store_id,
            items=items,
            user_id=session["user"]["id"],
            memo=memo,
        )
        flash("Transfer created successfully", "success")
        return redirect(url_for("transfer.detail_transfer", transfer_id=transfer_id))
    return render_template(
        "transfer/new.html",
        stores=stores,
        current_store_id=store["id"] if store else None,
    )


@transfer_bp.route("/<int:transfer_id>")
@login_required
def detail_transfer(transfer_id: int):
    """이동 상세"""
    transfer = transfer_controller.load_transfer_detail(transfer_id)
    if not transfer:
        flash("Transfer not found", "danger")
        return redirect(url_for("transfer.list_transfers"))
    store = session.get("store")
    return render_template(
        "transfer/detail.html",
        transfer=transfer,
        current_store_id=store["id"] if store else None,
    )


@transfer_bp.route("/<int:transfer_id>/ship", methods=["POST"])
@login_required
def ship_transfer(transfer_id: int):
    """발송 확인"""
    result = transfer_controller.ship_transfer(
        transfer_id=transfer_id,
        user_id=session["user"]["id"],
    )
    if result:
        flash("Transfer shipped — inventory deducted from source store", "success")
    else:
        flash("Cannot ship this transfer (invalid status)", "danger")
    return redirect(url_for("transfer.detail_transfer", transfer_id=transfer_id))


@transfer_bp.route("/<int:transfer_id>/receive", methods=["POST"])
@login_required
def receive_transfer(transfer_id: int):
    """수령 확인"""
    item_ids = request.form.getlist("item_id[]")
    recv_qtys = request.form.getlist("received_qty[]")
    received_items = []
    for item_id, qty in zip(item_ids, recv_qtys):
        if item_id and qty:
            received_items.append({
                "item_id": int(item_id),
                "received_quantity": float(qty),
            })
    result = transfer_controller.receive_transfer(
        transfer_id=transfer_id,
        user_id=session["user"]["id"],
        received_items=received_items if received_items else None,
    )
    if result:
        flash("Transfer received — inventory added to destination store", "success")
    else:
        flash("Cannot receive this transfer (invalid status)", "danger")
    return redirect(url_for("transfer.detail_transfer", transfer_id=transfer_id))


@transfer_bp.route("/<int:transfer_id>/cancel", methods=["POST"])
@login_required
def cancel_transfer(transfer_id: int):
    """이동 취소"""
    result = transfer_controller.cancel_transfer(
        transfer_id=transfer_id,
        user_id=session["user"]["id"],
    )
    if result:
        flash("Transfer cancelled", "warning")
    else:
        flash("Cannot cancel this transfer (only pending transfers can be cancelled)", "danger")
    return redirect(url_for("transfer.detail_transfer", transfer_id=transfer_id))


@transfer_bp.route("/api/lots/<int:store_id>/<int:product_id>")
@login_required
def api_store_product_lots(store_id: int, product_id: int):
    """특정 매장의 상품 로트 목록 API"""
    from datetime import date
    from app.controllers.inventory_controller import load_product_lots
    lots = load_product_lots(product_id, store_id)
    today = date.today()
    result = []
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
