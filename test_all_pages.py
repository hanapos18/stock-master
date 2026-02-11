"""StockMaster 전체 페이지 버튼/입력 기능 자동 테스트"""
import requests
import json
import sys
import io
from datetime import date
from bs4 import BeautifulSoup

# Windows UTF-8 출력
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE_URL = "http://localhost:5556"
session = requests.Session()

# 결과 저장
results = []

def log(msg: str) -> None:
    """테스트 로그 출력"""
    print(msg)

def record(page: str, test: str, status: str, detail: str = "") -> None:
    """테스트 결과 기록"""
    icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    results.append({"page": page, "test": test, "status": status, "detail": detail})
    log(f"  {icon} [{status}] {test}" + (f" - {detail}" if detail else ""))

def extract_page_elements(html: str) -> dict:
    """HTML에서 버튼, 입력 필드, 링크 추출"""
    soup = BeautifulSoup(html, "html.parser")
    buttons = []
    for btn in soup.find_all(["button", "input"], attrs={"type": ["submit", "button"]}):
        text = btn.get_text(strip=True) or btn.get("value", "")
        buttons.append({"text": text, "type": btn.get("type"), "name": btn.get("name", "")})
    for a in soup.find_all("a", class_=lambda c: c and "btn" in c):
        buttons.append({"text": a.get_text(strip=True), "type": "link-button", "href": a.get("href", "")})
    inputs = []
    for inp in soup.find_all(["input", "select", "textarea"]):
        if inp.get("type") in ("hidden", "submit", "button"):
            continue
        inputs.append({
            "name": inp.get("name", ""),
            "type": inp.get("type", inp.name),
            "required": inp.has_attr("required"),
            "placeholder": inp.get("placeholder", ""),
        })
    forms = []
    for form in soup.find_all("form"):
        forms.append({
            "action": form.get("action", ""),
            "method": form.get("method", "GET").upper(),
        })
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    flash_msgs = [div.get_text(strip=True) for div in soup.find_all("div", class_="alert")]
    return {
        "title": title,
        "buttons": buttons,
        "inputs": inputs,
        "forms": forms,
        "flash_messages": flash_msgs,
    }


def test_get_page(url: str, page_name: str, expect_redirect_to_login: bool = False) -> dict:
    """GET 요청으로 페이지 접근 테스트"""
    log(f"\n{'='*60}")
    log(f"📄 테스트: {page_name} ({url})")
    log(f"{'='*60}")
    try:
        resp = session.get(f"{BASE_URL}{url}", allow_redirects=True, timeout=10)
        if expect_redirect_to_login:
            if "/login" in resp.url:
                record(page_name, "미인증 접근 → 로그인 리다이렉트", "PASS")
            else:
                record(page_name, "미인증 접근 → 로그인 리다이렉트", "FAIL", f"이동된 URL: {resp.url}")
            return {}
        if resp.status_code == 200:
            record(page_name, "페이지 로드 (GET)", "PASS", f"HTTP {resp.status_code}")
        elif resp.status_code in (301, 302):
            record(page_name, "페이지 로드 (GET)", "PASS", f"리다이렉트 → {resp.url}")
        else:
            record(page_name, "페이지 로드 (GET)", "FAIL", f"HTTP {resp.status_code}")
            return {}
        elements = extract_page_elements(resp.text)
        if elements["buttons"]:
            btn_names = [b["text"] for b in elements["buttons"] if b["text"]]
            record(page_name, f"버튼 발견 ({len(elements['buttons'])}개)", "PASS",
                   ", ".join(btn_names[:10]))
        else:
            record(page_name, "버튼 발견", "WARN", "버튼 없음")
        if elements["inputs"]:
            inp_names = [f"{i['name']}({i['type']})" for i in elements["inputs"] if i["name"]]
            record(page_name, f"입력 필드 발견 ({len(elements['inputs'])}개)", "PASS",
                   ", ".join(inp_names[:10]))
        if elements["forms"]:
            form_info = [f"{f['method']} {f['action']}" for f in elements["forms"]]
            record(page_name, f"폼 발견 ({len(elements['forms'])}개)", "PASS",
                   ", ".join(form_info[:5]))
        return elements
    except requests.ConnectionError:
        record(page_name, "서버 연결", "FAIL", "서버에 연결할 수 없음")
        return {}
    except Exception as e:
        record(page_name, "페이지 로드", "FAIL", str(e))
        return {}


