-- ============================================
-- StockMaster Database Schema
-- MariaDB / MySQL
-- ============================================
CREATE DATABASE IF NOT EXISTS stock_master
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE stock_master;

-- ── 사업장 ──
CREATE TABLE IF NOT EXISTS stk_businesses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    type ENUM('restaurant','mart') NOT NULL DEFAULT 'restaurant',
    owner_name VARCHAR(100),
    business_number VARCHAR(20),
    address TEXT,
    phone VARCHAR(20),
    memo TEXT,
    is_active TINYINT(1) DEFAULT 1,
    pos_db_name VARCHAR(100) NULL COMMENT 'POS DB name (order_sys etc), NULL if no POS',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ── 매장 ──
CREATE TABLE IF NOT EXISTS stk_stores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    address TEXT,
    phone VARCHAR(20),
    is_active TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES stk_businesses(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── 사용자 ──
CREATE TABLE IF NOT EXISTS stk_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    role ENUM('admin','manager','staff') DEFAULT 'staff',
    is_active TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES stk_businesses(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── 카테고리 ──
CREATE TABLE IF NOT EXISTS stk_categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    parent_id INT NULL,
    display_order INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES stk_businesses(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES stk_categories(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ── 거래처 (납품업체) ──
CREATE TABLE IF NOT EXISTS stk_suppliers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    contact_person VARCHAR(100),
    phone VARCHAR(20),
    email VARCHAR(100),
    address TEXT,
    memo TEXT,
    is_active TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES stk_businesses(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── 상품 / 식자재 ──
CREATE TABLE IF NOT EXISTS stk_products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    category_id INT NULL,
    supplier_id INT NULL,
    code VARCHAR(50) NOT NULL,
    barcode VARCHAR(100),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    storage_location VARCHAR(200) NULL COMMENT 'physical storage location',
    unit VARCHAR(20) DEFAULT 'ea',
    unit_price DECIMAL(16,6) DEFAULT 0 COMMENT 'buy price',
    sell_price DECIMAL(16,6) DEFAULT 0 COMMENT 'sell price',
    min_stock DECIMAL(10,2) DEFAULT 0,
    max_stock DECIMAL(10,2) NULL,
    is_active TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES stk_businesses(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES stk_categories(id) ON DELETE SET NULL,
    FOREIGN KEY (supplier_id) REFERENCES stk_suppliers(id) ON DELETE SET NULL,
    UNIQUE KEY uk_business_code (business_id, code)
) ENGINE=InnoDB;

-- ── 재고 현황 ──
CREATE TABLE IF NOT EXISTS stk_inventory (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    store_id INT NOT NULL,
    location VARCHAR(50) DEFAULT 'warehouse',
    quantity DECIMAL(10,4) DEFAULT 0,
    expiry_date DATE NULL,
    batch_number VARCHAR(50),
    memo TEXT,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES stk_products(id) ON DELETE CASCADE,
    FOREIGN KEY (store_id) REFERENCES stk_stores(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── 입출고 내역 ──
CREATE TABLE IF NOT EXISTS stk_transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    store_id INT NOT NULL,
    type ENUM('in','out','adjust','discard','move','sale') NOT NULL,
    from_location VARCHAR(50),
    to_location VARCHAR(50),
    quantity DECIMAL(10,4) NOT NULL,
    unit_price DECIMAL(16,6) DEFAULT 0,
    total_amount DECIMAL(16,6) DEFAULT 0,
    reason TEXT,
    reference_id INT NULL COMMENT 'related purchase/order/sale ID',
    reference_type VARCHAR(50) NULL COMMENT 'purchase/wholesale_order/sale',
    user_id INT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES stk_products(id) ON DELETE CASCADE,
    FOREIGN KEY (store_id) REFERENCES stk_stores(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── 매입 ──
CREATE TABLE IF NOT EXISTS stk_purchases (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    store_id INT NOT NULL,
    supplier_id INT NULL,
    purchase_number VARCHAR(50),
    purchase_date DATE NOT NULL,
    total_amount DECIMAL(16,6) DEFAULT 0,
    status ENUM('draft','confirmed','received','cancelled') DEFAULT 'draft',
    memo TEXT,
    created_by INT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES stk_businesses(id) ON DELETE CASCADE,
    FOREIGN KEY (store_id) REFERENCES stk_stores(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES stk_suppliers(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ── 매입 상세 ──
CREATE TABLE IF NOT EXISTS stk_purchase_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    purchase_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity DECIMAL(10,4) NOT NULL,
    unit_price DECIMAL(16,6) DEFAULT 0,
    amount DECIMAL(16,6) DEFAULT 0,
    FOREIGN KEY (purchase_id) REFERENCES stk_purchases(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES stk_products(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── 레시피 (식당용) ──
CREATE TABLE IF NOT EXISTS stk_recipes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    name VARCHAR(100) NOT NULL COMMENT 'menu name',
    pos_menu_id INT NULL COMMENT 'POS menu_items.id link',
    description TEXT,
    yield_quantity DECIMAL(10,2) DEFAULT 1 COMMENT 'yield qty',
    yield_unit VARCHAR(20) DEFAULT 'ea',
    is_active TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES stk_businesses(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── 레시피 원재료 ──
CREATE TABLE IF NOT EXISTS stk_recipe_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    recipe_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity DECIMAL(10,4) NOT NULL COMMENT 'qty per yield',
    unit VARCHAR(20),
    FOREIGN KEY (recipe_id) REFERENCES stk_recipes(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES stk_products(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── 소분 / 리패키징 (전 업종) ──
CREATE TABLE IF NOT EXISTS stk_repackaging (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    name VARCHAR(100) DEFAULT NULL COMMENT 'rule name (e.g. 한우 앞다리 소분)',
    source_product_id INT NOT NULL COMMENT 'source product (bulk)',
    target_product_id INT DEFAULT NULL COMMENT '[deprecated] single target (legacy)',
    ratio DECIMAL(10,4) DEFAULT NULL COMMENT '[deprecated] single ratio (legacy)',
    is_active TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES stk_businesses(id) ON DELETE CASCADE,
    FOREIGN KEY (source_product_id) REFERENCES stk_products(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS stk_repackaging_targets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    repackaging_id INT NOT NULL,
    target_product_id INT NOT NULL COMMENT 'target product (split)',
    ratio DECIMAL(10,4) NOT NULL COMMENT 'qty per 1 source unit',
    FOREIGN KEY (repackaging_id) REFERENCES stk_repackaging(id) ON DELETE CASCADE,
    FOREIGN KEY (target_product_id) REFERENCES stk_products(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── 도매 거래처 (마트용) ──
CREATE TABLE IF NOT EXISTS stk_wholesale_clients (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    contact_person VARCHAR(100),
    phone VARCHAR(20),
    email VARCHAR(100),
    address TEXT,
    default_discount_rate DECIMAL(5,2) DEFAULT 0 COMMENT 'default discount rate pct',
    memo TEXT,
    is_active TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES stk_businesses(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── 업체별 상품 할인가 ──
CREATE TABLE IF NOT EXISTS stk_wholesale_pricing (
    id INT AUTO_INCREMENT PRIMARY KEY,
    client_id INT NOT NULL,
    product_id INT NOT NULL,
    discount_type ENUM('rate','fixed_price') DEFAULT 'rate',
    discount_rate DECIMAL(5,2) DEFAULT 0 COMMENT 'discount rate pct',
    fixed_price DECIMAL(16,6) NULL COMMENT 'fixed price',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES stk_wholesale_clients(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES stk_products(id) ON DELETE CASCADE,
    UNIQUE KEY uk_client_product (client_id, product_id)
) ENGINE=InnoDB;

-- ── 도매 주문 ──
CREATE TABLE IF NOT EXISTS stk_wholesale_orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    store_id INT NOT NULL,
    client_id INT NOT NULL,
    order_number VARCHAR(50),
    order_date DATE NOT NULL,
    delivery_date DATE NULL,
    status ENUM('draft','confirmed','shipped','delivered','cancelled') DEFAULT 'draft',
    total_amount DECIMAL(16,6) DEFAULT 0,
    discount_amount DECIMAL(16,6) DEFAULT 0,
    final_amount DECIMAL(16,6) DEFAULT 0,
    memo TEXT,
    created_by INT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES stk_businesses(id) ON DELETE CASCADE,
    FOREIGN KEY (store_id) REFERENCES stk_stores(id) ON DELETE CASCADE,
    FOREIGN KEY (client_id) REFERENCES stk_wholesale_clients(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── 도매 주문 상세 ──
CREATE TABLE IF NOT EXISTS stk_wholesale_order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity DECIMAL(10,4) NOT NULL,
    unit_price DECIMAL(16,6) DEFAULT 0,
    discount_rate DECIMAL(5,2) DEFAULT 0,
    discount_amount DECIMAL(16,6) DEFAULT 0,
    amount DECIMAL(16,6) DEFAULT 0,
    FOREIGN KEY (order_id) REFERENCES stk_wholesale_orders(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES stk_products(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── 실사 재고 보고 ──
CREATE TABLE IF NOT EXISTS stk_stock_counts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    store_id INT NOT NULL,
    count_date DATE NOT NULL,
    category_id INT NULL COMMENT 'category filter',
    status ENUM('draft','completed','approved') DEFAULT 'draft',
    memo TEXT,
    created_by INT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES stk_businesses(id) ON DELETE CASCADE,
    FOREIGN KEY (store_id) REFERENCES stk_stores(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── 실사 상세 ──
CREATE TABLE IF NOT EXISTS stk_stock_count_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stock_count_id INT NOT NULL,
    product_id INT NOT NULL,
    system_quantity DECIMAL(10,4) DEFAULT 0 COMMENT 'system qty',
    actual_quantity DECIMAL(10,4) DEFAULT 0 COMMENT 'actual qty',
    difference DECIMAL(10,4) DEFAULT 0 COMMENT 'diff',
    memo TEXT,
    FOREIGN KEY (stock_count_id) REFERENCES stk_stock_counts(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES stk_products(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── 자체 판매 (비POS용) ──
CREATE TABLE IF NOT EXISTS stk_sales (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    store_id INT NOT NULL,
    sale_number VARCHAR(50),
    sale_date DATE NOT NULL,
    customer_name VARCHAR(100),
    total_amount DECIMAL(16,6) DEFAULT 0,
    status ENUM('draft','confirmed','cancelled') DEFAULT 'draft',
    memo TEXT,
    created_by INT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES stk_businesses(id) ON DELETE CASCADE,
    FOREIGN KEY (store_id) REFERENCES stk_stores(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── 판매 상세 ──
CREATE TABLE IF NOT EXISTS stk_sale_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sale_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity DECIMAL(10,4) NOT NULL,
    unit_price DECIMAL(16,6) DEFAULT 0,
    amount DECIMAL(16,6) DEFAULT 0,
    FOREIGN KEY (sale_id) REFERENCES stk_sales(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES stk_products(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── 첨부파일 (영수증/배송원장 등) ──
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

-- ============================================
-- 기본 데이터: 초기 사업장 + 관리자
-- ============================================
INSERT INTO stk_businesses (name, type, owner_name)
VALUES ('My Business', 'restaurant', 'Admin')
ON DUPLICATE KEY UPDATE name=name;

INSERT INTO stk_stores (business_id, name)
VALUES (1, 'Main Store')
ON DUPLICATE KEY UPDATE name=name;

-- 기본 관리자: admin / admin123
INSERT INTO stk_users (business_id, username, password_hash, name, role)
VALUES (1, 'admin',
  'pbkdf2:sha256:600000$salt$e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  'Administrator', 'admin')
ON DUPLICATE KEY UPDATE username=username;
