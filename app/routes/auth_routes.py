"""인증 라우트"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.controllers import auth_controller

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """로그인 페이지"""
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        user = auth_controller.verify_login(username, password)
        if user:
            session.permanent = True
            data = auth_controller.load_user_session_data(user["id"])
            session["user"] = data["user"]
            session["stores"] = data["stores"]
            session["is_hq"] = data["is_hq"]
            session["business"] = {
                "id": user["business_id"],
                "name": user["business_name"],
                "type": user["business_type"],
                "pos_db_name": user.get("pos_db_name"),
            }
            if data["default_store"]:
                session["store"] = data["default_store"]
            store_name = data["default_store"]["name"] if data["default_store"] else "N/A"
            scope = "전체매장" if data["is_hq"] else f"지점({store_name})"
            print(f"로그인 성공: {username} ({user['business_name']}) - {scope}")
            return redirect(url_for("dashboard.index"))
        flash("Invalid username or password", "danger")
    has_users = auth_controller.has_any_user()
    return render_template("login.html", has_users=has_users)


@auth_bp.route("/setup", methods=["POST"])
def setup():
    """초기 설정 (첫 번째 관리자 생성)"""
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    business_name = request.form.get("business_name", "")
    business_type = request.form.get("business_type", "restaurant")
    if not all([username, password, business_name]):
        flash("All fields are required", "danger")
        return redirect(url_for("auth.login"))
    result = auth_controller.create_initial_admin(username, password, business_name, business_type)
    print(f"초기 설정 완료: {business_name} ({business_type})")
    flash("Setup complete! Please login.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/logout")
def logout():
    """로그아웃"""
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/switch-store/<int:store_id>")
def switch_store(store_id: int):
    """매장 전환 (접근 가능한 매장만)"""
    stores = session.get("stores", [])
    matched = False
    for s in stores:
        if s["id"] == store_id:
            session["store"] = s
            flash(f"Switched to {s['name']}", "info")
            matched = True
            break
    if not matched:
        flash("Access denied: You don't have permission for this store", "danger")
    return redirect(request.referrer or url_for("dashboard.index"))
