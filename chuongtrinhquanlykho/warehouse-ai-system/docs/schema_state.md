# Schema & Project State (Auto-Updated)

## 1. Models & Fields (Current State)

*   **User** (`users`)
    *   `id` (Integer, PK)
    *   `username` (String, Unique)
    *   `full_name` (String)
    *   `email` (String)
    *   `role` (Enum: admin, warehouse_manager, warehouse_keeper)
    *   `password_hash` (String)
    *   `is_active` (Boolean)
    *   `created_at` (DateTime)
*   **Supplier** (`suppliers`)
    *   `id` (Integer, PK)
    *   `name` (String)
    *   `contact_person` (String)
    *   `phone` (String)
    *   `email` (String)
    *   `address` (String)
    *   `tax_code` (String, Unique)
    *   `notes` (Text)
    *   `status` (Enum: active, inactive)
    *   `created_at`, `updated_at` (DateTime)
*   **Category** (`categories`)
    *   `id` (Integer, PK)
    *   `name` (String)
*   **Goods** (`goods`)
    *   `id` (Integer, PK)
    *   `category_id` (Integer, FK)
    *   `preferred_supplier_id` (Integer, FK)
    *   `sku` (String, Unique)
    *   `name` (String)
    *   `unit` (String)
    *   `min_stock` (Float)
    *   `max_stock` (Float)
    *   `quantity_on_hand` (Float)
    *   `selling_price` (Float)
    *   `description` (Text)
    *   `image_url` (String)
    *   `status` (Enum: active, inactive)
    *   `created_at`, `updated_at` (DateTime)
*   **PurchaseOrder** (`purchase_orders`)
    *   `id` (Integer, PK)
    *   `supplier_id` (Integer, FK)
    *   `created_by` (Integer, FK)
    *   `order_date` (DateTime)
    *   `status` (Enum: chờ xác nhận, đã xác nhận, đang giao, đã nhận, hủy)
    *   `created_at`, `updated_at` (DateTime)
*   **PurchaseOrderItem** (`purchase_order_items`)
    *   `id` (Integer, PK)
    *   `po_id` (Integer, FK)
    *   `goods_id` (Integer, FK)
    *   `quantity_ordered` (Float)
    *   `unit_price` (Float)
*   **GoodsReceipt** (`goods_receipts`)
    *   `id` (Integer, PK)
    *   `supplier_id` (Integer, FK)
    *   `po_id` (Integer, FK, Nullable)
    *   `created_by` (Integer, FK)
    *   `received_date` (DateTime)
    *   `note` (Text)
    *   `created_at`, `updated_at` (DateTime)
*   **GoodsReceiptItem** (`goods_receipt_items`)
    *   `id` (Integer, PK)
    *   `receipt_id` (Integer, FK)
    *   `goods_id` (Integer, FK)
    *   `quantity` (Float)
    *   `unit_price` (Float)

## 2. Relationships (Foreign Keys)

*   `Goods.category_id` → `Category.id`
*   `Goods.preferred_supplier_id` → `Supplier.id`
*   `PurchaseOrder.supplier_id` → `Supplier.id`
*   `PurchaseOrder.created_by` → `User.id`
*   `PurchaseOrderItem.po_id` → `PurchaseOrder.id`
*   `PurchaseOrderItem.goods_id` → `Goods.id`
*   `GoodsReceipt.supplier_id` → `Supplier.id`
*   `GoodsReceipt.po_id` → `PurchaseOrder.id`
*   `GoodsReceipt.created_by` → `User.id`
*   `GoodsReceiptItem.receipt_id` → `GoodsReceipt.id`
*   `GoodsReceiptItem.goods_id` → `Goods.id`

## 3. Conventions

*   **API Response Format**:
    *   Thành công (List): `{"total": int, "page": int, "page_size": int, "data": [...]}`
    *   Thành công (Object): Trả về JSON object trực tiếp của resource đó.
    *   Lỗi: `{"error_code": "SCREAMING_SNAKE_CASE", "message": "Mô tả lỗi tiếng Việt"}`
*   **Date/Time**: ISO 8601 UTC (`YYYY-MM-DDTHH:mm:ssZ`).
*   **Authentication**: JWT truyền qua Header `Authorization: Bearer <token>`.
*   **Soft Delete**: Thay vì xóa cứng, thay đổi trường `status` thành `inactive` (VD: Supplier, Goods).
*   **Naming Style**: `snake_case` cho DB columns, JSON keys, python variables/functions; `PascalCase` cho Classes (Models).

## 4. Module Status (ref: `api_contract.md`)

*   ✅ **Auth**
*   ✅ **Suppliers** (Nhà cung cấp)
*   ✅ **Goods** (Hàng hóa)
*   ✅ **Purchase Orders** (Đơn đặt hàng)
*   ✅ **Goods Receipts** (Phiếu nhập kho)
*   ⬜ **Goods Issues** (Phiếu xuất kho) - *Tiếp theo*
*   ⬜ **Stocktakes** (Kiểm kê)
*   ⬜ **Supplier Invoices & Payments** (Công nợ)
*   ⬜ **Reports** (Thống kê/báo cáo)
*   ⬜ **AI Features** (Tích hợp AI)
