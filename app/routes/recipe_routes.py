"""레시피 관리 라우트 (식당용)"""
from io import BytesIO
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from app.routes.dashboard_routes import login_required
from app.controllers import recipe_controller
from app.services.excel_service import generate_recipe_template, generate_excel_report

recipe_bp = Blueprint("recipe", __name__, url_prefix="/recipes")


@recipe_bp.route("/")
@login_required
def list_recipes():
    """레시피 목록"""
    business_id = session["business"]["id"]
    recipes = recipe_controller.load_recipes(business_id)
    return render_template("recipe/list.html", recipes=recipes)


@recipe_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_recipe():
    """레시피 생성"""
    business_id = session["business"]["id"]
    if request.method == "POST":
        data = {
            "business_id": business_id,
            "name": request.form["name"],
            "pos_menu_id": request.form.get("pos_menu_id") or None,
            "description": request.form.get("description", ""),
            "yield_quantity": request.form.get("yield_quantity", 1),
            "yield_unit": request.form.get("yield_unit", "ea"),
        }
        items = _extract_recipe_items(request.form)
        recipe_controller.save_recipe(data, items)
        flash("Recipe created successfully", "success")
        return redirect(url_for("recipe.list_recipes"))
    pos_menu = []
    pos_db = session["business"].get("pos_db_name")
    if pos_db:
        pos_menu = recipe_controller.load_pos_menu_items(pos_db)
    return render_template("recipe/form.html", recipe=None, pos_menu=pos_menu)


@recipe_bp.route("/<int:recipe_id>/edit", methods=["GET", "POST"])
@login_required
def edit_recipe(recipe_id: int):
    """레시피 수정"""
    recipe = recipe_controller.load_recipe(recipe_id)
    if request.method == "POST":
        data = {
            "name": request.form["name"],
            "pos_menu_id": request.form.get("pos_menu_id") or None,
            "description": request.form.get("description", ""),
            "yield_quantity": request.form.get("yield_quantity", 1),
            "yield_unit": request.form.get("yield_unit", "ea"),
        }
        items = _extract_recipe_items(request.form)
        recipe_controller.update_recipe(recipe_id, data, items)
        flash("Recipe updated successfully", "success")
        return redirect(url_for("recipe.list_recipes"))
    pos_menu = []
    pos_db = session["business"].get("pos_db_name")
    if pos_db:
        pos_menu = recipe_controller.load_pos_menu_items(pos_db)
    return render_template("recipe/form.html", recipe=recipe, pos_menu=pos_menu)


@recipe_bp.route("/<int:recipe_id>/delete", methods=["POST"])
@login_required
def delete_recipe(recipe_id: int):
    """레시피 삭제"""
    recipe_controller.delete_recipe(recipe_id)
    flash("Recipe deactivated", "warning")
    return redirect(url_for("recipe.list_recipes"))


@recipe_bp.route("/<int:recipe_id>/cost")
@login_required
def recipe_cost(recipe_id: int):
    """레시피 원가 계산 JSON"""
    result = recipe_controller.calculate_recipe_cost(recipe_id)
    return jsonify(result)


@recipe_bp.route("/deduct", methods=["POST"])
@login_required
def deduct_recipe():
    """레시피 기반 차감"""
    store = session.get("store")
    recipe_id = int(request.form["recipe_id"])
    quantity = float(request.form.get("quantity", 1))
    results = recipe_controller.deduct_by_recipe(
        recipe_id, quantity, store["id"], user_id=session["user"]["id"],
    )
    flash(f"Deducted {len(results)} ingredients from inventory", "success")
    return redirect(url_for("inventory.list_inventory"))


@recipe_bp.route("/excel/template")
@login_required
def download_template():
    """레시피 업로드용 엑셀 템플릿 다운로드"""
    output = generate_recipe_template()
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name="recipe_upload_template.xlsx")


@recipe_bp.route("/excel/export")
@login_required
def export_excel():
    """레시피 목록 엑셀 내보내기 (레시피별 원재료 포함)"""
    business_id = session["business"]["id"]
    recipes = recipe_controller.load_recipes(business_id)
    headers = ["Recipe Name", "Product Code", "Product Name", "Quantity", "Unit",
               "Yield Qty", "Yield Unit", "Description"]
    rows = []
    for r in recipes:
        detail = recipe_controller.load_recipe(r["id"])
        if detail and detail.get("ingredients"):
            for item in detail["ingredients"]:
                rows.append([r["name"], item.get("product_code", ""), item.get("product_name", ""),
                             float(item["quantity"]), item.get("unit", "") or item.get("product_unit", ""),
                             float(r.get("yield_quantity", 1)), r.get("yield_unit", "ea"),
                             r.get("description", "") or ""])
        else:
            rows.append([r["name"], "", "", 0, "", float(r.get("yield_quantity", 1)),
                         r.get("yield_unit", "ea"), r.get("description", "") or ""])
    output = generate_excel_report("Recipes", headers, rows,
                                   column_widths=[25, 14, 25, 12, 10, 12, 12, 30])
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name="recipes_export.xlsx")


@recipe_bp.route("/excel/upload", methods=["POST"])
@login_required
def upload_excel():
    """엑셀 파일로 레시피 일괄 업로드"""
    business_id = session["business"]["id"]
    file = request.files.get("excel_file")
    if not file or not file.filename:
        flash("Please select an Excel file", "warning")
        return redirect(url_for("recipe.list_recipes"))
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        flash("Only .xlsx or .xls files are supported", "danger")
        return redirect(url_for("recipe.list_recipes"))
    try:
        file_stream = BytesIO(file.read())
        result = recipe_controller.import_recipes_from_excel(business_id, file_stream)
        msgs = []
        if result["created"]:
            msgs.append(f"{result['created']} created")
        if result["updated"]:
            msgs.append(f"{result['updated']} updated")
        if result["items"]:
            msgs.append(f"{result['items']} ingredients")
        summary = ", ".join(msgs) if msgs else "No recipes processed"
        if result["errors"]:
            error_preview = "; ".join(result["errors"][:5])
            flash(f"Import: {summary}. Errors: {error_preview}", "warning")
        else:
            flash(f"Import complete: {summary}", "success")
    except Exception as e:
        print(f"❌ 레시피 엑셀 업로드 오류: {str(e)}")
        flash(f"Upload failed: {str(e)}", "danger")
    return redirect(url_for("recipe.list_recipes"))


def _extract_recipe_items(form) -> list:
    """폼에서 레시피 원재료를 추출합니다."""
    items = []
    product_ids = form.getlist("item_product_id[]")
    quantities = form.getlist("item_quantity[]")
    units = form.getlist("item_unit[]")
    for i in range(len(product_ids)):
        if product_ids[i] and quantities[i]:
            items.append({
                "product_id": int(product_ids[i]),
                "quantity": float(quantities[i]),
                "unit": units[i] if i < len(units) else "",
            })
    return items
