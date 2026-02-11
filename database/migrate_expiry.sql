-- ============================================
-- Migration: 유통기한(Expiry Date) 관리 지원
-- ============================================

-- 1. stk_purchase_items에 expiry_date 추가
ALTER TABLE stk_purchase_items
  ADD COLUMN IF NOT EXISTS expiry_date DATE NULL COMMENT 'expiry date for this lot'
  AFTER amount;

-- 2. stk_inventory에 UNIQUE 인덱스 (product + store + location + expiry_date)
--    같은 상품의 유통기한별 로트 구분을 위해 필요
--    NULL expiry_date도 별도 행으로 관리
ALTER TABLE stk_inventory
  ADD UNIQUE INDEX IF NOT EXISTS uk_inv_lot (product_id, store_id, location, expiry_date);

-- Done!
SELECT 'Migration complete: expiry date support added' AS result;
