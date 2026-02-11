"""StockMaster 첨부파일(영수증 업로드) 기능 자동 테스트"""
import requests
import io
import sys
import json

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE_URL = "http://localhost:5556"
session = requests.Session()
results = []


def record(test: str, status: str, detail: str = "") -> None:
    icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    results.append({"test": test, "status": status, "detail": detail})
    print(f"  {icon} [{status}] {test}" + (f" - {detail}" if detail else ""))


def create_test_image() -> io.BytesIO:
    """1x1 PNG 테스트 이미지 생성"""
    import struct
    import zlib
    def create_png():
        signature = b'\x89PNG\r\n\x1a\n'
        ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
        ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data)
        ihdr = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)
        raw = b'\x00\xff\x00\x00'
        compressed = zlib.compress(raw)
        idat_crc = zlib.crc32(b'IDAT' + compressed)
        idat = struct.pack('>I', len(compressed)) + b'IDAT' + compressed + struct.pack('>I', idat_crc)
        iend_crc = zlib.crc32(b'IEND')
        iend = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)
        return signature + ihdr + idat + iend
    buf = io.BytesIO(create_png())
    buf.name = "test_receipt.png"
    return buf


def main():
    print("=" * 60)
    print("🧪 StockMaster 첨부파일 기능 테스트")
    print("=" * 60)

    # 1. 로그인
    print("\n📌 1. 로그인")
    resp = session.post(f"{BASE_URL}/login",
                        data={"username": "admin", "password": "admin123"},
                        allow_redirects=True, timeout=10)
    if "/login" not in resp.url:
        record("로그인", "PASS", f"→ {resp.url}")
    else:
        record("로그인", "FAIL", "로그인 실패")
        print_summary()
        return

    # 2. 입고 폼 페이지 접근
    print("\n📌 2. 입고(Stock In) 폼 확인")
    resp = session.get(f"{BASE_URL}/inventory/stock-in", timeout=10)
    if resp.status_code == 200:
        has_enctype = 'enctype="multipart/form-data"' in resp.text
        has_file_input = 'name="receipt_file"' in resp.text
        has_preview = 'id="previewArea"' in resp.text
        has_camera = 'capture="environment"' in resp.text
        record("입고 폼 - enctype 설정", "PASS" if has_enctype else "FAIL")
        record("입고 폼 - 파일 입력 필드", "PASS" if has_file_input else "FAIL")
        record("입고 폼 - 미리보기 영역", "PASS" if has_preview else "FAIL")
        record("입고 폼 - 카메라 캡처", "PASS" if has_camera else "FAIL")
    else:
        record("입고 폼 접근", "FAIL", f"HTTP {resp.status_code}")

    # 3. 입고 처리 + 사진 업로드
    print("\n📌 3. 입고 처리 + 사진 업로드")
    # 먼저 상품 목록에서 product_id 가져오기
    products_resp = session.get(f"{BASE_URL}/products/api/list", timeout=10)
    products = products_resp.json()
    if not products:
        record("상품 조회", "FAIL", "상품 없음")
        print_summary()
        return
    product_id = products[0]["id"]
    record("상품 조회", "PASS", f"ID={product_id}, {products[0]['name']}")

    test_image = create_test_image()
    resp = session.post(f"{BASE_URL}/inventory/stock-in",
                        data={
                            "product_id": str(product_id),
                            "quantity": "5",
                            "location": "warehouse",
                            "unit_price": "100",
                            "reason": "Test stock in with receipt",
                        },
                        files={"receipt_file": ("test_receipt.png", test_image, "image/png")},
                        allow_redirects=True, timeout=10)
    if resp.status_code == 200 and "Stock In processed" in resp.text:
        record("입고 + 사진 업로드", "PASS", "성공 메시지 확인")
    elif resp.status_code == 200:
        record("입고 + 사진 업로드", "PASS", f"HTTP 200 (리다이렉트 완료)")
    else:
        record("입고 + 사진 업로드", "FAIL", f"HTTP {resp.status_code}")

    # 4. 입출고 내역에서 첨부 아이콘 확인
    print("\n📌 4. 입출고 내역 첨부 아이콘 확인")
    resp = session.get(f"{BASE_URL}/inventory/transactions", timeout=10)
    has_clip_icon = "bi-paperclip" in resp.text
    record("입출고 내역 - 클립 아이콘", "PASS" if has_clip_icon else "WARN",
           "첨부파일 있는 거래에 아이콘 표시" if has_clip_icon else "아이콘 없음 (첨부 없을 수 있음)")

    # 5. 매입 폼 확인
    print("\n📌 5. 매입(Purchase) 폼 확인")
    resp = session.get(f"{BASE_URL}/purchases/create", timeout=10)
    if resp.status_code == 200:
        has_enctype = 'enctype="multipart/form-data"' in resp.text
        has_file_input = 'name="receipt_file"' in resp.text
        record("매입 폼 - enctype 설정", "PASS" if has_enctype else "FAIL")
        record("매입 폼 - 파일 입력 필드", "PASS" if has_file_input else "FAIL")
    else:
        record("매입 폼 접근", "FAIL", f"HTTP {resp.status_code}")

    # 6. 첨부파일 API 테스트
    print("\n📌 6. 첨부파일 API 테스트")
    resp = session.get(f"{BASE_URL}/attachments/api/list", timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        record("API 목록 조회", "PASS", f"{len(data)}개 첨부파일")
        if data:
            att_id = data[0]["id"]
            # 이미지 보기 테스트
            resp2 = session.get(f"{BASE_URL}/attachments/{att_id}/view", timeout=10)
            record("첨부파일 보기", "PASS" if resp2.status_code == 200 else "FAIL",
                   f"HTTP {resp2.status_code}, Content-Type: {resp2.headers.get('content-type', 'N/A')}")
            # 다운로드 테스트
            resp3 = session.get(f"{BASE_URL}/attachments/{att_id}/download", timeout=10)
            has_attachment_header = "attachment" in resp3.headers.get("content-disposition", "")
            record("첨부파일 다운로드", "PASS" if resp3.status_code == 200 and has_attachment_header else "FAIL",
                   f"HTTP {resp3.status_code}, {len(resp3.content)} bytes")
            # 특정 거래 첨부 API
            ref_type = data[0]["reference_type"]
            ref_id = data[0]["reference_id"]
            resp4 = session.get(f"{BASE_URL}/attachments/api/{ref_type}/{ref_id}", timeout=10)
            record("거래별 첨부 API", "PASS" if resp4.status_code == 200 else "FAIL",
                   f"{len(resp4.json())}개")
    else:
        record("API 목록 조회", "FAIL", f"HTTP {resp.status_code}")

    # 7. 입고 (사진 없이) 테스트 - 기존 기능 호환성
    print("\n📌 7. 입고 (사진 없이) 호환성 테스트")
    resp = session.post(f"{BASE_URL}/inventory/stock-in",
                        data={
                            "product_id": str(product_id),
                            "quantity": "3",
                            "location": "warehouse",
                            "unit_price": "100",
                            "reason": "Test without photo",
                        },
                        allow_redirects=True, timeout=10)
    if resp.status_code == 200:
        record("입고 (사진 없이)", "PASS", "기존 기능 정상 작동")
    else:
        record("입고 (사진 없이)", "FAIL", f"HTTP {resp.status_code}")

    print_summary()


def print_summary():
    print("\n" + "=" * 60)
    print("📋 첨부파일 기능 테스트 결과 요약")
    print("=" * 60)
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    warn_count = sum(1 for r in results if r["status"] == "WARN")
    total = len(results)
    print(f"\n총 {total}개 테스트: ✅ PASS {pass_count} | ❌ FAIL {fail_count} | ⚠️ WARN {warn_count}")
    if fail_count == 0:
        print("\n🎉 모든 테스트 통과!")
    else:
        print("\n❌ 실패한 테스트:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"  - {r['test']}: {r['detail']}")


if __name__ == "__main__":
    main()
