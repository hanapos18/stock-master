-- migrate_store_number.sql
-- stk_stores에 POS store_number 매핑 컬럼 추가
-- 실행: mysql -u root -p stock_master < database/migrate_store_number.sql

ALTER TABLE stk_stores
  ADD COLUMN store_number VARCHAR(20) NULL COMMENT 'POS store_number 매핑 (예: 001, 002)' AFTER name;

ALTER TABLE stk_stores
  ADD UNIQUE KEY uq_business_store_number (business_id, store_number);
