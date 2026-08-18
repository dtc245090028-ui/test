# API Contract — Hệ thống quản lý kho có tích hợp AI

> Đây là NGUỒN SỰ THẬT DUY NHẤT cho mọi endpoint. Trước khi code module mới,
> điền endpoint vào đây TRƯỚC, code SAU. Nếu phát sinh field/endpoint mới khi
> code, quay lại cập nhật file này ngay, không để lệch giữa code và tài liệu.
>
> Chuẩn chung mọi API:
> - Base path: `/api`
> - Response lỗi: `{"error_code": "...", "message": "..."}`  (xem AGENTS.md mục 8)
> - Danh sách (GET nhiều bản ghi) luôn hỗ trợ `?page=&page_size=`
> - Auth: header `Authorization: Bearer <JWT>` (trừ endpoint đăng nhập)
> - Ngày giờ: ISO 8601 (`YYYY-MM-DDTHH:mm:ssZ`)

---

## Trạng thái điền tài liệu

| Module | Trạng thái |
|---|---|
| Auth | ✅ Đã code (2026-08-04) |
| Suppliers (Nhà cung cấp) | ✅ Đã code (2026-08-08) |
| Goods (Hàng hóa) | ✅ Đã code (2026-08-08) |
| Purchase Orders (Đơn đặt hàng) | ✅ Đã code (2026-08-09) |
| Goods Receipts (Phiếu nhập) | ✅ Đã code (2026-08-12) |
| Goods Issues (Phiếu xuất) | ✅ Đã code (2026-08-14) |
| Stocktakes (Kiểm kê) | ✅ Đã code (2026-08-18) |
| Supplier Invoices & Payments (Công nợ) | ✅ Đã code(2026-08-18) |
| Reports (Thống kê/báo cáo) | ⬜ Chưa điền |
| AI Features | ⬜ Chưa điền |

Đổi ⬜ → ✅ khi module đã code xong và endpoint khớp đúng với mục dưới đây.

---

## 1. Auth

| Method | Path | Mô tả | Role được gọi |
|---|---|---|---|
| POST | `/api/auth/login` | Đăng nhập, trả JWT | Public |
| POST | `/api/auth/logout` | Đăng xuất | Đã đăng nhập |
| GET | `/api/auth/me` | Lấy thông tin user hiện tại | Đã đăng nhập |

**Request `POST /api/auth/login`**
```json
{ "username": "string", "password": "string" }
```
**Response 200**
```json
{
  "access_token": "string",
  "role": "admin | warehouse_manager | warehouse_keeper",
  "user": { "id": 0, "username": "string", "full_name": "string" }
}
```
> *Trường `user` thêm so với đặc tả gốc — tránh phải gọi thêm `/me` ngay sau login.*

**Error codes**
| HTTP | error_code | Trường hợp |
|---|---|---|
| 400 | `MISSING_FIELDS` | Thiếu username hoặc password |
| 401 | `INVALID_CREDENTIALS` | Sai username hoặc password |
| 403 | `ACCOUNT_INACTIVE` | Tài khoản bị vô hiệu hóa |

**Response `GET /api/auth/me` (200)**
```json
{
  "id": 0, "username": "string", "full_name": "string",
  "email": "string", "role": "string", "is_active": true,
  "created_at": "2026-01-01T08:00:00"
}
```

**JWT Error codes (trả về khi thiếu/sai token)**
| HTTP | error_code | Trường hợp |
|---|---|---|
| 401 | `TOKEN_MISSING` | Không có Authorization header |
| 401 | `TOKEN_INVALID` | Token sai chữ ký |
| 401 | `TOKEN_EXPIRED` | Token hết hạn |

---

## 2. Suppliers (Nhà cung cấp)

