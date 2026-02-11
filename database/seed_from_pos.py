"""order_sys POS DB를 참조하여 stock_master에 기본 데이터를 삽입합니다."""
import pymysql
import pymysql.cursors
from werkzeug.security import generate_password_hash

DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "manila72",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}

POS_DB = "order_sys"
STK_DB = "stock_master"


def get_connection(db_name: str):
    return pymysql.connect(**DB_CONFIG, database=db_name)


def seed_all():
    pos = get_connection(POS_DB)
    stk = get_connection(STK_DB)

    print("=" * 60)
    print("  StockMaster 기본 데이터 삽입 (order_sys 참조)")
    print("=" * 60)

    # 1. 기존 데이터 정리
    print("\n[1] 기존 데이터 정리...")
    cleanup(stk)

    # 2. 사업장 - store_info 참조
    print("[2] 사업장 생성 (store_info 참조)...")
    business_id = seed_business(pos, stk)

    # 3. 매장
    print("[3] 매장 생성...")
    store_id = seed_store(stk, business_id)

    # 4. 사용자 - employee 참조
    print("[4] 사용자 생성 (employee 참조)...")
    seed_users(pos, stk, business_id)

    # 5. 카테고리 - menuclass 참조
    print("[5] 카테고리 생성 (menuclass 참조)...")
    category_map = seed_categories(pos, stk, business_id)

    # 6. 거래처 (샘플)
    print("[6] 거래처 생성 (샘플)...")
    supplier_map = seed_suppliers(stk, business_id)

    # 7. 상품 - menulist 참조 + 식자재 추가
    print("[7] 상품 생성 (menulist + 식자재)...")
    product_map = seed_products(pos, stk, business_id, category_map, supplier_map)

    # 8. 초기 재고
    print("[8] 초기 재고 설정...")
    seed_inventory(stk, store_id, product_map)

    # 9. 레시피 (주요 메뉴)
    print("[9] 레시피 생성 (주요 메뉴)...")
    seed_recipes(stk, business_id, product_map)

    print("\n" + "=" * 60)
    print("  기본 데이터 삽입 완료!")
    print(f"  로그인: admin / admin123")
    print(f"  URL: http://localhost:5556")
    print("=" * 60)

    pos.close()
    stk.close()


def cleanup(stk):
    """기존 데이터를 모두 삭제합니다."""
    tables = [
        "stk_stock_count_items", "stk_stock_counts",
        "stk_sale_items", "stk_sales",
        "stk_wholesale_order_items", "stk_wholesale_orders",
        "stk_wholesale_pricing", "stk_wholesale_clients",
        "stk_repackaging", "stk_recipe_items", "stk_recipes",
        "stk_purchase_items", "stk_purchases",
        "stk_transactions", "stk_inventory",
        "stk_products", "stk_suppliers", "stk_categories",
        "stk_users", "stk_stores", "stk_businesses",
    ]
    with stk.cursor() as cur:
        cur.execute("SET FOREIGN_KEY_CHECKS=0")
        for table in tables:
            cur.execute(f"TRUNCATE TABLE {table}")
        cur.execute("SET FOREIGN_KEY_CHECKS=1")
    print("  기존 데이터 삭제 완료")


def seed_business(pos, stk) -> int:
    """store_info에서 사업장 정보를 가져와 생성합니다."""
    with pos.cursor() as cur:
        cur.execute("SELECT * FROM store_info LIMIT 1")
        store = cur.fetchone()
    name = store["store_name"] if store else "My Business"
    address = store["address"] if store else ""
    phone = store["phone"] if store else ""
    with stk.cursor() as cur:
        cur.execute(
            "INSERT INTO stk_businesses (name, type, owner_name, address, phone, pos_db_name) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (name, "restaurant", "Admin", address, phone, POS_DB),
        )
        business_id = cur.lastrowid
    print(f"  사업장: {name} (ID: {business_id})")
    return business_id


def seed_store(stk, business_id: int) -> int:
    """기본 매장을 생성합니다."""
    with stk.cursor() as cur:
        cur.execute(
            "INSERT INTO stk_stores (business_id, name) VALUES (%s, %s)",
            (business_id, "Main Store"),
        )
        store_id = cur.lastrowid
    print(f"  매장: Main Store (ID: {store_id})")
    return store_id


