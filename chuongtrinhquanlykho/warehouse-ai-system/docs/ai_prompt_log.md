# Nhật ký sử dụng AI — Hệ thống quản lý kho

> Đây là minh chứng bắt buộc chấm điểm. Ghi lại **mỗi lần** dùng AI để sinh code,
> thiết kế, tối ưu prompt, hoặc review code.

| Ngày | Giai đoạn | Mục đích | Prompt (rút gọn) | Phản hồi AI (tóm tắt) | Đã kiểm chứng/chỉnh sửa | Người thực hiện |
|---|---|---|---|---|---|---|
| 2026-08-04 | KT2 | Dựng khung + module Auth | "Đọc AGENTS.md, Prompt.md, api_contract.md → dựng cấu trúc thư mục + requirements.txt + seed_data.sql + .env.example + Auth module (bcrypt, JWT, role middleware)" | Tạo 12 file: extensions.py, models/user.py, auth/routes.py, auth/decorators.py, main.py, tests/test_auth.py, requirements.txt, .env.example, seed_data.sql, các placeholder package | Cần kiểm tra bcrypt hash trong seed_data.sql khớp với Password@123 | Sinh viên |

| 2026-08-08 | KT2 | Sinh module Suppliers | "Đọc AGENTS.md mục 8 (error format), Prompt.md mục 6 (bảng suppliers), api_contract.md mục 2 (Suppliers) → kiểm tra file cũ còn dang dở rồi hoàn thiện: models/supplier.py, routers/suppliers.py (5 endpoint, role middleware), tests/test_suppliers.py (19 TC). Ràng buộc: DELETE soft-delete, response lỗi đúng format {error_code, message}" | Phát hiện 3 file đã được AI trước sinh nhưng chưa "nối dây": (1) uncomment import Supplier trong models/__init__.py, (2) đăng ký suppliers_bp trong main.py, (3) comment relationships đến PurchaseOrder/GoodsReceipt/Goods chưa tồn tại để tránh mapper error. Sửa thêm: thêm test_config param vào create_app() để fixture dùng sqlite:///:memory: đúng cách, thêm db.drop_all() teardown | Chạy pytest: **19/19 PASSED** (28.74s). Kiểm chứng soft-delete: DB vẫn còn bản ghi sau DELETE, status='inactive'. Kiểm chứng 403/401/404 error_code đúng format | Sinh viên |

| 2026-08-08 | KT2 | Sinh module Goods | "Đọc Prompt.md mục 6, api_contract.md mục 3 → hoàn thiện models/goods.py, routers/goods.py (5 endpoint), tests/test_goods.py. Ràng buộc: low-stock < min_stock, mở comment relationship Supplier <-> Goods, chuẩn format lỗi, check đủ role middleware." | Tạo mới models/category.py, models/goods.py, routers/goods.py, tests/test_goods.py. Cập nhật main.py và models/__init__.py để đăng ký module. Mở comment preferred_goods trong models/supplier.py. Bổ sung trọn bộ test fixture (tạo user, app, dữ liệu test). | Chạy pytest: **6/6 PASSED** (9.86s). Logic low-stock và phân quyền hoạt động chính xác. | Sinh viên |


---

## Ghi chú cách điền

- **Giai đoạn**: KT1 / KT2 / KT3 / Cuối kỳ
- **Prompt (rút gọn)**: tóm tắt nội dung prompt gửi AI (không cần copy nguyên văn)
- **Phản hồi AI**: tóm tắt những gì AI đã làm / sinh ra
- **Kiểm chứng**: bạn đã chạy thử chưa, có sửa gì không, kết quả test pass/fail
## Đánh giá mức độ hoàn thiện module Suppliers (Đối chiếu Prompt.md & api_contract.md)

Qua kiểm tra đối chiếu giữa source code đã sinh và tài liệu đặc tả, module Suppliers đã **cơ bản đáp ứng đúng và đủ** các yêu cầu cốt lõi (5 endpoints, soft-delete, phân quyền đúng role). Tuy nhiên, có một số điểm thiếu sót/xung đột cần lưu ý và xử lý:

**1. Điểm chưa hoàn thiện trong tài liệu (`api_contract.md`)**
- Trạng thái của module Suppliers trong bảng "Trạng thái điền tài liệu" vẫn đang là `⬜ Chưa điền`. Cần cập nhật thành `✅ Đã code`.
- Chưa điền chi tiết request/response JSON schema cho các endpoint của mục `2. Suppliers` như hướng dẫn `(Điền field request/response cụ thể khi code)`.

**2. Xung đột nhỏ trong đặc tả (`Prompt.md`)**
- Ở mục `3.2` mô tả trường dữ liệu có "mã NCC", nhưng ở mục `6.1` bảng `suppliers` lại chỉ có `id` (PK) chứ không có trường mã riêng (như `code` hay `supplier_code`). Source code hiện tại đang tuân thủ chặt chẽ theo ERD mục `6.1` (dùng `id`), đây là cách tiếp cận an toàn nhưng cần ghi nhận sự sai lệch nhẹ trong bản thân tài liệu.

**3. Vấn đề Technical Debt (Nợ kỹ thuật trong Code)**
- Các Relationship từ `Supplier` đến `PurchaseOrder`, `GoodsReceipt`, `SupplierInvoice`, `Goods` đang bị comment lại trong `models/supplier.py` để tránh lỗi "mapper failed to initialize" do các entity tương ứng chưa được tạo. Phải ghi nhớ để uncomment các đoạn này khi xây dựng các module tiếp theo.
