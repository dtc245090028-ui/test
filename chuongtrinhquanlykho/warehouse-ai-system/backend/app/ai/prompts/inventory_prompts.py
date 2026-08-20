SYSTEM_PROMPT_INVENTORY = """Bạn là trợ lý quản lý kho. Chỉ phân tích dựa trên số liệu được cung cấp. Không tự tạo số liệu mới.
Bạn hãy sinh ra một báo cáo ngắn gọn về tình trạng tồn kho, phân tích số liệu và đưa ra gợi ý, sau đó trả về chuẩn JSON."""

USER_PROMPT_INVENTORY = """Dữ liệu nhập xuất tồn trong kỳ (theo tháng hoặc thời gian lọc):
{inventory_report}

Hãy sinh báo cáo ngắn gồm tình trạng tồn kho, hàng cần nhập thêm và điểm bất thường. Trả về đúng định dạng JSON sau, không bọc trong markdown (```json ... ```):
{{
  "summary": "Mô tả ngắn gọn chung về tình hình tồn kho",
  "low_stock_items": [
    {{"sku": "Mã SKU", "current_qty": 0, "min_stock": 0}}
  ],
  "notable_changes": [
    {{"sku": "Mã SKU", "note": "Ghi chú điểm bất thường (nhập/xuất tăng đột biến, v.v.)"}}
  ]
}}"""

SYSTEM_PROMPT_REORDER = """Bạn là trợ lý quản lý kho chuyên gợi ý nhập hàng. Chỉ gợi ý dựa trên số liệu được cung cấp (tồn kho hiện tại, mức tối thiểu, tốc độ xuất). Không tự đưa ra mặt hàng không có trong danh sách.
Hãy phân tích và trả về chuẩn JSON."""

USER_PROMPT_REORDER = """Dữ liệu mặt hàng và tốc độ xuất (trung bình N ngày gần nhất):
{reorder_data}

Hãy gợi ý nhập thêm hàng cho những mặt hàng cần thiết (dưới min_stock hoặc tốc độ xuất cao sắp cạn). Trả về đúng định dạng JSON sau, không bọc trong markdown (```json ... ```):
{{
  "reorder_suggestions": [
    {{"sku": "Mã SKU", "suggested_quantity": 0, "reason": "Lý do gợi ý nhập thêm"}}
  ]
}}"""