| Method | Path | Mô tả | Role |
|---|---|---|---|
| GET | `/api/suppliers` | Danh sách, filter `?search=&status=` | Quản lý kho, Ban điều hành |
| POST | `/api/suppliers` | Tạo mới | Quản lý kho, Ban điều hành |
| GET | `/api/suppliers/{id}` | Chi tiết | Thủ kho, Quản lý kho, Ban điều hành |
| PUT | `/api/suppliers/{id}` | Cập nhật | Quản lý kho, Ban điều hành |
| DELETE | `/api/suppliers/{id}` | Xóa (hoặc đổi status ngừng hợp tác) | Ban điều hành |

**Request `POST /api/suppliers` & `PUT /api/suppliers/{id}`**
```json
{
  "name": "string (bắt buộc)",
  "contact_person": "string (tùy chọn)",
  "phone": "string (tùy chọn)",
  "email": "string (tùy chọn, chuẩn định dạng email)",
  "address": "string (tùy chọn)",
  "tax_code": "string (tùy chọn)",
  "status": "active | inactive (mặc định active)"
}
```

**Response 200 / 201 (Chi tiết Supplier)**
```json
{
  "id": 1,
  "name": "Công ty TNHH ABC",
  "contact_person": "Nguyễn Văn A",
  "phone": "0901234567",
  "email": "contact@abc.com",
  "address": "123 Đường XYZ, TP.HCM",
  "tax_code": "0312345678",
  "status": "active"
}
```

**Response `GET /api/suppliers` (200 - Phân trang)**
```json
{
  "total": 100,
  "page": 1,
  "page_size": 20,
  "data": [
    {
      "id": 1,
      "name": "Công ty TNHH ABC",
      "contact_person": "Nguyễn Văn A",
      "phone": "0901234567",
      "email": "contact@abc.com",
      "address": "123 Đường XYZ, TP.HCM",
      "tax_code": "0312345678",
      "status": "active"
    }
  ]
}
```

**Response `DELETE /api/suppliers/{id}` (200)**
```json
{
  "message": "Đã xóa (ngừng hợp tác) nhà cung cấp thành công"
}
```

---

## 3. Goods (Hàng hóa)

| Method | Path | Mô tả | Role |
|---|---|---|---|
| GET | `/api/goods` | Danh sách, filter `?search=&category_id=&status=` | Tất cả role |
| POST | `/api/goods` | Tạo mới | Quản lý kho, Ban điều hành |
| GET | `/api/goods/{id}` | Chi tiết | Tất cả role |
| PUT | `/api/goods/{id}` | Cập nhật | Quản lý kho, Ban điều hành |
| GET | `/api/goods/low-stock` | Danh sách hàng dưới ngưỡng Min | Tất cả role |

**Request `POST /api/goods` & `PUT /api/goods/{id}`**
```json
{
  "sku": "string (bắt buộc, duy nhất)",
  "name": "string (bắt buộc)",
  "category_id": "integer (bắt buộc)",
  "preferred_supplier_id": "integer (tùy chọn)",
  "unit": "string (bắt buộc, ví dụ: Cái, Hộp, kg)",
  "min_stock": "integer/float (tùy chọn, mặc định 0)",
  "max_stock": "integer/float (tùy chọn)",
  "selling_price": "float (tùy chọn, mặc định 0)",
  "description": "string (tùy chọn)",
  "image_url": "string (tùy chọn)",
  "status": "active | inactive (mặc định active)"
}
```
*(Lưu ý: `quantity_on_hand` không truyền vào khi tạo/cập nhật, vì chỉ được thay đổi qua giao dịch kho.)*

**Response 200 / 201 (Chi tiết Hàng hóa)**
```json
{
  "id": 1,
  "sku": "SP001",
  "name": "Sản phẩm A",
  "category_id": 2,
  "preferred_supplier_id": 3,
  "unit": "Cái",
  "min_stock": 10,
  "max_stock": 100,
  "quantity_on_hand": 50,
  "selling_price": 150000.0,
  "description": "Mô tả sản phẩm A",
  "image_url": "https://example.com/image.jpg",
  "status": "active"
}
```

