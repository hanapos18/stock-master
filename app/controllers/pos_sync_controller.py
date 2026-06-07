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


def handle_product_sync(business_id: int, items: List[Dict]) -> Dict:
    """POS 상품 등록/수정 -> StockMaster stk_products 동기화."""
    result = {"processed": 0, "skipped": 0, "created": 0, "updated": 0}
    for item in items:
        mcode = str(item.get("mcode", "")).strip()
        mname = str(item.get("mname", "")).strip()
        if not mcode or not mname:
            result["skipped"] += 1
            continue
        sell_price = float(item.get("mprice1", 0) or 0)
        cost_price = float(item.get("cost_price", 0) or 0)
        barcode = item.get("barcode")
        existing = fetch_one(
            "SELECT id FROM stk_products WHERE business_id = %s AND code = %s",
            (business_id, mcode),
        )
        if existing:
            execute(
                "UPDATE stk_products SET name = %s, sell_price = %s, unit_price = %s, "
                "barcode = %s WHERE id = %s",
                (mname, sell_price, cost_price, barcode, existing["id"]),
            )
            result["updated"] += 1
            print(f"  상품 업데이트: {mcode} - {mname}")
        else:
            category_prefix = mcode[:2] if len(mcode) >= 2 else ""
            category_id = None
            if category_prefix:
                cat = fetch_one(
                    "SELECT id FROM stk_categories WHERE business_id = %s AND code = %s",
                    (business_id, category_prefix),
                )
                if cat:
                    category_id = cat["id"]
            insert(
                "INSERT INTO stk_products "
                "(business_id, category_id, code, name, sell_price, unit_price, barcode, unit) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (business_id, category_id, mcode, mname, sell_price, cost_price, barcode, "ea"),
            )
            result["created"] += 1
            print(f"  상품 생성: {mcode} - {mname}")
        result["processed"] += 1
    return result


def handle_store_sync(business_id: int, items: List[Dict]) -> Dict:
    """POS 매장 등록/수정 -> StockMaster stk_stores 동기화."""
    result = {"processed": 0, "created": 0, "updated": 0}
    for item in items:
        store_number = str(item.get("store_number", "")).strip()
        store_name = str(item.get("store_name", "")).strip()
        if not store_number or not store_name:
            continue
        address = item.get("address", "")
        phone = item.get("phone", "")
        existing = fetch_one(
            "SELECT id FROM stk_stores WHERE business_id = %s AND store_number = %s",
            (business_id, store_number),
        )
        if existing:
            execute(
                "UPDATE stk_stores SET name = %s, address = %s, phone = %s WHERE id = %s",
                (store_name, address, phone, existing["id"]),
            )
            result["updated"] += 1
            print(f"  매장 업데이트: {store_number} - {store_name}")
        else:
            insert(
                "INSERT INTO stk_stores (business_id, name, store_number, address, phone) "
                "VALUES (%s, %s, %s, %s, %s)",
                (business_id, store_name, store_number, address, phone),
            )
            result["created"] += 1
            print(f"  매장 생성: {store_number} - {store_name}")
        result["processed"] += 1
    return result


def handle_employee_sync(business_id: int, items: List[Dict]) -> Dict:
    """POS 직원 등록/수정 -> StockMaster stk_users 동기화."""
    from werkzeug.security import generate_password_hash
    result = {"processed": 0, "skipped": 0, "created": 0, "updated": 0}
    for item in items:
        store_number = str(item.get("store_number", "")).strip()
        username = str(item.get("employee_id") or item.get("ID") or item.get("username") or "").strip()
        name = str(item.get("employee_name") or item.get("NAME") or item.get("name") or username).strip()
        if not store_number or not username or not name:
            result["skipped"] += 1
            continue
        store = fetch_one(
            "SELECT id FROM stk_stores WHERE business_id = %s AND store_number = %s",
            (business_id, store_number),
        )
        if not store:
            result["skipped"] += 1
            print(f"  직원 동기화 스킵: 매장 없음 {store_number} / {username}")
            continue
        role = _resolve_employee_role(item.get("grade") or item.get("GRADE") or item.get("role"))
        is_active = _resolve_boolean(item.get("is_active", item.get("enabled", 1)))
        password = str(item.get("password") or item.get("PW") or "").strip()
        existing = fetch_one("SELECT id FROM stk_users WHERE username = %s", (username,))
        if existing:
            execute(
                "UPDATE stk_users SET business_id = %s, name = %s, role = %s, "
                "store_id = %s, is_active = %s WHERE id = %s",
                (business_id, name, role, store["id"], is_active, existing["id"]),
            )
            if password:
                execute(
                    "UPDATE stk_users SET password_hash = %s WHERE id = %s",
                    (generate_password_hash(password), existing["id"]),
                )
            result["updated"] += 1
            print(f"  직원 업데이트: {username} - {name} ({role})")
        else:
            password_hash = generate_password_hash(password or "1234")
            insert(
                "INSERT INTO stk_users "
                "(business_id, username, password_hash, name, role, store_id, is_active) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (business_id, username, password_hash, name, role, store["id"], is_active),
            )
            result["created"] += 1
            print(f"  직원 생성: {username} - {name} ({role})")
        result["processed"] += 1
    return result


