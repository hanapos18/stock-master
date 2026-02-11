-- ============================================
-- Migration: stk_attachments 테이블 생성
-- 영수증/배송원장 사진 업로드 기능
-- ============================================
USE stock_master;

CREATE TABLE IF NOT EXISTS stk_attachments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    reference_type VARCHAR(50) NOT NULL COMMENT 'transaction / purchase',
    reference_id INT NOT NULL COMMENT 'stk_transactions.id or stk_purchases.id',
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(100) NOT NULL COMMENT 'MIME type',
    file_size INT NOT NULL COMMENT 'bytes',
    file_data LONGBLOB NOT NULL,
    memo VARCHAR(255),
    uploaded_by INT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES stk_businesses(id) ON DELETE CASCADE,
    INDEX idx_ref (reference_type, reference_id)
) ENGINE=InnoDB;