**Response `GET /api/goods` & `GET /api/goods/low-stock` (200 - Phân trang)**
```json
{
  "total": 50,
  "page": 1,
  "page_size": 20,
  "data": [
    {
      "id": 1,
      "sku": "SP001",
      "name": "Sản phẩm A",
      "category_id": 2,
      "unit": "Cái",
      "quantity_on_hand": 50,
      "min_stock": 10,
      "status": "active"
    }
  ]
}
```

---

## 4. Purchase Orders (Đơn đặt hàng)

| Method | Path | Mô tả | Role |
|---|---|---|---|
| GET | `/api/purchase-orders` | Danh sách, filter `?status=&supplier_id=` | Thủ kho, Quản lý kho |
| POST | `/api/purchase-orders` | Tạo PO | Thủ kho |
| GET | `/api/purchase-orders/{id}` | Chi tiết + items | Thủ kho, Quản lý kho |
| PUT | `/api/purchase-orders/{id}/status` | Cập nhật trạng thái | Thủ kho |

**Request `POST /api/purchase-orders`**
```json
{
  "supplier_id": 2,
  "order_date": "2026-08-09T16:00:00Z",
  "items": [
    {
      "goods_id": 5,
      "quantity_ordered": 100,
      "unit_price": 50000.0
    }
  ]
}
```
*(Yêu cầu: `quantity_ordered` > 0 cho mọi item)*

**Response 200 / 201 (Chi tiết Purchase Order mới tạo)**
```json
{
  "id": 1,
  "supplier_id": 2,
  "created_by": 3,
  "order_date": "2026-08-09T16:00:00Z",
  "status": "chờ xác nhận",
  "items": [
    {
      "id": 1,
      "goods_id": 5,
      "quantity_ordered": 100,
      "unit_price": 50000.0
    }
  ]
}
```

**Request `PUT /api/purchase-orders/{id}/status`**
```json
{
  "status": "chờ xác nhận | đã xác nhận | đang giao | đã nhận | hủy"
}
```
*(Ghi chú: PO đã "hủy" hoặc "đã nhận" thì không được phép sửa item hoặc đổi về trạng thái trước đó. Luồng trạng thái sẽ được chốt sau khi xác nhận với người dùng.)*

**Response `GET /api/purchase-orders` (200 - Phân trang)**
```json
{
  "total": 50,
  "page": 1,
  "page_size": 20,
  "data": [
    {
      "id": 1,
      "supplier_id": 2,
      "created_by": 3,
      "order_date": "2026-08-09T16:00:00Z",
      "status": "chờ xác nhận"
    }
  ]
}
```

**Response `GET /api/purchase-orders/{id}` (200 - Chi tiết)**
*(Cấu trúc tương tự Response 201 của `POST`, gồm các trường cơ bản và mảng `items` chi tiết).*

---

## 5. Goods Receipts (Phiếu nhập kho)

| Method | Path | Mô tả | Role |
|---|---|---|---|
| GET | `/api/goods-receipts` | Danh sách, filter `?supplier_id=&date_from=&date_to=&po_id=` | Thủ kho, Quản lý kho |
| POST | `/api/goods-receipts` | Lập phiếu nhập (transaction, cập nhật tồn) | Thủ kho |
| GET | `/api/goods-receipts/{id}` | Chi tiết | Thủ kho, Quản lý kho |

**Request `POST /api/goods-receipts`**
```json
{
  "supplier_id": 1,
  "po_id": 2,
  "received_date": "2026-08-12T10:00:00Z",
  "note": "string (tùy chọn)",
  "items": [
    {
      "goods_id": 5,
      "quantity": 100,
      "unit_price": 50000.0
    }
  ]
}
```
*(Yêu cầu: `quantity` > 0; `unit_price` >= 0 — lưu cố định snapshot theo lần nhập, không thay đổi sau này; `po_id` tùy chọn — nếu có thì phải thuộc đúng `supplier_id`)*

