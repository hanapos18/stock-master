-- ============================================
-- 도매 결제/잔금 관리 마이그레이션
-- ============================================

-- 1. stk_wholesale_orders에 결제 관련 컬럼 추가
ALTER TABLE stk_wholesale_orders
  ADD COLUMN IF NOT EXISTS paid_amount DECIMAL(16,6) DEFAULT 0 COMMENT 'total paid so far',
  ADD COLUMN IF NOT EXISTS payment_status ENUM('unpaid','partial','paid') DEFAULT 'unpaid';

-- 2. 결제 내역 테이블
CREATE TABLE IF NOT EXISTS stk_wholesale_payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    business_id INT NOT NULL,
    client_id INT NOT NULL,
    payment_method ENUM('cash','check','bank_transfer','credit') NOT NULL,
    amount DECIMAL(16,6) NOT NULL,
    check_date DATE NULL COMMENT 'check maturity date',
    check_number VARCHAR(50) NULL,
    bank_name VARCHAR(50) NULL,
    bank_ref VARCHAR(100) NULL COMMENT 'bank transfer reference',
    memo TEXT,
    paid_by INT NULL,
    paid_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES stk_wholesale_orders(id) ON DELETE CASCADE,
    FOREIGN KEY (business_id) REFERENCES stk_businesses(id),
    FOREIGN KEY (client_id) REFERENCES stk_wholesale_clients(id)
) ENGINE=InnoDB;
