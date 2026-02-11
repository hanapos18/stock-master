"""도매 결제/잔금 기능 통합 테스트"""
import requests
import pymysql
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

BASE = "http://localhost:5556"
DB_CFG = dict(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "3306")),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", ""),
    database=os.getenv("DB_NAME", "stock_master"),
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)


def db_query(sql, params=None):
    conn = pymysql.connect(**DB_CFG)
    cur = conn.cursor()
    cur.execute(sql, params)
    result = cur.fetchall()
    conn.close()
    return result


def db_one(sql, params=None):
    rows = db_query(sql, params)
    return rows[0] if rows else None


results = []


def check(name, condition):
    status = "PASS" if condition else "FAIL"
    results.append((name, status))
    print(f"  [{status}] {name}")


print("=== 도매 결제/잔금 테스트 시작 ===\n")

# 1. 로그인
print("1. 로그인")
s = requests.Session()
r = s.post(f"{BASE}/login", data={"username": "admin", "password": "admin123"}, allow_redirects=True)
check("로그인 성공", r.status_code == 200)

# 2. 기존 도매 주문 확인 (또는 생성)
print("\n2. 도매 주문 확인")
order = db_one(
    "SELECT * FROM stk_wholesale_orders WHERE status != 'cancelled' "
    "ORDER BY id DESC LIMIT 1"
)
if order:
    order_id = order["id"]
    print(f"   기존 주문 사용: id={order_id}, number={order['order_number']}, final={order['final_amount']}")
else:
    print("   도매 주문 없음 - 테스트 데이터 생성 필요")
    order_id = None

if order_id:
    # 3. 주문 상세 페이지 접근
    print("\n3. 주문 상세 페이지 접근")
    r = s.get(f"{BASE}/wholesale/orders/{order_id}")
    check("주문 상세 접근 성공", r.status_code == 200)
    check("결제 모달 존재", "paymentModal" in r.text)
    check("Add Payment 버튼 존재", "Add Payment" in r.text)
    check("Balance Due 표시", "Balance Due" in r.text)

    # 4. 결제 등록 (현금 - 부분결제)
    print("\n4. 현금 부분결제 등록")
    final_amount = float(order["final_amount"])
    partial_amount = round(final_amount * 0.3, 2)  # 30%
    r = s.post(f"{BASE}/wholesale/orders/{order_id}/pay", data={
        "payment_method": "cash",
        "amount": str(partial_amount),
        "memo": "Test partial cash payment",
    }, allow_redirects=True)
    check("부분결제 등록 성공", r.status_code == 200)

    # DB 확인
    order_after = db_one("SELECT * FROM stk_wholesale_orders WHERE id = %s", (order_id,))
    check("payment_status = partial", order_after["payment_status"] == "partial")
    check(f"paid_amount = {partial_amount}", abs(float(order_after["paid_amount"]) - partial_amount) < 0.01)

    payment = db_one(
        "SELECT * FROM stk_wholesale_payments WHERE order_id = %s ORDER BY id DESC LIMIT 1",
        (order_id,),
    )
    check("결제 레코드 생성됨", payment is not None)
    check("결제 방법 = cash", payment["payment_method"] == "cash")

    # 5. 수표 부분결제 등록
    print("\n5. 수표 부분결제 등록")
    check_amount = round(final_amount * 0.3, 2)  # 30%
    r = s.post(f"{BASE}/wholesale/orders/{order_id}/pay", data={
        "payment_method": "check",
        "amount": str(check_amount),
        "check_number": "CHK-12345",
        "check_date": "2026-03-15",
        "memo": "Test check payment",
    }, allow_redirects=True)
    check("수표 결제 등록 성공", r.status_code == 200)

    order_after = db_one("SELECT * FROM stk_wholesale_orders WHERE id = %s", (order_id,))
    check("payment_status 여전히 partial", order_after["payment_status"] == "partial")

    # 6. 은행입금 잔금 결제 (나머지 전부)
    print("\n6. 은행입금으로 잔금 결제")
    remaining = final_amount - partial_amount - check_amount
    r = s.post(f"{BASE}/wholesale/orders/{order_id}/pay", data={
        "payment_method": "bank_transfer",
        "amount": str(round(remaining, 2)),
        "bank_name": "KB Bank",
        "bank_ref": "TRF-2026-0001",
        "memo": "Final bank payment",
    }, allow_redirects=True)
    check("은행입금 잔금 결제 성공", r.status_code == 200)

    order_after = db_one("SELECT * FROM stk_wholesale_orders WHERE id = %s", (order_id,))
    check("payment_status = paid", order_after["payment_status"] == "paid")
    check("잔금 0원 확인", abs(float(order_after["final_amount"]) - float(order_after["paid_amount"])) < 0.01)

    # 7. 결제 내역 API
    print("\n7. 결제 내역 API 확인")
    r = s.get(f"{BASE}/wholesale/orders/{order_id}/payments")
    check("결제 내역 API 접근", r.status_code == 200)
    payments_json = r.json()
    check("결제 건수 3건", len(payments_json) == 3)

    # 8. 주문 목록에서 결제 상태 표시 확인
    print("\n8. 주문 목록 결제 상태 확인")
    r = s.get(f"{BASE}/wholesale/orders")
    check("주문 목록 접근", r.status_code == 200)
    check("Payment 컬럼 존재", "Payment" in r.text)
    check("Paid 배지 표시", "Paid" in r.text)

# 9. 미수금 현황 페이지
print("\n9. 미수금 현황 페이지")
r = s.get(f"{BASE}/wholesale/balances")
check("미수금 현황 접근 성공", r.status_code == 200)
check("Client Balances 표시", "Client Balances" in r.text)
check("Total Outstanding 표시", "Total Outstanding" in r.text)

# 10. 거래처 목록에서 잔고 표시 확인
print("\n10. 거래처 목록 잔고 확인")
r = s.get(f"{BASE}/wholesale/clients")
check("거래처 목록 접근", r.status_code == 200)
check("Balance 컬럼 존재", "Balance" in r.text)

# 11. 거래명세서 확인
if order_id:
    print("\n11. 거래명세서 확인")
    client_id = order["client_id"]
    r = s.get(f"{BASE}/wholesale/clients/{client_id}/statement")
    check("거래명세서 접근", r.status_code == 200)
    check("Balance Summary 표시", "Balance Summary" in r.text)
    check("Payment History 표시", "Payment History" in r.text)
    check("Orders 표시", "Orders" in r.text)

# 12. 수표 만기 스케줄 확인
print("\n12. 수표 만기 스케줄 확인 (DB)")
checks = db_query(
    "SELECT * FROM stk_wholesale_payments WHERE payment_method = 'check' AND check_date IS NOT NULL"
)
check("수표 레코드 존재", len(checks) > 0)
if checks:
    check("수표번호 기록됨", checks[-1]["check_number"] is not None)
    check("수표 만기일 기록됨", checks[-1]["check_date"] is not None)

# 결과 요약
print("\n" + "=" * 50)
passed = sum(1 for _, s in results if s == "PASS")
failed = sum(1 for _, s in results if s == "FAIL")
print(f"결과: {passed} PASS / {failed} FAIL / 총 {len(results)} 건")
if failed > 0:
    print("\n실패 항목:")
    for name, status in results:
        if status == "FAIL":
            print(f"  - {name}")
print("=" * 50)