**Response 200 / 201 (Chi tiết Phiếu nhập)**
```json
{
  "id": 1,
  "supplier_id": 1,
  "po_id": 2,
  "created_by": 3,
  "received_date": "2026-08-12T10:00:00",
  "note": "Nhập lô hàng tháng 8",
  "created_at": "2026-08-12T10:00:05",
  "updated_at": "2026-08-12T10:00:05",
  "items": [
    {
      "id": 1,
      "receipt_id": 1,
      "goods_id": 5,
      "quantity": 100,
      "unit_price": 50000.0
    }
  ]
}
```

**Response `GET /api/goods-receipts` (200 — Phân trang)**
```json
{
  "total": 30,
  "page": 1,
  "page_size": 20,
  "data": [
    {
      "id": 1,
      "supplier_id": 1,
      "po_id": 2,
      "created_by": 3,
      "received_date": "2026-08-12T10:00:00",
      "note": null,
      "created_at": "2026-08-12T10:00:05",
      "updated_at": "2026-08-12T10:00:05"
    }
  ]
}
```
*(Lưu ý: `data` trong danh sách không bao gồm mảng `items` — gọi GET/{id} để lấy chi tiết)*

**Error codes**
| HTTP | error_code | Trường hợp |
|---|---|---|
| 400 | `MISSING_FIELDS` | Thiếu `supplier_id` hoặc `items` rỗng |
| 400 | `INVALID_QUANTITY` | `quantity` ≤ 0 trong bất kỳ dòng nào |
| 400 | `INVALID_UNIT_PRICE` | `unit_price` âm trong bất kỳ dòng nào |
| 400 | `SUPPLIER_INACTIVE` | NCC đã ngừng hợp tác |
| 400 | `GOODS_INACTIVE` | Hàng hóa đã ngừng kinh doanh |
| 400 | `PO_SUPPLIER_MISMATCH` | `po_id` không thuộc `supplier_id` đã chọn |
| 400 | `INVALID_DATE_FORMAT` | `received_date` sai định dạng ISO 8601 |
| 404 | `SUPPLIER_NOT_FOUND` | Không tìm thấy NCC |
| 404 | `GOODS_NOT_FOUND` | Không tìm thấy hàng hóa |
| 404 | `PO_NOT_FOUND` | Không tìm thấy đơn đặt hàng |
| 404 | `RECEIPT_NOT_FOUND` | Không tìm thấy phiếu nhập |

> **Ràng buộc quan trọng**: `goods.quantity_on_hand` chỉ được cập nhật qua transaction (flush → add items → cập nhật tồn → commit). Nếu bất kỳ bước nào thất bại → rollback toàn bộ. `goods_receipt_items.unit_price` lưu cố định (snapshot) tại thời điểm nhập, không thay đổi dù giá nhập sau này thay đổi.

---

## 6. Goods Issues (Phiếu xuất kho)

| Method | Path | Mô tả | Role |
|---|---|---|---|
| GET | `/api/goods-issues` | Danh sách, filter `?date_from=&date_to=` | Thủ kho, Quản lý kho |
| POST | `/api/goods-issues` | Lập phiếu xuất (chặn xuất vượt tồn) | Thủ kho |
| GET | `/api/goods-issues/{id}` | Chi tiết | Thủ kho, Quản lý kho |

**Request `POST /api/goods-issues`**
```json
{
  "issued_date": "2026-08-14T08:00:00Z",
  "note": "string (tùy chọn)",
  "items": [
    {
      "goods_id": 5,
      "quantity": 10
    }
  ]
}
```
*(Yêu cầu: `quantity` > 0 cho mọi item; `quantity` ≤ `goods.quantity_on_hand` — không cho xuất vượt tồn)*

**Response 200 / 201 (Chi tiết Phiếu xuất mới tạo)**
```json
{
  "id": 1,
  "created_by": 3,
  "issued_date": "2026-08-14T08:00:00",
  "note": "Xuất hàng cho bộ phận sản xuất",
  "created_at": "2026-08-14T08:00:05",
  "updated_at": "2026-08-14T08:00:05",
  "items": [
    {
      "id": 1,
      "issue_id": 1,
      "goods_id": 5,
      "quantity": 10
    }
  ]
}
```

