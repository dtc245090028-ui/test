"""
scheduler.py — Tác vụ nền định kỳ (APScheduler)
==================================================
Nhiệm vụ:
  - Quét tồn kho mỗi 24h, tìm hàng dưới ngưỡng Min
  - Gọi AI sinh gợi ý nhập hàng → log vào ai_interaction_logs

Lưu ý thiết kế:
  - `_scheduler` là singleton ở module level (chỉ tạo 1 lần)
  - `init_scheduler(app)` có thể được gọi nhiều lần (Flask dev-reload,
    test fixture...) → dùng replace_existing=True và guard `running`
    để không bao giờ bị ConflictingIdError hay SchedulerAlreadyRunningError
"""

from apscheduler.schedulers.background import BackgroundScheduler

# Singleton scheduler — khởi tạo 1 lần khi module được import
_scheduler = BackgroundScheduler()


def check_low_stock(app):
    """
    Hàm được APScheduler gọi định kỳ.

    Quy trình:
      1. Truy vấn hàng hóa active có quantity_on_hand < min_stock
      2. Nếu có → gọi generate_reorder_suggestion() để AI phân tích
      3. Kết quả được log tự động vào bảng ai_interaction_logs
         bởi hàm generate_reorder_suggestion (không cần DB riêng)
    """
    with app.app_context():
        # Import lazy để tránh circular import khi module load
        from app.models.goods import Goods
        from app.ai.reorder_suggestion_service import generate_reorder_suggestion

        app.logger.info("🔄 [Scheduler] Bắt đầu quét tồn kho dưới ngưỡng Min...")

        low_stock_items = Goods.query.filter(
            Goods.status == 'active',
            Goods.min_stock > 0,
            Goods.quantity_on_hand < Goods.min_stock
        ).all()

        if not low_stock_items:
            app.logger.info("✅ [Scheduler] Không có mặt hàng nào dưới ngưỡng tối thiểu.")
            return

        # Chuẩn bị dữ liệu gửi cho AI (chỉ các trường cần thiết — bảo mật)
        reorder_data = [
            {
                "sku": item.sku,
                "name": item.name,
                "quantity_on_hand": float(item.quantity_on_hand),
                "min_stock": float(item.min_stock),
            }
            for item in low_stock_items
        ]

        app.logger.info(
            f"⚠️ [Scheduler] Phát hiện {len(reorder_data)} mặt hàng dưới ngưỡng Min. "
            "Bắt đầu gọi AI..."
        )

        # Gọi AI sinh gợi ý — kết quả được log vào ai_interaction_logs tự động
        result = generate_reorder_suggestion(reorder_data, user_id=None)

        if "error" in result:
            app.logger.error(f"❌ [Scheduler] Lỗi khi gọi AI: {result['error']}")
        else:
            suggestions = result.get("reorder_suggestions", [])
            app.logger.info(
                f"💡 [Scheduler] AI đã sinh {len(suggestions)} gợi ý nhập hàng thành công."
            )


def init_scheduler(app):
    """
    Đăng ký job và khởi động scheduler (nếu chưa chạy).

    An toàn khi gọi nhiều lần:
      - replace_existing=True: ghi đè job cũ nếu đã tồn tại (không raise ConflictingIdError)
      - Guard `_scheduler.running`: không gọi start() nếu đã running
        (tránh SchedulerAlreadyRunningError khi Flask debug-reload)
    """
    # Đăng ký (hoặc cập nhật) job — không raise lỗi nếu job ID đã tồn tại
    _scheduler.add_job(
        func=check_low_stock,
        trigger="interval",
        hours=24,
        args=[app],
        id="check_low_stock_job",
        replace_existing=True,   # ← quan trọng: tránh ConflictingIdError
    )

    # Chỉ start nếu scheduler chưa chạy
    if not _scheduler.running:
        _scheduler.start()
        app.logger.info("✅ [Scheduler] Tác vụ lập lịch đã được khởi động.")
    else:
        app.logger.info("ℹ️ [Scheduler] Scheduler đang chạy, job đã được cập nhật.")