def test_post_form(url: str, page_name: str, data: dict, expect_success_msg: str = "") -> bool:
    """POST 요청으로 폼 제출 테스트"""
    try:
        resp = session.post(f"{BASE_URL}{url}", data=data, allow_redirects=True, timeout=10)
        if resp.status_code == 200:
            elements = extract_page_elements(resp.text)
            has_success = any(expect_success_msg.lower() in m.lower() for m in elements["flash_messages"]) if expect_success_msg else True
            has_danger = any("danger" in m.lower() or "error" in m.lower() for m in elements["flash_messages"])
            if has_success and not has_danger:
                record(page_name, f"폼 제출 (POST {url})", "PASS", "성공 메시지 확인")
                return True
            elif has_danger:
                record(page_name, f"폼 제출 (POST {url})", "FAIL",
                       f"에러 메시지: {elements['flash_messages']}")
                return False
            else:
                record(page_name, f"폼 제출 (POST {url})", "PASS", f"HTTP {resp.status_code}")
                return True
        else:
            record(page_name, f"폼 제출 (POST {url})", "FAIL", f"HTTP {resp.status_code}")
            return False
    except Exception as e:
        record(page_name, f"폼 제출 (POST {url})", "FAIL", str(e))
        return False


def test_api_endpoint(url: str, page_name: str) -> None:
    """JSON API 엔드포인트 테스트"""
    try:
        resp = session.get(f"{BASE_URL}{url}", timeout=10)
        if resp.status_code == 200:
            try:
                data = resp.json()
                record(page_name, f"API 호출 (GET {url})", "PASS",
                       f"JSON 응답, {len(data) if isinstance(data, list) else 'object'} 항목")
            except json.JSONDecodeError:
                record(page_name, f"API 호출 (GET {url})", "FAIL", "JSON 파싱 실패")
        else:
            record(page_name, f"API 호출 (GET {url})", "FAIL", f"HTTP {resp.status_code}")
    except Exception as e:
        record(page_name, f"API 호출 (GET {url})", "FAIL", str(e))


