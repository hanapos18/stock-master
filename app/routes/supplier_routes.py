"""거래처 관리 라우트"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.routes.dashboard_routes import login_required
from app.controllers import supplier_controller

supplier_bp = Blueprint("supplier", __name__, url_prefix="/suppliers")


@supplier_bp.route("/")
@login_required
def list_suppliers():
    """거래처 목록"""
    business_id = session["business"]["id"]
    suppliers = supplier_controller.load_suppliers(business_id)
    return render_template("supplier/list.html", suppliers=suppliers)


@supplier_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_supplier():
    """거래처 생성"""
    if request.method == "POST":
        data = {
            "business_id": session["business"]["id"],
            "name": request.form["name"],
            "contact_person": request.form.get("contact_person", ""),
            "phone": request.form.get("phone", ""),
            "email": request.form.get("email", ""),
            "address": request.form.get("address", ""),
            "memo": request.form.get("memo", ""),
        }
        supplier_controller.save_supplier(data)
        flash("Supplier created successfully", "success")
        return redirect(url_for("supplier.list_suppliers"))
    return render_template("supplier/form.html", supplier=None)


@supplier_bp.route("/<int:supplier_id>/edit", methods=["GET", "POST"])
@login_required
def edit_supplier(supplier_id: int):
    """거래처 수정"""
    supplier = supplier_controller.load_supplier(supplier_id)
    if request.method == "POST":
        data = {
            "name": request.form["name"],
            "contact_person": request.form.get("contact_person", ""),
            "phone": request.form.get("phone", ""),
            "email": request.form.get("email", ""),
            "address": request.form.get("address", ""),
            "memo": request.form.get("memo", ""),
        }
        supplier_controller.update_supplier(supplier_id, data)
        flash("Supplier updated successfully", "success")
        return redirect(url_for("supplier.list_suppliers"))
    return render_template("supplier/form.html", supplier=supplier)


@supplier_bp.route("/<int:supplier_id>/delete", methods=["POST"])
@login_required
def delete_supplier(supplier_id: int):
    """거래처 비활성화"""
    supplier_controller.delete_supplier(supplier_id)
    flash("Supplier deactivated", "warning")
    return redirect(url_for("supplier.list_suppliers"))