**Response `GET /api/goods-issues` (200 — Phân trang)**
```json
{
  "total": 20,
  "page": 1,
  "page_size": 20,
  "data": [
    {
      "id": 1,
      "created_by": 3,
      "issued_date": "2026-08-14T08:00:00",
      "note": null,
      "created_at": "2026-08-14T08:00:05",
      "updated_at": "2026-08-14T08:00:05"
    }
  ]
}
```
*(Lưu ý: `data` trong danh sách không bao gồm mảng `items` — gọi GET/{id} để lấy chi tiết)*

**Error codes**
| HTTP | error_code | Trường hợp |
|---|---|---|
| 400 | `MISSING_FIELDS` | `items` rỗng hoặc thiếu |
| 400 | `INVALID_QUANTITY` | `quantity` ≤ 0 trong bất kỳ dòng nào |
| 400 | `INSUFFICIENT_STOCK` | `quantity` vượt quá tồn kho hiện tại |
| 400 | `GOODS_INACTIVE` | Hàng hóa đã ngừng kinh doanh |
| 400 | `INVALID_DATE_FORMAT` | `issued_date` sai định dạng ISO 8601 |
| 404 | `GOODS_NOT_FOUND` | Không tìm thấy hàng hóa |
| 404 | `ISSUE_NOT_FOUND` | Không tìm thấy phiếu xuất |

> **Ràng buộc quan trọng**: `goods.quantity_on_hand` chỉ được cập nhật qua transaction (flush → add items → trừ tồn → commit). Nếu bất kỳ bước nào thất bại → rollback toàn bộ. Không cho phép tồn kho âm (`quantity_on_hand` không được giảm xuống dưới 0).

---

## 7. Stocktakes (Kiểm kê)

| Method | Path | Mô tả | Role |
|---|---|---|---|
| GET | `/api/stocktakes` | Danh sách | Thủ kho, Quản lý kho |
| POST | `/api/stocktakes` | Lập phiếu kiểm kê | Thủ kho |
| PUT | `/api/stocktakes/{id}/propose` | Thủ kho đề xuất xử lý chênh lệch | Thủ kho |
| PUT | `/api/stocktakes/{id}/approve` | Quản lý kho phê duyệt → cập nhật tồn | Quản lý kho |

**Request `POST /api/stocktakes`**
```json
{
  "note": "string (tùy chọn)",
  "items": [
    {
      "goods_id": 5,
      "actual_quantity": 48
    }
  ]
}
```
*(Hệ thống sẽ tự lấy `goods.quantity_on_hand` gán vào `system_quantity` và tính `difference = actual_quantity - system_quantity`. Trạng thái mặc định là "đang kiểm kê")*

**Response 200 / 201 (Chi tiết Phiếu kiểm kê mới tạo)**
```json
{
  "id": 1,
  "created_by": 3,
  "approved_by": null,
  "stocktake_date": "2026-08-18T08:00:00",
  "status": "đang kiểm kê",
  "note": "Kiểm kê định kỳ tháng 8",
  "items": [
    {
      "id": 1,
      "stocktake_id": 1,
      "goods_id": 5,
      "system_quantity": 50,
      "actual_quantity": 48,
      "difference": -2,
      "action": null
    }
  ]
}
```

**Request `PUT /api/stocktakes/{id}/propose`**
```json
{
  "items": [
    {
      "id": 1,
      "action": "Thanh lý hàng hỏng do vỡ"
    }
  ]
}
```
*(Cập nhật `action` cho các chi tiết chênh lệch và đổi trạng thái thành "chờ phê duyệt")*

**Request `PUT /api/stocktakes/{id}/approve`**
*(Không có body. Sau khi gọi API này, status đổi thành "đã phê duyệt", và tồn kho được cập nhật thành `actual_quantity` cho từng item)*

