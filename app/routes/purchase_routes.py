"""매입 관리 라우트"""
from io import BytesIO
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from app.routes.dashboard_routes import login_required
from app.controllers import purchase_controller, supplier_controller, attachment_controller
from app.services.excel_service import generate_purchase_template, generate_excel_report
from app.db import fetch_all, fetch_one, insert, execute

purchase_bp = Blueprint("purchase", __name__, url_prefix="/purchases")


@purchase_bp.route("/")
@login_required
def list_purchases():
    """매입 목록"""
    business_id = session["business"]["id"]
    status = request.args.get("status", "")
    purchases = purchase_controller.load_purchases(business_id, status=status)
    return render_template("purchase/list.html", purchases=purchases, selected_status=status)


@purchase_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_purchase():
    """매입 생성"""
    business_id = session["business"]["id"]
    store = session.get("store")
    if request.method == "POST":
        data = {
            "business_id": business_id,
            "store_id": store["id"],
            "supplier_id": request.form.get("supplier_id") or None,
            "purchase_date": request.form["purchase_date"],
            "memo": request.form.get("memo", ""),
            "created_by": session["user"]["id"],
        }
        items = _extract_items(request.form)
        purchase_id = purchase_controller.save_purchase(data, items)
        receipt_file = request.files.get("receipt_file")
        if receipt_file and receipt_file.filename:
            attachment_controller.save_attachment(
                business_id=business_id,
                reference_type="purchase",
                reference_id=purchase_id,
                file=receipt_file,
                user_id=session["user"]["id"],
            )
        flash("Purchase created successfully", "success")
        return redirect(url_for("purchase.view_purchase", purchase_id=purchase_id))
    suppliers = supplier_controller.load_suppliers(business_id)
    return render_template("purchase/form.html", purchase=None, suppliers=suppliers)


@purchase_bp.route("/<int:purchase_id>")
@login_required
def view_purchase(purchase_id: int):
    """매입 상세"""
    purchase = purchase_controller.load_purchase(purchase_id)
    attachments = attachment_controller.load_attachments("purchase", purchase_id)
    return render_template("purchase/view.html", purchase=purchase, attachments=attachments)


@purchase_bp.route("/<int:purchase_id>/receive", methods=["POST"])
@login_required
def receive_purchase(purchase_id: int):
    """매입 입고 처리"""
    result = purchase_controller.receive_purchase(purchase_id, user_id=session["user"]["id"])
    if result:
        flash("Purchase received - inventory updated", "success")
    else:
        flash("Cannot receive this purchase", "danger")
    return redirect(url_for("purchase.view_purchase", purchase_id=purchase_id))


@purchase_bp.route("/<int:purchase_id>/cancel", methods=["POST"])
@login_required
def cancel_purchase(purchase_id: int):
    """매입 취소"""
    purchase_controller.cancel_purchase(purchase_id)
    flash("Purchase cancelled", "warning")
    return redirect(url_for("purchase.list_purchases"))


@purchase_bp.route("/excel/template")
@login_required
def download_template():
    """매입 업로드용 엑셀 템플릿 다운로드"""
    output = generate_purchase_template()
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name="purchase_upload_template.xlsx")


@purchase_bp.route("/excel/export")
@login_required
def export_excel():
    """매입 목록 엑셀 내보내기"""
    business_id = session["business"]["id"]
    purchases = purchase_controller.load_purchases(business_id)
    headers = ["Number", "Date", "Supplier", "Store", "Amount", "Status", "Memo"]
    rows = [[p["purchase_number"], str(p["purchase_date"]), p.get("supplier_name", "") or "",
             p.get("store_name", ""), float(p["total_amount"]),
             p["status"], p.get("memo", "") or ""] for p in purchases]
    output = generate_excel_report("Purchases", headers, rows,
                                   column_widths=[20, 14, 20, 18, 16, 12, 25])
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name="purchases_export.xlsx")


