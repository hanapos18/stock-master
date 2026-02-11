"""소분/리패키징 관리 라우트 (1:N 지원)"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.routes.dashboard_routes import login_required
from app.controllers import repackaging_controller

repackaging_bp = Blueprint("repackaging", __name__, url_prefix="/repackaging")


@repackaging_bp.route("/")
@login_required
def list_rules():
    """소분 규칙 목록"""
    business_id = session["business"]["id"]
    rules = repackaging_controller.load_repackaging_rules(business_id)
    return render_template("repackaging/list.html", rules=rules)


@repackaging_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_rule():
    """소분 규칙 생성 (1:N)"""
    if request.method == "POST":
        data = _parse_rule_form()
        repackaging_controller.save_repackaging_rule(data)
        flash("Repackaging rule created successfully", "success")
        return redirect(url_for("repackaging.list_rules"))
    return render_template("repackaging/form.html", rule=None)


@repackaging_bp.route("/<int:rule_id>/edit", methods=["GET", "POST"])
@login_required
def edit_rule(rule_id: int):
    """소분 규칙 수정 (1:N)"""
    rule = repackaging_controller.load_repackaging_rule(rule_id)
    if request.method == "POST":
        data = _parse_rule_form()
        repackaging_controller.update_repackaging_rule(rule_id, data)
        flash("Repackaging rule updated successfully", "success")
        return redirect(url_for("repackaging.list_rules"))
    return render_template("repackaging/form.html", rule=rule)


@repackaging_bp.route("/<int:rule_id>/delete", methods=["POST"])
@login_required
def delete_rule(rule_id: int):
    """소분 규칙 삭제"""
    repackaging_controller.delete_repackaging_rule(rule_id)
    flash("Repackaging rule deactivated", "warning")
    return redirect(url_for("repackaging.list_rules"))


@repackaging_bp.route("/<int:rule_id>/execute", methods=["POST"])
@login_required
def execute_rule(rule_id: int):
    """소분 실행 (1:N)"""
    store = session.get("store")
    source_quantity = float(request.form["source_quantity"])
    result = repackaging_controller.execute_repackaging(
        rule_id, source_quantity, store["id"], user_id=session["user"]["id"],
    )
    if result["success"]:
        target_summary = ", ".join(
            f"{t['qty']:.2f} {t['unit']} {t['name']}" for t in result["targets"]
        )
        flash(
            f"Repackaged: {result['source_qty']} {result['source_name']} → {target_summary}",
            "success",
        )
    else:
        flash(result["message"], "danger")
    return redirect(url_for("repackaging.list_rules"))


def _parse_rule_form() -> dict:
    """폼에서 소분 규칙 데이터를 파싱합니다 (다중 타겟)."""
    target_ids = request.form.getlist("target_product_id[]")
    target_ratios = request.form.getlist("target_ratio[]")
    targets = []
    for pid, ratio in zip(target_ids, target_ratios):
        if pid and ratio:
            targets.append({
                "target_product_id": int(pid),
                "ratio": float(ratio),
            })
    return {
        "business_id": session["business"]["id"],
        "name": request.form.get("name", "").strip(),
        "source_product_id": int(request.form["source_product_id"]),
        "targets": targets,
    }
