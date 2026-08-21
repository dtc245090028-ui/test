/* =====================================================
   api.js — Wrapper cho Fetch API gọi backend
   Xử lý tập trung: thêm JWT header, parse lỗi chuẩn
   Base URL: /api
   ===================================================== */

const API_BASE = '/api';

const api = {

  /* Lấy JWT token từ localStorage */
  getToken() {
    return localStorage.getItem('access_token') || '';
  },

  /* Build headers có Authorization + Content-Type */
  buildHeaders(extra = {}) {
    const token = this.getToken();
    const h = { 'Content-Type': 'application/json', ...extra };
    if (token) h['Authorization'] = `Bearer ${token}`;
    return h;
  },

  /* Xử lý response: parse JSON, ném lỗi có error_code nếu không ok */
  async handleResponse(res) {
    let body;
    try { body = await res.json(); } catch { body = {}; }

    if (!res.ok) {
      // Nếu 401 TOKEN_EXPIRED hoặc TOKEN_MISSING → redirect về login
      if (res.status === 401) {
        const code = body.error_code || '';
        if (code === 'TOKEN_EXPIRED' || code === 'TOKEN_MISSING' || code === 'TOKEN_INVALID') {
          // Chỉ redirect nếu không đang ở trang login
          if (!window.location.pathname.endsWith('index.html') && window.location.pathname !== '/') {
            localStorage.removeItem('access_token');
            localStorage.removeItem('user_role');
            localStorage.removeItem('user_info');
            window.location.href = '/index.html';
          }
        }
      }
      // Ném lỗi có đủ thông tin để UI hiển thị
      const err = new Error(body.message || `HTTP ${res.status}`);
      err.error_code = body.error_code || `HTTP_${res.status}`;
      err.status = res.status;
      err.body = body;
      throw err;
    }
    return body;
  },

  /* Chuyển object params thành query string: {a:1, b:'x'} → '?a=1&b=x' */
  buildQuery(params = {}) {
    const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '');
    if (!entries.length) return '';
    return '?' + entries.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&');
  },

  /* GET /api{path}?{params} */
  async get(path, params = {}) {
    const url = `${API_BASE}${path}${this.buildQuery(params)}`;
    const res = await fetch(url, { method: 'GET', headers: this.buildHeaders() });
    return this.handleResponse(res);
  },

  /* POST /api{path} với JSON body */
  async post(path, body = {}) {
    const url = `${API_BASE}${path}`;
    const res = await fetch(url, {
      method: 'POST',
      headers: this.buildHeaders(),
      body: JSON.stringify(body),
    });
    return this.handleResponse(res);
  },

  /* PUT /api{path} với JSON body */
  async put(path, body = {}) {
    const url = `${API_BASE}${path}`;
    const res = await fetch(url, {
      method: 'PUT',
      headers: this.buildHeaders(),
      body: JSON.stringify(body),
    });
    return this.handleResponse(res);
  },

  /* DELETE /api{path} */
  async delete(path) {
    const url = `${API_BASE}${path}`;
    const res = await fetch(url, { method: 'DELETE', headers: this.buildHeaders() });
    return this.handleResponse(res);
  },
};
