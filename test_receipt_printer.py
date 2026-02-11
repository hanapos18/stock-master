"""ESC/POS 영수증 프린터 통합 테스트"""
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

results = []


def db_one(sql, params=None):
    conn = pymysql.connect(**DB_CFG)
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    conn.close()
    return row


def check(name, condition):
    status = "PASS" if condition else "FAIL"
    results.append((name, status))
    print(f"  [{status}] {name}")


print("=== ESC/POS 영수증 프린터 테스트 시작 ===\n")

# 1. 포맷 엔진 단위 테스트
print("1. ReceiptPrinter 포맷 엔진 테스트")
from app.services.receipt_printer import ReceiptPrinter, format_number

# 40자 프린터 테스트
p40 = ReceiptPrinter(ip="", port=9100, width=40, encoding="euc-kr")
p40.reset()
p40.center().double_size().line("TEST SHOP")
p40.normal().center().double_separator()
p40.left().pair_line("No:", "SA-20260212-001")
p40.pair_line("Date:", "2026-02-12")
p40.separator()
p40.bold_on()
p40.columns([("Item", 14, "L"), ("Qty", 6, "R"), ("Price", 10, "R"), ("Amt", 10, "R")])
p40.bold_off()
p40.columns([("Rice 10kg", 14, "L"), ("2", 6, "R"), ("30,000", 10, "R"), ("60,000", 10, "R")])
p40.columns([("Soy Sauce 1L", 14, "L"), ("3", 6, "R"), ("5,000", 10, "R"), ("15,000", 10, "R")])
p40.separator()
p40.bold_on().pair_line("TOTAL:", "75,000")
p40.bold_off()
p40.cut()

preview40 = p40.get_text_preview()
print("--- 40자 영수증 미리보기 ---")
print(preview40)
print("---")
check("40자 헤더 포함", "TEST SHOP" in preview40)
check("40자 라인번호 포함", "SA-20260212-001" in preview40)
check("40자 상품 포함", "Rice 10kg" in preview40)
check("40자 합계 포함", "TOTAL:" in preview40)
check("40자 구분선 포함", "====" in preview40)
check("40자 바이트 생성", len(p40.buffer) > 100)

# 20자 프린터 테스트
print("\n2. 20자 폭 프린터 테스트")
p20 = ReceiptPrinter(ip="", port=9100, width=20, encoding="euc-kr")
p20.reset()
p20.center().double_size().line("SHOP")
p20.normal().center().double_separator()
p20.left().pair_line("No:", "SA-001")
p20.separator()
p20.line("Rice 10kg")
p20.pair_line(" 2 x 30,000", "60,000")
p20.separator()
p20.bold_on().pair_line("TOTAL:", "60,000")
p20.cut()

preview20 = p20.get_text_preview()
print("--- 20자 영수증 미리보기 ---")
print(preview20)
print("---")
check("20자 구분선 길이", "====================" in preview20)
check("20자 바이트 생성", len(p20.buffer) > 50)

# 한글 폭 계산 테스트
print("\n3. 한글 폭 계산 테스트")
check("영문 폭 계산", p40._display_width("Hello") == 5)
check("한글 폭 계산", p40._display_width("안녕") == 4)
check("혼합 폭 계산", p40._display_width("Rice밥") == 6)

# 숫자 포맷 테스트
print("\n4. 숫자 포맷 테스트")
check("정수 포맷", format_number(75000.0) == "75,000")
check("소수 포맷", format_number(123.50) == "123.5")
check("0원 포맷", format_number(0.0) == "0")

# 5. 로그인 & 판매 영수증 빌드 테스트
print("\n5. 웹 라우트 테스트")
s = requests.Session()
r = s.post(f"{BASE}/login", data={"username": "admin", "password": "admin123"}, allow_redirects=True)
check("로그인 성공", r.status_code == 200)

