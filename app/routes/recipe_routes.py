"""레시피 관리 라우트 (식당용)"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app.routes.dashboard_routes import login_required
from app.controllers import recipe_controller

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
