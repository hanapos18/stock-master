-- =============================================
-- 사용자 소속 매장 마이그레이션
-- store_id = NULL → 전체 매장 접근 (본점/관리자)
-- store_id = X   → 해당 지점만 접근
-- =============================================

-- 1) stk_users에 store_id 컬럼 추가
ALTER TABLE stk_users
  ADD COLUMN store_id INT NULL DEFAULT NULL AFTER role,
  ADD CONSTRAINT fk_users_store FOREIGN KEY (store_id) REFERENCES stk_stores(id) ON DELETE SET NULL;

-- 2) 기존 admin 사용자는 store_id = NULL (전체 접근) 유지
-- 별도 작업 불필요 (DEFAULT NULL)
