"""POS 연동 비즈니스 로직 — Webhook 수신 및 폴링 동기화"""
from typing import Dict, List, Optional
from app.db import fetch_one, fetch_all, insert, execute, execute_pos_db


def find_product_by_mcode(business_id: int, menu_code: str) -> Optional[Dict]:
    """mcode(상품코드)로 Hana StockMaster 상품을 조회합니다."""
    return fetch_one(
        "SELECT id, code, name, unit, sell_price, unit_price FROM stk_products "
        "WHERE business_id = %s AND code = %s AND is_active = 1",
        (business_id, menu_code),
    )


def find_recipe_by_pos_menu_id(business_id: int, pos_menu_id: int) -> Optional[Dict]:
    """POS 메뉴 ID로 레시피를 조회합니다."""
    return fetch_one(
        "SELECT id, name, pos_menu_id FROM stk_recipes "
        "WHERE business_id = %s AND pos_menu_id = %s AND is_active = 1",
        (business_id, pos_menu_id),
    )


def find_recipe_by_menu_code(business_id: int, menu_code: str) -> Optional[Dict]:
    """mcode로 레시피를 조회합니다 (pos_menu_id 미설정 시 이름 매칭 폴백)."""
    product = find_product_by_mcode(business_id, menu_code)
    if not product:
        return None
    return fetch_one(
        "SELECT r.id, r.name, r.pos_menu_id FROM stk_recipes r "
        "JOIN stk_recipe_items ri ON ri.recipe_id = r.id "
        "WHERE r.business_id = %s AND r.is_active = 1 "
        "AND ri.product_id = %s LIMIT 1",
        (business_id, product["id"]),
    )


def handle_sale(business_id: int, business_type: str, store_id: int,
                items: List[Dict], user_id: Optional[int] = None) -> Dict:
    """POS 판매 처리 — 업종별 자동 분기."""
    from app.controllers.inventory_controller import process_stock_out
    from app.controllers.recipe_controller import deduct_by_recipe
    result = {"processed": 0, "skipped": 0, "errors": []}
    for item in items:
        menu_code = str(item.get("menu_code", "")).strip()
        quantity = float(item.get("quantity", 0))
        if not menu_code or quantity <= 0:
            result["skipped"] += 1
            continue
        try:
            if business_type == "restaurant":
                _handle_restaurant_sale(
                    business_id, store_id, menu_code, quantity, user_id,
                    deduct_by_recipe, result,
                )
            else:
                _handle_mart_sale(
                    business_id, store_id, menu_code, quantity, user_id,
                    process_stock_out, result,
                )
        except Exception as e:
            result["errors"].append(f"{menu_code}: {str(e)}")
    return result


def _handle_restaurant_sale(business_id: int, store_id: int,
                            menu_code: str, quantity: float,
                            user_id: Optional[int],
                            deduct_by_recipe, result: Dict) -> None:
    """식당: 레시피 기반 원재료 차감."""
    product = find_product_by_mcode(business_id, menu_code)
    recipe = None
    if product:
        recipe = fetch_one(
            "SELECT r.id, r.name FROM stk_recipes r "
            "WHERE r.business_id = %s AND r.is_active = 1 "
            "AND (r.pos_menu_id = %s OR r.name = %s)",
            (business_id, product["id"], product["name"]),
        )
    if recipe:
        deduct_by_recipe(recipe["id"], quantity, store_id, user_id)
        result["processed"] += 1
        print(f"  🍳 레시피 차감: {recipe['name']} x{quantity}")
    else:
        result["skipped"] += 1
        print(f"  ⚠️ 레시피 없음 (mcode={menu_code}) - 건너뜀")


def _handle_mart_sale(business_id: int, store_id: int,
                      menu_code: str, quantity: float,
                      user_id: Optional[int],
                      process_stock_out, result: Dict) -> None:
    """마트: mcode로 상품 직접 차감."""
    product = find_product_by_mcode(business_id, menu_code)
    if product:
        process_stock_out(
            product_id=product["id"], store_id=store_id,
            quantity=quantity, reason=f"POS Sale (mcode={menu_code})",
            user_id=user_id,
        )
        result["processed"] += 1
        print(f"  🛒 직접 차감: {product['name']} x{quantity}")
    else:
        result["skipped"] += 1
        print(f"  ⚠️ 상품 없음 (mcode={menu_code}) - 건너뜀")


