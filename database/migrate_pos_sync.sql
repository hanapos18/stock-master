-- POS 연동을 위한 마이그레이션
-- 1) 상품코드 M 접두어 제거 (mcode 그대로 사용)
UPDATE stk_products SET code = SUBSTRING(code, 2) WHERE code LIKE 'M%';

-- 2) POS 동기화 로그 테이블
CREATE TABLE IF NOT EXISTS stk_pos_sync_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    pos_table VARCHAR(50) NOT NULL COMMENT 'sale_items or stock_transactions',
    pos_last_id INT NOT NULL DEFAULT 0 COMMENT 'last synced POS record id',
    synced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    record_count INT DEFAULT 0 COMMENT 'records synced in this batch',
    FOREIGN KEY (business_id) REFERENCES stk_businesses(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 3) POS 동기화 상세 로그 (개별 건 추적)
CREATE TABLE IF NOT EXISTS stk_pos_sync_detail (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    pos_table VARCHAR(50) NOT NULL,
    pos_record_id INT NOT NULL,
    sync_type VARCHAR(20) NOT NULL COMMENT 'sale, stock_in, loss',
    menu_code VARCHAR(50),
    quantity DECIMAL(10,2),
    status VARCHAR(20) DEFAULT 'success' COMMENT 'success, skipped, error',
    error_message TEXT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_pos_record (pos_table, pos_record_id),
    INDEX idx_business_date (business_id, created_at)
) ENGINE=InnoDB;