**Error codes**
| HTTP | error_code | Trường hợp |
|---|---|---|
| 400 | `MISSING_FIELDS` | `items` rỗng hoặc thiếu |
| 400 | `INVALID_QUANTITY` | `actual_quantity` < 0 trong bất kỳ dòng nào |
| 400 | `INVALID_STATUS` | Hành động không hợp lệ ở trạng thái hiện tại |
| 403 | `UNAUTHORIZED_ACTION` | Không có quyền (ví dụ: Thủ kho cố duyệt phiếu) |
| 404 | `GOODS_NOT_FOUND` | Không tìm thấy hàng hóa |
| 404 | `STOCKTAKE_NOT_FOUND` | Không tìm thấy phiếu kiểm kê |

---

## 8. Supplier Invoices & Payments (Công nợ)

| Method | Path | Mô tả | Role |
|---|---|---|---|
| GET | `/api/supplier-invoices` | Danh sách, filter `?supplier_id=&payment_status=` | Quản lý kho, Ban điều hành |
| POST | `/api/supplier-invoices` | Tạo hóa đơn từ phiếu nhập | Thủ kho, Quản lý kho |
| GET | `/api/supplier-invoices/{id}` | Chi tiết hóa đơn + lịch sử thanh toán | Quản lý kho, Ban điều hành |
| POST | `/api/supplier-payments` | Ghi nhận thanh toán → tự cập nhật payment_status | Quản lý kho, Ban điều hành |

**Request `POST /api/supplier-invoices`**
```json
{
  "supplier_id": 1,
  "receipt_id": 3,
  "invoice_number": "INV-2026-001",
  "issue_date": "2026-08-18T08:00:00Z",
  "total_amount": 5000000.0
}
```
*(Ràng buộc: `receipt_id` tùy chọn — nếu có thì phải thuộc đúng `supplier_id`; mỗi `receipt_id` chỉ được tạo 1 hóa đơn; `total_amount` > 0; `invoice_number` bắt buộc)*

**Response 200 / 201 (Chi tiết Hóa đơn)**
```json
{
  "id": 1,
  "supplier_id": 1,
  "receipt_id": 3,
  "invoice_number": "INV-2026-001",
  "issue_date": "2026-08-18T08:00:00",
  "total_amount": 5000000.0,
  "paid_amount": 0.0,
  "payment_status": "chưa thanh toán",
  "created_at": "2026-08-18T08:00:05",
  "updated_at": "2026-08-18T08:00:05"
}
```

**Response `GET /api/supplier-invoices` (200 — Phân trang)**
```json
{
  "total": 10,
  "page": 1,
  "page_size": 20,
  "data": [
    {
      "id": 1,
      "supplier_id": 1,
      "receipt_id": 3,
      "invoice_number": "INV-2026-001",
      "issue_date": "2026-08-18T08:00:00",
      "total_amount": 5000000.0,
      "paid_amount": 2000000.0,
      "payment_status": "thanh toán một phần"
    }
  ]
}
```

**Response `GET /api/supplier-invoices/{id}` (200 — Chi tiết + lịch sử thanh toán)**
```json
{
  "id": 1,
  "supplier_id": 1,
  "receipt_id": 3,
  "invoice_number": "INV-2026-001",
  "issue_date": "2026-08-18T08:00:00",
  "total_amount": 5000000.0,
  "paid_amount": 2000000.0,
  "payment_status": "thanh toán một phần",
  "payments": [
    {
      "id": 1,
      "invoice_id": 1,
      "amount": 2000000.0,
      "payment_date": "2026-08-20T10:00:00",
      "method": "chuyển khoản"
    }
  ]
}
```

**Request `POST /api/supplier-payments`**
```json
{
  "invoice_id": 1,
  "amount": 3000000.0,
  "payment_date": "2026-08-20T10:00:00Z",
  "method": "chuyển khoản"
}
```
*(Ràng buộc: `amount` > 0; tổng tiền thanh toán không được vượt quá `total_amount`; hóa đơn đã trạng thái "đã thanh toán" thì không thể thanh toán thêm; sau khi thanh toán nếu `paid_amount >= total_amount` thì tự động đổi `payment_status` → "đã thanh toán")*

