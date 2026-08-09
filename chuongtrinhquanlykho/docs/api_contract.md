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
| Goods Receipts (Phiếu nhập) | ⬜ Chưa điền |
| Goods Issues (Phiếu xuất) | ⬜ Chưa điền |
| Stocktakes (Kiểm kê) | ⬜ Chưa điền |
| Supplier Invoices & Payments (Công nợ) | ⬜ Chưa điền |
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
| GET | `/api/goods-receipts` | Danh sách, filter theo ngày/NCC | Thủ kho, Quản lý kho |
| POST | `/api/goods-receipts` | Lập phiếu nhập (transaction, cập nhật tồn) | Thủ kho |
| GET | `/api/goods-receipts/{id}` | Chi tiết | Thủ kho, Quản lý kho |

*(Điền chi tiết khi code — nhớ ràng buộc: unit_price lưu cố định theo lần nhập)*

---

## 6. Goods Issues (Phiếu xuất kho)

| Method | Path | Mô tả | Role |
|---|---|---|---|
| GET | `/api/goods-issues` | Danh sách | Thủ kho, Quản lý kho |
| POST | `/api/goods-issues` | Lập phiếu xuất (chặn xuất vượt tồn) | Thủ kho |
| GET | `/api/goods-issues/{id}` | Chi tiết | Thủ kho, Quản lý kho |

*(Điền chi tiết khi code)*

---

## 7. Stocktakes (Kiểm kê)

| Method | Path | Mô tả | Role |
|---|---|---|---|
| GET | `/api/stocktakes` | Danh sách | Thủ kho, Quản lý kho |
| POST | `/api/stocktakes` | Lập phiếu kiểm kê | Thủ kho |
| PUT | `/api/stocktakes/{id}/propose` | Thủ kho đề xuất xử lý chênh lệch | Thủ kho |
| PUT | `/api/stocktakes/{id}/approve` | Quản lý kho phê duyệt → cập nhật tồn | Quản lý kho |

*(Điền chi tiết khi code)*

---

## 8. Supplier Invoices & Payments (Công nợ)

| Method | Path | Mô tả | Role |
|---|---|---|---|
| GET | `/api/supplier-invoices` | Danh sách, filter theo NCC/trạng thái | Quản lý kho, Ban điều hành |
| POST | `/api/supplier-invoices` | Tạo hóa đơn từ phiếu nhập | Thủ kho, Quản lý kho |
| POST | `/api/supplier-payments` | Ghi nhận thanh toán | Quản lý kho, Ban điều hành |

*(Điền chi tiết khi code)*

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
