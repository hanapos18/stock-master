-- ============================================
-- 매입 품목 마스터 (Purchase Variants) 마이그레이션
-- 전 업종 공통: 마트/식당 모두 N:1 구조 지원
-- 실행: mysql -u root -p stock_master < migrate_purchase_variants.sql
-- ============================================
USE stock_master;

-- ── 1. stk_purchase_variants (매입 품목 마스터) ──
-- 실제 시장에서 구매하는 단위(바코드 포장 형태)를 관리
-- 여러 매입 품목이 하나의 재고 품목(stk_products)으로 환산됨
CREATE TABLE IF NOT EXISTS stk_purchase_variants (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    product_id INT NOT NULL COMMENT 'FK → stk_products (재고 품목)',
    name VARCHAR(150) NOT NULL COMMENT '매입 품목명 (예: 해표 식용유 18L, 신라면 40입 수출용)',
    barcode VARCHAR(100) NULL COMMENT '바코드 (없을 수 있음)',
    purchase_unit VARCHAR(30) NOT NULL DEFAULT 'ea' COMMENT '매입 단위 (통, 박스, 포대, 봉지...)',
    conversion_rate DECIMAL(12,4) NOT NULL DEFAULT 1 COMMENT '1 매입단위 = 재고품목 몇 base_unit',
    supplier_id INT NULL COMMENT '주 거래처',
    last_purchase_price DECIMAL(16,6) NULL COMMENT '최근 매입가 (매입단위 기준)',
    is_active TINYINT(1) DEFAULT 1,
    memo TEXT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES stk_businesses(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES stk_products(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES stk_suppliers(id) ON DELETE SET NULL,
    INDEX idx_barcode (barcode),
    INDEX idx_product (product_id),
    INDEX idx_business_active (business_id, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── 2. stk_products에 이동평균원가 컬럼 추가 ──
-- 입고 시마다 갱신되는 base_unit 1개당 평균 원가
ALTER TABLE stk_products
    ADD COLUMN avg_unit_cost DECIMAL(16,6) NOT NULL DEFAULT 0
    COMMENT '이동평균원가 (base_unit 1개당)' AFTER unit_price;

-- ── 3. stk_products에 total_stock_value 컬럼 추가 ──
-- 현재 재고의 총 장부 가치 (avg_unit_cost * 총 재고량)
-- 이동평균 계산 시 (기존가치 + 신규가치) / (기존수량 + 신규수량) 에 사용
ALTER TABLE stk_products
    ADD COLUMN total_stock_value DECIMAL(16,6) NOT NULL DEFAULT 0
    COMMENT '현재 재고 총 장부가치 (이동평균 계산용)' AFTER avg_unit_cost;
