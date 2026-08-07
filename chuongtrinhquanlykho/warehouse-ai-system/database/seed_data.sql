-- ============================================================
-- seed_data.sql — Dữ liệu mẫu cho hệ thống quản lý kho
-- ============================================================
-- Cách chạy (SQLite):
--   sqlite3 warehouse.db < database/seed_data.sql
--
-- Cách chạy (PostgreSQL):
--   psql -U <user> -d warehouse -f database/seed_data.sql
--
-- Dữ liệu bao gồm:
--   - 3 nhà cung cấp (suppliers)
--   - 3 danh mục hàng hóa (categories)
--   - 8 hàng hóa đa dạng — có hàng dưới Min, có hàng vượt Max để test cảnh báo
--   - 3 user: 1 admin, 1 warehouse_manager, 1 warehouse_keeper
--
-- MẬT KHẨU MẪU (đã hash bcrypt, password gốc: "Password@123"):
--   Dùng chung cho cả 3 tài khoản để dễ demo
-- ============================================================

-- Xóa dữ liệu cũ theo thứ tự ngược FK để tránh lỗi constraint
DELETE FROM supplier_payments;
DELETE FROM supplier_invoices;
DELETE FROM stocktake_items;
DELETE FROM stocktakes;
DELETE FROM goods_issue_items;
DELETE FROM goods_issues;
DELETE FROM goods_receipt_items;
DELETE FROM goods_receipts;
DELETE FROM purchase_order_items;
DELETE FROM purchase_orders;
DELETE FROM goods;
DELETE FROM categories;
DELETE FROM suppliers;
DELETE FROM users;

-- ============================================================
-- BẢNG: users
-- role: admin | warehouse_manager | warehouse_keeper
-- password_hash: bcrypt hash của "Password@123"
-- (sinh bằng: python -c "import bcrypt; print(bcrypt.hashpw(b'Password@123', bcrypt.gensalt()).decode())")
-- ============================================================
INSERT INTO users (id, username, full_name, email, role, password_hash, is_active, created_at) VALUES
(
    1,
    'admin01',
    'Nguyễn Văn Admin',
    'admin@warehouse.local',
    'admin',
    -- bcrypt hash của "Password@123" (cost=12)
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TiJPL9bBjFwMVQ8Ckq3KvWfAZ5Hy',
    1,
    '2026-01-01T08:00:00'
),
(
    2,
    'manager01',
    'Trần Thị Quản Lý',
    'manager@warehouse.local',
    'warehouse_manager',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TiJPL9bBjFwMVQ8Ckq3KvWfAZ5Hy',
    1,
    '2026-01-01T08:00:00'
),
(
    3,
    'keeper01',
    'Lê Văn Thủ Kho',
    'keeper@warehouse.local',
    'warehouse_keeper',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TiJPL9bBjFwMVQ8Ckq3KvWfAZ5Hy',
    1,
    '2026-01-01T08:00:00'
);

-- ============================================================
-- BẢNG: suppliers — 3 nhà cung cấp
-- status: active | inactive
-- ============================================================
INSERT INTO suppliers (id, supplier_code, name, contact_person, phone, email, address, tax_code, status, notes, created_at) VALUES
(
    1,
    'NCC001',
    'Công ty TNHH Phụ Tùng Thiên Long',
    'Phạm Minh Đức',
    '0901234567',
    'duc.pham@thienlong.vn',
    '123 Đường Lý Thường Kiệt, Q.10, TP.HCM',
    '0312345678',
    'active',
    'NCC ưu tiên cho linh kiện điện tử',
    '2026-01-05T09:00:00'
),
(
    2,
    'NCC002',
    'HTX Sản Xuất Văn Phòng Phẩm Bình Dương',
    'Nguyễn Thị Hoa',
    '0912345678',
    'hoa.nt@vppbinhduong.vn',
    '45 Đường Trần Phú, TX.Thủ Dầu Một, Bình Dương',
    '3702345678',
    'active',
    'Chuyên cung cấp văn phòng phẩm, giao hàng mỗi thứ 2',
    '2026-01-10T09:00:00'
),
(
    3,
    'NCC003',
    'Công ty CP Thiết Bị Bảo Hộ An Toàn Việt',
    'Trần Quốc Hùng',
    '0987654321',
    'hung.tq@baohoanviet.vn',
    '789 Đường Cộng Hòa, Q.Tân Bình, TP.HCM',
    '0312987654',
    'inactive',
    'Tạm ngừng hợp tác từ 2026-06 do giao hàng chậm',
    '2026-02-01T09:00:00'
);

