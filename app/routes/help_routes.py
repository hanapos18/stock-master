"""도움말 라우트"""
from flask import Blueprint, render_template
from app.routes.dashboard_routes import login_required

help_bp = Blueprint("help", __name__, url_prefix="/help")


@help_bp.route("/")
@login_required
def index():
    """도움말 메인 페이지"""
    return render_template("help/index.html")


@help_bp.route("/<section>")
@login_required
def section(section: str):
    """도움말 섹션 페이지"""
    return render_template("help/index.html", active_section=section)
