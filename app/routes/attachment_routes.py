"""첨부파일 라우트 (영수증/배송원장 사진 보기/다운로드/삭제 + 세무 앱 연동 API)"""
from flask import Blueprint, Response, jsonify, request, redirect, url_for, flash, session
from app.routes.dashboard_routes import login_required
from app.controllers import attachment_controller

attachment_bp = Blueprint("attachment", __name__, url_prefix="/attachments")


@attachment_bp.route("/<int:attachment_id>/view")
@login_required
def view_attachment(attachment_id: int):
    """첨부파일 이미지 보기 (브라우저 인라인 표시)"""
    att = attachment_controller.load_attachment_data(attachment_id)
    if not att:
        return "Not found", 404
    return Response(
        att["file_data"],
        mimetype=att["file_type"],
        headers={"Content-Disposition": f'inline; filename="{att["file_name"]}"'},
    )


@attachment_bp.route("/<int:attachment_id>/download")
@login_required
def download_attachment(attachment_id: int):
    """첨부파일 다운로드"""
    att = attachment_controller.load_attachment_data(attachment_id)
    if not att:
        return "Not found", 404
    return Response(
        att["file_data"],
        mimetype=att["file_type"],
        headers={"Content-Disposition": f'attachment; filename="{att["file_name"]}"'},
    )


@attachment_bp.route("/<int:attachment_id>/delete", methods=["POST"])
@login_required
def delete_attachment(attachment_id: int):
    """첨부파일 삭제"""
    att = attachment_controller.load_attachment_data(attachment_id)
    if not att:
        flash("Attachment not found", "danger")
        return redirect(request.referrer or url_for("dashboard.index"))
    attachment_controller.delete_attachment(attachment_id)
    flash("Attachment deleted", "warning")
    return redirect(request.referrer or url_for("dashboard.index"))


@attachment_bp.route("/upload/purchase/<int:purchase_id>", methods=["POST"])
@login_required
def upload_to_purchase(purchase_id: int):
    """매입 상세 페이지에서 추가 첨부파일 업로드"""
    receipt_file = request.files.get("receipt_file")
    if receipt_file and receipt_file.filename:
        attachment_controller.save_attachment(
            business_id=session["business"]["id"],
            reference_type="purchase",
            reference_id=purchase_id,
            file=receipt_file,
            user_id=session["user"]["id"],
        )
        flash("Attachment uploaded", "success")
    else:
        flash("No file selected", "warning")
    return redirect(url_for("purchase.view_purchase", purchase_id=purchase_id))


# ── 세무 앱 연동 API ──

@attachment_bp.route("/api/list")
@login_required
def api_list_attachments():
    """기간별 첨부파일 목록 JSON (세무 앱 연동용)"""
    business_id = session["business"]["id"]
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    ref_type = request.args.get("type", "")
    data = attachment_controller.load_attachments_by_period(
        business_id, start_date=start_date, end_date=end_date,
        reference_type=ref_type,
    )
    serialized = []
    for row in data:
        serialized.append({
            "id": row["id"],
            "reference_type": row["reference_type"],
            "reference_id": row["reference_id"],
            "file_name": row["file_name"],
            "file_type": row["file_type"],
            "file_size": row["file_size"],
            "memo": row.get("memo", ""),
            "created_at": row["created_at"].isoformat() if row.get("created_at") else "",
            "view_url": f"/attachments/{row['id']}/view",
            "download_url": f"/attachments/{row['id']}/download",
        })
    return jsonify(serialized)


@attachment_bp.route("/api/<ref_type>/<int:ref_id>")
@login_required
def api_ref_attachments(ref_type: str, ref_id: int):
    """특정 거래의 첨부파일 목록 JSON"""
    data = attachment_controller.load_attachments(ref_type, ref_id)
    serialized = []
    for row in data:
        serialized.append({
            "id": row["id"],
            "file_name": row["file_name"],
            "file_type": row["file_type"],
            "file_size": row["file_size"],
            "memo": row.get("memo", ""),
            "created_at": row["created_at"].isoformat() if row.get("created_at") else "",
            "view_url": f"/attachments/{row['id']}/view",
            "download_url": f"/attachments/{row['id']}/download",
        })
    return jsonify(serialized)


@attachment_bp.route("/api/<int:attachment_id>/data")
@login_required
def api_attachment_data(attachment_id: int):
    """첨부파일 바이너리 데이터 (세무 앱 연동용)"""
    att = attachment_controller.load_attachment_data(attachment_id)
    if not att:
        return jsonify({"error": "Not found"}), 404
    return Response(
        att["file_data"],
        mimetype=att["file_type"],
        headers={"Content-Disposition": f'inline; filename="{att["file_name"]}"'},
    )


def register_attachment_routes(application) -> None:
    """첨부파일 라우트를 등록합니다."""
    application.register_blueprint(attachment_bp)
    print("✅ Attachment routes registered")