def handle_stock_in(business_id: int, store_id: int,
                    items: List[Dict], user_id: Optional[int] = None) -> Dict:
    """POS 입고 처리 → Hana StockMaster 재고 증가."""
    from app.controllers.inventory_controller import process_stock_in
    result = {"processed": 0, "skipped": 0, "errors": []}
    for item in items:
        menu_code = str(item.get("menu_code", "")).strip()
        quantity = float(item.get("quantity", 0))
        if not menu_code or quantity <= 0:
            result["skipped"] += 1
            continue
        try:
            product = find_product_by_mcode(business_id, menu_code)
            if product:
                unit_price = float(item.get("unit_cost", 0))
                process_stock_in(
                    product_id=product["id"], store_id=store_id,
                    quantity=quantity, location="warehouse",
                    unit_price=unit_price,
                    reason=f"POS Stock In (mcode={menu_code})",
                    user_id=user_id,
                )
                result["processed"] += 1
                print(f"  📦 입고 반영: {product['name']} +{quantity}")
            else:
                result["skipped"] += 1
                print(f"  ⚠️ 상품 없음 (mcode={menu_code}) - 건너뜀")
        except Exception as e:
            result["errors"].append(f"{menu_code}: {str(e)}")
    return result


def handle_loss(business_id: int, store_id: int,
                items: List[Dict], user_id: Optional[int] = None) -> Dict:
    """POS Loss/폐기 처리 → Hana StockMaster 재고 차감 (FEFO 자동)."""
    from app.controllers.inventory_controller import process_stock_out
    result = {"processed": 0, "skipped": 0, "errors": []}
    for item in items:
        menu_code = str(item.get("menu_code", "")).strip()
        quantity = float(item.get("quantity", 0))
        if not menu_code or quantity <= 0:
            result["skipped"] += 1
            continue
        try:
            product = find_product_by_mcode(business_id, menu_code)
            if product:
                reason = item.get("reason", "POS Loss")
                process_stock_out(
                    product_id=product["id"], store_id=store_id,
                    quantity=quantity,
                    reason=f"POS Loss: {reason} (mcode={menu_code})",
                    user_id=user_id,
                )
                result["processed"] += 1
                print(f"  🗑️ Loss 반영: {product['name']} -{quantity}")
            else:
                result["skipped"] += 1
                print(f"  ⚠️ 상품 없음 (mcode={menu_code}) - 건너뜀")
        except Exception as e:
            result["errors"].append(f"{menu_code}: {str(e)}")
    return result


def log_sync_detail(business_id: int, pos_table: str, pos_record_id: int,
                    sync_type: str, menu_code: str, quantity: float,
                    status: str = "success", error_message: str = "") -> None:
    """동기화 상세 로그를 기록합니다."""
    insert(
        "INSERT INTO stk_pos_sync_detail "
        "(business_id, pos_table, pos_record_id, sync_type, menu_code, quantity, status, error_message) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (business_id, pos_table, pos_record_id, sync_type, menu_code, quantity, status, error_message),
    )


def update_sync_checkpoint(business_id: int, pos_table: str,
                           pos_last_id: int, record_count: int) -> None:
    """동기화 체크포인트를 업데이트합니다."""
    existing = fetch_one(
        "SELECT id FROM stk_pos_sync_log WHERE business_id = %s AND pos_table = %s",
        (business_id, pos_table),
    )
    if existing:
        execute(
            "UPDATE stk_pos_sync_log SET pos_last_id = %s, record_count = %s, "
            "synced_at = NOW() WHERE id = %s",
            (pos_last_id, record_count, existing["id"]),
        )
    else:
        insert(
            "INSERT INTO stk_pos_sync_log (business_id, pos_table, pos_last_id, record_count) "
            "VALUES (%s, %s, %s, %s)",
            (business_id, pos_table, pos_last_id, record_count),
        )


def sync_categories_from_pos(business_id: int, pos_db_name: str = "") -> Dict:
    """POS menuclass → stk_categories 동기화 (신규 추가, 이름 변경 반영)."""
    import config
    db_name = pos_db_name or config.POS_DB_NAME
    pos_classes = execute_pos_db(
        "SELECT id, classcode, classname FROM menuclass ORDER BY id",
        db_name=db_name,
    )
    existing = fetch_all(
        "SELECT id, name FROM stk_categories WHERE business_id = %s",
        (business_id,),
    )
    existing_map = {c["name"]: c["id"] for c in existing}
    created = 0
    updated = 0
    for idx, cls in enumerate(pos_classes):
        pos_name = cls["classname"].strip()
        if not pos_name:
            continue
        if pos_name in existing_map:
            continue
        try:
            insert(
                "INSERT INTO stk_categories (business_id, name, display_order) "
                "VALUES (%s, %s, %s)",
                (business_id, pos_name, idx),
            )
            created += 1
            print(f"  📂 카테고리 추가: {pos_name}")
        except Exception:
            pass
    print(f"📡 카테고리 동기화: 신규 {created}건, POS 전체 {len(pos_classes)}건")
    return {"created": created, "updated": updated, "total_pos": len(pos_classes)}