@purchase_bp.route("/excel/upload", methods=["POST"])
@login_required
def upload_excel():
    """엑셀 파일로 매입 일괄 업로드"""
    business_id = session["business"]["id"]
    store = session.get("store")
    if not store:
        flash("No store selected", "danger")
        return redirect(url_for("purchase.list_purchases"))
    file = request.files.get("excel_file")
    if not file or not file.filename:
        flash("Please select an Excel file", "warning")
        return redirect(url_for("purchase.list_purchases"))
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        flash("Only .xlsx or .xls files are supported", "danger")
        return redirect(url_for("purchase.list_purchases"))
    try:
        file_stream = BytesIO(file.read())
        result = purchase_controller.import_purchases_from_excel(
            business_id, store["id"], session["user"]["id"], file_stream)
        _flash_purchase_import_result(result)
    except Exception as e:
        print(f"❌ 매입 엑셀 업로드 오류: {str(e)}")
        flash(f"Upload failed: {str(e)}", "danger")
    return redirect(url_for("purchase.list_purchases"))


def _flash_purchase_import_result(result: dict) -> None:
    """매입 업로드 결과 플래시 메시지."""
    msgs = []
    if result["created"]:
        msgs.append(f"{result['created']} purchases created ({result['items']} items)")
    if result["skipped"]:
        msgs.append(f"{result['skipped']} skipped")
    summary = ", ".join(msgs) if msgs else "No purchases processed"
    if result["errors"]:
        error_preview = "; ".join(result["errors"][:5])
        if len(result["errors"]) > 5:
            error_preview += f" ... +{len(result['errors']) - 5} more"
        flash(f"Import: {summary}. Errors: {error_preview}", "warning")
    else:
        flash(f"Import complete: {summary}", "success")


def _extract_items(form) -> list:
    """폼에서 매입 항목들을 추출합니다 (유통기한 포함)."""
    items = []
    product_ids = form.getlist("item_product_id[]")
    quantities = form.getlist("item_quantity[]")
    prices = form.getlist("item_unit_price[]")
    expiry_dates = form.getlist("item_expiry_date[]")
    for i in range(len(product_ids)):
        if product_ids[i] and quantities[i]:
            expiry = expiry_dates[i] if i < len(expiry_dates) and expiry_dates[i] else None
            items.append({
                "product_id": int(product_ids[i]),
                "quantity": float(quantities[i]),
                "unit_price": float(prices[i]) if i < len(prices) else 0,
                "expiry_date": expiry,
            })
    return items


# ============================================================
# 매입 품목(Purchase Variants) 관리 및 빠른 입고
# ============================================================

@purchase_bp.route("/variants")
@login_required
def list_variants():
    """매입 품목 목록"""
    business_id = session["business"]["id"]
    variants = fetch_all(
        "SELECT pv.*, p.name AS product_name, p.unit AS base_unit, "
        "s.name AS supplier_name "
        "FROM stk_purchase_variants pv "
        "JOIN stk_products p ON pv.product_id = p.id "
        "LEFT JOIN stk_suppliers s ON pv.supplier_id = s.id "
        "WHERE pv.business_id = %s "
        "ORDER BY p.name, pv.name",
        (business_id,),
    )
    return render_template("purchase/variants.html", variants=variants)


@purchase_bp.route("/variants/create", methods=["GET", "POST"])
@login_required
def create_variant():
    """매입 품목 등록"""
    business_id = session["business"]["id"]
    if request.method == "POST":
        insert(
            "INSERT INTO stk_purchase_variants "
            "(business_id, product_id, name, barcode, purchase_unit, conversion_rate, supplier_id, memo) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                business_id,
                int(request.form["product_id"]),
                request.form["name"].strip(),
                request.form.get("barcode", "").strip() or None,
                request.form.get("purchase_unit", "ea").strip(),
                float(request.form["conversion_rate"]),
                request.form.get("supplier_id") or None,
                request.form.get("memo", "").strip() or None,
            ),
        )
        flash("Purchase variant created", "success")
        return redirect(url_for("purchase.list_variants"))
    products = fetch_all(
        "SELECT id, code, name, unit FROM stk_products "
        "WHERE business_id = %s AND is_active = 1 ORDER BY name",
        (business_id,),
    )
    suppliers = supplier_controller.load_suppliers(business_id)
    return render_template("purchase/variant_form.html",
                           variant=None, products=products, suppliers=suppliers)


