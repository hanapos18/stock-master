-- ============================================
-- 매장 간 이동(Inter-Store Transfer) 마이그레이션
-- ============================================

-- 1. stk_stores에 is_warehouse 컬럼 추가
ALTER TABLE stk_stores ADD COLUMN IF NOT EXISTS is_warehouse TINYINT(1) DEFAULT 0;

-- 2. stk_transactions type ENUM 확장 (transfer_out, transfer_in 추가)
ALTER TABLE stk_transactions
  MODIFY COLUMN type ENUM('in','out','adjust','discard','move','sale','transfer_out','transfer_in') NOT NULL;

-- 3. 매장 간 이동 요청 테이블
CREATE TABLE IF NOT EXISTS stk_transfers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    from_store_id INT NOT NULL,
    to_store_id INT NOT NULL,
    status ENUM('pending','shipped','received','cancelled') DEFAULT 'pending',
    requested_by INT NULL,
    shipped_by INT NULL,
    received_by INT NULL,
    shipped_at DATETIME NULL,
    received_at DATETIME NULL,
    memo TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES stk_businesses(id),
    FOREIGN KEY (from_store_id) REFERENCES stk_stores(id),
    FOREIGN KEY (to_store_id) REFERENCES stk_stores(id)
) ENGINE=InnoDB;

-- 4. 이동 품목 상세 테이블
CREATE TABLE IF NOT EXISTS stk_transfer_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    transfer_id INT NOT NULL,
    product_id INT NOT NULL,
    inventory_id INT NULL COMMENT 'source lot inventory ID',
    quantity DECIMAL(10,4) NOT NULL,
    received_quantity DECIMAL(10,4) NULL COMMENT 'actual received qty (NULL = same as quantity)',
    expiry_date DATE NULL,
    location VARCHAR(50) DEFAULT 'warehouse',
    FOREIGN KEY (transfer_id) REFERENCES stk_transfers(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES stk_products(id)
) ENGINE=InnoDB;
