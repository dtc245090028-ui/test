# Nhật ký sử dụng AI — Hệ thống quản lý kho

> Đây là minh chứng bắt buộc chấm điểm. Ghi lại **mỗi lần** dùng AI để sinh code,
> thiết kế, tối ưu prompt, hoặc review code.

| Ngày | Giai đoạn | Mục đích | Prompt (rút gọn) | Phản hồi AI (tóm tắt) | Đã kiểm chứng/chỉnh sửa | Người thực hiện |
|---|---|---|---|---|---|---|
| 2026-08-04 | KT2 | Dựng khung + module Auth | "Đọc AGENTS.md, Prompt.md, api_contract.md → dựng cấu trúc thư mục + requirements.txt + seed_data.sql + .env.example + Auth module (bcrypt, JWT, role middleware)" | Tạo 12 file: extensions.py, models/user.py, auth/routes.py, auth/decorators.py, main.py, tests/test_auth.py, requirements.txt, .env.example, seed_data.sql, các placeholder package | Cần kiểm tra bcrypt hash trong seed_data.sql khớp với Password@123 | Sinh viên |

| 2026-08-08 | KT2 | Sinh module Suppliers | "Đọc AGENTS.md mục 8 (error format), Prompt.md mục 6 (bảng suppliers), api_contract.md mục 2 (Suppliers) → kiểm tra file cũ còn dang dở rồi hoàn thiện: models/supplier.py, routers/suppliers.py (5 endpoint, role middleware), tests/test_suppliers.py (19 TC). Ràng buộc: DELETE soft-delete, response lỗi đúng format {error_code, message}" | Phát hiện 3 file đã được AI trước sinh nhưng chưa "nối dây": (1) uncomment import Supplier trong models/__init__.py, (2) đăng ký suppliers_bp trong main.py, (3) comment relationships đến PurchaseOrder/GoodsReceipt/Goods chưa tồn tại để tránh mapper error. Sửa thêm: thêm test_config param vào create_app() để fixture dùng sqlite:///:memory: đúng cách, thêm db.drop_all() teardown | Chạy pytest: **19/19 PASSED** (28.74s). Kiểm chứng soft-delete: DB vẫn còn bản ghi sau DELETE, status='inactive'. Kiểm chứng 403/401/404 error_code đúng format | Sinh viên |

| 2026-08-08 | KT2 | Sinh module Goods | "Đọc Prompt.md mục 6, api_contract.md mục 3 → hoàn thiện models/goods.py, routers/goods.py (5 endpoint), tests/test_goods.py. Ràng buộc: low-stock < min_stock, mở comment relationship Supplier <-> Goods, chuẩn format lỗi, check đủ role middleware." | Tạo mới models/category.py, models/goods.py, routers/goods.py, tests/test_goods.py. Cập nhật main.py và models/__init__.py để đăng ký module. Mở comment preferred_goods trong models/supplier.py. Bổ sung trọn bộ test fixture (tạo user, app, dữ liệu test). | Chạy pytest: **6/6 PASSED** (9.86s). Logic low-stock và phân quyền hoạt động chính xác. | Sinh viên |

| 09/08/2026 | KT2 | Hoàn thiện Module Purchase      
  Orders (PO) | Đọc AGENTS.md, Prompt.md (3.5, 6.1,      
  10), api_contract.md. Yêu cầu: Điền chi tiết API Doc   
  trước. Chốt flow chuyển trạng thái. Code models,       
  routers (có phân quyền), tests. Ràng buộc: quantity    
  > 0, status luồng chuẩn, cập nhật relationship file    
  cũ. Chạy pytest. | 1. Cập nhật api_contract.md. 2.     
  Hỏi người dùng để chốt flow (chờ xác nhận -> đã xác    
  nhận -> đang giao -> đã nhận). 3. Tạo
  models/purchase_order.py. 4. Bỏ comment relationship   
  ở supplier và goods. 5. Tạo routers/purchase_orders.   
  py phân quyền đúng role. 6. Tạo
  tests/test_purchase_orders.py. 7. Chạy 4/4 test        
  cases passed 100%. | Đã kiểm tra luồng API và code     
  pass toàn bộ test. | (Tên của bạn) |
---

## Ghi chú cách điền

- **Giai đoạn**: KT1 / KT2 / KT3 / Cuối kỳ
- **Prompt (rút gọn)**: tóm tắt nội dung prompt gửi AI (không cần copy nguyên văn)
- **Phản hồi AI**: tóm tắt những gì AI đã làm / sinh ra
- **Kiểm chứng**: bạn đã chạy thử chưa, có sửa gì không, kết quả test pass/fail