@purchase_bp.route("/variants/<int:variant_id>/edit", methods=["GET", "POST"])
@login_required
def edit_variant(variant_id: int):
    """매입 품목 수정"""
    business_id = session["business"]["id"]
    variant = fetch_one(
        "SELECT * FROM stk_purchase_variants WHERE id = %s AND business_id = %s",
        (variant_id, business_id),
    )
    if not variant:
        flash("Variant not found", "danger")
        return redirect(url_for("purchase.list_variants"))
    if request.method == "POST":
        execute(
            "UPDATE stk_purchase_variants SET "
            "product_id=%s, name=%s, barcode=%s, purchase_unit=%s, "
            "conversion_rate=%s, supplier_id=%s, memo=%s "
            "WHERE id=%s",
            (
                int(request.form["product_id"]),
                request.form["name"].strip(),
                request.form.get("barcode", "").strip() or None,
                request.form.get("purchase_unit", "ea").strip(),
                float(request.form["conversion_rate"]),
                request.form.get("supplier_id") or None,
                request.form.get("memo", "").strip() or None,
                variant_id,
            ),
        )
        flash("Purchase variant updated", "success")
        return redirect(url_for("purchase.list_variants"))
    products = fetch_all(
        "SELECT id, code, name, unit FROM stk_products "
        "WHERE business_id = %s AND is_active = 1 ORDER BY name",
        (business_id,),
    )
    suppliers = supplier_controller.load_suppliers(business_id)
    return render_template("purchase/variant_form.html",
                           variant=variant, products=products, suppliers=suppliers)


@purchase_bp.route("/quick-stock-in", methods=["GET", "POST"])
@login_required
def quick_stock_in():
    """바코드/매입품목 기반 빠른 입고 (이동평균원가 자동 계산)"""
    from app.services.stock_cost_service import process_variant_stock_in
    store = session.get("store")
    if not store:
        flash("Please select a store first", "warning")
        return redirect(url_for("dashboard.index"))
    business_id = session["business"]["id"]
    if request.method == "POST":
        variant_id = int(request.form["variant_id"])
        purchase_qty = float(request.form["purchase_qty"])
        total_cost_raw = request.form.get("total_cost", "").strip()
        total_cost = float(total_cost_raw) if total_cost_raw else None
        expiry_date = request.form.get("expiry_date") or None
        reason = request.form.get("reason", "")
        try:
            result = process_variant_stock_in(
                variant_id=variant_id,
                store_id=store["id"],
                purchase_qty=purchase_qty,
                total_cost=total_cost,
                user_id=session["user"]["id"],
                reason=reason,
                expiry_date=expiry_date,
            )
            flash(
                f"Stock In: +{result['base_qty']:.1f} units "
                f"(Cost: {result['new_avg_cost']:.2f}/unit)",
                "success",
            )
        except Exception as e:
            print(f"❌ 빠른 입고 오류: {e}")
            flash(f"Stock In failed: {str(e)}", "danger")
        return redirect(url_for("purchase.quick_stock_in"))
    variants = fetch_all(
        "SELECT pv.id, pv.name, pv.barcode, pv.purchase_unit, pv.conversion_rate, "
        "pv.last_purchase_price, p.name AS product_name, p.unit AS base_unit, "
        "p.avg_unit_cost "
        "FROM stk_purchase_variants pv "
        "JOIN stk_products p ON pv.product_id = p.id "
        "WHERE pv.business_id = %s AND pv.is_active = 1 "
        "ORDER BY p.name, pv.name",
        (business_id,),
    )
    return render_template("purchase/quick_stock_in.html", variants=variants)


@purchase_bp.route("/api/variant-by-barcode")
@login_required
def api_variant_by_barcode():
    """바코드로 매입 품목 검색 (AJAX)"""
    business_id = session["business"]["id"]
    barcode = request.args.get("barcode", "").strip()
    if not barcode:
        return jsonify({"found": False})
    variant = fetch_one(
        "SELECT pv.id, pv.name, pv.barcode, pv.purchase_unit, pv.conversion_rate, "
        "pv.last_purchase_price, p.name AS product_name, p.unit AS base_unit "
        "FROM stk_purchase_variants pv "
        "JOIN stk_products p ON pv.product_id = p.id "
        "WHERE pv.business_id = %s AND pv.barcode = %s AND pv.is_active = 1",
        (business_id, barcode),
    )
    if not variant:
        return jsonify({"found": False})
    return jsonify({"found": True, "variant": variant})