def _resolve_employee_role(value) -> str:
    """POS 등급 값을 StockMaster 역할로 변환."""
    if str(value).lower() in ("admin", "manager", "staff"):
        return str(value).lower()
    try:
        grade = int(value or 0)
    except (TypeError, ValueError):
        grade = 0
    if grade >= 9:
        return "admin"
    if grade >= 7:
        return "manager"
    return "staff"


def _resolve_boolean(value) -> int:
    """여러 표현의 boolean 값을 0/1로 변환."""
    if isinstance(value, str):
        return 1 if value.lower() in ("1", "true", "yes", "on", "active") else 0
    return 1 if value else 0


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


def sync_stores_from_pos(business_id: int, pos_db_name: str = "") -> Dict:
    """POS store_info -> stk_stores 동기화 (신규 추가, 정보 업데이트)."""
    import config
    db_name = pos_db_name or config.POS_DB_NAME
    pos_stores = execute_pos_db(
        "SELECT store_number, store_name, address, phone FROM store_info WHERE enabled = 1",
        db_name=db_name,
    )
    result = {"synced": 0, "created": 0, "updated": 0}
    for ps in pos_stores:
        store_number = ps["store_number"]
        store_name = ps["store_name"]
        address = ps.get("address", "")
        phone = ps.get("phone", "")
        existing = fetch_one(
            "SELECT id, name FROM stk_stores WHERE business_id = %s AND store_number = %s",
            (business_id, store_number),
        )
        if existing:
            execute(
                "UPDATE stk_stores SET name = %s, address = %s, phone = %s WHERE id = %s",
                (store_name, address, phone, existing["id"]),
            )
            result["updated"] += 1
        else:
            insert(
                "INSERT INTO stk_stores (business_id, name, store_number, address, phone) "
                "VALUES (%s, %s, %s, %s, %s)",
                (business_id, store_name, store_number, address, phone),
            )
            result["created"] += 1
        result["synced"] += 1
    print(f"매장 동기화: {result['synced']}건 (신규 {result['created']}, 업데이트 {result['updated']})")
    return result


def run_full_sync(business_id: int, business_type: str,
                  store_id: int, pos_db_name: str = "") -> Dict:
    """전체 폴링 동기화를 실행합니다 (마스터 + 거래)."""
    store_result = sync_stores_from_pos(business_id, pos_db_name)
    master_result = sync_master_from_pos(business_id, pos_db_name)
    sales_result = sync_sales_from_pos(business_id, business_type, store_id, pos_db_name)
    stock_result = sync_stock_transactions_from_pos(business_id, store_id, pos_db_name)
    return {
        "stores": store_result,
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


def sync_inventory_to_pos(product_id: int, store_id: int) -> bool:
    """StockMaster 재고를 POS menulist.minventory에 동기화합니다."""
    from app.db import write_pos_db
    product = fetch_one(
        "SELECT code FROM stk_products WHERE id = %s", (product_id,),
    )
    if not product or not product["code"]:
        return False
    mcode = product["code"]
    total_row = fetch_one(
        "SELECT COALESCE(SUM(quantity), 0) AS total_qty "
        "FROM stk_inventory WHERE product_id = %s AND store_id = %s",
        (product_id, store_id),
    )
    total_qty = int(float(total_row["total_qty"])) if total_row else 0
    try:
        affected = write_pos_db(
            "UPDATE menulist SET minventory = %s WHERE mcode = %s",
            (total_qty, mcode),
        )
        if affected > 0:
            print(f"POS 재고 동기화: {mcode} -> {total_qty}")
        return affected > 0
    except Exception as e:
        print(f"POS 재고 동기화 실패 ({mcode}): {e}")
        return False


def sync_product_to_pos(product_id: int) -> bool:
    """StockMaster 상품 정보를 POS menulist에 동기화합니다 (가격, 원가)."""
    from app.db import write_pos_db
    product = fetch_one(
        "SELECT code, name, sell_price, unit_price FROM stk_products WHERE id = %s",
        (product_id,),
    )
    if not product or not product["code"]:
        return False
    try:
        affected = write_pos_db(
            "UPDATE menulist SET mprice1 = %s, cost_price = %s WHERE mcode = %s",
            (float(product["sell_price"]), float(product["unit_price"]), product["code"]),
        )
        if affected > 0:
            print(f"POS 상품 동기화: {product['code']} price={product['sell_price']}")
        return affected > 0
    except Exception as e:
        print(f"POS 상품 동기화 실패 ({product['code']}): {e}")
        return False


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
