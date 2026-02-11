-- ============================================
-- Migration: Repackaging 1:1 → 1:N 지원
-- 기존 데이터를 stk_repackaging_targets로 이전
-- ============================================

-- 1. name 컬럼 추가, 기존 컬럼 NULL 허용
ALTER TABLE stk_repackaging
  ADD COLUMN IF NOT EXISTS name VARCHAR(100) DEFAULT NULL COMMENT 'rule name'
  AFTER business_id;

ALTER TABLE stk_repackaging MODIFY COLUMN target_product_id INT DEFAULT NULL;
ALTER TABLE stk_repackaging MODIFY COLUMN ratio DECIMAL(10,4) DEFAULT NULL;

-- 2. targets 자식 테이블 생성
CREATE TABLE IF NOT EXISTS stk_repackaging_targets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    repackaging_id INT NOT NULL,
    target_product_id INT NOT NULL COMMENT 'target product (split)',
    ratio DECIMAL(10,4) NOT NULL COMMENT 'qty per 1 source unit',
    FOREIGN KEY (repackaging_id) REFERENCES stk_repackaging(id) ON DELETE CASCADE,
    FOREIGN KEY (target_product_id) REFERENCES stk_products(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 3. 기존 1:1 데이터를 targets 테이블로 이전
INSERT INTO stk_repackaging_targets (repackaging_id, target_product_id, ratio)
SELECT id, target_product_id, ratio
FROM stk_repackaging
WHERE target_product_id IS NOT NULL
  AND id NOT IN (SELECT repackaging_id FROM stk_repackaging_targets);

-- 4. 기존 규칙에 이름 자동 생성
UPDATE stk_repackaging r
JOIN stk_products sp ON r.source_product_id = sp.id
SET r.name = CONCAT(sp.name, ' 소분')
WHERE r.name IS NULL;

-- Done!
SELECT 'Migration complete: repackaging 1:N support added' AS result;