def sync_products_from_pos(business_id: int, pos_db_name: str = "") -> Dict:
    """POS menulist → stk_products 동기화 (신규 추가, 가격 변경 반영)."""
    import config
    db_name = pos_db_name or config.POS_DB_NAME
    pos_items = execute_pos_db(
        "SELECT id, mcode, mname, mprice1, barcode, cost_price FROM menulist ORDER BY mname",
        db_name=db_name,
    )
    existing = fetch_all(
        "SELECT id, code, name, sell_price, unit_price FROM stk_products "
        "WHERE business_id = %s AND is_active = 1",
        (business_id,),
    )
    existing_by_code = {p["code"]: p for p in existing}
    categories = fetch_all(
        "SELECT id, name FROM stk_categories WHERE business_id = %s",
        (business_id,),
    )
    cat_by_name = {c["name"]: c["id"] for c in categories}
    # POS menuclass 매핑 (mprn → classname)
    pos_classes = execute_pos_db(
        "SELECT id, classcode, classname FROM menuclass ORDER BY id",
        db_name=db_name,
    )
    created = 0
    updated = 0
    skipped = 0
    for item in pos_items:
        mname = (item.get("mname") or "").strip()
        if not mname:
            skipped += 1
            continue
        mcode = (item["mcode"] or "").strip() if item.get("mcode") else f"{item['id']:04d}"
        sell_price = float(item.get("mprice1") or 0)
        cost_price = float(item.get("cost_price") or 0)
        barcode = (item.get("barcode") or "").strip()
        if mcode in existing_by_code:
            # 기존 상품 — 가격 변경 확인
            ex = existing_by_code[mcode]
            is_price_changed = (
                abs(float(ex["sell_price"] or 0) - sell_price) > 0.001 or
                abs(float(ex["unit_price"] or 0) - cost_price) > 0.001
            )
            if is_price_changed:
                execute(
                    "UPDATE stk_products SET sell_price = %s, unit_price = %s WHERE id = %s",
                    (sell_price, cost_price, ex["id"]),
                )
                updated += 1
                print(f"  🔄 가격 변경: {mname} (sell:{sell_price}, cost:{cost_price})")
        else:
            # 신규 상품
            cat_id = None
            try:
                insert(
                    "INSERT INTO stk_products "
                    "(business_id, category_id, code, barcode, name, unit, unit_price, sell_price, min_stock) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (business_id, cat_id, mcode, barcode, mname, "ea", cost_price, sell_price, 5),
                )
                created += 1
                print(f"  ➕ 상품 추가: {mname} (code:{mcode})")
            except Exception as e:
                skipped += 1
                print(f"  ⚠️ 상품 추가 실패: {mname} - {e}")
    print(f"📡 상품 동기화: 신규 {created}건, 변경 {updated}건, 스킵 {skipped}건, POS 전체 {len(pos_items)}건")
    return {"created": created, "updated": updated, "skipped": skipped, "total_pos": len(pos_items)}


def sync_master_from_pos(business_id: int, pos_db_name: str = "") -> Dict:
    """카테고리 + 상품 마스터 데이터를 POS에서 동기화합니다."""
    cat_result = sync_categories_from_pos(business_id, pos_db_name)
    prod_result = sync_products_from_pos(business_id, pos_db_name)
    return {"categories": cat_result, "products": prod_result}


def sync_sales_from_pos(business_id: int, business_type: str,
                        store_id: int, pos_db_name: str = "") -> Dict:
    """POS DB에서 미동기화 판매 건을 폴링합니다."""
    import config
    db_name = pos_db_name or config.POS_DB_NAME
    checkpoint = fetch_one(
        "SELECT pos_last_id FROM stk_pos_sync_log "
        "WHERE business_id = %s AND pos_table = 'sale_items'",
        (business_id,),
    )
    last_id = checkpoint["pos_last_id"] if checkpoint else 0
    rows = execute_pos_db(
        "SELECT id, menu_code, quantity, unit_price, receipt_id "
        "FROM sale_items WHERE id > %s ORDER BY id",
        (last_id,), db_name=db_name,
    )
    if not rows:
        return {"synced": 0, "skipped": 0, "errors": []}
    items = [{"menu_code": r["menu_code"], "quantity": float(r["quantity"])} for r in rows]
    result = handle_sale(business_id, business_type, store_id, items)
    max_id = max(r["id"] for r in rows)
    for r in rows:
        status = "success"
        log_sync_detail(business_id, "sale_items", r["id"], "sale",
                        r["menu_code"], float(r["quantity"]), status)
    update_sync_checkpoint(business_id, "sale_items", max_id, len(rows))
    print(f"📡 판매 폴링 동기화: {len(rows)}건 (last_id: {last_id} → {max_id})")
    return {"synced": result["processed"], "skipped": result["skipped"],
            "errors": result["errors"], "total": len(rows)}


