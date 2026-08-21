/* =====================================================
   utils.js — Các hàm tiện ích dùng chung toàn ứng dụng
   ===================================================== */

const utils = {

  /* Format số tiền VND: 1500000 → "1.500.000 ₫" */
  formatCurrency(amount) {
    if (amount === null || amount === undefined) return '—';
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount);
  },

  /* Format ngày giờ ISO → "21/08/2026 09:30" */
  formatDateTime(isoStr) {
    if (!isoStr) return '—';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString('vi-VN') + ' ' +
        d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
    } catch { return isoStr; }
  },

  /* Format ngày ISO → "21/08/2026" */
  formatDate(isoStr) {
    if (!isoStr) return '—';
    try {
      return new Date(isoStr).toLocaleDateString('vi-VN');
    } catch { return isoStr; }
  },

  /* Escape HTML để tránh XSS */
  escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  },

  /* Tóm tắt chuỗi dài */
  truncate(str, maxLen = 50) {
    if (!str) return '';
    return str.length > maxLen ? str.substring(0, maxLen) + '…' : str;
  },

  /* Debounce cho search input */
  debounce(fn, delay = 300) {
    let timer;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), delay);
    };
  },

  /* Badge trạng thái hàng hóa / nhà cung cấp */
  statusBadge(status) {
    if (status === 'active') return `<span class="badge badge-status-active">Đang hoạt động</span>`;
    return `<span class="badge badge-status-inactive">Ngừng hoạt động</span>`;
  },

  /* Badge trạng thái đơn đặt hàng */
  poBadge(status) {
    const map = {
      'chờ xác nhận': 'bg-warning text-dark',
      'đã xác nhận':  'bg-info text-dark',
      'đang giao':    'bg-primary',
      'đã nhận':      'bg-success',
      'hủy':          'bg-danger',
    };
    const cls = map[status] || 'bg-secondary';
    return `<span class="badge ${cls}">${this.escapeHtml(status)}</span>`;
  },

  /* Badge trạng thái thanh toán */
  paymentBadge(status) {
    const map = {
      'chưa thanh toán':      'bg-danger',
      'thanh toán một phần':  'bg-warning text-dark',
      'đã thanh toán':        'bg-success',
    };
    const cls = map[status] || 'bg-secondary';
    return `<span class="badge ${cls}">${this.escapeHtml(status)}</span>`;
  },

  /* Badge trạng thái kiểm kê */
  stocktakeBadge(status) {
    const map = {
      'đang kiểm kê':  'bg-info text-dark',
      'chờ phê duyệt': 'bg-warning text-dark',
      'đã phê duyệt':  'bg-success',
    };
    const cls = map[status] || 'bg-secondary';
    return `<span class="badge ${cls}">${this.escapeHtml(status)}</span>`;
  },

  /* Hiển thị toast notification ở góc phải trên
     type: 'success' | 'danger' | 'warning' | 'info' */
  showToast(message, type = 'success') {
    // Tạo container nếu chưa có
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.className = 'toast-container position-fixed top-0 end-0 p-3';
      document.body.appendChild(container);
    }

    const icons = { success: 'bi-check-circle-fill', danger: 'bi-x-circle-fill',
                    warning: 'bi-exclamation-triangle-fill', info: 'bi-info-circle-fill' };
    const icon = icons[type] || 'bi-info-circle-fill';

    const toastEl = document.createElement('div');
    toastEl.className = `toast align-items-center text-bg-${type} border-0`;
    toastEl.setAttribute('role', 'alert');
    toastEl.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">
          <i class="bi ${icon} me-2"></i>${this.escapeHtml(message)}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>`;
    container.appendChild(toastEl);

    const toast = new bootstrap.Toast(toastEl, { delay: 4000 });
    toast.show();
    toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
  },

  /* Modal xác nhận trước hành động nguy hiểm (xóa/hủy)
     Trả về Promise<boolean> */
  confirmDialog(title = 'Xác nhận', message = 'Bạn có chắc chắn không?') {
    return new Promise(resolve => {
      // Tạo modal xác nhận
      let modal = document.getElementById('confirm-modal');
      if (!modal) {
        modal = document.createElement('div');
        modal.id = 'confirm-modal';
        modal.className = 'modal fade';
        modal.innerHTML = `
          <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title" id="confirm-modal-title"></h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
              </div>
              <div class="modal-body" id="confirm-modal-body"></div>
              <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Hủy bỏ</button>
                <button type="button" class="btn btn-danger" id="confirm-modal-ok">Xác nhận</button>
              </div>
            </div>
          </div>`;
        document.body.appendChild(modal);
      }
      document.getElementById('confirm-modal-title').textContent = title;
      document.getElementById('confirm-modal-body').textContent = message;

      const bsModal = bootstrap.Modal.getOrCreateInstance(modal);

      const okBtn = document.getElementById('confirm-modal-ok');
      const newOkBtn = okBtn.cloneNode(true); // Remove old listeners
      okBtn.parentNode.replaceChild(newOkBtn, okBtn);

      newOkBtn.addEventListener('click', () => { bsModal.hide(); resolve(true); });
      modal.addEventListener('hidden.bs.modal', () => resolve(false), { once: true });

      bsModal.show();
    });
  },

  /* Render phân trang Bootstrap vào container
     onPageChange(newPage) callback */
  renderPagination(containerId, total, page, pageSize, onPageChange) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const totalPages = Math.ceil(total / pageSize);
    if (totalPages <= 1) { container.innerHTML = ''; return; }

    let html = `<nav><ul class="pagination pagination-sm mb-0">`;

    // Nút Trước
    html += `<li class="page-item ${page <= 1 ? 'disabled' : ''}">
      <a class="page-link" href="#" data-page="${page - 1}">«</a></li>`;

    // Số trang (hiển thị tối đa 5 trang xung quanh trang hiện tại)
    const range = 2;
    for (let p = Math.max(1, page - range); p <= Math.min(totalPages, page + range); p++) {
      html += `<li class="page-item ${p === page ? 'active' : ''}">
        <a class="page-link" href="#" data-page="${p}">${p}</a></li>`;
    }

    // Nút Sau
    html += `<li class="page-item ${page >= totalPages ? 'disabled' : ''}">
      <a class="page-link" href="#" data-page="${page + 1}">»</a></li>`;

    html += `</ul></nav>
      <small class="text-muted ms-2">Tổng: ${total} bản ghi</small>`;
    container.innerHTML = html;

    // Gắn sự kiện click
    container.querySelectorAll('.page-link').forEach(a => {
      a.addEventListener('click', e => {
        e.preventDefault();
        const p = parseInt(a.dataset.page);
        if (p >= 1 && p <= totalPages && p !== page) onPageChange(p);
      });
    });
  },

  /* Format số lượng (loại bỏ số thập phân không cần thiết) */
  formatQty(n) {
    if (n === null || n === undefined) return '—';
    return parseFloat(n).toLocaleString('vi-VN');
  },
};
