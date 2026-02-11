"""리포트 라우트"""
from datetime import date, timedelta
from flask import Blueprint, render_template, request, session, jsonify, send_file
from app.routes.dashboard_routes import login_required
from app.controllers import report_controller, business_controller, inventory_controller
from app.services.excel_service import generate_excel_report

report_bp = Blueprint("report", __name__, url_prefix="/reports")


@report_bp.route("/inventory")
@login_required
def inventory_report():
    """재고 현황 리포트"""
    business_id = session["business"]["id"]
    store_id = request.args.get("store_id", 0, type=int)
    data = report_controller.load_inventory_report(business_id, store_id=store_id)
    stores = business_controller.load_stores(business_id)
    total_value = sum(float(r.get("stock_value") or 0) for r in data)
    return render_template("reports/inventory.html", data=data, stores=stores,
                           selected_store=store_id, total_value=total_value)


@report_bp.route("/purchases")
@login_required
def purchase_report():
    """매입 리포트"""
    business_id = session["business"]["id"]
    end = request.args.get("end_date", date.today().isoformat())
    start = request.args.get("start_date", (date.today() - timedelta(days=30)).isoformat())
    data = report_controller.load_purchase_report(business_id, start, end)
    total = sum(float(r.get("total_amount") or 0) for r in data)
    return render_template("reports/purchases.html", data=data,
                           start_date=start, end_date=end, total=total)


@report_bp.route("/sales")
@login_required
def sales_report():
    """매출 리포트"""
    business_id = session["business"]["id"]
    end = request.args.get("end_date", date.today().isoformat())
    start = request.args.get("start_date", (date.today() - timedelta(days=30)).isoformat())
    data = report_controller.load_sales_report(business_id, start, end)
    total = sum(float(r.get("total_amount") or 0) for r in data)
    return render_template("reports/sales.html", data=data,
                           start_date=start, end_date=end, total=total)


@report_bp.route("/wholesale")
@login_required
def wholesale_report():
    """도매 리포트"""
    business_id = session["business"]["id"]
    end = request.args.get("end_date", date.today().isoformat())
    start = request.args.get("start_date", (date.today() - timedelta(days=30)).isoformat())
    data = report_controller.load_wholesale_report(business_id, start, end)
    total = sum(float(r.get("final_amount") or 0) for r in data)
    return render_template("reports/wholesale.html", data=data,
                           start_date=start, end_date=end, total=total)


@report_bp.route("/low-stock")
@login_required
def low_stock_report():
    """재고 부족 리포트"""
    business_id = session["business"]["id"]
    data = report_controller.load_low_stock_products(business_id)
    return render_template("reports/low_stock.html", data=data)


@report_bp.route("/expiry")
@login_required
def expiry_report():
    """유통기한 리포트"""
    business_id = session["business"]["id"]
    filter_type = request.args.get("filter", "all")
    data = inventory_controller.load_expiry_report(business_id, filter_type=filter_type)
    alerts = inventory_controller.load_expiry_alerts(business_id)
    return render_template("reports/expiry.html", data=data,
                           filter_type=filter_type, alerts=alerts,
                           today=date.today())


@report_bp.route("/api/export/<report_type>")
@login_required
def export_report(report_type: str):
    """리포트 데이터 JSON 내보내기 (엑셀 변환용)"""
    business_id = session["business"]["id"]
    end = request.args.get("end_date", date.today().isoformat())
    start = request.args.get("start_date", (date.today() - timedelta(days=30)).isoformat())
    if report_type == "inventory":
        data = report_controller.load_inventory_report(business_id)
    elif report_type == "purchases":
        data = report_controller.load_purchase_report(business_id, start, end)
    elif report_type == "sales":
        data = report_controller.load_sales_report(business_id, start, end)
    elif report_type == "wholesale":
        data = report_controller.load_wholesale_report(business_id, start, end)
    else:
        data = []
    serialized = []
    for row in data:
        s_row = {}
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                s_row[k] = v.isoformat()
            else:
                s_row[k] = v
        serialized.append(s_row)
    return jsonify(serialized)


@report_bp.route("/excel/<report_type>")
@login_required
def download_excel(report_type: str):
    """엑셀 파일 다운로드"""
    business_id = session["business"]["id"]
    end = request.args.get("end_date", date.today().isoformat())
    start = request.args.get("start_date", (date.today() - timedelta(days=30)).isoformat())
    if report_type == "inventory":
        data = report_controller.load_inventory_report(business_id)
        headers = ["Code", "Product", "Category", "Store", "Unit", "Qty", "Buy Price", "Sell Price", "Value"]
        rows = [[r.get("code"), r.get("name"), r.get("category_name", ""), r.get("store_name", ""),
                 r.get("unit"), float(r.get("total_qty", 0)), float(r.get("unit_price", 0)),
                 float(r.get("sell_price", 0)), float(r.get("stock_value") or 0)] for r in data]
        title = "Inventory Report"
    elif report_type == "purchases":
        data = report_controller.load_purchase_report(business_id, start, end)
        headers = ["Date", "Number", "Supplier", "Store", "Amount", "Status"]
        rows = [[str(r.get("purchase_date")), r.get("purchase_number"), r.get("supplier_name", ""),
                 r.get("store_name"), float(r.get("total_amount", 0)), r.get("status")] for r in data]
        title = "Purchase Report"
    elif report_type == "sales":
        data = report_controller.load_sales_report(business_id, start, end)
        headers = ["Date", "Number", "Customer", "Store", "Amount", "Status"]
        rows = [[str(r.get("sale_date")), r.get("sale_number"), r.get("customer_name", ""),
                 r.get("store_name"), float(r.get("total_amount", 0)), r.get("status")] for r in data]
        title = "Sales Report"
    elif report_type == "wholesale":
        data = report_controller.load_wholesale_report(business_id, start, end)
        headers = ["Date", "Number", "Client", "Total", "Discount", "Final", "Status"]
        rows = [[str(r.get("order_date")), r.get("order_number"), r.get("client_name"),
                 float(r.get("total_amount", 0)), float(r.get("discount_amount", 0)),
                 float(r.get("final_amount", 0)), r.get("status")] for r in data]
        title = "Wholesale Report"
    else:
        headers = []
        rows = []
        title = "Report"
    output = generate_excel_report(title, headers, rows)
    filename = f"stockmaster_{report_type}_{date.today().isoformat()}.xlsx"
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name=filename)
