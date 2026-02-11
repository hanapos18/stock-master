"""StockMaster Flask 앱 팩토리"""
from datetime import timedelta
from flask import Flask
from app.db import init_db


def create_app() -> Flask:
    """Flask 앱을 생성하고 설정합니다."""
    import config
    application = Flask(__name__)
    application.secret_key = config.SECRET_KEY
    application.permanent_session_lifetime = timedelta(hours=24)
    init_db(application)
    _register_blueprints(application)
    _register_context_processors(application)
    _register_template_filters(application)
    _register_error_handlers(application)
    return application


def _register_blueprints(application: Flask) -> None:
    """모든 Blueprint를 등록합니다."""
    from app.routes.auth_routes import auth_bp
    from app.routes.dashboard_routes import dashboard_bp
    from app.routes.business_routes import business_bp
    from app.routes.product_routes import product_bp
    from app.routes.category_routes import category_bp
    from app.routes.supplier_routes import supplier_bp
    from app.routes.inventory_routes import inventory_bp
    from app.routes.purchase_routes import purchase_bp
    from app.routes.recipe_routes import recipe_bp
    from app.routes.wholesale_routes import wholesale_bp
    from app.routes.repackaging_routes import repackaging_bp
    from app.routes.sales_routes import sales_bp
    from app.routes.stock_count_routes import stock_count_bp
    from app.routes.report_routes import report_bp
    from app.routes.help_routes import help_bp
    from app.routes.attachment_routes import attachment_bp
    application.register_blueprint(auth_bp)
    application.register_blueprint(dashboard_bp)
    application.register_blueprint(business_bp)
    application.register_blueprint(product_bp)
    application.register_blueprint(category_bp)
    application.register_blueprint(supplier_bp)
    application.register_blueprint(inventory_bp)
    application.register_blueprint(purchase_bp)
    application.register_blueprint(recipe_bp)
    application.register_blueprint(wholesale_bp)
    application.register_blueprint(repackaging_bp)
    application.register_blueprint(sales_bp)
    application.register_blueprint(stock_count_bp)
    application.register_blueprint(report_bp)
    application.register_blueprint(help_bp)
    application.register_blueprint(attachment_bp)


def _register_template_filters(application: Flask) -> None:
    """커스텀 Jinja2 필터를 등록합니다."""
    from decimal import Decimal

    @application.template_filter("fmt_price")
    def format_price(value, decimals: int = 6) -> str:
        """가격을 소수점 최대 decimals 자리까지 표시하고 트레일링 0을 제거합니다."""
        if value is None:
            return "0"
        num = Decimal(str(value))
        formatted = f"{num:.{decimals}f}"
        if "." in formatted:
            formatted = formatted.rstrip("0").rstrip(".")
        return formatted

    @application.template_filter("fmt_qty")
    def format_quantity(value, decimals: int = 4) -> str:
        """수량을 소수점 최대 decimals 자리까지 표시하고 트레일링 0을 제거합니다."""
        if value is None:
            return "0"
        num = Decimal(str(value))
        formatted = f"{num:.{decimals}f}"
        if "." in formatted:
            formatted = formatted.rstrip("0").rstrip(".")
        return formatted


def _register_error_handlers(application: Flask) -> None:
    """글로벌 에러 핸들러를 등록합니다."""
    from flask import session, redirect, url_for, flash, request
    from werkzeug.exceptions import HTTPException

    @application.errorhandler(Exception)
    def handle_exception(error):
        if isinstance(error, HTTPException):
            return error
        import traceback
        print(f"❌ 예외 발생 [{request.path}]: {type(error).__name__}: {error}")
        traceback.print_exc()
        if "user" in session:
            flash(f"Error: {str(error)[:100]}", "danger")
            referrer = request.referrer
            if referrer and "/auth/" not in referrer:
                return redirect(referrer)
            return redirect(url_for("dashboard.index"))
        return redirect(url_for("auth.login"))

    @application.before_request
    def ensure_session_store():
        if "user" not in session:
            return
        if "store" not in session and "business" in session:
            from app.db import fetch_all
            try:
                stores = fetch_all(
                    "SELECT id, name FROM stk_stores WHERE business_id = %s AND is_active = 1",
                    (session["business"]["id"],),
                )
                if stores:
                    session["store"] = stores[0]
                    session["stores"] = stores
                    print(f"🔧 세션에 store 자동 복구: {stores[0]['name']}")
            except Exception as e:
                print(f"❌ store 복구 실패: {e}")


def _register_context_processors(application: Flask) -> None:
    """전역 템플릿 변수를 등록합니다."""
    from flask import session

    @application.context_processor
    def inject_globals() -> dict:
        return {
            "current_user": session.get("user"),
            "current_business": session.get("business"),
            "current_store": session.get("store"),
        }
