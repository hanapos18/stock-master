# -*- coding: utf-8 -*-
"""백원 POS Firebird Bridge 웹훅 수신 테스트

StockMaster 웹 서버가 실행중인 상태에서 실행합니다.
Firebird DB 없이 웹훅 수신부만 테스트합니다.
"""
import json
import requests

BASE_URL = "http://localhost:5556"
API_KEY = "baekwon-bridge-key"
HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
}


def test_baekwon_products():
    """백원 POS 상품 마스터 수신 테스트."""
    print("=" * 50)
    print("  테스트 1: 백원 POS 상품 마스터 수신")
    print("=" * 50)

    payload = {
        "type": "baekwon_products",
        "source": "firebird_bridge",
        "store_code": "",
        "items": [
            {"code": "BW001", "name": "백원POS 테스트상품A", "sell_price": 5000},
            {"code": "BW002", "name": "백원POS 테스트상품B", "sell_price": 3000},
            {"code": "BW003", "name": "백원POS 테스트상품C", "sell_price": 8000},
        ],
    }

    resp = requests.post(f"{BASE_URL}/api/pos/webhook", json=payload, headers=HEADERS)
    print(f"  HTTP 상태: {resp.status_code}")
    try:
        data = resp.json()
        print(f"  응답: {json.dumps(data, ensure_ascii=False, indent=2)}")
        if resp.status_code == 200 and data.get("success"):
            print("  ✅ 상품 마스터 수신 성공")
        else:
            print(f"  ❌ 상품 마스터 수신 실패: {data.get('error', 'unknown')}")
    except Exception as e:
        print(f"  ❌ 응답 파싱 실패: {e}")
        print(f"  응답 본문: {resp.text[:200]}")
    print()


def test_baekwon_sale():
    """백원 POS 판매 데이터 수신 테스트."""
    print("=" * 50)
    print("  테스트 2: 백원 POS 판매 데이터 수신")
    print("=" * 50)

    payload = {
        "type": "baekwon_sale",
        "source": "firebird_bridge",
        "pos_no": 1,
        "store_code": "",
        "sale_date": "02112026",
        "receipt_no": 99901,
        "items": [
            {"menu_code": "BW001", "quantity": 2, "sale_amount": 10000, "sname": "CASH"},
            {"menu_code": "BW002", "quantity": 1, "sale_amount": 3000, "sname": "CASH"},
        ],
    }

    resp = requests.post(f"{BASE_URL}/api/pos/webhook", json=payload, headers=HEADERS)
    print(f"  HTTP 상태: {resp.status_code}")
    try:
        data = resp.json()
        print(f"  응답: {json.dumps(data, ensure_ascii=False, indent=2)}")
        if resp.status_code == 200 and data.get("success"):
            print("  ✅ 판매 데이터 수신 성공")
        else:
            print(f"  ❌ 판매 데이터 수신 실패: {data.get('error', 'unknown')}")
    except Exception as e:
        print(f"  ❌ 응답 파싱 실패: {e}")
        print(f"  응답 본문: {resp.text[:200]}")
    print()


def test_baekwon_sale_duplicate():
    """백원 POS 중복 영수증 스킵 테스트."""
    print("=" * 50)
    print("  테스트 3: 중복 영수증 스킵 테스트")
    print("=" * 50)

    payload = {
        "type": "baekwon_sale",
        "source": "firebird_bridge",
        "pos_no": 1,
        "store_code": "",
        "sale_date": "02112026",
        "receipt_no": 99901,
        "items": [
            {"menu_code": "BW001", "quantity": 2, "sale_amount": 10000, "sname": "CASH"},
        ],
    }

    resp = requests.post(f"{BASE_URL}/api/pos/webhook", json=payload, headers=HEADERS)
    print(f"  HTTP 상태: {resp.status_code}")
    try:
        data = resp.json()
        result = data.get("result", {})
        skipped = result.get("skipped", 0)
        print(f"  응답: {json.dumps(data, ensure_ascii=False, indent=2)}")
        if resp.status_code == 200 and skipped > 0:
            print("  ✅ 중복 영수증 정상 스킵됨")
        else:
            print("  ⚠️ 중복 체크 결과 확인 필요")
    except Exception as e:
        print(f"  ❌ 응답 파싱 실패: {e}")
    print()


def test_invalid_api_key():
    """잘못된 API Key 거부 테스트."""
    print("=" * 50)
    print("  테스트 4: 잘못된 API Key 거부")
    print("=" * 50)

    headers = {"Content-Type": "application/json", "X-API-Key": "wrong-key"}
    payload = {"type": "baekwon_sale", "items": []}

    resp = requests.post(f"{BASE_URL}/api/pos/webhook", json=payload, headers=headers)
    print(f"  HTTP 상태: {resp.status_code}")
    if resp.status_code == 401:
        print("  ✅ 잘못된 API Key 정상 거부됨")
    else:
        print(f"  ❌ 예상: 401, 실제: {resp.status_code}")
    print()


def test_baekwon_disabled():
    """백원 동기화 비활성화 테스트 (설정이 True일 때는 403이 아님)."""
    print("=" * 50)
    print("  테스트 5: 백원 동기화 상태 확인")
    print("=" * 50)

    payload = {
        "type": "baekwon_sale",
        "source": "firebird_bridge",
        "pos_no": 1,
        "sale_date": "02112026",
        "receipt_no": 99999,
        "items": [{"menu_code": "NOEXIST", "quantity": 1, "sale_amount": 0, "sname": "CASH"}],
    }

    resp = requests.post(f"{BASE_URL}/api/pos/webhook", json=payload, headers=HEADERS)
    print(f"  HTTP 상태: {resp.status_code}")
    if resp.status_code == 200:
        print("  ✅ 백원 동기화 활성 상태 확인")
    elif resp.status_code == 403:
        print("  ⚠️ 백원 동기화 비활성 상태 (BAEKWON_SYNC_ENABLED=false)")
    else:
        print(f"  ⚠️ 예상치 못한 상태: {resp.status_code}")
    print()


if __name__ == "__main__":
    print("\n🔶 백원 POS Firebird Bridge 웹훅 테스트")
    print(f"   서버: {BASE_URL}")
    print(f"   API Key: {API_KEY}")
    print()

    test_invalid_api_key()
    test_baekwon_products()
    test_baekwon_sale()
    test_baekwon_sale_duplicate()
    test_baekwon_disabled()

    print("=" * 50)
    print("  전체 테스트 완료")
    print("=" * 50)
