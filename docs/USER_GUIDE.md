# Hana StockMaster — 사용 가이드

> 식당 · 마트 통합 재고 관리 시스템  
> 버전: 2026-06-08 | 포트: 5556 (클라우드) / 5555 (로컬)

---

## 목차

1. [시스템 개요](#1-시스템-개요)
2. [접속 및 로그인](#2-접속-및-로그인)
3. [초기 설정](#3-초기-설정)
4. [상품(재고 품목) 관리](#4-상품재고-품목-관리)
5. [매입 품목(Purchase Variants)](#5-매입-품목purchase-variants)
6. [입고 (Stock-In)](#6-입고-stock-in)
7. [레시피 관리 (식당)](#7-레시피-관리-식당)
8. [재고 실사 (Stock Count)](#8-재고-실사-stock-count)
9. [매입 관리 (Purchase Orders)](#9-매입-관리-purchase-orders)
10. [도매 관리 (Wholesale)](#10-도매-관리-wholesale)
11. [소분/리패키징](#11-소분리패키징)
12. [매장 간 이동 (Transfer)](#12-매장-간-이동-transfer)
13. [판매 관리 (Sales)](#13-판매-관리-sales)
14. [보고서 (Reports)](#14-보고서-reports)
15. [POS 연동 (Webhook)](#15-pos-연동-webhook)
16. [환경 설정](#16-환경-설정)
17. [서버 운영](#17-서버-운영)

---

## 1. 시스템 개요

### 구조

```
[POS (hanapos_multitenant)] ──webhook──► [StockMaster (stock-master)]
       매출 발생 시                              재고 자동 차감
                                                 (식당: 레시피 기반)
                                                 (마트: 상품 직접 차감)
```

### 업종별 차이

| 기능 | 식당 (restaurant) | 마트 (mart) |
|---|---|---|
| 매출 차감 방식 | 레시피 기반 (BOM) | 상품 직접 차감 |
| 실사 방식 | 전체 상품 + 위치별 | 카테고리별 |
| 레시피 | 사용 | 미사용 |
| 도매 | 미사용 | 사용 |
| 소분(리패키징) | 사용 | 사용 |

### 핵심 개념

- **상품 (Product)**: 재고로 관리되는 단위 (예: 식용유 ml, 밀가루 g, 신라면 개)
- **매입 품목 (Purchase Variant)**: 실제 구매 형태 (예: 식용유 18L 통, 신라면 40개입 박스)
- **환산율 (Conversion Rate)**: 매입 1단위 = 재고 몇 base_unit (예: 1통 = 18000ml)
- **이동평균원가 (Moving Average Cost)**: 입고 시 자동 계산되는 단위당 평균 원가

---

## 2. 접속 및 로그인

### URL

| 환경 | URL |
|---|---|
| 로컬 개발 | `http://localhost:5555` |
| 클라우드 서버 | `http://http://211.188.58.193:5556` |

### 기본 계정

| 아이디 | 비밀번호 | 권한 |
|---|---|---|
| admin | admin123 | 관리자 (admin) |

### 권한 체계

| 역할 | 설명 |
|---|---|
| admin | 모든 기능 접근 가능, 사용자/사업장 관리 |
| manager | 대부분 기능 사용 가능, 사업장 설정 제외 |
| staff | 입출고, 실사, 판매 등 일상 업무만 |

---

## 3. 초기 설정

처음 사용 시 아래 순서로 설정합니다:

### 3.1 사업장 설정 (`/business`)

1. 사업장명, 업종(restaurant/mart), 대표자명 입력
2. 사업자번호, 주소, 연락처 입력
3. POS 연동 시: `pos_db_name` 설정

### 3.2 매장 추가 (`/business` → Stores)

1. 매장명 입력 (예: "본점", "강남점")
2. `store_number`: POS와 매칭되는 매장 번호 (예: "001")
3. 중앙 창고 여부 (`is_warehouse`) 체크

### 3.3 카테고리 등록 (`/categories`)

상품 분류를 위한 카테고리 생성:
- 식당 예: 양념류, 유지류, 곡물류, 육류, 채소류
- 마트 예: 라면/면류, 음료, 과자, 생활용품

### 3.4 거래처 등록 (`/suppliers`)

납품업체 정보 등록:
- 업체명, 담당자, 연락처
- 나중에 매입 품목에 연결

### 3.5 사용자 추가 (`/users`)

직원 계정 생성:
- 역할 지정 (admin/manager/staff)
- 소속 매장 지정 (NULL = 전체 매장 접근)

---

## 4. 상품(재고 품목) 관리

### 메뉴: `/products`

상품 = **재고의 최소 관리 단위**

### 등록 시 필수 항목

| 필드 | 설명 | 예시 |
|---|---|---|
| code | 상품 코드 (사업장 내 유니크) | OIL-001 |
| name | 상품명 | 식용유 |
| unit | 재고 단위 (base unit) | ml |
| category | 분류 | 유지류 |

### 등록 시 선택 항목

| 필드 | 설명 | 예시 |
|---|---|---|
| barcode | 바코드 (있으면 입력) | 8801234567890 |
| unit_price | 기본 매입가 | 2.0 (원/ml) |
| sell_price | 판매가 (마트용) | 3.5 |
| min_stock | 최소 재고 경고 | 5000 |
| max_stock | 최대 재고 경고 | 50000 |
| supplier | 주 거래처 | (주)해표 |
| storage_location | 보관 위치 | 창고 선반 A-3 |

### 식당 예시

| code | name | unit | 의미 |
|---|---|---|---|
| OIL-001 | 식용유 | ml | 밀리리터 단위로 관리 |
| FLOUR-001 | 밀가루 | g | 그램 단위 |
| SUGAR-001 | 설탕 | g | 그램 단위 |
| NOODLE-001 | 중면 | ea | 개 단위 (1인분=1ea) |
| PORK-001 | 돼지고기 삼겹살 | g | 그램 단위 |

### 마트 예시

| code | name | unit | 의미 |
|---|---|---|---|
| RAMEN-001 | 신라면 | ea | 개 단위 |
| WATER-001 | 삼다수 2L | ea | 개 단위 |
| TISSUE-001 | 화장지 | ea | 개 단위 |

---

## 5. 매입 품목(Purchase Variants)

### 메뉴: `/purchases/variants`

**핵심 개념: N:1 매핑**

하나의 재고 품목(Product)에 여러 매입 형태(Variant)를 등록할 수 있습니다.

```
식용유 18L 통     ─┐
식용유 500ml 병   ─┤──► 재고 품목: 식용유 (unit: ml)
식용유 1L PET    ─┘
```

### 등록 (`/purchases/variants/create`)

| 필드 | 설명 | 예시 |
|---|---|---|
| 재고 품목 | 연결할 stk_products | 식용유 |
| 매입 품목명 | 구매 시 상품명 | 해표 식용유 18L |
| 바코드 | 포장 바코드 | 8801007... |
| 매입 단위 | 구매 단위 | 통 |
| 환산율 | 1 매입단위 = 재고 몇 단위 | 18000 (1통=18000ml) |
| 거래처 | 주 납품업체 | (주)CJ제일제당 |

### 예시

| 매입 품목명 | 매입 단위 | 환산율 | → 재고 품목 (base unit) |
|---|---|---|---|
| 해표 식용유 18L | 통 | 18000 | 식용유 (ml) |
| 해표 식용유 500ml | 병 | 500 | 식용유 (ml) |
| 신라면 40개입 (수출용) | 박스 | 40 | 신라면 (ea) |
| 신라면 30개입 (내수용) | 박스 | 30 | 신라면 (ea) |
| 백설 밀가루 20kg | 포대 | 20000 | 밀가루 (g) |
| 백설 밀가루 1kg | 봉지 | 1000 | 밀가루 (g) |

---

## 6. 입고 (Stock-In)

### 빠른 입고: `/purchases/quick-stock-in`

일상적인 입고 처리에 사용합니다.

**사용 방법:**

1. **바코드 스캔** 또는 **매입 품목 검색**으로 품목 선택
2. **수량** 입력 (매입 단위 기준, 예: 2통)
3. **총 구매금액** 입력 (선택 — 입력 안 해도 됨)
4. **유통기한** 입력 (선택)
5. **Submit** → 자동으로:
   - 재고 수량 증가 (환산율 적용: 2통 × 18000 = +36,000ml)
   - 이동평균원가 갱신 (금액 입력 시)
   - 거래 이력(stk_transactions) 기록

### 이동평균원가 계산

```
새 평균원가 = (기존 총 장부가치 + 이번 구매금액) ÷ (기존 재고량 + 이번 입고량)
```

**예시:**
- 현재: 식용유 10,000ml, 평균원가 3.5원/ml → 장부가치 35,000원
- 입고: 18L 통 1개 = 36,000원
- 계산: (35,000 + 36,000) ÷ (10,000 + 18,000) = 71,000 ÷ 28,000 = **2.536원/ml**

### 금액 미입력 시

- 재고 수량만 증가
- 기존 평균원가 유지 (원가 왜곡 없음)
- 소규모 식당에서 가격 추적이 필요 없을 때 사용

---

## 7. 레시피 관리 (식당)

### 메뉴: `/recipes`

POS 메뉴 1개 판매 시 차감할 원재료를 정의합니다.

### 레시피 등록

1. **레시피명** = POS 메뉴명 (예: 짜장면)
2. **POS 메뉴 ID** = POS의 `menu_items.id` (연동용)
3. **원재료 추가**:

| 원재료 | 수량 | 단위 | 의미 |
|---|---|---|---|
| 중면 | 1 | ea | 면 1인분 |
| 식용유 | 30 | ml | 볶음용 |
| 춘장 | 50 | g | 소스 |
| 돼지고기 | 100 | g | 고기 |
| 양파 | 80 | g | 채소 |

### 원가 계산

레시피 원가 = 각 원재료의 (수량 × 이동평균원가) 합산

```
짜장면 원가:
  중면 1ea × 350원 = 350원
  식용유 30ml × 2.5원 = 75원
  춘장 50g × 8원 = 400원
  돼지고기 100g × 20원 = 2,000원
  양파 80g × 3원 = 240원
  ─────────────────────
  합계: 3,065원
```

### 매출 연동 (자동 차감)

POS에서 짜장면 2개 판매 → webhook → StockMaster:
- 중면 -2ea
- 식용유 -60ml
- 춘장 -100g
- 돼지고기 -200g
- 양파 -160g

---

## 8. 재고 실사 (Stock Count)

### 메뉴: `/stock-count`

실제 재고를 세어 시스템 재고와 비교 → 차이를 조정합니다.

### 식당: 위치별 실사 (권장)

식당은 주방(kitchen)과 창고(warehouse) 재고가 분리됩니다.

**워크플로우:**

```
Step 1. [New Count] → Location: Kitchen 선택 → Start
Step 2. 주방의 모든 재료를 세서 Actual 수량 입력 → Save
Step 3. [New Count] → Location: Warehouse 선택 → Start
Step 4. 창고의 모든 재료를 세서 Actual 수량 입력 → Save
Step 5. [Combined Review] → 합산 확인
Step 6. 차이가 있는 항목에 사유(Reason) 선택 → Approve All
```

### 합산 리뷰 (`/stock-count/combined-review`)

같은 날짜에 수행한 위치별 실사를 합산하여 확인합니다:

```
─────────────────────────────────────────────────────────────
상품      │ 단위 │ KITCHEN       │ WAREHOUSE     │ 합계  │ 차이
식용유    │ ml   │ 5000→3500     │ 18000→15000   │ 18500 │ -4500
밀가루    │ g    │ 2000→1200     │ 5000→3500     │ 4700  │ -2300
─────────────────────────────────────────────────────────────
```

### 조정 사유 (Reason)

| 코드 | 설명 | 사용 시점 |
|---|---|---|
| overuse | Over-use | 레시피보다 많이 사용 |
| spoilage | Spoilage | 폐기 (유통기한, 변질) |
| staff_meal | Staff Meal | 직원 식사 사용 |
| loss | Loss / Unknown | 원인 불명 손실 |
| measurement | Measurement Error | 측정/입력 오류 |
| unrecorded_in | Unrecorded Stock-In | 입고 기록 누락 (실제 > 전산) |
| other | Other | 기타 |

### 마트: 카테고리별 실사

마트는 상품이 많으므로 카테고리(선반) 단위로 실사합니다:
1. [Coverage Report]에서 미실시 카테고리 확인
2. 카테고리 선택 → 해당 카테고리 상품만 로드
3. 실사 수량 입력 → 승인

---

## 9. 매입 관리 (Purchase Orders)

### 메뉴: `/purchases`

정식 발주서 기반의 매입 프로세스입니다.

**워크플로우:**

```
Draft (작성) → Confirmed (발주 확정) → Received (입고 완료)
```

1. **발주서 작성**: 거래처 선택, 상품/수량/단가 입력
2. **발주 확정**: 업체에 발주
3. **입고 처리**: 실제 도착 시 확인 → 재고 반영

---

## 10. 도매 관리 (Wholesale)

### 메뉴: `/wholesale` (마트용)

다른 업체에 도매 판매할 때 사용합니다.

### 설정

1. **도매 거래처** 등록 (`/wholesale/clients`)
   - 기본 할인율 설정 가능
2. **업체별 개별 가격** 설정 (`/wholesale/pricing`)
   - 상품별 할인율 또는 고정가

### 도매 주문

```
Draft → Confirmed → Shipped → Delivered
```

- 주문 생성 시 거래처별 할인 자동 적용
- 출하(Shipped) 시 재고 자동 차감
- 결제 관리: 현금/수표/계좌이체/외상

---

## 11. 소분/리패키징

### 메뉴: `/repackaging`

대량 포장 → 소분 판매 시 사용합니다.

**예시:**
- 한우 앞다리 10kg → 500g 팩 × 18 + 로스 1kg
- 참기름 18L → 500ml 병 × 36

### 사용 방법

1. **규칙 등록**: 원재료(source) → 소분 상품(target) + 비율
2. **실행**: 원재료 출고 → 소분 상품 입고 (자동)

---

## 12. 매장 간 이동 (Transfer)

### 메뉴: `/transfers`

본점 ↔ 지점, 창고 → 매장 간 재고 이동입니다.

**워크플로우:**

```
Pending (요청) → Shipped (출고) → Received (입고 확인)
```

- 출고 매장: 재고 감소 (transfer_out)
- 입고 매장: 재고 증가 (transfer_in)
- 수량 차이 발생 시 자동 조정

---

## 13. 판매 관리 (Sales)

### 메뉴: `/sales`

POS 없이 StockMaster에서 직접 판매를 기록할 때 사용합니다.

- 판매 전표 작성 → 확정 → 재고 자동 차감
- 도매 거래처 연결 시 할인 자동 적용

---

## 14. 보고서 (Reports)

### 메뉴: `/reports`

| 보고서 | 내용 |
|---|---|
| 재고 현황 | 전 상품 현재 재고, 금액 |
| 입출고 내역 | 기간별 거래 이력 |
| 재고 부족 경고 | min_stock 이하 상품 |
| 카테고리별 요약 | 카테고리별 재고 가치 |

---

## 15. POS 연동 (Webhook)

### 엔드포인트: `/pos-sync/webhook`

HANAPOS(hanapos_multitenant)에서 매출/상품/직원 데이터를 받습니다.

### 인증

```
Header: X-API-Key: {POS_API_KEY}
```

### 지원 이벤트

| event_type | 동작 |
|---|---|
| sale | 매출 → 재고 차감 (식당: 레시피, 마트: 직접) |
| stock_in | 입고 알림 → 재고 증가 |
| product_sync | POS 상품 → StockMaster 동기화 |
| store_sync | POS 매장 → StockMaster 동기화 |
| employee_sync | POS 직원 → StockMaster 사용자 동기화 |
| loss | 로스 보고 → 재고 감소 |

### Webhook 요청 예시 (sale)

```json
{
  "event_type": "sale",
  "store_number": "001",
  "data": {
    "receipt_number": "20260608-001-0001",
    "items": [
      {"menu_id": 15, "name": "짜장면", "quantity": 2, "price": 8000}
    ]
  }
}
```

---

## 16. 환경 설정

### `.env` 파일

```dotenv
# 데이터베이스
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=yourpassword
DB_NAME=stock_master
POS_DB_NAME=order_sys

# 앱 설정
SECRET_KEY=your-random-secret-key-here
APP_PORT=5555
APP_DEBUG=true

# POS 연동
POS_API_KEY=your-pos-api-key

# 프린터 (선택)
PRINTER_IP=192.168.0.100
PRINTER_PORT=9100
PRINTER_WIDTH=40
PRINTER_ENCODING=euc-kr
```

### 데이터베이스 초기화

```bash
mysql -u root -p < database/schema.sql
```

### 마이그레이션 적용

```bash
mysql -u root -p stock_master < database/migrate_purchase_variants.sql
mysql -u root -p stock_master < database/migrate_stock_count_location.sql
```

---

## 17. 서버 운영

### 클라우드 서버 (49.50.136.21)

| 항목 | 값 |
|---|---|
| 경로 | `/root/stock_master` |
| 서비스명 | `stockmaster.service` |
| 포트 | 5556 |
| WSGI | Gunicorn (2 workers) |

### 주요 명령어

```bash
# 서비스 관리
systemctl status stockmaster
systemctl restart stockmaster
systemctl stop stockmaster

# 로그 확인
journalctl -u stockmaster -n 50 --no-pager
tail -f /root/stock_master/error.log
tail -f /root/stock_master/access.log

# 코드 업데이트
cd /root/stock_master
git pull origin main
systemctl restart stockmaster
```

### 로컬 개발 (Windows)

```powershell
cd C:\Dev\stock-master
python run_stockmaster.py
```

---

## URL 전체 목록

| 경로 | 기능 |
|---|---|
| `/` | 대시보드 |
| `/login` | 로그인 |
| `/business` | 사업장/매장 설정 |
| `/users` | 사용자 관리 |
| `/categories` | 카테고리 관리 |
| `/suppliers` | 거래처 관리 |
| `/products` | 상품(재고 품목) 관리 |
| `/purchases` | 매입 관리 (발주서) |
| `/purchases/variants` | 매입 품목 관리 (N:1) |
| `/purchases/quick-stock-in` | 빠른 입고 |
| `/inventory` | 재고 현황 |
| `/recipes` | 레시피 관리 (식당) |
| `/stock-count` | 재고 실사 |
| `/stock-count/combined-review` | 합산 리뷰 (위치별 실사) |
| `/stock-count/coverage` | 커버리지 보고 (마트) |
| `/wholesale` | 도매 관리 |
| `/wholesale/clients` | 도매 거래처 |
| `/repackaging` | 소분/리패키징 |
| `/transfers` | 매장 간 이동 |
| `/sales` | 판매 관리 |
| `/reports` | 보고서 |
| `/pos-sync/webhook` | POS Webhook |
| `/help` | 도움말 |

---

## 자주 묻는 질문 (FAQ)

### Q: 바코드가 없는 원재료는 어떻게 입고하나요?

A: 매입 품목(Purchase Variant) 등록 시 바코드는 선택 사항입니다. 바코드 없이도 매입 품목명으로 검색하여 입고할 수 있습니다.

### Q: 같은 상품을 다른 크기로 구매했는데 원가는 어떻게 되나요?

A: 매입 품목별로 환산율이 다르므로, 모든 구매는 base unit으로 변환되어 이동평균원가가 자동 계산됩니다.
- 18L 통 구매: 36,000원 ÷ 18,000ml = 2원/ml
- 500ml 병 구매: 2,500원 ÷ 500ml = 5원/ml
- 이동평균으로 혼합: 현재 재고량과 장부가치 기준으로 새 평균 산출

### Q: 입고 시 가격을 입력 안 하면 어떻게 되나요?

A: 재고 수량만 증가하고, 기존 평균원가는 그대로 유지됩니다. 원가 추적이 필요 없는 소규모 매장에 적합합니다.

### Q: 실사에서 차이가 나면 원가도 바뀌나요?

A: 승인(Approve) 시 재고량이 조정되며, `total_stock_value`가 현재 `avg_unit_cost × 실제수량`으로 재계산됩니다. 단위당 원가는 변하지 않습니다.

### Q: 주방과 창고를 구분하지 않고 실사할 수 있나요?

A: 네. 실사 생성 시 Location을 선택하지 않으면 전체 합산 방식으로 작동합니다 (기존 방식 호환).
