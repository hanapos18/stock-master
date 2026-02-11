"""상품 관리 라우트"""
from io import BytesIO
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from app.routes.dashboard_routes import login_required
from app.controllers import product_controller, category_controller, supplier_controller
from app.services.excel_service import generate_product_template, generate_excel_report

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


@product_bp.route("/excel/template")
@login_required
def download_template():
    """상품 업로드용 엑셀 템플릿 다운로드"""
    output = generate_product_template()
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="product_upload_template.xlsx",
    )


@product_bp.route("/excel/export")
@login_required
def export_excel():
    """현재 상품 목록을 엑셀로 내보내기"""
    business_id = session["business"]["id"]
    products = product_controller.load_products(business_id, active_only=False)
    headers = ["Code", "Name", "Barcode", "Category", "Supplier",
               "Unit", "Buy Price", "Sell Price", "Min Stock", "Max Stock",
               "Storage Location", "Description"]
    rows = [
        [p["code"], p["name"], p.get("barcode", ""),
         p.get("category_name", "") or "", p.get("supplier_name", "") or "",
         p["unit"], float(p["unit_price"]), float(p["sell_price"]),
         float(p["min_stock"]), float(p["max_stock"]) if p.get("max_stock") else "",
         p.get("storage_location", "") or "", p.get("description", "") or ""]
        for p in products
    ]
    output = generate_excel_report("Products", headers, rows,
                                   column_widths=[14, 25, 18, 18, 18, 10, 14, 14, 12, 12, 20, 30])
    print(f"📊 엑셀 내보내기 완료 - {len(products)}개 상품")
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="products_export.xlsx",
    )


@product_bp.route("/excel/upload", methods=["POST"])
@login_required
def upload_excel():
    """엑셀 파일로 상품 일괄 업로드"""
    business_id = session["business"]["id"]
    file = request.files.get("excel_file")
    if not file or not file.filename:
        flash("Please select an Excel file", "warning")
        return redirect(url_for("product.list_products"))
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        flash("Only .xlsx or .xls files are supported", "danger")
        return redirect(url_for("product.list_products"))
    try:
        file_stream = BytesIO(file.read())
        result = product_controller.import_products_from_excel(business_id, file_stream)
        _flash_import_result(result)
    except Exception as e:
        print(f"❌ 엑셀 업로드 오류: {str(e)}")
        flash(f"Upload failed: {str(e)}", "danger")
    return redirect(url_for("product.list_products"))


def _flash_import_result(result: dict) -> None:
    """업로드 결과를 플래시 메시지로 표시합니다."""
    messages = []
    if result["created"]:
        messages.append(f"{result['created']} created")
    if result["updated"]:
        messages.append(f"{result['updated']} updated")
    if result["skipped"]:
        messages.append(f"{result['skipped']} skipped")
    summary = ", ".join(messages) if messages else "No products processed"
    if result["errors"]:
        error_preview = "; ".join(result["errors"][:5])
        if len(result["errors"]) > 5:
            error_preview += f" ... and {len(result['errors']) - 5} more errors"
        flash(f"Import complete: {summary}. Errors: {error_preview}", "warning")
    else:
        flash(f"Import complete: {summary}", "success")


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
