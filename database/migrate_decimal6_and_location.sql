-- ============================================
-- Migration: Decimal 6 digits + Product storage_location
-- ============================================
USE stock_master;

-- 1. stk_products: price to DECIMAL(16,6), add storage_location
ALTER TABLE stk_products
  MODIFY unit_price DECIMAL(16,6) DEFAULT 0,
  MODIFY sell_price DECIMAL(16,6) DEFAULT 0,
  MODIFY min_stock DECIMAL(10,2) DEFAULT 0,
  MODIFY max_stock DECIMAL(10,2) NULL,
  ADD COLUMN storage_location VARCHAR(200) NULL AFTER description;

-- 2. stk_transactions: price/amount to DECIMAL(16,6)
ALTER TABLE stk_transactions
  MODIFY quantity DECIMAL(10,4) NOT NULL,
  MODIFY unit_price DECIMAL(16,6) DEFAULT 0,
  MODIFY total_amount DECIMAL(16,6) DEFAULT 0;

-- 3. stk_purchases: total_amount to DECIMAL(16,6)
ALTER TABLE stk_purchases
  MODIFY total_amount DECIMAL(16,6) DEFAULT 0;

-- 4. stk_purchase_items: price/amount to DECIMAL(16,6)
ALTER TABLE stk_purchase_items
  MODIFY quantity DECIMAL(10,4) NOT NULL,
  MODIFY unit_price DECIMAL(16,6) DEFAULT 0,
  MODIFY amount DECIMAL(16,6) DEFAULT 0;

-- 5. stk_wholesale_pricing: fixed_price to DECIMAL(16,6)
ALTER TABLE stk_wholesale_pricing
  MODIFY fixed_price DECIMAL(16,6) NULL;

-- 6. stk_wholesale_orders: amounts to DECIMAL(16,6)
ALTER TABLE stk_wholesale_orders
  MODIFY total_amount DECIMAL(16,6) DEFAULT 0,
  MODIFY discount_amount DECIMAL(16,6) DEFAULT 0,
  MODIFY final_amount DECIMAL(16,6) DEFAULT 0;

-- 7. stk_wholesale_order_items: price/amounts to DECIMAL(16,6)
ALTER TABLE stk_wholesale_order_items
  MODIFY quantity DECIMAL(10,4) NOT NULL,
  MODIFY unit_price DECIMAL(16,6) DEFAULT 0,
  MODIFY discount_amount DECIMAL(16,6) DEFAULT 0,
  MODIFY amount DECIMAL(16,6) DEFAULT 0;

-- 8. stk_sales: total_amount to DECIMAL(16,6)
ALTER TABLE stk_sales
  MODIFY total_amount DECIMAL(16,6) DEFAULT 0;

-- 9. stk_sale_items: price/amount to DECIMAL(16,6)
ALTER TABLE stk_sale_items
  MODIFY quantity DECIMAL(10,4) NOT NULL,
  MODIFY unit_price DECIMAL(16,6) DEFAULT 0,
  MODIFY amount DECIMAL(16,6) DEFAULT 0;

-- 10. stk_inventory: quantity precision
ALTER TABLE stk_inventory
  MODIFY quantity DECIMAL(10,4) DEFAULT 0;

-- 11. stk_stock_count_items: precision
ALTER TABLE stk_stock_count_items
  MODIFY system_quantity DECIMAL(10,4) DEFAULT 0,
  MODIFY actual_quantity DECIMAL(10,4) DEFAULT 0,
  MODIFY difference DECIMAL(10,4) DEFAULT 0;

SELECT 'Migration complete: DECIMAL(16,6) + storage_location' AS result;
