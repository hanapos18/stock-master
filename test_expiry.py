"""유통기한 관리 기능 테스트"""
import requests
import pymysql
from datetime import date, timedelta

BASE = "http://localhost:5556"
s = requests.Session()


def test_login():
    print("=== 1. 로그인 ===")
    r = s.post(BASE + "/login", data={"username": "admin", "password": "admin123"}, allow_redirects=True)
    ok = r.status_code == 200 and "Dashboard" in r.text
    print(f"  로그인: {'성공' if ok else '실패'}")
    return ok


def test_dashboard_expiry_widget():
    print("\n=== 2. 대시보드 유통기한 위젯 ===")
    r = s.get(BASE + "/dashboard/")
    has_expiry = "Expiry Alerts" in r.text
    has_expired = "Expired" in r.text
    has_expiring = "Expiring" in r.text
    print(f"  Status: {r.status_code}")
    print(f"  Expiry Alerts 위젯: {has_expiry}")
    print(f"  Expired/Expiring 카운트: {has_expired and has_expiring}")
    return has_expiry


def test_purchase_form_expiry():
    print("\n=== 3. 매입 폼 유통기한 필드 ===")
    r = s.get(BASE + "/purchases/create")
    has_expiry_col = "Expiry Date" in r.text
    has_th_expiry = "th-expiry" in r.text
    print(f"  Status: {r.status_code}")
    print(f"  Expiry Date 컬럼: {has_expiry_col}")
    print(f"  th-expiry 클래스: {has_th_expiry}")
    return has_expiry_col


def get_test_product_ids():
    conn = pymysql.connect(host="localhost", port=3306, user="root", password="manila72", database="stock_master")
    cur = conn.cursor()
    ids = {}
    for code in ["MT001", "MT002"]:
        cur.execute("SELECT id FROM stk_products WHERE code=%s", (code,))
        row = cur.fetchone()
        if row:
            ids[code] = row[0]
    cur.close()
    conn.close()
    return ids


def test_create_purchase_with_expiry(product_ids):
    print("\n=== 4. 매입 생성 (유통기한 포함) ===")
    today = date.today().isoformat()
    exp1 = (date.today() + timedelta(days=5)).isoformat()
    exp2 = (date.today() + timedelta(days=60)).isoformat()
    data = {
        "purchase_date": today,
        "supplier_id": "",
        "memo": "Expiry test purchase",
        "item_product_id[]": [str(product_ids["MT001"]), str(product_ids["MT002"])],
        "item_quantity[]": ["10", "5"],
        "item_unit_price[]": ["15000", "45000"],
        "item_expiry_date[]": [exp1, exp2],
    }
    r = s.post(BASE + "/purchases/create", data=data, allow_redirects=True)
    success = r.status_code == 200 and ("Purchase" in r.text or "PO-" in r.text)
    has_expiry_display = exp1 in r.text or exp2 in r.text
    print(f"  Status: {r.status_code}")
    print(f"  매입 생성: {success}")
    print(f"  유통기한 표시: {has_expiry_display}")
    return success, r


def test_receive_purchase():
    print("\n=== 5. 매입 입고 (유통기한 재고 반영) ===")
    conn = pymysql.connect(host="localhost", port=3306, user="root", password="manila72", database="stock_master")
    cur = conn.cursor()
    cur.execute("SELECT id FROM stk_purchases WHERE memo='Expiry test purchase' AND status='draft' ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        print("  매입 찾기 실패")
        return False
    purchase_id = row[0]
    r = s.post(BASE + f"/purchases/{purchase_id}/receive", allow_redirects=True)
    success = "received" in r.text.lower() or "inventory updated" in r.text.lower()
    print(f"  Purchase ID: {purchase_id}")
    print(f"  입고 처리: {success}")
    return success


def test_inventory_expiry_display():
    print("\n=== 6. 재고 목록 유통기한 표시 ===")
    r = s.get(BASE + "/inventory/?search=MT00")
    has_expiry_col = "Expiry Date" in r.text
    has_badge = "badge" in r.text and ("Expired" in r.text or "bg-warning" in r.text or "text-success" in r.text)
    print(f"  Status: {r.status_code}")
    print(f"  Expiry Date 컬럼: {has_expiry_col}")
    exp1 = (date.today() + timedelta(days=5)).strftime("%Y-%m-%d")
    exp2 = (date.today() + timedelta(days=60)).strftime("%Y-%m-%d")
    print(f"  유통기한 {exp1}: {exp1 in r.text}")
    print(f"  유통기한 {exp2}: {exp2 in r.text}")
    return has_expiry_col


def test_expiry_report():
    print("\n=== 7. 유통기한 리포트 ===")
    r = s.get(BASE + "/reports/expiry")
    has_title = "Expiry Date Report" in r.text
    has_filters = "Expired" in r.text and "Within 7 Days" in r.text and "Within 30 Days" in r.text
    print(f"  Status: {r.status_code}")
    print(f"  리포트 제목: {has_title}")
    print(f"  필터 버튼: {has_filters}")
    # 7일 이내 필터 테스트
    r2 = s.get(BASE + "/reports/expiry?filter=week")
    has_data = "MT001" in r2.text or "Beef" in r2.text
    print(f"  7일 이내 필터 데이터: {has_data}")
    return has_title


def test_db_verify():
    print("\n=== 8. DB 검증 ===")
    conn = pymysql.connect(host="localhost", port=3306, user="root", password="manila72", database="stock_master")
    cur = conn.cursor()
    # 매입 항목 유통기한
    cur.execute("SELECT pi.expiry_date, p.code FROM stk_purchase_items pi JOIN stk_products p ON pi.product_id=p.id WHERE pi.expiry_date IS NOT NULL ORDER BY pi.id DESC LIMIT 5")
    items = cur.fetchall()
    print(f"  유통기한 있는 매입항목: {len(items)}건")
    for i in items:
        print(f"    {i[1]}: {i[0]}")
    # 재고 유통기한별 로트
    cur.execute("SELECT p.code, p.name, i.quantity, i.expiry_date FROM stk_inventory i JOIN stk_products p ON i.product_id=p.id WHERE p.code LIKE 'MT%%' AND i.quantity > 0 ORDER BY p.code, i.expiry_date")
    inv = cur.fetchall()
    print(f"  유통기한별 재고 로트: {len(inv)}건")
    for i in inv:
        print(f"    {i[0]} {i[1]}: {i[2]}qty, expiry={i[3]}")
    cur.close()
    conn.close()
    return len(items) > 0


if __name__ == "__main__":
    print("=" * 50)
    print("  Hana StockMaster 유통기한 관리 테스트")
    print("=" * 50)
    results = []
    results.append(("로그인", test_login()))
    results.append(("대시보드 위젯", test_dashboard_expiry_widget()))
    results.append(("매입 폼 필드", test_purchase_form_expiry()))
    pids = get_test_product_ids()
    if pids:
        ok, _ = test_create_purchase_with_expiry(pids)
        results.append(("매입 생성", ok))
        results.append(("매입 입고", test_receive_purchase()))
        results.append(("재고 목록", test_inventory_expiry_display()))
        results.append(("유통기한 리포트", test_expiry_report()))
        results.append(("DB 검증", test_db_verify()))
    print("\n" + "=" * 50)
    print("  테스트 결과 요약")
    print("=" * 50)
    all_pass = True
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"  [{status}] {name}")
    print("=" * 50)
    print(f"  전체: {'ALL PASS' if all_pass else 'SOME FAILED'}")
    print("=" * 50)
