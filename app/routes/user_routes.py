"""사용자 관리 라우트"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.routes.dashboard_routes import login_required
from app.db import fetch_all, fetch_one, execute
from werkzeug.security import generate_password_hash

user_bp = Blueprint("users", __name__, url_prefix="/users")


@user_bp.route("/")
@login_required
def list_users():
    """사용자 목록 (admin만 접근)"""
    if session.get("user", {}).get("role") != "admin":
        flash("Access denied: Admin only", "danger")
        return redirect(url_for("dashboard.index"))
    business_id = session["business"]["id"]
    users = fetch_all(
        "SELECT u.id, u.username, u.name, u.role, u.store_id, u.is_active, "
        "u.created_at, s.name AS store_name "
        "FROM stk_users u "
        "LEFT JOIN stk_stores s ON u.store_id = s.id "
        "WHERE u.business_id = %s ORDER BY u.id",
        (business_id,),
    )
    stores = fetch_all(
        "SELECT id, name, is_warehouse FROM stk_stores "
        "WHERE business_id = %s AND is_active = 1",
        (business_id,),
    )
    return render_template("users/list.html", users=users, stores=stores)


@user_bp.route("/create", methods=["POST"])
@login_required
def create_user():
    """사용자 생성"""
    if session.get("user", {}).get("role") != "admin":
        flash("Access denied: Admin only", "danger")
        return redirect(url_for("dashboard.index"))
    business_id = session["business"]["id"]
    username = request.form.get("username", "").strip()
    name = request.form.get("name", "").strip()
    password = request.form.get("password", "").strip()
    role = request.form.get("role", "staff")
    store_id = request.form.get("store_id", "")
    store_id = int(store_id) if store_id else None
    if not all([username, name, password]):
        flash("All fields are required", "danger")
        return redirect(url_for("users.list_users"))
    existing = fetch_one("SELECT id FROM stk_users WHERE username=%s", (username,))
    if existing:
        flash(f"Username '{username}' already exists", "danger")
        return redirect(url_for("users.list_users"))
    password_hash = generate_password_hash(password)
    execute(
        "INSERT INTO stk_users (business_id, username, password_hash, name, role, store_id) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (business_id, username, password_hash, name, role, store_id),
    )
    scope = "HQ (All Stores)" if store_id is None else f"Store ID={store_id}"
    print(f"사용자 생성: {username} ({role}) - {scope}")
    flash(f"User '{username}' created successfully", "success")
    return redirect(url_for("users.list_users"))


@user_bp.route("/<int:user_id>/update", methods=["POST"])
@login_required
def update_user(user_id: int):
    """사용자 정보 수정 (역할, 소속 매장)"""
    if session.get("user", {}).get("role") != "admin":
        flash("Access denied: Admin only", "danger")
        return redirect(url_for("dashboard.index"))
    role = request.form.get("role", "staff")
    store_id = request.form.get("store_id", "")
    store_id = int(store_id) if store_id else None
    name = request.form.get("name", "").strip()
    new_password = request.form.get("new_password", "").strip()
    if name:
        execute("UPDATE stk_users SET name=%s, role=%s, store_id=%s WHERE id=%s",
                (name, role, store_id, user_id))
    else:
        execute("UPDATE stk_users SET role=%s, store_id=%s WHERE id=%s",
                (role, store_id, user_id))
    if new_password:
        password_hash = generate_password_hash(new_password)
        execute("UPDATE stk_users SET password_hash=%s WHERE id=%s",
                (password_hash, user_id))
    print(f"사용자 수정: ID={user_id}, role={role}, store_id={store_id}")
    flash("User updated successfully", "success")
    return redirect(url_for("users.list_users"))


@user_bp.route("/<int:user_id>/toggle", methods=["POST"])
@login_required
def toggle_user(user_id: int):
    """사용자 활성/비활성 전환"""
    if session.get("user", {}).get("role") != "admin":
        flash("Access denied: Admin only", "danger")
        return redirect(url_for("dashboard.index"))
    if user_id == session.get("user", {}).get("id"):
        flash("Cannot deactivate yourself", "danger")
        return redirect(url_for("users.list_users"))
    execute("UPDATE stk_users SET is_active = NOT is_active WHERE id=%s", (user_id,))
    flash("User status updated", "success")
    return redirect(url_for("users.list_users"))