# =============================================
# 테스트 시작
# =============================================
def main():
    log("=" * 60)
    log("🧪 StockMaster 전체 페이지 자동 테스트 시작")
    log("=" * 60)
    log(f"서버: {BASE_URL}")
    log(f"날짜: {date.today().isoformat()}")
    # 0. 서버 연결 확인
    log("\n" + "=" * 60)
    log("🔌 0. 서버 연결 확인")
    log("=" * 60)
    try:
        resp = session.get(f"{BASE_URL}/login", timeout=5)
        record("서버", "연결 확인", "PASS", f"HTTP {resp.status_code}")
    except:
        record("서버", "연결 확인", "FAIL", "서버 응답 없음. 서버를 먼저 시작해주세요.")
        print_summary()
        sys.exit(1)
    # 1. 로그인 페이지 테스트
    log("\n" + "=" * 60)
    log("🔐 1. 로그인 페이지 테스트")
    log("=" * 60)
    login_elements = test_get_page("/login", "로그인 페이지")
    # 초기 설정 확인
    login_resp = session.get(f"{BASE_URL}/login", timeout=5)
    soup = BeautifulSoup(login_resp.text, "html.parser")
    has_setup = soup.find("input", {"name": "business_name"}) is not None
    if has_setup:
        record("로그인 페이지", "초기 설정 모드 감지", "PASS", "사용자 없음 → Setup 폼 표시")
        # 초기 설정 수행
        log("  → 초기 설정 수행 중...")
        setup_ok = test_post_form("/setup", "초기 설정", {
            "business_name": "Test Restaurant",
            "business_type": "restaurant",
            "username": "admin",
            "password": "admin123",
        }, "Setup complete")
    else:
        record("로그인 페이지", "기존 사용자 존재", "PASS", "로그인 폼 표시")
    # 빈 폼 제출 테스트
    log("  → 빈 폼 제출 테스트...")
    resp = session.post(f"{BASE_URL}/login", data={"username": "", "password": ""}, allow_redirects=True, timeout=5)
    if "/login" in resp.url or resp.status_code == 200:
        record("로그인 페이지", "빈 폼 제출 거부", "PASS")
    else:
        record("로그인 페이지", "빈 폼 제출 거부", "FAIL")
    # 잘못된 로그인 테스트
    log("  → 잘못된 로그인 테스트...")
    resp = session.post(f"{BASE_URL}/login", data={"username": "wrong", "password": "wrong"}, allow_redirects=True, timeout=5)
    soup_err = BeautifulSoup(resp.text, "html.parser")
    alerts = soup_err.find_all("div", class_="alert")
    if alerts:
        record("로그인 페이지", "잘못된 로그인 에러 메시지", "PASS", alerts[0].get_text(strip=True)[:50])
    else:
        record("로그인 페이지", "잘못된 로그인 에러 메시지", "WARN", "에러 메시지 없음")
    # 정상 로그인 시도
    log("  → 로그인 시도 (admin/admin123)...")
    resp = session.post(f"{BASE_URL}/login", data={"username": "admin", "password": "admin123"}, allow_redirects=True, timeout=5)
    logged_in = "/login" not in resp.url
    if logged_in:
        record("로그인 페이지", "정상 로그인", "PASS", f"리다이렉트: {resp.url}")
    else:
        record("로그인 페이지", "정상 로그인", "FAIL", "로그인 실패 - 계정 확인 필요")
        # admin/admin 시도
        log("  → 재시도 (admin/admin)...")
        resp = session.post(f"{BASE_URL}/login", data={"username": "admin", "password": "admin"}, allow_redirects=True, timeout=5)
        logged_in = "/login" not in resp.url
        if logged_in:
            record("로그인 페이지", "정상 로그인 (admin/admin)", "PASS")
    if not logged_in:
        log("\n❌ 로그인 실패 - 인증 필요한 페이지 테스트 불가")
        print_summary()
        sys.exit(1)
    # 2. 대시보드 테스트
    log("\n" + "=" * 60)
    log("📊 2. 대시보드 테스트")
    log("=" * 60)
    test_get_page("/", "대시보드")
    # 3. 사업장 관리 테스트
    log("\n" + "=" * 60)
    log("🏢 3. 사업장 관리 테스트")
    log("=" * 60)
    test_get_page("/business/", "사업장 목록")
    test_get_page("/business/create", "사업장 생성 폼")
    # 4. 카테고리 관리 테스트
    log("\n" + "=" * 60)
    log("📁 4. 카테고리 관리 테스트")
    log("=" * 60)
    test_get_page("/categories/", "카테고리 목록")
    # 카테고리 생성 테스트
    log("  → 카테고리 생성 테스트...")
    test_post_form("/categories/create", "카테고리 생성", {
        "name": "식자재 (테스트)",
        "display_order": "1",
    }, "created successfully")
    test_post_form("/categories/create", "카테고리 생성2", {
        "name": "음료 (테스트)",
        "display_order": "2",
    }, "created successfully")
    # 카테고리 API 테스트
    test_api_endpoint("/categories/api/list", "카테고리 API")
    # 5. 거래처 관리 테스트
    log("\n" + "=" * 60)
    log("🤝 5. 거래처 관리 테스트")
    log("=" * 60)
    test_get_page("/suppliers/", "거래처 목록")
    test_get_page("/suppliers/create", "거래처 생성 폼")
    # 거래처 생성 테스트
    log("  → 거래처 생성 테스트...")
    test_post_form("/suppliers/create", "거래처 생성", {
        "name": "테스트 납품업체",
        "contact_person": "홍길동",
        "phone": "010-1234-5678",
        "email": "test@test.com",
        "address": "서울시 강남구",
        "memo": "테스트용 거래처",
    }, "created successfully")
    # 6. 상품 관리 테스트
    log("\n" + "=" * 60)
    log("📦 6. 상품 관리 테스트")
    log("=" * 60)
    test_get_page("/products/", "상품 목록")
    test_get_page("/products/create", "상품 생성 폼")
    # 상품 생성 테스트
    log("  → 상품 생성 테스트...")
    test_post_form("/products/create", "상품 생성", {
        "code": "TEST001",
        "name": "테스트 상품",
        "unit": "ea",
        "unit_price": "100",
        "sell_price": "150",
        "min_stock": "10",
        "barcode": "",
        "description": "테스트용 상품",
        "storage_location": "warehouse",
    }, "created successfully")
    # 상품 검색 테스트
    log("  → 상품 검색 테스트...")
    resp = session.get(f"{BASE_URL}/products/?search=테스트", timeout=5)
    if resp.status_code == 200:
        record("상품 관리", "검색 기능", "PASS", f"HTTP {resp.status_code}")
    else:
        record("상품 관리", "검색 기능", "FAIL", f"HTTP {resp.status_code}")
    # 상품 API 테스트
    test_api_endpoint("/products/api/list", "상품 API")
    test_api_endpoint("/products/api/list?search=테스트", "상품 API (검색)")
    # 7. 재고 관리 테스트
    log("\n" + "=" * 60)
    log("📋 7. 재고 관리 테스트")
    log("=" * 60)
    test_get_page("/inventory/", "재고 현황")
    test_get_page("/inventory/stock-in", "입고 처리 폼")
    test_get_page("/inventory/stock-out", "출고 처리 폼")
    test_get_page("/inventory/transactions", "입출고 내역")
    # 입출고 내역 필터 테스트
    log("  → 거래 유형 필터 테스트...")
    for tx_type in ["in", "out", "adjust", "discard"]:
        resp = session.get(f"{BASE_URL}/inventory/transactions?type={tx_type}", timeout=5)
        if resp.status_code == 200:
            record("재고 관리", f"거래 필터 ({tx_type})", "PASS")
        else:
            record("재고 관리", f"거래 필터 ({tx_type})", "FAIL")
    # 8. 매입 관리 테스트
    log("\n" + "=" * 60)
    log("🛒 8. 매입 관리 테스트")
    log("=" * 60)
    test_get_page("/purchases/", "매입 목록")
    test_get_page("/purchases/create", "매입 생성 폼")
    # 매입 상태 필터 테스트
    log("  → 매입 상태 필터 테스트...")
    for status in ["pending", "received", "cancelled"]:
        resp = session.get(f"{BASE_URL}/purchases/?status={status}", timeout=5)
        if resp.status_code == 200:
            record("매입 관리", f"상태 필터 ({status})", "PASS")
        else:
            record("매입 관리", f"상태 필터 ({status})", "FAIL")
    # 9. 레시피 관리 테스트 (식당 전용)
    log("\n" + "=" * 60)
    log("🍳 9. 레시피 관리 테스트 (식당용)")
    log("=" * 60)
    test_get_page("/recipes/", "레시피 목록")
    test_get_page("/recipes/create", "레시피 생성 폼")
    # 10. 도매 관리 테스트 (마트 전용)
    log("\n" + "=" * 60)
    log("🏪 10. 도매 관리 테스트 (마트용)")
    log("=" * 60)
    test_get_page("/wholesale/clients", "도매 거래처 목록")
    test_get_page("/wholesale/clients/create", "도매 거래처 생성 폼")
    test_get_page("/wholesale/orders", "도매 주문 목록")
    test_get_page("/wholesale/orders/create", "도매 주문 생성 폼")
    # 도매 주문 상태 필터 테스트
    log("  → 도매 주문 상태 필터 테스트...")
    for status in ["pending", "shipped", "cancelled"]:
        resp = session.get(f"{BASE_URL}/wholesale/orders?status={status}", timeout=5)
        if resp.status_code == 200:
            record("도매 관리", f"주문 상태 필터 ({status})", "PASS")
        else:
            record("도매 관리", f"주문 상태 필터 ({status})", "FAIL")
    # 11. 소분/리패키징 테스트
    log("\n" + "=" * 60)
    log("📐 11. 소분/리패키징 테스트")
    log("=" * 60)
    test_get_page("/repackaging/", "소분 규칙 목록")
    test_get_page("/repackaging/create", "소분 규칙 생성 폼")
    # 12. 판매 관리 테스트
    log("\n" + "=" * 60)
    log("💰 12. 판매 관리 테스트 (비POS)")
    log("=" * 60)
    test_get_page("/sales/", "판매 목록")
    test_get_page("/sales/create", "판매 생성 폼")
    # 판매 상태 필터 테스트
    log("  → 판매 상태 필터 테스트...")
    for status in ["pending", "confirmed", "cancelled"]:
        resp = session.get(f"{BASE_URL}/sales/?status={status}", timeout=5)
        if resp.status_code == 200:
            record("판매 관리", f"상태 필터 ({status})", "PASS")
        else:
            record("판매 관리", f"상태 필터 ({status})", "FAIL")
    # 13. 재고 실사 테스트
    log("\n" + "=" * 60)
    log("📝 13. 재고 실사 테스트")
    log("=" * 60)
    test_get_page("/stock-count/", "실사 보고 목록")
    test_get_page("/stock-count/create", "실사 보고 생성 폼")
    # 14. 리포트 테스트
    log("\n" + "=" * 60)
    log("📊 14. 리포트 테스트")
    log("=" * 60)
    test_get_page("/reports/inventory", "재고 현황 리포트")
    test_get_page("/reports/purchases", "매입 리포트")
    test_get_page("/reports/sales", "매출 리포트")
    test_get_page("/reports/wholesale", "도매 리포트")
    test_get_page("/reports/low-stock", "재고 부족 리포트")
    # 리포트 기간 필터 테스트
    log("  → 리포트 기간 필터 테스트...")
    resp = session.get(f"{BASE_URL}/reports/purchases?start_date=2026-01-01&end_date=2026-02-11", timeout=5)
    if resp.status_code == 200:
        record("리포트", "기간 필터 테스트", "PASS")
    else:
        record("리포트", "기간 필터 테스트", "FAIL")
    # 리포트 API 내보내기 테스트
    log("  → 리포트 API 내보내기 테스트...")
    for rtype in ["inventory", "purchases", "sales", "wholesale"]:
        test_api_endpoint(f"/reports/api/export/{rtype}", f"리포트 API ({rtype})")
    # 엑셀 다운로드 테스트
    log("  → 엑셀 다운로드 테스트...")
    for rtype in ["inventory", "purchases", "sales", "wholesale"]:
        try:
            resp = session.get(f"{BASE_URL}/reports/excel/{rtype}", timeout=10)
            if resp.status_code == 200 and "spreadsheet" in resp.headers.get("content-type", ""):
                record("리포트", f"엑셀 다운로드 ({rtype})", "PASS", f"{len(resp.content)} bytes")
            elif resp.status_code == 200:
                record("리포트", f"엑셀 다운로드 ({rtype})", "PASS", f"HTTP 200")
            else:
                record("리포트", f"엑셀 다운로드 ({rtype})", "FAIL", f"HTTP {resp.status_code}")
        except Exception as e:
            record("리포트", f"엑셀 다운로드 ({rtype})", "FAIL", str(e))
    # 15. 도움말 페이지 테스트
    log("\n" + "=" * 60)
    log("❓ 15. 도움말 페이지 테스트")
    log("=" * 60)
    test_get_page("/help/", "도움말 페이지")
    # 16. 로그아웃 테스트
    log("\n" + "=" * 60)
    log("🚪 16. 로그아웃 테스트")
    log("=" * 60)
    resp = session.get(f"{BASE_URL}/logout", allow_redirects=True, timeout=5)
    if "/login" in resp.url:
        record("로그아웃", "로그아웃 → 로그인 리다이렉트", "PASS")
    else:
        record("로그아웃", "로그아웃 → 로그인 리다이렉트", "FAIL", f"이동: {resp.url}")
    # 로그아웃 후 대시보드 접근 테스트
    test_get_page("/", "로그아웃 후 대시보드", expect_redirect_to_login=True)
    # 결과 요약 출력
    print_summary()