def sync_stock_transactions_from_pos(business_id: int, store_id: int,
                                     pos_db_name: str = "") -> Dict:
    """POS DB에서 미동기화 입고/Loss 건을 폴링합니다."""
    import config
    db_name = pos_db_name or config.POS_DB_NAME
    checkpoint = fetch_one(
        "SELECT pos_last_id FROM stk_pos_sync_log "
        "WHERE business_id = %s AND pos_table = 'stock_transactions'",
        (business_id,),
    )
    last_id = checkpoint["pos_last_id"] if checkpoint else 0
    rows = execute_pos_db(
        "SELECT id, transaction_type, menu_code, quantity, unit_cost, reason "
        "FROM stock_transactions WHERE id > %s ORDER BY id",
        (last_id,), db_name=db_name,
    )
    if not rows:
        return {"synced": 0, "skipped": 0, "errors": []}
    in_items = []
    out_items = []
    for r in rows:
        item = {"menu_code": r["menu_code"], "quantity": abs(float(r["quantity"])),
                "unit_cost": float(r["unit_cost"] or 0), "reason": r.get("reason", "")}
        if r["transaction_type"] == "IN":
            in_items.append(item)
        elif r["transaction_type"] in ("OUT", "ADJUST"):
            out_items.append(item)
    result_in = handle_stock_in(business_id, store_id, in_items) if in_items else {"processed": 0, "skipped": 0, "errors": []}
    result_out = handle_loss(business_id, store_id, out_items) if out_items else {"processed": 0, "skipped": 0, "errors": []}
    max_id = max(r["id"] for r in rows)
    for r in rows:
        sync_type = "stock_in" if r["transaction_type"] == "IN" else "loss"
        log_sync_detail(business_id, "stock_transactions", r["id"], sync_type,
                        r["menu_code"], abs(float(r["quantity"])))
    update_sync_checkpoint(business_id, "stock_transactions", max_id, len(rows))
    total_processed = result_in["processed"] + result_out["processed"]
    total_skipped = result_in["skipped"] + result_out["skipped"]
    print(f"📡 재고거래 폴링 동기화: {len(rows)}건 (IN:{len(in_items)}, OUT:{len(out_items)})")
    return {"synced": total_processed, "skipped": total_skipped,
            "errors": result_in["errors"] + result_out["errors"], "total": len(rows)}


def run_full_sync(business_id: int, business_type: str,
                  store_id: int, pos_db_name: str = "") -> Dict:
    """전체 폴링 동기화를 실행합니다 (마스터 + 거래)."""
    master_result = sync_master_from_pos(business_id, pos_db_name)
    sales_result = sync_sales_from_pos(business_id, business_type, store_id, pos_db_name)
    stock_result = sync_stock_transactions_from_pos(business_id, store_id, pos_db_name)
    return {
        "master": master_result,
        "sales": sales_result,
        "stock_transactions": stock_result,
    }


