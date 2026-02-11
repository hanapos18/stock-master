"""실사 재고 보고 라우트"""
from datetime import date as dt_date
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.routes.dashboard_routes import login_required
from app.controllers import stock_count_controller, category_controller

stock_count_bp = Blueprint("stock_count", __name__, url_prefix="/stock-count")


def _is_restaurant() -> bool:
    """현재 사업자가 식당인지 판단합니다."""
    biz_type = session.get("business", {}).get("type", "")
    return biz_type == "restaurant"


@stock_count_bp.route("/")
@login_required
def list_counts():
    """실사 보고 목록"""
    business_id = session["business"]["id"]
    is_hq = session.get("is_hq", True)
    store = session.get("store")
    store_id = None if is_hq else (store["id"] if store else None)
    counts = stock_count_controller.load_stock_counts(business_id, store_id=store_id)
    return render_template("stock-count/list.html", counts=counts,
                           is_restaurant=_is_restaurant())


@stock_count_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_count():
    """실사 보고 생성 (식당: 전체, 마트: 카테고리별)"""
    business_id = session["business"]["id"]
    store = session.get("store")
    if request.method == "POST":
        mode = request.form.get("mode", "category")
        if mode == "full":
            data = {
                "business_id": business_id,
                "store_id": store["id"],
                "count_date": request.form["count_date"],
                "memo": request.form.get("memo", ""),
                "created_by": session["user"]["id"],
            }
            count_id = stock_count_controller.create_full_stock_count(data)
            print(f"전체 실사 생성: count_id={count_id}")
            flash("Full stock count created - enter actual quantities", "success")
        else:
            data = {
                "business_id": business_id,
                "store_id": store["id"],
                "count_date": request.form["count_date"],
                "category_id": request.form.get("category_id") or None,
                "memo": request.form.get("memo", ""),
                "created_by": session["user"]["id"],
            }
            count_id = stock_count_controller.create_stock_count(data)
            flash("Stock count created - enter actual quantities", "success")
        return redirect(url_for("stock_count.edit_count", count_id=count_id))
    categories = category_controller.load_categories(business_id)
    return render_template("stock-count/create.html", categories=categories,
                           is_restaurant=_is_restaurant())


@stock_count_bp.route("/<int:count_id>")
@login_required
def view_count(count_id: int):
    """실사 보고 상세"""
    count = stock_count_controller.load_stock_count(count_id)
    return render_template("stock-count/view.html", count=count)


@stock_count_bp.route("/<int:count_id>/edit", methods=["GET", "POST"])
@login_required
def edit_count(count_id: int):
    """실사 수량 입력/수정"""
    count = stock_count_controller.load_stock_count(count_id)
    if request.method == "POST":
        items = []
        for key, val in request.form.items():
            if key.startswith("actual_"):
                item_id = int(key.replace("actual_", ""))
                memo_key = f"memo_{item_id}"
                items.append({
                    "id": item_id,
                    "actual_quantity": float(val),
                    "memo": request.form.get(memo_key, ""),
                })
        stock_count_controller.update_stock_count_items(count_id, items)
        flash("Stock count updated", "success")
        return redirect(url_for("stock_count.view_count", count_id=count_id))
    # 카테고리별 그룹핑 (식당 전체 실사용)
    grouped = {}
    if count and count.get("line_items"):
        for item in count["line_items"]:
            cat = item.get("category_name", "Uncategorized")
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(item)
    return render_template("stock-count/edit.html", count=count, grouped=grouped)


@stock_count_bp.route("/<int:count_id>/approve", methods=["POST"])
@login_required
def approve_count(count_id: int):
    """실사 승인 (재고 조정 반영)"""
    result = stock_count_controller.approve_stock_count(count_id, user_id=session["user"]["id"])
    if result:
        flash("Stock count approved - inventory adjusted", "success")
    else:
        flash("Cannot approve this stock count", "danger")
    return redirect(url_for("stock_count.view_count", count_id=count_id))


@stock_count_bp.route("/coverage")
@login_required
def coverage_report():
    """마트용: 카테고리별 실사 커버리지 보고"""
    business_id = session["business"]["id"]
    store = session.get("store")
    count_date = request.args.get("count_date", dt_date.today().strftime("%Y-%m-%d"))
    coverage = stock_count_controller.load_count_coverage_summary(
        business_id, store["id"], count_date
    )
    return render_template("stock-count/coverage.html",
                           coverage=coverage, count_date=count_date)
