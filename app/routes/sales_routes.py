"""자체 판매 관리 라우트 (비POS 사용자용)"""
import json
from datetime import date
from io import BytesIO
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from app.routes.dashboard_routes import login_required
from app.controllers import sales_controller, inventory_controller
from app.services import excel_service
from app.services import receipt_printer

sales_bp = Blueprint("sales", __name__, url_prefix="/sales")


@sales_bp.route("/")
@login_required
def list_sales():
    """판매 목록 (날짜/상태/매장 필터)"""
    from datetime import date as dt_date, timedelta
    business_id = session["business"]["id"]
    is_hq = session.get("is_hq", True)
    store = session.get("store")
    store_id = None if is_hq else (store["id"] if store else None)
    status = request.args.get("status", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    sales = sales_controller.load_sales(business_id, status=status,
                                        date_from=date_from, date_to=date_to,
                                        store_id=store_id)
    summary = sales_controller.load_sales_summary(business_id,
                                                  date_from=date_from, date_to=date_to,
                                                  store_id=store_id)
    today = dt_date.today()
    week_ago = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
    month_start = today.replace(day=1).strftime("%Y-%m-%d")
    return render_template("sales/list.html", sales=sales, selected_status=status,
                           date_from=date_from, date_to=date_to, summary=summary,
                           today=today.strftime("%Y-%m-%d"),
                           week_ago=week_ago, month_start=month_start, is_hq=is_hq)


@sales_bp.route("/settlement")
@login_required
def settlement():
    """일별 정산 페이지 (매장별 필터)"""
    business_id = session["business"]["id"]
    is_hq = session.get("is_hq", True)
    store = session.get("store")
    store_id = None if is_hq else (store["id"] if store else None)
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    if not date_from and not date_to:
        from datetime import date as dt_date, timedelta
        today = dt_date.today()
        date_from = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        date_to = today.strftime("%Y-%m-%d")
    daily = sales_controller.load_daily_settlement(business_id,
                                                   date_from=date_from, date_to=date_to,
                                                   store_id=store_id)
    summary = sales_controller.load_sales_summary(business_id,
                                                  date_from=date_from, date_to=date_to,
                                                  store_id=store_id)
    return render_template("sales/settlement.html", daily=daily, summary=summary,
                           date_from=date_from, date_to=date_to, is_hq=is_hq)


@sales_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_sale():
    """판매 생성"""
    business_id = session["business"]["id"]
    store = session.get("store")
    if request.method == "POST":
        data = {
            "business_id": business_id,
            "store_id": store["id"],
            "sale_date": request.form["sale_date"],
            "customer_name": request.form.get("customer_name", ""),
            "memo": request.form.get("memo", ""),
            "created_by": session["user"]["id"],
        }
        items = _extract_sale_items(request.form)
        sale_id = sales_controller.save_sale(data, items)
        flash("Sale created successfully", "success")
        return redirect(url_for("sales.view_sale", sale_id=sale_id))
    return render_template("sales/form.html", sale=None)


@sales_bp.route("/<int:sale_id>")
@login_required
def view_sale(sale_id: int):
    """판매 상세"""
    sale = sales_controller.load_sale(sale_id)
    return render_template("sales/view.html", sale=sale)


@sales_bp.route("/<int:sale_id>/confirm", methods=["GET", "POST"])
@login_required
def confirm_sale(sale_id: int):
    """판매 확정 — GET: 로트 선택 페이지, POST: 확정 처리"""
    sale = sales_controller.load_sale(sale_id)
    if not sale or sale["status"] != "draft":
        flash("Cannot confirm this sale", "danger")
        return redirect(url_for("sales.view_sale", sale_id=sale_id))
    store = session.get("store")
    if request.method == "GET":
        for item in sale["line_items"]:
            item["lots"] = inventory_controller.load_product_lots(
                item["product_id"], store["id"],
            )
        return render_template("sales/confirm_lots.html", sale=sale, today_date=date.today())
    # POST: 로트 지정 차감 처리
    lot_ids = request.form.getlist("lot_id[]")
    lot_qtys = request.form.getlist("lot_qty[]")
    lot_deductions = []
    for inv_id, qty in zip(lot_ids, lot_qtys):
        if inv_id and qty and float(qty) > 0:
            lot_deductions.append({"inventory_id": int(inv_id), "quantity": float(qty)})
    if lot_deductions:
        inventory_controller.process_lot_stock_out(
            lot_deductions=lot_deductions,
            store_id=store["id"],
            reason=f"Sale #{sale['sale_number']}",
            user_id=session["user"]["id"],
            reference_id=sale_id,
            reference_type="sale",
        )
    from app.db import execute as db_execute
    db_execute("UPDATE stk_sales SET status = 'confirmed' WHERE id = %s", (sale_id,))
    flash("Sale confirmed - inventory updated", "success")
    return redirect(url_for("sales.view_sale", sale_id=sale_id))


@sales_bp.route("/<int:sale_id>/cancel", methods=["POST"])
@login_required
def cancel_sale(sale_id: int):
    """판매 취소"""
    sales_controller.cancel_sale(sale_id)
    flash("Sale cancelled", "warning")
    return redirect(url_for("sales.list_sales"))


@sales_bp.route("/<int:sale_id>/print")
@login_required
def print_delivery(sale_id: int):
    """배송리스트 A4 인쇄용"""
    sale = sales_controller.load_sale(sale_id)
    return render_template("sales/delivery_print.html", sale=sale)


# ── ESC/POS 영수증 프린터 ──

@sales_bp.route("/<int:sale_id>/receipt", methods=["POST"])
@login_required
def print_receipt(sale_id: int):
    """ESC/POS 영수증 프린터로 출력"""
    sale = sales_controller.load_sale(sale_id)
    if not sale:
        return jsonify({"success": False, "message": "Sale not found"}), 404
    business_name = session.get("business", {}).get("name", "Hana StockMaster")
    store_name = session.get("store", {}).get("name", "")
    printer = receipt_printer.build_sale_receipt(sale, store_name, business_name)
    success, message = printer.send()
    return jsonify({"success": success, "message": message})


@sales_bp.route("/<int:sale_id>/receipt/preview")
@login_required
def preview_receipt(sale_id: int):
    """영수증 텍스트 미리보기"""
    sale = sales_controller.load_sale(sale_id)
    if not sale:
        flash("Sale not found", "danger")
        return redirect(url_for("sales.list_sales"))
    business_name = session.get("business", {}).get("name", "Hana StockMaster")
    store_name = session.get("store", {}).get("name", "")
    printer = receipt_printer.build_sale_receipt(sale, store_name, business_name)
    preview_text = printer.get_text_preview()
    import config
    return render_template("sales/receipt_preview.html",
                           sale=sale, preview_text=preview_text,
                           printer_ip=config.PRINTER_IP,
                           printer_width=config.PRINTER_WIDTH)


@sales_bp.route("/printer/test", methods=["POST"])
@login_required
def test_printer():
    """프린터 연결 테스트"""
    success, message = receipt_printer.print_test_page()
    return jsonify({"success": success, "message": message})


@sales_bp.route("/printer/test-connection", methods=["POST"])
@login_required
def test_printer_connection():
    """프린터 연결만 테스트 (인쇄 없이)"""
    success, message = receipt_printer.test_connection()
    return jsonify({"success": success, "message": message})


# ── 엑셀 일괄 업로드 ──

@sales_bp.route("/excel/template")
@login_required
def download_sales_template():
    """판매 엑셀 템플릿 다운로드"""
    output = excel_service.generate_sales_template()
    return send_file(output, as_attachment=True,
                     download_name="sales_upload_template.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@sales_bp.route("/excel/upload", methods=["GET", "POST"])
@login_required
def upload_sales_excel():
    """판매 엑셀 업로드 및 미리보기"""
    if request.method == "GET":
        return render_template("sales/excel_upload.html")
    file = request.files.get("excel_file")
    if not file or not file.filename:
        flash("Please select an Excel file", "danger")
        return redirect(url_for("sales.upload_sales_excel"))
    try:
        file_stream = BytesIO(file.read())
        rows, parse_errors = excel_service.parse_sales_excel(file_stream)
    except Exception as e:
        flash(f"Failed to parse Excel file: {str(e)}", "danger")
        return redirect(url_for("sales.upload_sales_excel"))
    if parse_errors:
        return render_template("sales/excel_upload.html", errors=parse_errors)
    if not rows:
        flash("No data found in the Excel file", "warning")
        return redirect(url_for("sales.upload_sales_excel"))
    business_id = session["business"]["id"]
    resolved, resolve_errors = sales_controller.resolve_sales_items(rows, business_id)
    if resolve_errors:
        return render_template("sales/excel_upload.html", errors=resolve_errors)
    grouped = sales_controller.group_sales_from_rows(resolved)
    grouped_json = json.dumps(grouped, ensure_ascii=False)
    return render_template("sales/excel_preview.html", grouped_sales=grouped,
                           grouped_json=grouped_json,
                           total_items=len(resolved), total_sales=len(grouped))


@sales_bp.route("/excel/process", methods=["POST"])
@login_required
def process_sales_excel():
    """미리보기 후 일괄 처리"""
    grouped_json = request.form.get("grouped_data")
    grouped = json.loads(grouped_json) if grouped_json else None
    if not grouped:
        flash("No pending upload data. Please upload again.", "warning")
        return redirect(url_for("sales.upload_sales_excel"))
    business_id = session["business"]["id"]
    store_id = session["store"]["id"]
    user_id = session["user"]["id"]
    auto_confirm = request.form.get("auto_confirm") == "1"
    created_ids, errors = sales_controller.batch_create_sales(
        grouped, business_id, store_id, user_id, auto_confirm=auto_confirm,
    )
    if errors:
        for err in errors:
            flash(err, "danger")
    if created_ids:
        action = "created and confirmed" if auto_confirm else "created as draft"
        flash(f"{len(created_ids)} sale(s) {action} successfully", "success")
    return redirect(url_for("sales.list_sales"))


def _extract_sale_items(form) -> list:
    """폼에서 판매 항목을 추출합니다."""
    items = []
    product_ids = form.getlist("item_product_id[]")
    quantities = form.getlist("item_quantity[]")
    prices = form.getlist("item_unit_price[]")
    for i in range(len(product_ids)):
        if product_ids[i] and quantities[i]:
            items.append({
                "product_id": int(product_ids[i]),
                "quantity": float(quantities[i]),
                "unit_price": float(prices[i]) if i < len(prices) else 0,
            })
    return items
