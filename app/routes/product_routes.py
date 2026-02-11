"""상품 관리 라우트"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app.routes.dashboard_routes import login_required
from app.controllers import product_controller, category_controller, supplier_controller

product_bp = Blueprint("product", __name__, url_prefix="/products")


@product_bp.route("/")
@login_required
def list_products():
    """상품 목록"""
    business_id = session["business"]["id"]
    category_id = request.args.get("category_id", type=int)
    search = request.args.get("search", "")
    products = product_controller.load_products(business_id, category_id=category_id, search=search)
    categories = category_controller.load_categories(business_id)
    return render_template("product/list.html", products=products, categories=categories,
                           search=search, selected_category=category_id)


@product_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_product():
    """상품 생성"""
    business_id = session["business"]["id"]
    if request.method == "POST":
        data = _extract_product_data(business_id)
        product_controller.save_product(data)
        flash("Product created successfully", "success")
        return redirect(url_for("product.list_products"))
    categories = category_controller.load_categories(business_id)
    suppliers = supplier_controller.load_suppliers(business_id)
    next_code = product_controller.generate_product_code(business_id)
    return render_template("product/form.html", product=None, categories=categories,
                           suppliers=suppliers, next_code=next_code)


@product_bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit_product(product_id: int):
    """상품 수정"""
    business_id = session["business"]["id"]
    product = product_controller.load_product(product_id)
    if request.method == "POST":
        data = _extract_product_data(business_id)
        product_controller.update_product(product_id, data)
        flash("Product updated successfully", "success")
        return redirect(url_for("product.list_products"))
    categories = category_controller.load_categories(business_id)
    suppliers = supplier_controller.load_suppliers(business_id)
    return render_template("product/form.html", product=product, categories=categories,
                           suppliers=suppliers, next_code="")


@product_bp.route("/<int:product_id>/delete", methods=["POST"])
@login_required
def delete_product(product_id: int):
    """상품 비활성화"""
    product_controller.delete_product(product_id)
    flash("Product deactivated", "warning")
    return redirect(url_for("product.list_products"))


@product_bp.route("/api/list")
@login_required
def api_list_products():
    """상품 목록 JSON API"""
    business_id = session["business"]["id"]
    search = request.args.get("search", "")
    products = product_controller.load_products(business_id, search=search)
    return jsonify([{
        "id": p["id"], "code": p["code"], "name": p["name"],
        "unit": p["unit"], "unit_price": float(p["unit_price"]),
        "sell_price": float(p["sell_price"]),
    } for p in products])


def _extract_product_data(business_id: int) -> dict:
    """폼에서 상품 데이터를 추출합니다."""
    return {
        "business_id": business_id,
        "code": request.form["code"],
        "name": request.form["name"],
        "barcode": request.form.get("barcode", ""),
        "description": request.form.get("description", ""),
        "storage_location": request.form.get("storage_location", ""),
        "category_id": request.form.get("category_id") or None,
        "supplier_id": request.form.get("supplier_id") or None,
        "unit": request.form.get("unit", "ea"),
        "unit_price": request.form.get("unit_price", 0),
        "sell_price": request.form.get("sell_price", 0),
        "min_stock": request.form.get("min_stock", 0),
        "max_stock": request.form.get("max_stock") or None,
    }