Dựa trên việc đọc và phân tích 3 tài liệu đặc tả (Prompt.md, ai_prompt_log.md, api_contract.md) cùng với mã nguồn thực tế của dự án, mình xin đưa ra đánh giá chi tiết cho các câu hỏi của bạn như sau:

1. Các file sinh ra có hoạt động được và đúng như mong muốn không?
Trả lời: CÓ, hoạt động rất tốt và bám sát 100% tài liệu đặc tả. Qua 3 lần làm việc (sinh module Auth, Suppliers và Goods), code được tạo ra tuân thủ cực kỳ nghiêm ngặt các quy tắc đã đề ra trong api_contract.md và Prompt.md:

Module Auth: Xử lý mã hóa mật khẩu an toàn với bcrypt, cấp phát JWT đúng chuẩn, có API /api/auth/me để lấy thông tin.
Module Suppliers: Đủ 5 endpoint, xử lý phân trang chuẩn mực. Đặc biệt, chức năng DELETE tuân thủ đúng yêu cầu nghiệp vụ là soft-delete (chỉ đổi trạng thái sang inactive thay vì xóa hẳn trong CSDL để bảo vệ dữ liệu lịch sử).
Module Goods: Đủ 5 endpoint, có API riêng biệt /api/goods/low-stock để hiển thị hàng dưới định mức.
Chuẩn mực thiết kế: Các lỗi trả về đều đúng cấu trúc {"error_code": "SCREAMING_SNAKE_CASE", "message": "..."}.
2. Có kết nối với nhau không hay "mỗi module chơi 1 kiểu"?
Trả lời: ĐƯỢC KẾT NỐI VÀ QUY HOẠCH RẤT ĐỒNG BỘ, NHẤT QUÁN. Không hề có tình trạng "mỗi module chơi 1 kiểu", mà cả 3 module đều tuân theo một kiến trúc thống nhất (Application Factory Pattern):

Quản lý tập trung tại main.py: Tất cả các module đều đăng ký Blueprint tại main.py. Việc xử lý lỗi (400, 401, 403, 404, 500) và lỗi JWT đều được quy về một mối tại main.py, giúp toàn bộ hệ thống trả về thông báo lỗi có cấu trúc giống hệt nhau.
Bảo mật đồng bộ: Cả module Suppliers và Goods đều dùng chung hệ thống JWT auth và decorator @roles_required("admin", "warehouse_manager", ...) phân quyền cực kỳ chặt chẽ đến từng endpoint.
Kết nối CSDL (Giải quyết Nợ kỹ thuật): Trong file ai_prompt_log.md (ngày 08/08) có ghi nhận việc "bị lỗi mapper vì các bảng chưa tồn tại". Hiện tại, khi check mã nguồn models/supplier.py và models/goods.py, AI đã kết nối thành công khóa ngoại (preferred_supplier_id) từ Goods sang Supplier. Chúng đã giao tiếp được với nhau dưới DB.
3. Có thể hoạt động như 1 hệ thống quản lý kho không?
Trả lời: HIỆN TẠI THÌ CHƯA. Hệ thống hiện tại mới chỉ là "nền móng" (quản lý danh mục cơ sở). Để thực sự được gọi là hệ thống quản lý kho, hệ thống đang thiếu đi các "Nghiệp vụ cốt lõi" (Core Business Logic) như đã định nghĩa trong Prompt.md và api_contract.md:

❌ Chưa có Phiếu nhập kho (Goods Receipts) & Phiếu xuất kho (Goods Issues): Hiện tại hàng hóa Goods đang có cột quantity_on_hand, nhưng chưa có tính năng nào tác động (cộng/trừ) một cách hợp lệ thông qua giao dịch (transaction) phiếu nhập/xuất để ngăn việc kho bị xuất âm.
❌ Chưa có Đơn đặt hàng (Purchase Orders) & Công nợ: Chưa liên kết được với Nhà cung cấp.
❌ Chưa có Kiểm kê định kỳ (Stocktakes).
❌ Chưa có AI Engine: 2 tính năng trí tuệ nhân tạo (sinh báo cáo và gợi ý nhập hàng) chưa được viết.
(Trạng thái trong file api_contract.md hiện tại cho các module này vẫn đang là ⬜ Chưa điền).

Tóm lại: 3 lần làm việc trước đã tạo ra một bộ khung kiến trúc hoàn hảo, code sạch, tính gắn kết cao và cực kỳ chuẩn mực. Bạn có thể tự tin sử dụng bộ khung này.