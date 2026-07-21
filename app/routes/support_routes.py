"""Support Request System 라우트 — POS API + 관리 페이지"""
from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for, flash
from app.routes.dashboard_routes import login_required
from app.controllers import support_controller

support_bp = Blueprint("support", __name__, url_prefix="/support")


# ═══════════════════════════════════════════════════════════════
# POS API (라이센스/로그인 불필요 — /api/pos/support prefix)
# ═══════════════════════════════════════════════════════════════

support_api_bp = Blueprint("support_api", __name__, url_prefix="/api/pos/support")


@support_api_bp.route("/request", methods=["POST"])
def api_create_request():
    """POS에서 소모품 주문 또는 A/S 접수."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "Invalid JSON"}), 400
    store_code = data.get("store_code", "")
    request_type = data.get("request_type", "")
    if not store_code or request_type not in ("ORDER", "AS"):
        return jsonify({"success": False, "error": "store_code and valid request_type required"}), 400
    request_id = support_controller.create_request(data)
    print(f"📦 Support 접수: type={request_type}, store={store_code}, id={request_id}")
    return jsonify({"success": True, "request_id": request_id})


@support_api_bp.route("/status", methods=["GET"])
def api_request_status():
    """POS에서 내 매장 접수 상태 조회."""
    store_code = request.args.get("store_code", "")
    if not store_code:
        return jsonify({"success": False, "error": "store_code required"}), 400
    rows = support_controller.get_requests(store_code=store_code, limit=50)
    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "request_type": r["request_type"],
            "items": r["items"],
            "memo": r["memo"],
            "status": r["status"],
            "admin_note": r["admin_note"] or "",
            "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M") if r.get("created_at") else "",
        })
    return jsonify({"success": True, "requests": result})


@support_api_bp.route("/catalog", methods=["GET"])
def api_catalog():
    """POS에서 소모품 카탈로그 조회 (active만)."""
    items = support_controller.get_catalog_list(active_only=True)
    result = []
    for item in items:
        result.append({
            "id": item["id"],
            "category": item["category"],
            "name": item["name"],
            "description": item["description"] or "",
            "unit_price": float(item["unit_price"]) if item["unit_price"] else 0,
            "image_url": item["image_url"] or "",
        })
    return jsonify({"success": True, "catalog": result})


@support_api_bp.route("/videos", methods=["GET"])
def api_videos():
    """POS에서 자가해결 유튜브 동영상 목록 조회 (active만)."""
    category = request.args.get("category", "")
    items = support_controller.get_video_list(active_only=True)
    if category:
        items = [v for v in items if v["category"] == category.upper()]
    result = []
    for v in items:
        result.append({
            "id": v["id"],
            "category": v["category"],
            "title": v["title"],
            "youtube_url": v["youtube_url"],
            "description": v["description"] or "",
        })
    return jsonify({"success": True, "videos": result})


# ═══════════════════════════════════════════════════════════════
# 관리 페이지 (로그인 필요)
# ═══════════════════════════════════════════════════════════════

@support_bp.route("/list")
@login_required
def request_list():
    """접수 목록 페이지."""
    status_filter = request.args.get("status", "")
    type_filter = request.args.get("type", "")
    rows = support_controller.get_requests(
        status=status_filter or None,
        request_type=type_filter or None,
        limit=200,
    )
    pending_count = support_controller.get_pending_count()
    return render_template(
        "support/list.html",
        requests=rows,
        pending_count=pending_count,
        status_filter=status_filter,
        type_filter=type_filter,
    )


@support_bp.route("/<int:request_id>")
@login_required
def request_detail(request_id: int):
    """접수 상세 페이지."""
    req = support_controller.get_request_detail(request_id)
    if not req:
        flash("Request not found", "warning")
        return redirect(url_for("support.request_list"))
    return render_template("support/detail.html", req=req)


@support_bp.route("/<int:request_id>/update", methods=["POST"])
@login_required
def update_status(request_id: int):
    """접수 상태 변경 + 해결 시 육하원칙 기록."""
    status = request.form.get("status", "PENDING")
    admin_note = request.form.get("admin_note", "")
    resolution_data = None
    if status == "DONE":
        resolution_data = {
            "resolved_by": request.form.get("resolved_by", ""),
            "resolution_location": request.form.get("resolution_location", ""),
            "root_cause": request.form.get("root_cause", ""),
            "resolution": request.form.get("resolution", ""),
            "parts_used": request.form.get("parts_used", ""),
        }
    support_controller.update_request_status(request_id, status, admin_note, resolution_data)
    flash("Status updated successfully", "success")
    return redirect(url_for("support.request_detail", request_id=request_id))


@support_bp.route("/api/unread-count")
@login_required
def unread_count():
    """AJAX 폴링용: PENDING 건수 반환."""
    count = support_controller.get_pending_count()
    return jsonify({"count": count})


# ─── 카탈로그 관리 ─────────────────────────────────────────────

@support_bp.route("/catalog")
@login_required
def catalog_list():
    """소모품 카탈로그 관리 페이지."""
    items = support_controller.get_catalog_list()
    return render_template("support/catalog.html", items=items)


@support_bp.route("/catalog/save", methods=["POST"])
@login_required
def catalog_save():
    """카탈로그 항목 추가 또는 수정."""
    item_id = request.form.get("id", type=int)
    data = {
        "category": request.form.get("category", "OTHER"),
        "name": request.form.get("name", "").strip(),
        "description": request.form.get("description", "").strip(),
        "unit_price": request.form.get("unit_price", 0, type=float),
        "image_url": request.form.get("image_url", "").strip(),
        "sort_order": request.form.get("sort_order", 0, type=int),
        "is_active": 1 if request.form.get("is_active") else 0,
    }
    if not data["name"]:
        flash("Name is required", "warning")
        return redirect(url_for("support.catalog_list"))
    if item_id:
        support_controller.update_catalog_item(item_id, data)
        flash("Catalog item updated", "success")
    else:
        data["is_active"] = 1
        support_controller.create_catalog_item(data)
        flash("Catalog item added", "success")
    return redirect(url_for("support.catalog_list"))


@support_bp.route("/catalog/<int:item_id>/delete", methods=["POST"])
@login_required
def catalog_delete(item_id: int):
    """카탈로그 항목 삭제."""
    support_controller.delete_catalog_item(item_id)
    flash("Catalog item deleted", "success")
    return redirect(url_for("support.catalog_list"))


# ─── 동영상 관리 ───────────────────────────────────────────────

@support_bp.route("/videos")
@login_required
def video_list():
    """유튜브 동영상 관리 페이지."""
    items = support_controller.get_video_list()
    return render_template("support/videos.html", items=items)


@support_bp.route("/videos/save", methods=["POST"])
@login_required
def video_save():
    """동영상 추가 또는 수정."""
    video_id = request.form.get("id", type=int)
    data = {
        "category": request.form.get("category", "OTHER"),
        "title": request.form.get("title", "").strip(),
        "youtube_url": request.form.get("youtube_url", "").strip(),
        "description": request.form.get("description", "").strip(),
        "sort_order": request.form.get("sort_order", 0, type=int),
        "is_active": 1 if request.form.get("is_active") else 0,
    }
    if not data["title"] or not data["youtube_url"]:
        flash("Title and YouTube URL are required", "warning")
        return redirect(url_for("support.video_list"))
    if video_id:
        support_controller.update_video(video_id, data)
        flash("Video updated", "success")
    else:
        data["is_active"] = 1
        support_controller.create_video(data)
        flash("Video added", "success")
    return redirect(url_for("support.video_list"))


@support_bp.route("/videos/<int:video_id>/delete", methods=["POST"])
@login_required
def video_delete(video_id: int):
    """동영상 삭제."""
    support_controller.delete_video(video_id)
    flash("Video deleted", "success")
    return redirect(url_for("support.video_list"))
