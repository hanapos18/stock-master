"""소분(Repackaging) 1:N 기능 테스트"""
import requests
import pymysql

BASE = "http://localhost:5556"
s = requests.Session()


def test_login():
    print("=== 1. 로그인 ===")
    r = s.post(BASE + "/login", data={"username": "admin", "password": "admin123"}, allow_redirects=True)
    ok = r.status_code == 200 and "Dashboard" in r.text
    print(f"  로그인: {'성공' if ok else '실패'} (status={r.status_code})")
    return ok


def test_list_page():
    print("\n=== 2. 소분 목록 페이지 ===")
    r = s.get(BASE + "/repackaging/")
    has_title = "Repackaging Rules" in r.text
    has_new_btn = "New Rule" in r.text
    print(f"  Status: {r.status_code}")
    print(f"  제목 표시: {has_title}")
    print(f"  New Rule 버튼: {has_new_btn}")
    return r.status_code == 200


def test_create_form():
    print("\n=== 3. 소분 생성 폼 확인 ===")
    r = s.get(BASE + "/repackaging/create")
    has_name = "Rule Name" in r.text
    has_source = "Source Product" in r.text
    has_target = "Target Products" in r.text
    has_add_btn = "Add Target" in r.text
    has_example = "1:N" in r.text or "식당" in r.text
    print(f"  Status: {r.status_code}")
    print(f"  Rule Name 필드: {has_name}")
    print(f"  Source Product 필드: {has_source}")
    print(f"  Target Products 섹션: {has_target}")
    print(f"  Add Target 버튼: {has_add_btn}")
    print(f"  1:N 예시: {has_example}")
    return r.status_code == 200


def get_product_ids():
    """테스트 상품 ID 조회"""
    conn = pymysql.connect(host="localhost", port=3306, user="root", password="manila72", database="stock_master")
    cur = conn.cursor()
    products = {}
    for code in ["MT001", "MT002", "MT003", "MT004", "MT005"]:
        cur.execute("SELECT id, name FROM stk_products WHERE code=%s", (code,))
        row = cur.fetchone()
        if row:
            products[code] = {"id": row[0], "name": row[1]}
    cur.close()
    conn.close()
    return products


def test_create_rule(products):
    print("\n=== 4. 소분 규칙 생성 (1:N) ===")
    data = {
        "name": "한우 앞다리 소분",
        "source_product_id": products["MT001"]["id"],
        "target_product_id[]": [
            products["MT002"]["id"],
            products["MT003"]["id"],
            products["MT004"]["id"],
            products["MT005"]["id"],
        ],
        "target_ratio[]": ["3", "2", "2", "3"],
    }
    r = s.post(BASE + "/repackaging/create", data=data, allow_redirects=True)
    success = "successfully" in r.text or "한우 앞다리 소분" in r.text
    print(f"  Status: {r.status_code}")
    print(f"  생성 성공: {success}")
    if "한우 앞다리 소분" in r.text:
        print(f"  규칙 이름 표시: True")
    if "Bulgogi Cut" in r.text:
        print(f"  타겟 1 (Bulgogi Cut) 표시: True")
    if "Stew Cut" in r.text:
        print(f"  타겟 2 (Stew Cut) 표시: True")
    if "Braised Cut" in r.text:
        print(f"  타겟 3 (Braised Cut) 표시: True")
    if "Bone/Stock" in r.text:
        print(f"  타겟 4 (Bone/Stock) 표시: True")
    return success


def test_db_verify():
    print("\n=== 5. DB 검증 ===")
    conn = pymysql.connect(host="localhost", port=3306, user="root", password="manila72", database="stock_master")
    cur = conn.cursor()
    cur.execute("SELECT id, name, source_product_id FROM stk_repackaging WHERE is_active=1")
    rules = cur.fetchall()
    print(f"  활성 소분 규칙: {len(rules)}건")
    for rule in rules:
        rid, name, src = rule
        print(f"    - id={rid}, name={name}")
        cur.execute("SELECT rt.target_product_id, rt.ratio, p.name FROM stk_repackaging_targets rt JOIN stk_products p ON rt.target_product_id=p.id WHERE rt.repackaging_id=%s", (rid,))
        targets = cur.fetchall()
        print(f"      타겟: {len(targets)}개")
        for t in targets:
            print(f"        → {t[2]} (ratio={t[1]})")
    rule_id = rules[0][0] if rules else None
    cur.close()
    conn.close()
    return rule_id


def test_execute(rule_id):
    print(f"\n=== 6. 소분 실행 (rule_id={rule_id}, qty=1) ===")
    r = s.post(BASE + f"/repackaging/{rule_id}/execute", data={"source_quantity": "1"}, allow_redirects=True)
    success = "Repackaged" in r.text
    print(f"  Status: {r.status_code}")
    print(f"  실행 성공: {success}")
    return success


def test_inventory_after():
    print("\n=== 7. 실행 후 재고 확인 ===")
    conn = pymysql.connect(host="localhost", port=3306, user="root", password="manila72", database="stock_master")
    cur = conn.cursor()
    for code in ["MT001", "MT002", "MT003", "MT004", "MT005"]:
        cur.execute(
            "SELECT p.name, COALESCE(i.quantity,0) FROM stk_products p LEFT JOIN stk_inventory i ON p.id=i.product_id AND i.store_id=1 WHERE p.code=%s",
            (code,),
        )
        row = cur.fetchone()
        if row:
            print(f"  {code} {row[0]}: {row[1]}kg")
    # 트랜잭션 확인
    cur.execute("SELECT t.type, p.name, t.quantity, t.reason FROM stk_transactions t JOIN stk_products p ON t.product_id=p.id ORDER BY t.id DESC LIMIT 5")
    print("\n  최근 트랜잭션:")
    for tx in cur.fetchall():
        print(f"    [{tx[0]}] {tx[1]} qty={tx[2]} / {tx[3]}")
    cur.close()
    conn.close()


def test_edit_page(rule_id):
    print(f"\n=== 8. 수정 폼 확인 (rule_id={rule_id}) ===")
    r = s.get(BASE + f"/repackaging/{rule_id}/edit")
    has_name = "한우 앞다리 소분" in r.text
    has_targets = "Bulgogi Cut" in r.text
    print(f"  Status: {r.status_code}")
    print(f"  규칙 이름 로드: {has_name}")
    print(f"  기존 타겟 로드: {has_targets}")
    return r.status_code == 200


if __name__ == "__main__":
    print("=" * 50)
    print("  Hana StockMaster Repackaging 1:N 테스트")
    print("=" * 50)

    results = []
    results.append(("로그인", test_login()))
    results.append(("목록 페이지", test_list_page()))
    results.append(("생성 폼", test_create_form()))

    products = get_product_ids()
    print(f"\n  테스트 상품: {len(products)}개 확인")

    results.append(("규칙 생성", test_create_rule(products)))
    rule_id = test_db_verify()
    results.append(("DB 검증", rule_id is not None))

    if rule_id:
        results.append(("소분 실행", test_execute(rule_id)))
        test_inventory_after()
        results.append(("수정 폼", test_edit_page(rule_id)))

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
