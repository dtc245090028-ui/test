# AGENTS.md — Hệ thống quản lý kho có tích hợp AI

> File này là bản rút gọn của `Prompt.md` gốc (đặc tả hợp nhất). Đọc file này
> ĐẦU TIÊN mỗi phiên làm việc trước khi code. Nếu cần chi tiết đầy đủ (use case,
> test case, rubric...), tham chiếu `Prompt.md` ở gốc project.

## 1. Vai trò & ràng buộc bắt buộc

- Đây là đồ án môn học, sinh viên phải GIẢI THÍCH ĐƯỢC mọi dòng code — comment
  đầy đủ, không "hộp đen".
- Ưu tiên MVP đúng nghiệp vụ trước, tối ưu sau.
- Sau khi hoàn thành 1 module hoặc tối ưu 1 prompt AI: chủ động nhắc sinh viên
  ghi vào `docs/ai_prompt_log.md`.
- Không tự ý mở rộng phạm vi (feature creep). Bám sát đặc tả — nếu cần thêm gì
  ngoài phạm vi, hỏi trước khi làm.

## 2. Nguyên tắc xuyên suốt

**AI là lớp hỗ trợ, không phải nghiệp vụ lõi.** Nếu AI service sập, phần quản
lý kho (nhập/xuất/tồn/kiểm kê) vẫn phải chạy bình thường.

## 3. Stack

| Lớp | Chọn |
|---|---|
| Backend | Flask (Python) |
| Frontend | React hoặc HTML/JS + Bootstrap |
| CSDL | SQLite (dev/demo) → PostgreSQL (nếu triển khai thật) |
| AI | Gemini API mặc định, đổi được qua `.env` (`AI_PROVIDER`) |

## 4. Cấu trúc thư mục cố định — KHÔNG tự đổi

```
warehouse-ai-system/
├── backend/
│   ├── app/
│   │   ├── models/            # SQLAlchemy models — theo đúng bảng mục 6
│   │   ├── routers/           # 1 file/module nghiệp vụ, xem docs/api_contract.md
│   │   ├── auth/              # JWT, phân quyền theo role
│   │   ├── ai/
│   │   │   ├── prompts/       # BẮT BUỘC tách prompt khỏi code
│   │   │   ├── inventory_report_service.py
│   │   │   ├── reorder_suggestion_service.py
│   │   │   └── scheduler.py
│   │   ├── schemas/           # Pydantic/Marshmallow — validate input
│   │   └── main.py
│   ├── tests/
│   ├── .env.example
│   └── requirements.txt
├── frontend/
├── database/
│   └── seed_data.sql
├── docs/
│   ├── api_contract.md        # nguồn sự thật cho mọi endpoint
│   ├── ai_prompt_log.md
│   ├── test_report.md
│   └── final_report.md
└── README.md
```

## 5. Quy ước đặt tên — BẮT BUỘC theo, không tự sáng tạo

- DB field & JSON key: `snake_case` (VD: `quantity_on_hand`, `unit_price`).
- Route path: số nhiều, kebab-case nếu ghép từ (VD: `/api/goods-receipts`).
- Trước khi tạo field/API mới không có trong `docs/api_contract.md` hoặc
  `Prompt.md` mục 6 → phải hỏi lại hoặc cập nhật tài liệu trước, không tự bịa.

## 6. Danh sách bảng CSDL (tóm tắt — chi tiết ở `Prompt.md` mục 6)

`users`, `suppliers`, `categories`, `goods`, `purchase_orders`,
`purchase_order_items`, `goods_receipts`, `goods_receipt_items`,
`goods_issues`, `goods_issue_items`, `stocktakes`, `stocktake_items`,
`supplier_invoices`, `supplier_payments`, `ai_interaction_logs`.

## 7. Ràng buộc nghiệp vụ tối quan trọng — KHÔNG được vi phạm

1. `goods.quantity_on_hand` chỉ đổi qua transaction (nhập/xuất/kiểm kê) —
   chặn ở tầng CSDL/ORM để **không bao giờ về âm**.
2. `goods_receipt_items.unit_price` lưu cố định theo từng lần nhập, **không**
   tính lại từ giá hiện tại của `goods` — đây là nguồn duy nhất để tính giá vốn.
3. Kiểm kê: Thủ kho đề xuất → Quản lý kho phê duyệt → mới cập nhật tồn kho.
   Không cho cập nhật tồn trực tiếp từ đề xuất chưa duyệt.
4. AI chỉ phân tích số liệu được cung cấp, không tự bịa số liệu ngoài input.
5. Mọi output AI phải kèm dòng cảnh báo: *"Gợi ý từ AI chỉ mang tính tham
   khảo, không tự động tạo phiếu nhập/xuất kho."*

## 8. Chuẩn response lỗi — dùng thống nhất mọi API

```json
{
  "error_code": "OUT_OF_STOCK",
  "message": "Số lượng xuất vượt tồn kho hiện có"
}
```

`error_code` viết SCREAMING_SNAKE_CASE, `message` luôn bằng tiếng Việt, rõ ràng.

## 9. Bảo mật — luôn nhớ

- API key AI/DB chỉ đọc từ `.env`, không hardcode, không commit `.env` thật.
- Không gửi giá nhập/giá bán/thông tin liên hệ NCC lên AI nếu tác vụ không cần.
- Phân quyền kiểm tra ở **backend** (route level), không chỉ ẩn UI.

## 10. Quy trình làm việc mỗi module (theo mục 14 của `Prompt.md`)

1. Xác nhận phạm vi & giả định trước khi code nếu có gì chưa rõ.
2. Tạo cấu trúc thư mục/file liên quan trước.
3. Triển khai tuần tự.
4. Sau khi xong: tóm tắt file đã tạo/sửa + cách test (curl/lệnh chạy thử) +
   xác nhận field/API mới (nếu có) đã được thêm vào `docs/api_contract.md`.
5. Nhắc ghi nhật ký AI vào `docs/ai_prompt_log.md`.
