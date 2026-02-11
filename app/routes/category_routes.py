"""카테고리 관리 라우트"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app.routes.dashboard_routes import login_required
from app.controllers import category_controller

category_bp = Blueprint("category", __name__, url_prefix="/categories")


@category_bp.route("/")
@login_required
def list_categories():
    """카테고리 목록"""
    business_id = session["business"]["id"]
    categories = category_controller.load_categories(business_id)
    return render_template("category/list.html", categories=categories)


@category_bp.route("/create", methods=["POST"])
@login_required
def create_category():
    """카테고리 생성"""
    data = {
        "business_id": session["business"]["id"],
        "name": request.form["name"],
        "parent_id": request.form.get("parent_id") or None,
        "display_order": request.form.get("display_order", 0),
    }
    category_controller.save_category(data)
    flash("Category created successfully", "success")
    return redirect(url_for("category.list_categories"))


@category_bp.route("/<int:category_id>/edit", methods=["POST"])
@login_required
def edit_category(category_id: int):
    """카테고리 수정"""
    data = {
        "name": request.form["name"],
        "parent_id": request.form.get("parent_id") or None,
        "display_order": request.form.get("display_order", 0),
    }
    category_controller.update_category(category_id, data)
    flash("Category updated successfully", "success")
    return redirect(url_for("category.list_categories"))


@category_bp.route("/<int:category_id>/delete", methods=["POST"])
@login_required
def delete_category(category_id: int):
    """카테고리 삭제"""
    category_controller.delete_category(category_id)
    flash("Category deleted", "warning")
    return redirect(url_for("category.list_categories"))


@category_bp.route("/api/list")
@login_required
def api_list_categories():
    """카테고리 목록 JSON API"""
    business_id = session["business"]["id"]
    categories = category_controller.load_categories(business_id)
    return jsonify([{"id": c["id"], "name": c["name"], "parent_id": c["parent_id"]} for c in categories])
