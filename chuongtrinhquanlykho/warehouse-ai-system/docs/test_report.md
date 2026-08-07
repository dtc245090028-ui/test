# Báo cáo kiểm thử — Hệ thống quản lý kho

> Ghi lại kết quả test theo bảng ca kiểm thử mục 10 Prompt.md.
> Sau mỗi lần chạy test, cập nhật Pass/Fail và ghi chú.

## Kết quả test module Auth

| Ca kiểm thử | Test function | Kết quả | Ngày test | Ghi chú |
|---|---|---|---|---|
| Đăng nhập hợp lệ | `test_login_success` | ⬜ Chưa chạy | | |
| Sai password | `test_login_wrong_password` | ⬜ Chưa chạy | | |
| Username không tồn tại | `test_login_wrong_username` | ⬜ Chưa chạy | | |
| Thiếu field | `test_login_missing_fields` | ⬜ Chưa chạy | | |
| Body rỗng | `test_login_empty_body` | ⬜ Chưa chạy | | |
| Tài khoản bị khóa | `test_login_inactive_account` | ⬜ Chưa chạy | | |
| GET /me token hợp lệ | `test_me_with_valid_token` | ⬜ Chưa chạy | | |
| GET /me không có token | `test_me_without_token` | ⬜ Chưa chạy | | |
| GET /me token giả | `test_me_with_invalid_token` | ⬜ Chưa chạy | | |
| Logout thành công | `test_logout_success` | ⬜ Chưa chạy | | |
| Logout không có token | `test_logout_without_token` | ⬜ Chưa chạy | | |

*(Đổi ⬜ → ✅ Pass hoặc ❌ Fail sau khi chạy `pytest tests/test_auth.py -v`)*
