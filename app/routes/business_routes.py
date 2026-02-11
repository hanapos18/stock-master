"""사업장/매장 관리 라우트"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app.routes.dashboard_routes import login_required
from app.controllers import business_controller

business_bp = Blueprint("business", __name__, url_prefix="/business")


@business_bp.route("/")
@login_required
def list_businesses():
    """사업장 목록"""
    businesses = business_controller.load_businesses()
    return render_template("business/list.html", businesses=businesses)


@business_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_business():
    """사업장 생성"""
    if request.method == "POST":
        data = {
            "name": request.form["name"],
            "type": request.form["type"],
            "owner_name": request.form.get("owner_name", ""),
            "business_number": request.form.get("business_number", ""),
            "address": request.form.get("address", ""),
            "phone": request.form.get("phone", ""),
            "memo": request.form.get("memo", ""),
            "pos_db_name": request.form.get("pos_db_name") or None,
        }
        business_controller.save_business(data)
        flash("Business created successfully", "success")
        return redirect(url_for("business.list_businesses"))
    return render_template("business/form.html", business=None)


@business_bp.route("/<int:business_id>/edit", methods=["GET", "POST"])
@login_required
def edit_business(business_id: int):
    """사업장 수정"""
    business = business_controller.load_business(business_id)
    if request.method == "POST":
        data = {
            "name": request.form["name"],
            "type": request.form["type"],
            "owner_name": request.form.get("owner_name", ""),
            "business_number": request.form.get("business_number", ""),
            "address": request.form.get("address", ""),
            "phone": request.form.get("phone", ""),
            "memo": request.form.get("memo", ""),
            "pos_db_name": request.form.get("pos_db_name") or None,
        }
        business_controller.update_business(business_id, data)
        flash("Business updated successfully", "success")
        return redirect(url_for("business.list_businesses"))
    return render_template("business/form.html", business=business)


@business_bp.route("/<int:business_id>/delete", methods=["POST"])
@login_required
def delete_business(business_id: int):
    """사업장 삭제"""
    business_controller.delete_business(business_id)
    flash("Business deleted", "warning")
    return redirect(url_for("business.list_businesses"))


# ── 매장 관리 ──

@business_bp.route("/<int:business_id>/stores")
@login_required
def list_stores(business_id: int):
    """매장 목록"""
    business = business_controller.load_business(business_id)
    stores = business_controller.load_stores(business_id)
    return render_template("business/stores.html", business=business, stores=stores)


@business_bp.route("/<int:business_id>/stores/create", methods=["POST"])
@login_required
def create_store(business_id: int):
    """매장 생성"""
    data = {
        "business_id": business_id,
        "name": request.form["name"],
        "address": request.form.get("address", ""),
        "phone": request.form.get("phone", ""),
        "is_warehouse": 1 if request.form.get("is_warehouse") else 0,
    }
    business_controller.save_store(data)
    flash("Store created successfully", "success")
    return redirect(url_for("business.list_stores", business_id=business_id))


@business_bp.route("/stores/<int:store_id>/edit", methods=["POST"])
@login_required
def edit_store(store_id: int):
    """매장 수정"""
    store = business_controller.load_store(store_id)
    data = {
        "name": request.form["name"],
        "address": request.form.get("address", ""),
        "phone": request.form.get("phone", ""),
        "is_warehouse": 1 if request.form.get("is_warehouse") else 0,
    }
    business_controller.update_store(store_id, data)
    flash("Store updated successfully", "success")
    return redirect(url_for("business.list_stores", business_id=store["business_id"]))


@business_bp.route("/stores/<int:store_id>/delete", methods=["POST"])
@login_required
def delete_store(store_id: int):
    """매장 삭제"""
    store = business_controller.load_store(store_id)
    business_controller.delete_store(store_id)
    flash("Store deleted", "warning")
    return redirect(url_for("business.list_stores", business_id=store["business_id"]))
