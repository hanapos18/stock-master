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
    """실사 보고 생성 (식당: 전체/위치별, 마트: 카테고리별)"""
    business_id = session["business"]["id"]
    store = session.get("store")
    if request.method == "POST":
        mode = request.form.get("mode", "category")
        location = request.form.get("location") or None
        if mode == "full":
            data = {
                "business_id": business_id,
                "store_id": store["id"],
                "count_date": request.form["count_date"],
                "location": location,
                "memo": request.form.get("memo", ""),
                "created_by": session["user"]["id"],
            }
            count_id = stock_count_controller.create_full_stock_count(data)
            loc_label = location or "all"
            print(f"위치별 실사 생성: count_id={count_id}, location={loc_label}")
            flash(f"Stock count created ({loc_label}) - enter actual quantities", "success")
        else:
            data = {
                "business_id": business_id,
                "store_id": store["id"],
                "count_date": request.form["count_date"],
                "location": location,
                "category_id": request.form.get("category_id") or None,
                "memo": request.form.get("memo", ""),
                "created_by": session["user"]["id"],
            }
            count_id = stock_count_controller.create_stock_count(data)
            flash("Stock count created - enter actual quantities", "success")
        return redirect(url_for("stock_count.edit_count", count_id=count_id))
    categories = category_controller.load_categories(business_id)
    return render_template("stock-count/create.html", categories=categories,
                           is_restaurant=_is_restaurant(),
                           locations=stock_count_controller.STOCK_LOCATIONS)


@stock_count_bp.route("/<int:count_id>")
@login_required
def view_count(count_id: int):
    """실사 보고 상세"""
    count = stock_count_controller.load_stock_count(count_id)
    return render_template("stock-count/view.html", count=count)


@stock_count_bp.route("/<int:count_id>/edit", methods=["GET", "POST"])
@login_required
def edit_count(count_id: int):
    """실사 수량 입력/수정 (사유 선택 포함)"""
    count = stock_count_controller.load_stock_count(count_id)
    if request.method == "POST":
        items = []
        for key, val in request.form.items():
            if key.startswith("actual_"):
                item_id = int(key.replace("actual_", ""))
                memo_key = f"memo_{item_id}"
                reason_key = f"reason_{item_id}"
                items.append({
                    "id": item_id,
                    "actual_quantity": float(val),
                    "adjust_reason": request.form.get(reason_key, ""),
                    "memo": request.form.get(memo_key, ""),
                })
        stock_count_controller.update_stock_count_items(count_id, items)
        flash("Stock count updated", "success")
        return redirect(url_for("stock_count.view_count", count_id=count_id))
    grouped = {}
    if count and count.get("line_items"):
        for item in count["line_items"]:
            cat = item.get("category_name", "Uncategorized")
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(item)
    return render_template("stock-count/edit.html", count=count, grouped=grouped,
                           adjust_reasons=stock_count_controller.ADJUST_REASONS)


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


@stock_count_bp.route("/combined-review")
@login_required
def combined_review():
    """합산 리뷰: 같은 날짜의 위치별 실사를 합산하여 확인"""
    business_id = session["business"]["id"]
    store = session.get("store")
    count_date = request.args.get("count_date", dt_date.today().strftime("%Y-%m-%d"))
    review = stock_count_controller.load_combined_review(
        business_id, store["id"], count_date
    )
    return render_template("stock-count/combined_review.html",
                           review=review, count_date=count_date,
                           locations=stock_count_controller.STOCK_LOCATIONS)


@stock_count_bp.route("/combined-approve", methods=["POST"])
@login_required
def combined_approve():
    """합산 리뷰 후 일괄 승인"""
    business_id = session["business"]["id"]
    store = session.get("store")
    count_date = request.form["count_date"]
    result = stock_count_controller.approve_combined_counts(
        business_id, store["id"], count_date, user_id=session["user"]["id"]
    )
    if result:
        flash("All location counts approved - inventory adjusted", "success")
    else:
        flash("No pending counts to approve", "danger")
    return redirect(url_for("stock_count.combined_review", count_date=count_date))


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