**Response `POST /api/supplier-payments` (201)**
```json
{
  "id": 1,
  "invoice_id": 1,
  "amount": 3000000.0,
  "payment_date": "2026-08-20T10:00:00",
  "method": "chuyển khoản",
  "invoice_payment_status": "đã thanh toán"
}
```

**Error codes**
| HTTP | error_code | Trường hợp |
|---|---|---|
| 400 | `MISSING_FIELDS` | Thiếu trường bắt buộc |
| 400 | `INVALID_AMOUNT` | `total_amount` hoặc `amount` ≤ 0 |
| 400 | `OVERPAYMENT` | Tổng thanh toán vượt quá `total_amount` |
| 400 | `INVOICE_ALREADY_PAID` | Hóa đơn đã thanh toán đủ, không thể thanh toán thêm |
| 400 | `RECEIPT_ALREADY_INVOICED` | `receipt_id` đã có hóa đơn liên kết |
| 400 | `RECEIPT_SUPPLIER_MISMATCH` | `receipt_id` không thuộc `supplier_id` đã chọn |
| 400 | `INVALID_DATE_FORMAT` | `issue_date` / `payment_date` sai định dạng ISO 8601 |
| 404 | `SUPPLIER_NOT_FOUND` | Không tìm thấy nhà cung cấp |
| 404 | `RECEIPT_NOT_FOUND` | Không tìm thấy phiếu nhập |
| 404 | `INVOICE_NOT_FOUND` | Không tìm thấy hóa đơn |

> **Ràng buộc quan trọng**: `paid_amount` không lưu trực tiếp trong bảng mà được tính tổng từ `supplier_payments.amount` mỗi khi cần; `payment_status` cập nhật tự động trong transaction mỗi khi ghi nhận thanh toán. Không cho phép sửa/xóa hóa đơn hay lịch sử thanh toán sau khi đã tạo — chỉ được thêm mới.

---

## 9. Reports (Thống kê/báo cáo — không phải AI)

| Method | Path | Mô tả | Role |
|---|---|---|---|
| GET | `/api/reports/inventory-value` | Giá trị tồn kho theo thời gian | Quản lý kho, Ban điều hành |
| GET | `/api/reports/turnover` | Vòng quay tồn kho / slow-moving | Quản lý kho, Ban điều hành |
| GET | `/api/reports/top-goods` | Top hàng nhập/xuất nhiều nhất | Quản lý kho, Ban điều hành |
| GET | `/api/reports/stocktake-diff` | Chênh lệch kiểm kê theo kỳ | Quản lý kho, Ban điều hành |

*(Điền chi tiết khi code)*

---

## 10. AI Features

| Method | Path | Mô tả | Role |
|---|---|---|---|
| POST | `/api/ai/inventory-report` | Sinh báo cáo nhập-xuất-tồn | Quản lý kho, Ban điều hành |
| POST | `/api/ai/reorder-suggestion` | Gợi ý nhập hàng | Thủ kho, Quản lý kho |

**Response `/api/ai/inventory-report`** (theo mục 8.1 Prompt.md)
```json
{
  "summary": "string",
  "low_stock_items": [{ "sku": "string", "current_qty": 0, "min_stock": 0 }],
  "notable_changes": [{ "sku": "string", "note": "string" }]
}
```

**Response `/api/ai/reorder-suggestion`** (theo mục 8.2 Prompt.md)
```json
{
  "reorder_suggestions": [
    { "sku": "string", "suggested_quantity": 0, "reason": "string" }
  ]
}
```

Lỗi định dạng/timeout → trả `error_code: "AI_RESPONSE_INVALID"` hoặc
`"AI_TIMEOUT"`, không crash, không hiển thị dữ liệu rác (theo mục 8.4).