def seed_users(pos, stk, business_id: int):
    """employee에서 사용자를 가져옵니다."""
    admin_hash = generate_password_hash("admin123")
    with stk.cursor() as cur:
        cur.execute(
            "INSERT INTO stk_users (business_id, username, password_hash, name, role) "
            "VALUES (%s, %s, %s, %s, %s)",
            (business_id, "admin", admin_hash, "Administrator", "admin"),
        )
    with pos.cursor() as cur:
        cur.execute(
            "SELECT ID, NAME, GRADE, emp_name FROM employee WHERE NAME != '' AND ID != '' LIMIT 10"
        )
        employees = cur.fetchall()
    manager_hash = generate_password_hash("1234")
    with stk.cursor() as cur:
        for emp in employees:
            emp_name = emp.get("emp_name") or emp["NAME"]
            grade = emp.get("GRADE") or "5"
            role = "manager" if str(grade) in ("7", "10") else "staff"
            username = emp["NAME"].lower().replace(" ", "")
            if not username or username == "admin":
                continue
            try:
                cur.execute(
                    "INSERT INTO stk_users (business_id, username, password_hash, name, role) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (business_id, username, manager_hash, emp_name, role),
                )
                print(f"  사용자: {username} ({role})")
            except Exception:
                pass
    print(f"  admin (admin123) 생성 완료")


def seed_categories(pos, stk, business_id: int) -> dict:
    """menuclass에서 카테고리를 가져옵니다."""
    with pos.cursor() as cur:
        cur.execute("SELECT id, classcode, classname FROM menuclass ORDER BY id")
        classes = cur.fetchall()
    category_map = {}
    with stk.cursor() as cur:
        for idx, cls in enumerate(classes):
            cur.execute(
                "INSERT INTO stk_categories (business_id, name, display_order) VALUES (%s, %s, %s)",
                (business_id, cls["classname"], idx),
            )
            category_map[cls["classcode"]] = cur.lastrowid
            category_map[f"id_{cls['id']}"] = cur.lastrowid
            print(f"  카테고리: {cls['classname']} (code: {cls['classcode']})")
        # 식자재 전용 카테고리 추가
        for extra_name in ["Raw Materials", "Sauces & Seasonings", "Packaging"]:
            cur.execute(
                "INSERT INTO stk_categories (business_id, name, display_order) VALUES (%s, %s, %s)",
                (business_id, extra_name, 100),
            )
            category_map[extra_name] = cur.lastrowid
    return category_map


def seed_suppliers(stk, business_id: int) -> dict:
    """샘플 거래처를 생성합니다."""
    suppliers = [
        {"name": "Fresh Meat Supply", "contact": "Kim", "phone": "02-1234-5678", "memo": "Pork, beef, chicken"},
        {"name": "Ocean Seafood", "contact": "Park", "phone": "02-2345-6789", "memo": "Fish, shrimp, squid"},
        {"name": "Green Farm Vegetables", "contact": "Lee", "phone": "02-3456-7890", "memo": "Vegetables, fruits"},
        {"name": "Korean Beverage Co.", "contact": "Choi", "phone": "02-4567-8901", "memo": "Soju, beer, soft drinks"},
        {"name": "Pantry Essentials", "contact": "Jung", "phone": "02-5678-9012", "memo": "Rice, sauces, oil, seasonings"},
    ]
    supplier_map = {}
    with stk.cursor() as cur:
        for s in suppliers:
            cur.execute(
                "INSERT INTO stk_suppliers (business_id, name, contact_person, phone, memo) "
                "VALUES (%s, %s, %s, %s, %s)",
                (business_id, s["name"], s["contact"], s["phone"], s["memo"]),
            )
            supplier_map[s["name"]] = cur.lastrowid
            print(f"  거래처: {s['name']}")
    return supplier_map


