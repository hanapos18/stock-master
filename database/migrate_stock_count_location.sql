-- ============================================
-- 실사 위치별 분리 마이그레이션
-- stk_stock_counts에 location 컬럼 추가
-- 실행: mysql -u root -p stock_master < migrate_stock_count_location.sql
-- ============================================
USE stock_master;

-- ── 1. stk_stock_counts에 location 컬럼 추가 ──
-- 실사 시 위치 지정 (kitchen, warehouse, etc.)
-- NULL이면 전체 위치 합산 (기존 데이터 호환)
ALTER TABLE stk_stock_counts
    ADD COLUMN location VARCHAR(50) NULL DEFAULT NULL
    COMMENT '실사 위치 (kitchen, warehouse, NULL=전체)' AFTER store_id;

-- ── 2. 같은 날짜+매장의 위치별 실사를 묶기 위한 인덱스 ──
ALTER TABLE stk_stock_counts
    ADD INDEX idx_date_store_location (count_date, store_id, location);

-- ── 3. stk_inventory의 location 기본값 정리 ──
-- 기존 데이터 중 location이 비어있는 행을 'warehouse'로 통일
UPDATE stk_inventory SET location = 'warehouse'
WHERE location IS NULL OR location = '';