def handle_baekwon_sale(business_id: int, business_type: str, store_id: int,
                        data: Dict) -> Dict:
    """백원 POS 판매 데이터 처리 — Firebird Bridge 수신.

    data 구조:
    {
        "receipt_no": 123,
        "sale_date": "02112026",  (MMDDYYYY)
        "pos_no": 1,
        "items": [{"menu_code": "0101", "quantity": 2, "sale_amount": 10000, "sname": "CASH"}]
    }
    """
    from app.controllers.inventory_controller import process_stock_out
    from app.controllers.recipe_controller import deduct_by_recipe
    receipt_no = data.get("receipt_no", 0)
    sale_date_raw = data.get("sale_date", "")
    pos_no = data.get("pos_no", 1)
    items = data.get("items", [])
    sale_date = _convert_baekwon_date(sale_date_raw)
    result = {"processed": 0, "skipped": 0, "errors": [], "receipt_no": receipt_no}
    # 중복 체크 — 동일 영수증은 스킵
    existing = fetch_one(
        "SELECT id FROM stk_pos_sync_detail "
        "WHERE business_id = %s AND pos_table = 'baekwon_rdata' "
        "AND pos_record_id = %s",
        (business_id, receipt_no),
    )
    if existing:
        print(f"  ⏭️ 백원POS 영수증 #{receipt_no} 이미 동기화됨 — 스킵")
        result["skipped"] = len(items)
        return result
    for item in items:
        menu_code = str(item.get("menu_code", "")).strip()
        quantity = float(item.get("quantity", 0))
        if not menu_code or quantity <= 0:
            result["skipped"] += 1
            continue
        try:
            if business_type == "restaurant":
                _handle_restaurant_sale(
                    business_id, store_id, menu_code, quantity, None,
                    deduct_by_recipe, result,
                )
            else:
                _handle_mart_sale(
                    business_id, store_id, menu_code, quantity, None,
                    process_stock_out, result,
                )
        except Exception as e:
            result["errors"].append(f"{menu_code}: {str(e)}")
    # 동기화 로그 기록
    log_sync_detail(
        business_id, "baekwon_rdata", receipt_no,
        "baekwon_sale", f"POS{pos_no}", float(len(items)),
        "success" if result["processed"] > 0 else "skipped",
    )
    print(f"  🔶 백원POS 영수증 #{receipt_no}: {result['processed']}건 처리, {result['skipped']}건 스킵")
    return result


def handle_baekwon_products(business_id: int, data: Dict) -> Dict:
    """백원 POS 상품 마스터 수신 처리.

    data 구조:
    {
        "items": [{"code": "0101", "name": "상품A", "sell_price": 5000}]
    }
    """
    items = data.get("items", [])
    result = {"created": 0, "updated": 0, "skipped": 0, "total": len(items)}
    for item in items:
        code = str(item.get("code", "")).strip()
        name = str(item.get("name", "")).strip()
        sell_price = float(item.get("sell_price", 0))
        if not code:
            result["skipped"] += 1
            continue
        if not name:
            name = code
        existing = find_product_by_mcode(business_id, code)
        if existing:
            # 가격 변동 체크
            is_price_changed = abs(float(existing.get("sell_price", 0) or 0) - sell_price) > 0.01
            if is_price_changed:
                execute(
                    "UPDATE stk_products SET sell_price = %s WHERE id = %s",
                    (sell_price, existing["id"]),
                )
                result["updated"] += 1
                print(f"  🔄 백원상품 가격변경: {name} → {sell_price}")
            else:
                result["skipped"] += 1
        else:
            try:
                insert(
                    "INSERT INTO stk_products "
                    "(business_id, category_id, code, name, unit, sell_price, min_stock) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (business_id, None, code, name, "ea", sell_price, 0),
                )
                result["created"] += 1
                print(f"  ➕ 백원상품 추가: {name} (code:{code})")
            except Exception as e:
                result["skipped"] += 1
                print(f"  ⚠️ 백원상품 추가 실패: {name} — {e}")
    print(f"📡 백원POS 상품 동기화: 신규 {result['created']}건, 변경 {result['updated']}건, 스킵 {result['skipped']}건")
    return result


def _convert_baekwon_date(date_str: str) -> str:
    """백원POS 날짜를 YYYY-MM-DD로 변환합니다.

    Firebird RDATA.SDATE는 이미 'YYYY-MM-DD' 형식이므로
    그대로 반환하거나, 혹시 MMDDYYYY 형식이면 변환합니다.
    """
    if not date_str:
        return ""
    date_str = date_str.strip()
    if len(date_str) == 10 and date_str[4] == '-':
        return date_str
    if len(date_str) == 8:
        try:
            month = date_str[0:2]
            day = date_str[2:4]
            year = date_str[4:8]
            return f"{year}-{month}-{day}"
        except (ValueError, IndexError):
            pass
    return date_str


def load_sync_status(business_id: int) -> Dict:
    """POS 동기화 현재 상태를 조회합니다."""
    logs = fetch_all(
        "SELECT pos_table, pos_last_id, synced_at, record_count "
        "FROM stk_pos_sync_log WHERE business_id = %s",
        (business_id,),
    )
    recent_errors = fetch_all(
        "SELECT COUNT(*) AS cnt FROM stk_pos_sync_detail "
        "WHERE business_id = %s AND status = 'error' "
        "AND created_at > DATE_SUB(NOW(), INTERVAL 24 HOUR)",
        (business_id,),
    )
    error_count = recent_errors[0]["cnt"] if recent_errors else 0
    return {
        "checkpoints": {log["pos_table"]: log for log in logs},
        "recent_errors": error_count,
    }