def seed_products(pos, stk, business_id: int, category_map: dict, supplier_map: dict) -> dict:
    """menulist에서 상품을 가져오고, 식자재도 추가합니다."""
    product_map = {}

    # POS 메뉴 아이템 → 상품
    with pos.cursor() as cur:
        cur.execute(
            "SELECT id, mcode, mname, mprice1, mprn, barcode, cost_price "
            "FROM menulist ORDER BY mprn, mname"
        )
        menu_items = cur.fetchall()

    with stk.cursor() as cur:
        for item in menu_items:
            name = item["mname"].strip()
            if not name:
                continue
            code = f"M{item['mcode'].strip()}" if item["mcode"] else f"M{item['id']:04d}"
            sell_price = float(item["mprice1"] or 0)
            cost_price = float(item["cost_price"] or 0)
            barcode = item.get("barcode") or ""
            # mprn으로 카테고리 매핑 (프린터 = 메뉴 그룹 대략적 매핑)
            cat_id = None
            mprn = str(item.get("mprn") or "").strip()
            if mprn in ("1", "1,2"):
                cat_id = category_map.get("01") or category_map.get("02")  # MEAT or ALACART
            elif mprn in ("0", ""):
                cat_id = category_map.get("03")  # DRINKS
            elif mprn == "2":
                cat_id = category_map.get("04")  # Desserts
            elif mprn == "3":
                cat_id = category_map.get("08")  # coffee
            try:
                cur.execute(
                    "INSERT INTO stk_products "
                    "(business_id, category_id, code, barcode, name, unit, unit_price, sell_price, min_stock) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (business_id, cat_id, code, barcode, name, "ea", cost_price, sell_price, 5),
                )
                product_map[name] = cur.lastrowid
                product_map[f"pos_{item['id']}"] = cur.lastrowid
            except Exception as e:
                print(f"  [건너뜀] {name}: {e}")

    print(f"  POS 메뉴 상품 {len(menu_items)}개 삽입")

    # 식자재(원재료) 추가
    raw_materials = [
        # (code, name, unit, buy_price, sell_price, min_stock, category_key, supplier_key)
        ("R0001", "Pork Belly (Samgyupsal)", "kg", 12000, 0, 10, "Raw Materials", "Fresh Meat Supply"),
        ("R0002", "Pork Galbi", "kg", 15000, 0, 8, "Raw Materials", "Fresh Meat Supply"),
        ("R0003", "Beef Galbi", "kg", 35000, 0, 5, "Raw Materials", "Fresh Meat Supply"),
        ("R0004", "Beef Brisket (Chadol)", "kg", 28000, 0, 5, "Raw Materials", "Fresh Meat Supply"),
        ("R0005", "Makchang", "kg", 18000, 0, 5, "Raw Materials", "Fresh Meat Supply"),
        ("R0006", "Galbi Bonsal", "kg", 45000, 0, 3, "Raw Materials", "Fresh Meat Supply"),
        ("R0007", "Galbisal", "kg", 25000, 0, 5, "Raw Materials", "Fresh Meat Supply"),
        ("R0008", "Woo Samgyub", "kg", 22000, 0, 5, "Raw Materials", "Fresh Meat Supply"),
        ("R0009", "Gal Maegisal", "kg", 20000, 0, 5, "Raw Materials", "Fresh Meat Supply"),
        ("R0010", "Rice", "kg", 3000, 0, 50, "Raw Materials", "Pantry Essentials"),
        ("R0011", "Noodles (Naengmyeon)", "pack", 2500, 0, 30, "Raw Materials", "Pantry Essentials"),
        ("R0012", "Ramen Noodles", "pack", 800, 0, 50, "Raw Materials", "Pantry Essentials"),
        ("R0013", "Tofu (Sundubu)", "ea", 2000, 0, 20, "Raw Materials", "Pantry Essentials"),
        ("R0014", "Doenjang Paste", "kg", 8000, 0, 5, "Sauces & Seasonings", "Pantry Essentials"),
        ("R0015", "Gochujang Paste", "kg", 9000, 0, 5, "Sauces & Seasonings", "Pantry Essentials"),
        ("R0016", "Kimchi", "kg", 6000, 0, 20, "Raw Materials", "Green Farm Vegetables"),
        ("R0017", "Bean Sprouts", "kg", 3000, 0, 10, "Raw Materials", "Green Farm Vegetables"),
        ("R0018", "Green Onion", "kg", 4000, 0, 10, "Raw Materials", "Green Farm Vegetables"),
        ("R0019", "Garlic", "kg", 10000, 0, 5, "Sauces & Seasonings", "Green Farm Vegetables"),
        ("R0020", "Sesame Oil", "L", 15000, 0, 3, "Sauces & Seasonings", "Pantry Essentials"),
        ("R0021", "Soy Sauce", "L", 5000, 0, 5, "Sauces & Seasonings", "Pantry Essentials"),
        ("R0022", "Soju (Jinro)", "bottle", 1800, 0, 100, "Raw Materials", "Korean Beverage Co."),
        ("R0023", "Soju (Chumchurum)", "bottle", 1800, 0, 100, "Raw Materials", "Korean Beverage Co."),
        ("R0024", "Soju (Fresh)", "bottle", 1800, 0, 100, "Raw Materials", "Korean Beverage Co."),
        ("R0025", "Beer (San Miguel Pilsen)", "bottle", 60, 0, 100, "Raw Materials", "Korean Beverage Co."),
        ("R0026", "Beer (San Miguel Light)", "bottle", 65, 0, 100, "Raw Materials", "Korean Beverage Co."),
        ("R0027", "Beer (San Miguel Apple)", "bottle", 75, 0, 100, "Raw Materials", "Korean Beverage Co."),
        ("R0028", "Coke Can", "ea", 25, 0, 100, "Raw Materials", "Korean Beverage Co."),
        ("R0029", "Sprite Can", "ea", 25, 0, 100, "Raw Materials", "Korean Beverage Co."),
        ("R0030", "Bottled Water", "ea", 15, 0, 200, "Raw Materials", "Korean Beverage Co."),
        ("R0031", "Coffee Beans", "kg", 25000, 0, 5, "Raw Materials", "Pantry Essentials"),
        ("R0032", "Milk", "L", 80, 0, 20, "Raw Materials", "Pantry Essentials"),
        ("R0033", "Ugeoji (Cabbage Leaves)", "kg", 5000, 0, 10, "Raw Materials", "Green Farm Vegetables"),
        ("R0034", "Beef Bone Broth Base", "L", 8000, 0, 10, "Raw Materials", "Fresh Meat Supply"),
        ("R0035", "Bokbunja Wine", "bottle", 8000, 0, 20, "Raw Materials", "Korean Beverage Co."),
        ("R0036", "Saero Soju", "bottle", 2000, 0, 50, "Raw Materials", "Korean Beverage Co."),
        ("R0037", "CC Blueberry Soju", "bottle", 2200, 0, 50, "Raw Materials", "Korean Beverage Co."),
        ("R0038", "CC Grape Soju", "bottle", 2200, 0, 50, "Raw Materials", "Korean Beverage Co."),
        ("R0039", "CC Peach Soju", "bottle", 2200, 0, 50, "Raw Materials", "Korean Beverage Co."),
        ("R0040", "Pizza Dough", "ea", 1500, 0, 20, "Raw Materials", "Pantry Essentials"),
        ("R0041", "Mozzarella Cheese", "kg", 18000, 0, 5, "Raw Materials", "Pantry Essentials"),
        ("R0042", "Ice (Bingsu)", "kg", 500, 0, 30, "Raw Materials", "Pantry Essentials"),
        ("R0043", "Red Bean Paste", "kg", 7000, 0, 5, "Raw Materials", "Pantry Essentials"),
        ("R0044", "Mango", "kg", 350, 0, 10, "Raw Materials", "Green Farm Vegetables"),
    ]
    with stk.cursor() as cur:
        for rm in raw_materials:
            code, name, unit, buy_price, sell_price, min_stock, cat_key, sup_key = rm
            cat_id = category_map.get(cat_key)
            sup_id = supplier_map.get(sup_key)
            cur.execute(
                "INSERT INTO stk_products "
                "(business_id, category_id, supplier_id, code, name, unit, unit_price, sell_price, min_stock) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (business_id, cat_id, sup_id, code, name, unit, buy_price, sell_price, min_stock),
            )
            product_map[name] = cur.lastrowid
    print(f"  식자재 {len(raw_materials)}개 삽입")
    return product_map


