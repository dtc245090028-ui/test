/* =====================================================
   layout.js — Render sidebar navigation và top navbar
   Inject HTML vào #sidebar-container và #topbar-container
   ===================================================== */

/* Danh sách menu item — icon Bootstrap Icons, label, href, roles được phép */
const MENU_ITEMS = [
  { icon: 'bi-speedometer2', label: 'Dashboard',         href: '/dashboard.html',             roles: ['admin','warehouse_manager','warehouse_keeper'] },
  { icon: 'bi-truck',        label: 'Nhà cung cấp',      href: '/pages/suppliers.html',        roles: ['admin','warehouse_manager'] },
  { icon: 'bi-box-seam',     label: 'Hàng hóa',          href: '/pages/goods.html',            roles: ['admin','warehouse_manager','warehouse_keeper'] },
  { icon: 'bi-cart-plus',    label: 'Đơn đặt hàng',      href: '/pages/purchase-orders.html',  roles: ['admin','warehouse_manager','warehouse_keeper'] },
  { icon: 'bi-arrow-down-circle', label: 'Phiếu nhập kho', href: '/pages/goods-receipts.html', roles: ['admin','warehouse_manager','warehouse_keeper'] },
  { icon: 'bi-arrow-up-circle',   label: 'Phiếu xuất kho', href: '/pages/goods-issues.html',   roles: ['admin','warehouse_manager','warehouse_keeper'] },
  { icon: 'bi-clipboard-check',   label: 'Kiểm kê kho',    href: '/pages/stocktakes.html',     roles: ['admin','warehouse_manager','warehouse_keeper'] },
  { icon: 'bi-receipt',      label: 'Hóa đơn & Công nợ', href: '/pages/invoices.html',         roles: ['admin','warehouse_manager'] },
  { icon: 'bi-bar-chart-line', label: 'Báo cáo thống kê', href: '/pages/reports.html',         roles: ['admin','warehouse_manager'] },
  { icon: 'bi-robot',        label: 'AI Trợ lý',          href: '/pages/ai-features.html',     roles: ['admin','warehouse_manager','warehouse_keeper'] },
];

/* Đường dẫn prefix để xác định item active */
function isActiveLink(href) {
  const current = window.location.pathname;
  return current === href || current.endsWith(href);
}

/* Render toàn bộ layout (sidebar + topbar) */
function renderLayout() {
  const role = auth.getRole();
  const user = auth.getUser();
  const currentPath = window.location.pathname;

  /* ----- Render SIDEBAR ----- */
  const sidebarContainer = document.getElementById('sidebar-container');
  if (sidebarContainer) {
    // Lọc menu theo role
    const visibleItems = MENU_ITEMS.filter(item => item.roles.includes(role));

    const navLinks = visibleItems.map(item => {
      const active = isActiveLink(item.href) ? 'active' : '';
      return `
        <a href="${item.href}" class="${active}" title="${item.label}">
          <i class="bi ${item.icon}"></i>
          <span class="nav-label ms-2">${item.label}</span>
        </a>`;
    }).join('');

    sidebarContainer.innerHTML = `
      <div id="sidebar">
        <!-- Brand logo -->
        <div class="sidebar-brand">
          <span class="brand-icon"><i class="bi bi-boxes"></i></span>
          <span class="brand-text">Quản lý Kho</span>
        </div>

        <!-- Navigation links -->
        <nav class="sidebar-nav">
          ${navLinks}
        </nav>

        <!-- Footer sidebar: version -->
        <div class="sidebar-footer d-flex align-items-center" style="white-space:nowrap;overflow:hidden;">
          <i class="bi bi-info-circle text-muted" style="min-width:38px;text-align:center;"></i>
          <small class="nav-label text-muted">v1.0 — Đồ án 2026</small>
        </div>
      </div>
      <!-- Overlay mobile -->
      <div class="sidebar-overlay" id="sidebar-overlay"></div>
    `;
  }

  /* ----- Render TOPBAR ----- */
  const topbarContainer = document.getElementById('topbar-container');
  if (topbarContainer) {
    const roleLabel = auth.getRoleLabel();
    const roleBadgeClass = {
      admin: 'bg-danger',
      warehouse_manager: 'bg-primary',
      warehouse_keeper: 'bg-success',
    }[role] || 'bg-secondary';

    topbarContainer.innerHTML = `
      <div id="topbar">
        <!-- Nút toggle sidebar -->
        <button id="sidebar-toggle" class="btn btn-sm btn-outline-secondary" title="Thu/mở menu">
          <i class="bi bi-list fs-5"></i>
        </button>

        <!-- Tiêu đề trang (được set bởi mỗi trang) -->
        <span class="page-title" id="page-title-text">Hệ thống Quản lý Kho</span>

        <div class="ms-auto d-flex align-items-center gap-2">
          <!-- Badge role -->
          <span class="badge ${roleBadgeClass} d-none d-md-inline">${roleLabel}</span>

          <!-- Dropdown user -->
          <div class="dropdown">
            <button class="btn btn-sm btn-outline-secondary dropdown-toggle" data-bs-toggle="dropdown">
              <i class="bi bi-person-circle me-1"></i>
              <span class="d-none d-sm-inline">${utils.escapeHtml(user.full_name || user.username || 'User')}</span>
            </button>
            <ul class="dropdown-menu dropdown-menu-end">
              <li><span class="dropdown-item-text text-muted small">${utils.escapeHtml(user.username || '')}</span></li>
              <li><hr class="dropdown-divider"></li>
              <li>
                <a class="dropdown-item text-danger" href="#" id="btn-logout">
                  <i class="bi bi-box-arrow-right me-2"></i>Đăng xuất
                </a>
              </li>
            </ul>
          </div>
        </div>
      </div>
    `;

    /* Gắn sự kiện logout */
    document.getElementById('btn-logout')?.addEventListener('click', async (e) => {
      e.preventDefault();
      const ok = await utils.confirmDialog('Đăng xuất', 'Bạn có muốn đăng xuất khỏi hệ thống?');
      if (ok) auth.logout();
    });

    /* Toggle sidebar */
    document.getElementById('sidebar-toggle')?.addEventListener('click', () => {
      const sidebar = document.getElementById('sidebar');
      const mainWrapper = document.getElementById('main-wrapper');
      const overlay = document.getElementById('sidebar-overlay');

      if (window.innerWidth <= 768) {
        // Mobile: overlay mode
        sidebar?.classList.toggle('mobile-open');
        overlay?.classList.toggle('visible');
      } else {
        // Desktop: collapse mode
        sidebar?.classList.toggle('collapsed');
        mainWrapper?.classList.toggle('expanded');
      }
    });

    /* Click overlay để đóng sidebar trên mobile */
    document.getElementById('sidebar-overlay')?.addEventListener('click', () => {
      document.getElementById('sidebar')?.classList.remove('mobile-open');
      document.getElementById('sidebar-overlay')?.classList.remove('visible');
    });
  }

  /* Áp dụng ẩn/hiện theo role */
  auth.applyRoleVisibility();
}

/* Hàm tiện ích: set tiêu đề trang trên topbar */
function setPageTitle(title) {
  const el = document.getElementById('page-title-text');
  if (el) el.textContent = title;
  document.title = title + ' — Quản lý Kho';
}

/* Tự động gọi khi DOM ready */
document.addEventListener('DOMContentLoaded', () => {
  // Kiểm tra đăng nhập trước khi render layout
  if (!auth.requireLogin()) return;
  renderLayout();
});
