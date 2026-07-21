"""StockMaster 라이센스 활성화/상태 라우트"""
from flask import Blueprint, request, render_template, redirect, url_for, flash, session, jsonify
from app.utils.license import (
    get_machine_id, validate_license_key, save_license_cache,
    get_license_status, delete_license_cache, check_license,
    BETA_MACHINE_ID,
)

license_bp = Blueprint("license", __name__, url_prefix="/license")


@license_bp.route("/activate", methods=["GET", "POST"])
def activate():
    """라이센스 활성화 페이지."""
    machine_id = get_machine_id()
    status = get_license_status()
    if request.method == "GET":
        return render_template("license/activate.html", machine_id=machine_id, status=status)
    license_key = request.form.get("license_key", "").strip()
    if not license_key:
        flash("Please enter a license key.", "danger")
        return render_template("license/activate.html", machine_id=machine_id, status=status)
    is_valid, period_months = validate_license_key(license_key, machine_id)
    is_beta = license_key.strip().upper().startswith(f"STK-{BETA_MACHINE_ID[:8].upper()}")
    if not is_valid and is_beta:
        is_valid, period_months = validate_license_key(license_key, BETA_MACHINE_ID)
    if not is_valid:
        flash("Invalid license key. Check key and try again.", "danger")
        return render_template("license/activate.html", machine_id=machine_id, status=status)
    ok, msg = save_license_cache(license_key, machine_id, period_months, is_beta=is_beta)
    if ok:
        flash("License activated successfully!", "success")
        return redirect(url_for("license.status_page"))
    flash(f"Activation failed: {msg}", "danger")
    return render_template("license/activate.html", machine_id=machine_id, status=status)


@license_bp.route("/status")
def status_page():
    """라이센스 상태 페이지."""
    machine_id = get_machine_id()
    status = get_license_status()
    return render_template("license/status.html", machine_id=machine_id, status=status)


@license_bp.route("/api/status")
def api_status():
    """라이센스 상태 API (JSON)."""
    return jsonify(get_license_status())


@license_bp.route("/deactivate", methods=["POST"])
def deactivate():
    """라이센스 비활성화 (관리자용)."""
    if "user" in session and session["user"].get("role") == "admin":
        delete_license_cache()
        flash("License deactivated.", "info")
    else:
        flash("Admin access required.", "danger")
    return redirect(url_for("license.activate"))
