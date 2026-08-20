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

## Kết quả test module Reports (Thống kê/báo cáo)

| Ca kiểm thử | Test function | Kết quả | Ngày test | Ghi chú |
|---|---|---|---|---|
| Tính avg_cost đúng từ goods_receipt_items | `test_tc01_inventory_value_correct_avg_cost` | ✅ Pass | 2026-08-20 | |
| Filter category_id đúng | `test_tc02_inventory_value_filter_category` | ✅ Pass | 2026-08-20 | |
| Hàng chưa nhập avg_cost = 0 | `test_tc03_inventory_value_no_receipt` | ✅ Pass | 2026-08-20 | |
| Tính vòng quay đúng; is_slow_moving đúng | `test_tc04_turnover_correct_rate` | ✅ Pass | 2026-08-20 | |
| Hàng tồn = 0 turnover_rate = None | `test_tc05_turnover_zero_stock` | ✅ Pass | 2026-08-20 | |
| Top nhập đúng thứ hạng | `test_tc06_top_goods_receipt_ranking` | ✅ Pass | 2026-08-20 | |
| type="issue" chỉ trả top_issue | `test_tc07_top_goods_issue_only` | ✅ Pass | 2026-08-20 | |
| top_n limit đúng | `test_tc08_top_goods_limit_topn` | ✅ Pass | 2026-08-20 | |
| Chỉ lấy stocktake đã phê duyệt | `test_tc09_stocktake_diff_approved_only` | ✅ Pass | 2026-08-20 | |
| Filter has_diff=true | `test_tc10_stocktake_diff_has_diff_filter` | ✅ Pass | 2026-08-20 | |
| Tính đúng total_shortage, total_surplus | `test_tc11_stocktake_diff_summary` | ✅ Pass | 2026-08-20 | |
| Lỗi date_from sai định dạng | `test_tc12_invalid_date_format` | ✅ Pass | 2026-08-20 | |
| Lỗi top_n=0 | `test_tc13_invalid_topn` | ✅ Pass | 2026-08-20 | |
| Lỗi type="abc" | `test_tc14_invalid_type_param` | ✅ Pass | 2026-08-20 | |
| Lỗi slow_moving_threshold sai | `test_tc15_invalid_threshold` | ✅ Pass | 2026-08-20 | |
| Keeper không có quyền xem | `test_tc16_keeper_forbidden` | ✅ Pass | 2026-08-20 | |
| Không có token | `test_tc17_no_token` | ✅ Pass | 2026-08-20 | |

*(Đã cập nhật sau khi chạy `pytest tests/test_reports.py -v`)*