def seed_inventory(stk, store_id: int, product_map: dict):
    """초기 재고를 설정합니다."""
    initial_stocks = {
        "Pork Belly (Samgyupsal)": (30, "cold_storage"),
        "Pork Galbi": (20, "cold_storage"),
        "Beef Galbi": (15, "cold_storage"),
        "Beef Brisket (Chadol)": (10, "cold_storage"),
        "Makchang": (15, "cold_storage"),
        "Galbi Bonsal": (8, "cold_storage"),
        "Galbisal": (12, "cold_storage"),
        "Woo Samgyub": (15, "cold_storage"),
        "Gal Maegisal": (12, "cold_storage"),
        "Rice": (100, "dry_storage"),
        "Noodles (Naengmyeon)": (50, "dry_storage"),
        "Ramen Noodles": (80, "dry_storage"),
        "Tofu (Sundubu)": (30, "cold_storage"),
        "Doenjang Paste": (10, "dry_storage"),
        "Gochujang Paste": (10, "dry_storage"),
        "Kimchi": (50, "cold_storage"),
        "Bean Sprouts": (15, "cold_storage"),
        "Green Onion": (15, "cold_storage"),
        "Garlic": (8, "dry_storage"),
        "Sesame Oil": (5, "dry_storage"),
        "Soy Sauce": (10, "dry_storage"),
        "Soju (Jinro)": (200, "warehouse"),
        "Soju (Chumchurum)": (200, "warehouse"),
        "Soju (Fresh)": (200, "warehouse"),
        "Beer (San Miguel Pilsen)": (300, "warehouse"),
        "Beer (San Miguel Light)": (300, "warehouse"),
        "Beer (San Miguel Apple)": (200, "warehouse"),
        "Coke Can": (200, "warehouse"),
        "Sprite Can": (200, "warehouse"),
        "Bottled Water": (500, "warehouse"),
        "Coffee Beans": (10, "dry_storage"),
        "Milk": (30, "cold_storage"),
        "Ugeoji (Cabbage Leaves)": (20, "cold_storage"),
        "Beef Bone Broth Base": (20, "cold_storage"),
        "Bokbunja Wine": (30, "warehouse"),
        "Saero Soju": (100, "warehouse"),
        "CC Blueberry Soju": (80, "warehouse"),
        "CC Grape Soju": (80, "warehouse"),
        "CC Peach Soju": (80, "warehouse"),
        "Pizza Dough": (30, "cold_storage"),
        "Mozzarella Cheese": (8, "cold_storage"),
        "Ice (Bingsu)": (50, "freezer"),
        "Red Bean Paste": (8, "dry_storage"),
        "Mango": (15, "cold_storage"),
    }
    count = 0
    with stk.cursor() as cur:
        for name, (qty, location) in initial_stocks.items():
            pid = product_map.get(name)
            if not pid:
                continue
            cur.execute(
                "INSERT INTO stk_inventory (product_id, store_id, location, quantity) "
                "VALUES (%s, %s, %s, %s)",
                (pid, store_id, location, qty),
            )
            count += 1
    print(f"  초기 재고 {count}개 항목 설정")


