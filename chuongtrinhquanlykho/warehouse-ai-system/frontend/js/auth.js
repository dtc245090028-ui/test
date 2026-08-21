/* =====================================================
   auth.js — Quản lý xác thực, phân quyền, user info
   ===================================================== */

const auth = {

  /* Kiểm tra đã đăng nhập chưa (có token không) */
  isLoggedIn() {
    return !!localStorage.getItem('access_token');
  },

  /* Lấy thông tin user từ localStorage */
  getUser() {
    try {
      return JSON.parse(localStorage.getItem('user_info') || '{}');
    } catch {
      return {};
    }
  },

  /* Lấy role của user: 'admin' | 'warehouse_manager' | 'warehouse_keeper' */
  getRole() {
    return localStorage.getItem('user_role') || '';
  },

  /* Kiểm tra user có role trong danh sách cho phép không
     Ví dụ: auth.hasRole(['admin','warehouse_manager']) */
  hasRole(roles = []) {
    return roles.includes(this.getRole());
  },

  /* Đăng xuất: xóa localStorage, redirect về trang login */
  logout() {
    // Gọi API logout (fire-and-forget, không cần await)
    try {
      const token = localStorage.getItem('access_token');
      if (token) {
        fetch('/api/auth/logout', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` }
        });
      }
    } catch { /* bỏ qua lỗi logout */ }

    localStorage.removeItem('access_token');
    localStorage.removeItem('user_role');
    localStorage.removeItem('user_info');
    window.location.href = '/index.html';
  },

  /* Yêu cầu đăng nhập: nếu chưa login redirect về index.html */
  requireLogin() {
    if (!this.isLoggedIn()) {
      window.location.href = '/index.html';
      return false;
    }
    return true;
  },

  /* Ẩn/hiện element theo role dựa trên attribute data-roles
     Ví dụ: <button data-roles="admin,warehouse_manager">
     Gọi sau khi DOM ready */
  applyRoleVisibility() {
    const role = this.getRole();
    document.querySelectorAll('[data-roles]').forEach(el => {
      const allowed = el.dataset.roles.split(',').map(r => r.trim());
      if (!allowed.includes(role)) {
        el.style.display = 'none';
      }
    });
  },

  /* Hiển thị tên role thân thiện bằng tiếng Việt */
  getRoleLabel() {
    const map = {
      admin: 'Ban điều hành',
      warehouse_manager: 'Quản lý kho',
      warehouse_keeper: 'Thủ kho',
    };
    return map[this.getRole()] || this.getRole();
  },
};
