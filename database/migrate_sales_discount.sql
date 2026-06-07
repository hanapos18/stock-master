-- ============================================
-- Sales 거래처 할인 기능 추가
-- stk_sales 테이블에 client_id, discount 컬럼 추가
-- ============================================

ALTER TABLE stk_sales
    ADD COLUMN client_id INT NULL AFTER customer_name,
    ADD COLUMN discount_rate DECIMAL(5,2) DEFAULT 0 AFTER total_amount,
    ADD COLUMN discount_amount DECIMAL(16,6) DEFAULT 0 AFTER discount_rate,
    ADD COLUMN final_amount DECIMAL(16,6) DEFAULT 0 AFTER discount_amount,
    ADD FOREIGN KEY fk_sales_client (client_id) REFERENCES stk_wholesale_clients(id) ON DELETE SET NULL;

-- 기존 데이터: final_amount = total_amount (할인 없음)
UPDATE stk_sales SET final_amount = total_amount WHERE final_amount = 0 AND total_amount > 0;
