-- Support Request System 마이그레이션
-- POS에서 소모품 주문/A/S 요청을 접수받는 시스템

-- 1) 접수 기록 테이블
CREATE TABLE IF NOT EXISTS stk_support_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    store_code VARCHAR(20) NOT NULL COMMENT 'POS 매장코드',
    store_name VARCHAR(100) DEFAULT '' COMMENT '매장명',
    terminal_id VARCHAR(20) DEFAULT '' COMMENT 'POS 터미널 ID',
    request_type ENUM('ORDER','AS') NOT NULL COMMENT '주문 또는 A/S',
    items JSON COMMENT '주문 품목 또는 장비 정보',
    memo TEXT COMMENT '요청 메모/증상 설명',
    status ENUM('PENDING','PROCESSING','DONE','REJECTED') DEFAULT 'PENDING',
    admin_note TEXT COMMENT '관리자 메모',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_store (store_code),
    INDEX idx_status (status),
    INDEX idx_created (created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2) 소모품 카탈로그 (공급사가 관리, POS에서 조회)
CREATE TABLE IF NOT EXISTS stk_support_catalog (
    id INT AUTO_INCREMENT PRIMARY KEY,
    category ENUM('PAPER','RIBBON','PART','OTHER') NOT NULL DEFAULT 'OTHER',
    name VARCHAR(100) NOT NULL COMMENT '상품명',
    description VARCHAR(500) DEFAULT '' COMMENT '상품 설명',
    unit_price DECIMAL(10,2) DEFAULT 0 COMMENT '단가',
    image_url VARCHAR(500) DEFAULT '' COMMENT '상품 이미지 URL',
    is_active TINYINT(1) DEFAULT 1,
    sort_order INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_active_sort (is_active, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3) 자가해결 유튜브 동영상 (공급사가 관리, POS A/S 페이지에 표시)
CREATE TABLE IF NOT EXISTS stk_support_videos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    category ENUM('PRINTER','POS','MONITOR','DRAWER','NETWORK','OTHER') NOT NULL DEFAULT 'OTHER',
    title VARCHAR(200) NOT NULL COMMENT '동영상 제목',
    youtube_url VARCHAR(500) NOT NULL COMMENT '유튜브 URL',
    description VARCHAR(500) DEFAULT '' COMMENT '설명',
    sort_order INT DEFAULT 0,
    is_active TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_active_sort (is_active, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4) 해결 기록 컬럼 (육하원칙 5W1H)
ALTER TABLE stk_support_requests
    ADD COLUMN IF NOT EXISTS resolved_by VARCHAR(100) DEFAULT NULL COMMENT '누가 해결',
    ADD COLUMN IF NOT EXISTS resolved_at DATETIME DEFAULT NULL COMMENT '언제 해결',
    ADD COLUMN IF NOT EXISTS resolution_location VARCHAR(100) DEFAULT NULL COMMENT '어디서 (현장/원격/방문)',
    ADD COLUMN IF NOT EXISTS root_cause TEXT DEFAULT NULL COMMENT '왜 (원인)',
    ADD COLUMN IF NOT EXISTS resolution TEXT DEFAULT NULL COMMENT '어떻게 (해결방법)',
    ADD COLUMN IF NOT EXISTS parts_used TEXT DEFAULT NULL COMMENT '무엇을 (사용부품/자재)';

-- 초기 카탈로그 샘플 데이터
INSERT INTO stk_support_catalog (category, name, description, unit_price, sort_order) VALUES
('PAPER', 'Thermal Paper 57mm (50 rolls)', 'Standard receipt paper for 57mm printers', 850.00, 1),
('PAPER', 'Thermal Paper 80mm (50 rolls)', 'Standard receipt paper for 80mm printers', 1200.00, 2),
('RIBBON', 'Ribbon Cartridge (Black)', 'Compatible ribbon for dot-matrix printers', 350.00, 3),
('PART', 'Cash Drawer Key (Spare)', 'Replacement key for standard cash drawer', 150.00, 4),
('PART', 'Barcode Scanner Cable (USB)', 'Replacement USB cable for barcode scanner', 250.00, 5);

-- 초기 유튜브 동영상 샘플 데이터
INSERT INTO stk_support_videos (category, title, youtube_url, description, sort_order) VALUES
('PRINTER', 'Receipt Printer Paper Jam Fix', 'https://www.youtube.com/watch?v=example1', 'How to clear paper jam on thermal printer', 1),
('PRINTER', 'Printer Not Printing - Troubleshoot', 'https://www.youtube.com/watch?v=example2', 'Check connections, driver, and settings', 2),
('NETWORK', 'POS Network Connection Issue', 'https://www.youtube.com/watch?v=example3', 'Resolve common network problems between POS devices', 3),
('DRAWER', 'Cash Drawer Not Opening', 'https://www.youtube.com/watch?v=example4', 'Manual release and cable check guide', 4);
