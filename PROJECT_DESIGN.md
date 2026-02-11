# StockMaster - 재고 관리 시스템

식당과 마트를 위한 통합 재고 관리 시스템

## 📋 프로젝트 정보

- **프로젝트명**: StockMaster
- **대상**: 식당, 마트 사업자
- **개발 환경**: Windows 11
- **개발 기간**: 3개월 (MVP)

## 🎯 핵심 목표

1. 정확한 재고 파악 (창고/매장/주방 분리)
2. 실시간 재고 현황
3. 자동 발주 제안
4. 유통기한 관리
5. 간편한 입출고 처리

## 🏗️ 기술 스택

### Backend
- **Framework**: NestJS 10.x
- **Language**: TypeScript 5.x
- **Database**: PostgreSQL 15.x
- **ORM**: TypeORM
- **Auth**: JWT + Passport
- **Validation**: class-validator

### Frontend (향후)
- **Framework**: React 18.x + TypeScript
- **UI Library**: Ant Design
- **State**: Zustand
- **API**: Axios

### DevOps
- **Package Manager**: npm
- **Testing**: Jest
- **Linter**: ESLint
- **Formatter**: Prettier

## 📐 데이터베이스 설계

### 핵심 엔티티

#### 1. Business (사업장)
```
- id (UUID, PK)
- name (사업장명)
- type (restaurant | mart)
- owner_name (대표자명)
- business_number (사업자번호)
- address (주소)
- phone (전화번호)
- created_at
```

#### 2. Product (상품/식자재)
```
- id (UUID, PK)
- business_id (FK)
- category_id (FK)
- code (상품코드, unique)
- barcode (바코드)
- name (상품명)
- description (설명)
- unit (단위: kg, ea, box 등)
- unit_price (단가)
- min_stock (최소 재고)
- max_stock (최대 재고)
- supplier_id (FK)
- is_active (활성 여부)
- created_at
- updated_at
```

#### 3. Inventory (재고)
```
- id (UUID, PK)
- product_id (FK)
- location (창고 위치)
- quantity (수량)
- expiry_date (유통기한)
- batch_number (로트번호)
- last_updated
```

#### 4. Transaction (입출고 내역)
```
- id (UUID, PK)
- product_id (FK)
- type (in | out | adjust | discard | move)
- from_location (출발지)
- to_location (도착지)
- quantity (수량)
- unit_price (단가)
- total_amount (총액)
- reason (사유)
- user_id (FK)
- created_at
```

#### 5. Supplier (거래처)
```
- id (UUID, PK)
- business_id (FK)
- name (거래처명)
- contact_person (담당자)
- phone (전화번호)
- email (이메일)
- address (주소)
- created_at
```

#### 6. Order (발주)
```
- id (UUID, PK)
- business_id (FK)
- supplier_id (FK)
- order_number (발주번호)
- order_date (발주일)
- expected_date (입고예정일)
- status (pending | ordered | received | cancelled)
- total_amount (총액)
- memo (메모)
- created_by (FK)
- created_at
```

#### 7. OrderItem (발주 상세)
```
- id (UUID, PK)
- order_id (FK)
- product_id (FK)
- quantity (수량)
- unit_price (단가)
- amount (금액)
```

#### 8. Category (카테고리)
```
- id (UUID, PK)
- business_id (FK)
- name (카테고리명)
- parent_id (FK, 상위 카테고리)
- display_order (표시 순서)
```

#### 9. User (사용자)
```
- id (UUID, PK)
- business_id (FK)
- username (로그인 ID)
- password (해시)
- name (이름)
- role (admin | manager | staff)
- is_active (활성 여부)
- created_at
```

## 🎯 주요 기능

### Phase 1: 기본 재고 관리
- [ ] 상품 CRUD
- [ ] 재고 입출고
- [ ] 재고 현황 조회
- [ ] 위치별 재고 관리

### Phase 2: 알림 & 리포트
- [ ] 최소 재고 알림
- [ ] 유통기한 알림
- [ ] 일일 재고 리포트
- [ ] 엑셀 내보내기

### Phase 3: 발주 관리
- [ ] 거래처 관리
- [ ] 발주서 생성
- [ ] 자동 발주 제안
- [ ] 입고 처리

### Phase 4: 고급 기능
- [ ] ABC 분석
- [ ] 재고 회전율
- [ ] 원가/수익 분석
- [ ] 바코드 스캔

## 📂 프로젝트 구조

```
stock-master/
├── src/
│   ├── main.ts
│   ├── app.module.ts
│   │
│   ├── core/                    # 핵심 기능
│   │   ├── filters/
│   │   ├── guards/
│   │   ├── interceptors/
│   │   └── middleware/
│   │
│   ├── shared/                  # 공유 모듈
│   │   ├── database/
│   │   ├── config/
│   │   └── utils/
│   │
│   └── modules/
│       ├── auth/               # 인증
│       ├── businesses/         # 사업장
│       ├── products/           # 상품
│       ├── inventory/          # 재고
│       ├── transactions/       # 입출고
│       ├── orders/             # 발주
│       ├── suppliers/          # 거래처
│       ├── categories/         # 카테고리
│       └── reports/            # 리포트
│
├── test/
├── package.json
├── tsconfig.json
├── .env
└── README.md
```

## 🔐 보안

- JWT 토큰 인증
- bcrypt 비밀번호 해싱
- CORS 설정
- Rate limiting
- SQL Injection 방어 (TypeORM)

## 📊 성능

- 데이터베이스 인덱싱
- 쿼리 최적화
- 페이지네이션
- 캐싱 (Redis, 향후)

## 🧪 테스트

- Unit Tests (Jest)
- Integration Tests
- E2E Tests
- 커버리지 80% 이상 목표

## 📝 개발 원칙

- Clean Code
- SOLID 원칙
- DDD (Domain-Driven Design)
- 작은 함수/클래스
- 타입 안정성