# 판매 확인
sale = db_one("SELECT * FROM stk_sales ORDER BY id DESC LIMIT 1")
if sale:
    sale_id = sale["id"]
    print(f"   판매: id={sale_id}, number={sale['sale_number']}")

    # 영수증 미리보기 페이지 접근
    r = s.get(f"{BASE}/sales/{sale_id}/receipt/preview")
    check("미리보기 페이지 접근", r.status_code == 200)
    check("Receipt Preview 표시", "Receipt Preview" in r.text)
    check("모노스페이스 미리보기", "Courier" in r.text)
    check("Test Connection 버튼", "Test Connection" in r.text)
    check("Print Receipt 버튼", "Print Receipt" in r.text)
    check("판매번호 미리보기 포함", sale["sale_number"] in r.text)

    # 영수증 직접 인쇄 (프린터 미설정 -> 실패 예상)
    r = s.post(f"{BASE}/sales/{sale_id}/receipt")
    check("프린터 API 접근", r.status_code == 200)
    data = r.json()
    check("프린터 미설정 시 에러", data["success"] is False)
    check("IP 미설정 메시지", "not configured" in data["message"].lower())

    # 연결 테스트 (프린터 미설정)
    r = s.post(f"{BASE}/sales/printer/test-connection")
    check("연결 테스트 API", r.status_code == 200)
    data = r.json()
    check("연결 실패 메시지", data["success"] is False)

    # 판매 상세 페이지에서 버튼 확인
    r = s.get(f"{BASE}/sales/{sale_id}")
    check("판매 상세 접근", r.status_code == 200)
    check("Receipt Print 버튼 존재", "Receipt Print" in r.text)
    check("Quick Receipt 버튼 존재", "Quick Receipt" in r.text)
else:
    print("   판매 없음 - 일부 테스트 스킵")

# 6. build_sale_receipt 전체 흐름 테스트 (웹 미리보기 API로 검증)
print("\n6. build_sale_receipt 전체 흐름")
from app.services.receipt_printer import build_sale_receipt
if sale:
    # 웹 미리보기 페이지에서 영수증 내용 검증
    r = s.get(f"{BASE}/sales/{sale_id}/receipt/preview")
    check("영수증 미리보기 빌드 성공", r.status_code == 200)
    check("상호명 포함", "MAPLE" in r.text or "Hana StockMaster" in r.text)
    check("TOTAL 포함", "TOTAL:" in r.text)
    check("Thank you 포함", "Thank you" in r.text)
    # 직접 빌드 테스트 (더미 데이터)
    mock_sale = {
        "sale_number": "SA-TEST-001",
        "sale_date": "2026-02-12",
        "customer_name": "Test Customer",
        "total_amount": 75000,
        "line_items": [
            {"product_code": "P001", "product_name": "Rice 10kg", "quantity": 2, "unit_price": 30000, "amount": 60000, "unit": "bag"},
            {"product_code": "P002", "product_name": "Soy Sauce", "quantity": 3, "unit_price": 5000, "amount": 15000, "unit": "btl"},
        ],
    }
    mock_printer = build_sale_receipt(mock_sale, "Test Store", "My Business")
    mock_preview = mock_printer.get_text_preview()
    print("--- 더미 판매 영수증 ---")
    print(mock_preview)
    print("---")
    check("더미 영수증 빌드", len(mock_preview) > 50)
    check("더미 상호명", "My Business" in mock_preview)
    check("더미 매장명", "Test Store" in mock_preview)
    check("더미 판매번호", "SA-TEST-001" in mock_preview)
    check("더미 TOTAL", "75,000" in mock_preview)

# 결과 요약
print("\n" + "=" * 50)
passed = sum(1 for _, st in results if st == "PASS")
failed = sum(1 for _, st in results if st == "FAIL")
print(f"결과: {passed} PASS / {failed} FAIL / 총 {len(results)} 건")
if failed > 0:
    print("\n실패 항목:")
    for name, st in results:
        if st == "FAIL":
            print(f"  - {name}")
print("=" * 50)