-- ============================================================
-- BẢNG: categories — 3 nhóm hàng
-- ============================================================
INSERT INTO categories (id, name, description, created_at) VALUES
(1, 'Linh kiện điện tử',   'Các loại linh kiện, phụ tùng điện - điện tử',       '2026-01-01T08:00:00'),
(2, 'Văn phòng phẩm',      'Dụng cụ văn phòng, bút, giấy, mực in...',           '2026-01-01T08:00:00'),
(3, 'Thiết bị bảo hộ',     'Đồ bảo hộ lao động: mũ, găng tay, kính bảo hộ...', '2026-01-01T08:00:00');

-- ============================================================
-- BẢNG: goods — 8 hàng hóa đa dạng
--
-- Mục đích test cảnh báo Min/Max:
--   SKU001: tồn = 5  | min=20  → DƯỚI MIN   (cần cảnh báo + AI gợi ý nhập)
--   SKU002: tồn = 12 | min=10  → bình thường
--   SKU003: tồn = 3  | min=15  → DƯỚI MIN   (cảnh báo nghiêm trọng)
--   SKU004: tồn = 50 | max=40  → VƯỢT MAX   (tồn dư quá nhiều)
--   SKU005: tồn = 25 | min=20, max=100 → bình thường
--   SKU006: tồn = 8  | min=10  → DƯỚI MIN   (sắp hết)
--   SKU007: tồn = 0  | min=5   → HẾT HÀNG   (cảnh báo khẩn)
--   SKU008: tồn = 200| max=150 → VƯỢT MAX   (dư nhiều)
--
-- Lưu ý: KHÔNG có trường "unit_price" trên goods —
--        giá nhập lưu ở goods_receipt_items.unit_price (ràng buộc nghiệp vụ #2)
-- ============================================================
INSERT INTO goods (id, sku, name, category_id, preferred_supplier_id, unit,
                   min_stock, max_stock, quantity_on_hand,
                   selling_price, description, status, created_at) VALUES
(
    1, 'SKU001', 'Tụ điện 100μF 25V',
    1, 1, 'Cái',
    20, 200, 5,          -- DƯỚI MIN: tồn 5 < min 20
    2500.00,
    'Tụ điện điện phân, dùng cho mạch nguồn và bộ lọc',
    'active', '2026-01-15T10:00:00'
),
(
    2, 'SKU002', 'Điện trở 10kΩ (gói 100 cái)',
    1, 1, 'Gói',
    10, 100, 12,         -- bình thường: tồn 12, min 10
    15000.00,
    'Điện trở carbon film 1/4W, sai số 5%, gói 100 cái',
    'active', '2026-01-15T10:00:00'
),
(
    3, 'SKU003', 'IC vi điều khiển Arduino Nano',
    1, 1, 'Cái',
    15, 80, 3,           -- DƯỚI MIN NGHIÊM TRỌNG: tồn 3 < min 15
    120000.00,
    'Arduino Nano v3 có bootloader, chip ATmega328P',
    'active', '2026-01-15T10:00:00'
),
(
    4, 'SKU004', 'Giấy A4 70gsm (ream 500 tờ)',
    2, 2, 'Ream',
    10, 40, 50,          -- VƯỢT MAX: tồn 50 > max 40
    85000.00,
    'Giấy in văn phòng A4, 70gsm, 500 tờ/ream, đóng gói 10 ream/thùng',
    'active', '2026-01-20T10:00:00'
),
(
    5, 'SKU005', 'Bút bi Thiên Long TL-027',
    2, 2, 'Hộp',
    20, 100, 25,         -- bình thường: tồn 25, min 20, max 100
    25000.00,
    'Bút bi mực xanh, 0.7mm, hộp 20 cây',
    'active', '2026-01-20T10:00:00'
),
(
    6, 'SKU006', 'Mực in Canon PG-745 (đen)',
    2, 2, 'Hộp',
    10, 50, 8,           -- DƯỚI MIN: tồn 8 < min 10
    185000.00,
    'Hộp mực in Canon PG-745 màu đen, dùng cho máy in MG2570S, iP2870S',
    'active', '2026-02-01T10:00:00'
),
(
    7, 'SKU007', 'Mũ bảo hộ lao động (loại PE)',
    3, 3, 'Cái',
    5, 50, 0,            -- HẾT HÀNG: tồn 0 < min 5
    55000.00,
    'Mũ bảo hộ lao động nhựa PE, màu vàng, có khóa điều chỉnh',
    'active', '2026-02-10T10:00:00'
),
(
    8, 'SKU008', 'Băng keo đóng hàng 48mm x 100m',
    2, 2, 'Cuộn',
    30, 150, 200,        -- VƯỢT MAX: tồn 200 > max 150
    18000.00,
    'Băng keo OPP trong suốt, lõi 76mm, 48mm x 100m',
    'active', '2026-02-10T10:00:00'
);
