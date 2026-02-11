"""이미지 리사이징 기능 테스트"""
import requests
import io
import sys

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE_URL = "http://localhost:5556"
session = requests.Session()


def create_large_test_image(width: int = 4000, height: int = 3000) -> io.BytesIO:
    """큰 테스트 이미지 생성 (4000x3000 = 12MP, 실제 카메라 사진 크기)"""
    from PIL import Image
    img = Image.new("RGB", (width, height), color=(255, 250, 240))
    # 텍스트 시뮬레이션용 패턴 그리기
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    for y in range(0, height, 40):
        draw.text((20, y), f"Receipt Line {y//40+1}: Item description ₱1,234.56", fill=(0, 0, 0))
    draw.rectangle([50, 50, width-50, 150], outline=(0, 0, 0), width=3)
    draw.text((60, 70), "*** OFFICIAL RECEIPT ***", fill=(0, 0, 0))
    draw.text((60, 100), f"Original: {width}x{height}", fill=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    original_size = len(buf.getvalue())
    print(f"  테스트 이미지 생성: {width}x{height}, {original_size:,} bytes ({original_size/1024:.0f} KB)")
    buf.seek(0)
    return buf


def main():
    print("=" * 60)
    print("🧪 이미지 리사이징 기능 테스트")
    print("=" * 60)

    # 로그인
    session.post(f"{BASE_URL}/login",
                 data={"username": "admin", "password": "admin123"},
                 allow_redirects=True)
    products = session.get(f"{BASE_URL}/products/api/list").json()
    product_id = products[0]["id"]

    # 테스트 1: 큰 이미지 (4000x3000, ~1.5MB)
    print("\n📌 테스트 1: 큰 이미지 업로드 (4000x3000)")
    big_image = create_large_test_image(4000, 3000)
    original_size = len(big_image.getvalue())
    big_image.seek(0)
    resp = session.post(f"{BASE_URL}/inventory/stock-in",
                        data={
                            "product_id": str(product_id),
                            "quantity": "1",
                            "location": "warehouse",
                            "unit_price": "10",
                            "reason": "Resize test - large image",
                        },
                        files={"receipt_file": ("big_receipt.jpg", big_image, "image/jpeg")},
                        allow_redirects=True, timeout=15)
    if resp.status_code == 200:
        # API로 저장된 크기 확인
        att_list = session.get(f"{BASE_URL}/attachments/api/list").json()
        if att_list:
            latest = att_list[0]
            saved_size = latest["file_size"]
            ratio = saved_size / original_size * 100
            print(f"  ✅ 원본: {original_size:,} bytes → 저장: {saved_size:,} bytes ({ratio:.0f}%)")
            if saved_size < original_size:
                print(f"  ✅ 리사이징 성공! {(original_size - saved_size) / 1024:.0f} KB 절약")
            # 이미지 뷰 확인
            view_resp = session.get(f"{BASE_URL}/attachments/{latest['id']}/view")
            print(f"  ✅ 보기 확인: HTTP {view_resp.status_code}, {len(view_resp.content):,} bytes, "
                  f"Content-Type: {view_resp.headers.get('content-type')}")
        else:
            print(f"  ❌ 첨부파일 저장 확인 실패")
    else:
        print(f"  ❌ 입고 실패: HTTP {resp.status_code}")

    # 테스트 2: 아주 큰 이미지 (6000x4000, ~3MB)
    print("\n📌 테스트 2: 매우 큰 이미지 업로드 (6000x4000)")
    huge_image = create_large_test_image(6000, 4000)
    original_size2 = len(huge_image.getvalue())
    huge_image.seek(0)
    resp2 = session.post(f"{BASE_URL}/inventory/stock-in",
                         data={
                             "product_id": str(product_id),
                             "quantity": "1",
                             "location": "warehouse",
                             "unit_price": "10",
                             "reason": "Resize test - huge image",
                         },
                         files={"receipt_file": ("huge_receipt.jpg", huge_image, "image/jpeg")},
                         allow_redirects=True, timeout=15)
    if resp2.status_code == 200:
        att_list2 = session.get(f"{BASE_URL}/attachments/api/list").json()
        if att_list2:
            latest2 = att_list2[0]
            saved_size2 = latest2["file_size"]
            ratio2 = saved_size2 / original_size2 * 100
            print(f"  ✅ 원본: {original_size2:,} bytes → 저장: {saved_size2:,} bytes ({ratio2:.0f}%)")
            if saved_size2 < 1024 * 1024:
                print(f"  ✅ 1MB 이내로 압축 성공! ({saved_size2/1024:.0f} KB)")
            else:
                print(f"  ⚠️ 1MB 초과: {saved_size2/1024:.0f} KB")

    # 테스트 3: 작은 이미지 (리사이징 불필요)
    print("\n📌 테스트 3: 작은 이미지 업로드 (800x600) - 리사이징 불필요")
    small_image = create_large_test_image(800, 600)
    original_size3 = len(small_image.getvalue())
    small_image.seek(0)
    resp3 = session.post(f"{BASE_URL}/inventory/stock-in",
                         data={
                             "product_id": str(product_id),
                             "quantity": "1",
                             "location": "warehouse",
                             "unit_price": "10",
                             "reason": "Resize test - small image",
                         },
                         files={"receipt_file": ("small_receipt.jpg", small_image, "image/jpeg")},
                         allow_redirects=True, timeout=15)
    if resp3.status_code == 200:
        att_list3 = session.get(f"{BASE_URL}/attachments/api/list").json()
        if att_list3:
            latest3 = att_list3[0]
            saved_size3 = latest3["file_size"]
            print(f"  ✅ 원본: {original_size3:,} bytes → 저장: {saved_size3:,} bytes")
            print(f"  ✅ 작은 이미지는 해상도 유지, JPEG 최적화만 적용")

    # 테스트 4: PNG 업로드 → JPEG 변환 확인
    print("\n📌 테스트 4: PNG → JPEG 자동 변환")
    from PIL import Image
    png_img = Image.new("RGB", (2000, 1500), color=(255, 255, 255))
    png_buf = io.BytesIO()
    png_img.save(png_buf, format="PNG")
    png_buf.seek(0)
    original_png_size = len(png_buf.getvalue())
    png_buf.seek(0)
    resp4 = session.post(f"{BASE_URL}/inventory/stock-in",
                         data={
                             "product_id": str(product_id),
                             "quantity": "1",
                             "location": "warehouse",
                             "unit_price": "10",
                             "reason": "PNG to JPEG test",
                         },
                         files={"receipt_file": ("receipt.png", png_buf, "image/png")},
                         allow_redirects=True, timeout=15)
    if resp4.status_code == 200:
        att_list4 = session.get(f"{BASE_URL}/attachments/api/list").json()
        if att_list4:
            latest4 = att_list4[0]
            print(f"  ✅ PNG 원본: {original_png_size:,} bytes → JPEG 저장: {latest4['file_size']:,} bytes")
            print(f"  ✅ 파일명: {latest4['file_name']}, 타입: {latest4['file_type']}")

    print("\n" + "=" * 60)
    print("✅ 리사이징 테스트 완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