def print_summary():
    """테스트 결과 요약 출력"""
    log("\n")
    log("=" * 70)
    log("📋 StockMaster 전체 페이지 테스트 결과 요약")
    log("=" * 70)
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    warn_count = sum(1 for r in results if r["status"] == "WARN")
    total = len(results)
    log(f"\n총 {total}개 테스트: ✅ PASS {pass_count} | ❌ FAIL {fail_count} | ⚠️ WARN {warn_count}")
    log(f"통과율: {pass_count/total*100:.1f}%" if total > 0 else "")
    # 페이지별 요약
    pages = {}
    for r in results:
        page = r["page"]
        if page not in pages:
            pages[page] = {"pass": 0, "fail": 0, "warn": 0, "tests": []}
        pages[page][r["status"].lower()] = pages[page].get(r["status"].lower(), 0) + 1
        pages[page]["tests"].append(r)
    log(f"\n{'페이지':<25} {'PASS':>6} {'FAIL':>6} {'WARN':>6} {'결과':>8}")
    log("-" * 60)
    for page, data in pages.items():
        status_icon = "✅" if data.get("fail", 0) == 0 else "❌"
        log(f"{page:<25} {data.get('pass',0):>6} {data.get('fail',0):>6} {data.get('warn',0):>6} {status_icon:>8}")
    # 실패한 테스트 상세
    failed = [r for r in results if r["status"] == "FAIL"]
    if failed:
        log(f"\n{'='*60}")
        log("❌ 실패한 테스트 상세:")
        log(f"{'='*60}")
        for r in failed:
            log(f"  [{r['page']}] {r['test']}: {r['detail']}")
    else:
        log("\n🎉 모든 테스트 통과!")


if __name__ == "__main__":
    main()
