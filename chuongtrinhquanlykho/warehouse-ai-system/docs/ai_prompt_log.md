# Nhật ký sử dụng AI — Hệ thống quản lý kho

> Đây là minh chứng bắt buộc chấm điểm. Ghi lại **mỗi lần** dùng AI để sinh code,
> thiết kế, tối ưu prompt, hoặc review code.

| Ngày | Giai đoạn | Mục đích | Prompt (rút gọn) | Phản hồi AI (tóm tắt) | Đã kiểm chứng/chỉnh sửa | Người thực hiện |
|---|---|---|---|---|---|---|
| 2026-08-04 | KT2 | Dựng khung + module Auth | "Đọc AGENTS.md, Prompt.md, api_contract.md → dựng cấu trúc thư mục + requirements.txt + seed_data.sql + .env.example + Auth module (bcrypt, JWT, role middleware)" | Tạo 12 file: extensions.py, models/user.py, auth/routes.py, auth/decorators.py, main.py, tests/test_auth.py, requirements.txt, .env.example, seed_data.sql, các placeholder package | Cần kiểm tra bcrypt hash trong seed_data.sql khớp với Password@123 | Sinh viên |

---

## Ghi chú cách điền

- **Giai đoạn**: KT1 / KT2 / KT3 / Cuối kỳ
- **Prompt (rút gọn)**: tóm tắt nội dung prompt gửi AI (không cần copy nguyên văn)
- **Phản hồi AI**: tóm tắt những gì AI đã làm / sinh ra
- **Kiểm chứng**: bạn đã chạy thử chưa, có sửa gì không, kết quả test pass/fail