def seed_recipes(stk, business_id: int, product_map: dict):
    """주요 메뉴의 레시피를 생성합니다."""
    recipes = [
        {
            "name": "SAM GYUBSAL (1 serving)",
            "yield_qty": 1, "yield_unit": "serving",
            "items": [("Pork Belly (Samgyupsal)", 0.3, "kg"), ("Green Onion", 0.05, "kg"),
                      ("Garlic", 0.02, "kg"), ("Sesame Oil", 0.01, "L")]
        },
        {
            "name": "PORK GALBI (1 serving)",
            "yield_qty": 1, "yield_unit": "serving",
            "items": [("Pork Galbi", 0.35, "kg"), ("Soy Sauce", 0.03, "L"),
                      ("Garlic", 0.02, "kg"), ("Sesame Oil", 0.01, "L")]
        },
        {
            "name": "L.A GALBI (1 serving)",
            "yield_qty": 1, "yield_unit": "serving",
            "items": [("Beef Galbi", 0.4, "kg"), ("Soy Sauce", 0.04, "L"),
                      ("Garlic", 0.03, "kg"), ("Sesame Oil", 0.02, "L")]
        },
        {
            "name": "KIMCHI JJIGAE (1 bowl)",
            "yield_qty": 1, "yield_unit": "bowl",
            "items": [("Kimchi", 0.2, "kg"), ("Tofu (Sundubu)", 0.5, "ea"),
                      ("Pork Belly (Samgyupsal)", 0.1, "kg"), ("Green Onion", 0.03, "kg")]
        },
        {
            "name": "DEONJANG JJIGAE (1 bowl)",
            "yield_qty": 1, "yield_unit": "bowl",
            "items": [("Doenjang Paste", 0.05, "kg"), ("Tofu (Sundubu)", 0.5, "ea"),
                      ("Green Onion", 0.03, "kg"), ("Garlic", 0.01, "kg")]
        },
        {
            "name": "MUL NAENG MYEON (1 bowl)",
            "yield_qty": 1, "yield_unit": "bowl",
            "items": [("Noodles (Naengmyeon)", 1, "pack"), ("Beef Bone Broth Base", 0.3, "L"),
                      ("Kimchi", 0.05, "kg")]
        },
        {
            "name": "BIBIM NAENG MYEON (1 bowl)",
            "yield_qty": 1, "yield_unit": "bowl",
            "items": [("Noodles (Naengmyeon)", 1, "pack"), ("Gochujang Paste", 0.04, "kg"),
                      ("Sesame Oil", 0.01, "L")]
        },
        {
            "name": "RAMEN (1 bowl)",
            "yield_qty": 1, "yield_unit": "bowl",
            "items": [("Ramen Noodles", 1, "pack"), ("Green Onion", 0.02, "kg")]
        },
        {
            "name": "RICE (1 serving)",
            "yield_qty": 1, "yield_unit": "serving",
            "items": [("Rice", 0.15, "kg")]
        },
        {
            "name": "UGEOJI HAEJANG GUK (1 bowl)",
            "yield_qty": 1, "yield_unit": "bowl",
            "items": [("Ugeoji (Cabbage Leaves)", 0.15, "kg"), ("Beef Bone Broth Base", 0.4, "L"),
                      ("Doenjang Paste", 0.02, "kg"), ("Bean Sprouts", 0.05, "kg")]
        },
        {
            "name": "SUNDUBU JJIGAE (1 bowl)",
            "yield_qty": 1, "yield_unit": "bowl",
            "items": [("Tofu (Sundubu)", 1, "ea"), ("Gochujang Paste", 0.03, "kg"),
                      ("Green Onion", 0.03, "kg"), ("Garlic", 0.01, "kg")]
        },
        {
            "name": "YUK GEAJANG (1 bowl)",
            "yield_qty": 1, "yield_unit": "bowl",
            "items": [("Beef Brisket (Chadol)", 0.15, "kg"), ("Bean Sprouts", 0.1, "kg"),
                      ("Green Onion", 0.05, "kg"), ("Gochujang Paste", 0.03, "kg")]
        },
        {
            "name": "Americano (1 cup)",
            "yield_qty": 1, "yield_unit": "cup",
            "items": [("Coffee Beans", 0.02, "kg"), ("Bottled Water", 0.25, "ea")]
        },
        {
            "name": "Cafe Latte (1 cup)",
            "yield_qty": 1, "yield_unit": "cup",
            "items": [("Coffee Beans", 0.02, "kg"), ("Milk", 0.2, "L")]
        },
        {
            "name": "Pizza (1 ea)",
            "yield_qty": 1, "yield_unit": "ea",
            "items": [("Pizza Dough", 1, "ea"), ("Mozzarella Cheese", 0.15, "kg")]
        },
        {
            "name": "Bingsu (1 bowl)",
            "yield_qty": 1, "yield_unit": "bowl",
            "items": [("Ice (Bingsu)", 0.5, "kg"), ("Red Bean Paste", 0.1, "kg"),
                      ("Milk", 0.1, "L")]
        },
    ]
    count = 0
    with stk.cursor() as cur:
        for r in recipes:
            cur.execute(
                "INSERT INTO stk_recipes (business_id, name, yield_quantity, yield_unit) "
                "VALUES (%s, %s, %s, %s)",
                (business_id, r["name"], r["yield_qty"], r["yield_unit"]),
            )
            recipe_id = cur.lastrowid
            for item_name, qty, unit in r["items"]:
                pid = product_map.get(item_name)
                if not pid:
                    print(f"  [경고] 상품 없음: {item_name}")
                    continue
                cur.execute(
                    "INSERT INTO stk_recipe_items (recipe_id, product_id, quantity, unit) "
                    "VALUES (%s, %s, %s, %s)",
                    (recipe_id, pid, qty, unit),
                )
            count += 1
            print(f"  레시피: {r['name']} ({len(r['items'])} ingredients)")
    print(f"  레시피 {count}개 생성 완료")


if __name__ == "__main__":
    seed_all()
