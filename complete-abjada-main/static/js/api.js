const API_BASE = window.location.origin;
const TOKEN_KEY = 'token';
const USER_KEY = 'user';

function getToken() { return localStorage.getItem(TOKEN_KEY); }
function setToken(t) { localStorage.setItem(TOKEN_KEY, t); }
function clearToken() { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); }
function getUser() { try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null'); } catch { return null; } }
function setUser(u) { localStorage.setItem(USER_KEY, JSON.stringify(u)); }

function parseJwt(token) {
  try {
    if (!token || typeof token !== 'string') return null;
    const parts = token.split('.');
    if (parts.length < 2) return null;
    const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = payload + '='.repeat((4 - (payload.length % 4)) % 4);
    const json = decodeURIComponent(atob(padded).split('').map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)).join(''));
    return JSON.parse(json);
  } catch {
    return null;
  }
}

function getUserFromToken() {
  const token = getToken();
  const p = parseJwt(token);
  if (!p) return null;
  return {
    id: p.sub ?? null,
    username: p.username ?? null,
    role: p.role ?? null,
  };
}

function showToast(message, type = 'success', timeoutMs = 3000) {
  try {
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.textContent = message;
    document.body.appendChild(el);
    requestAnimationFrame(() => el.classList.add('show'));
    setTimeout(() => {
      el.classList.remove('show');
      setTimeout(() => el.remove(), 250);
    }, timeoutMs);
  } catch {
    // Fallback if DOM not ready
    alert(message);
  }
}

async function api(path, options = {}) {
  const url = path.startsWith('http') ? path : `${API_BASE}/api${path.startsWith('/') ? '' : '/'}${path}`;
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const token = getToken();
  if (token) headers['Authorization'] = 'Bearer ' + token;
  const res = await fetch(url, { ...options, headers: { ...headers, ...options.headers } });
  const data = await res.json().catch(async () => ({ message: await res.text().catch(() => '') }));
  // Failed sign-in also returns 401 — must not treat that like an expired session.
  const isAuthLogin =
    path === '/auth/login' ||
    path.startsWith('/auth/login?') ||
    url.indexOf('/api/auth/login') !== -1;
  if (res.status === 401 && !isAuthLogin) {
    clearToken();
    window.location.href = '/login';
    throw new Error('Session expired');
  }
  if (!res.ok) throw new Error(data.error || data.message || res.statusText);
  return data;
}

function apiBlob(path) {
  const url = path.startsWith('http') ? path : `${API_BASE}/api${path.startsWith('/') ? '' : '/'}${path}`;
  const headers = {};
  const token = getToken();
  if (token) headers['Authorization'] = 'Bearer ' + token;
  return fetch(url, { headers }).then(r => {
    if (r.status === 401) {
      clearToken();
      window.location.href = '/login';
      throw new Error('Session expired');
    }
    if (!r.ok) throw new Error('Download failed');
    return r.blob();
  });
}

/**
 * Fetches the order invoice PDF with auth and triggers a file download (not inline preview).
 */
async function downloadInvoicePdf(orderId) {
  try {
    const token = getToken();
    const url = `${API_BASE}/api/payments/invoice/${orderId}`;
    const res = await fetch(url, { headers: token ? { Authorization: 'Bearer ' + token } : {} });
    if (res.status === 401) {
      clearToken();
      window.location.href = '/login';
      return;
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showToast(err.error || 'Could not download invoice', 'error');
      return;
    }
    const blob = await res.blob();
    if (blob.type && blob.type.indexOf('application/json') === 0) {
      const t = await blob.text();
      try {
        const j = JSON.parse(t);
        showToast(j.error || 'Could not download invoice', 'error');
      } catch {
        showToast('Could not download invoice', 'error');
      }
      return;
    }
    const filename = `invoice_order_${orderId}.pdf`;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(a.href);
  } catch (e) {
    showToast(e.message || 'Download failed', 'error');
  }
}

/** Open a finance PDF in a new tab (preview / print from browser PDF viewer). Path is under /api, e.g. finance/reports/received.pdf */
async function openFinancePdf(apiPath) {
  try {
    const token = getToken();
    const path = apiPath.startsWith('/') ? apiPath : '/' + apiPath;
    const url = `${API_BASE}/api${path}`;
    const res = await fetch(url, { headers: token ? { Authorization: 'Bearer ' + token } : {} });
    if (res.status === 401) {
      clearToken();
      window.location.href = '/login';
      return;
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showToast(err.error || 'Could not open PDF', 'error');
      return;
    }
    const blob = await res.blob();
    if (blob.type && blob.type.indexOf('application/json') === 0) {
      const t = await blob.text();
      try {
        const j = JSON.parse(t);
        showToast(j.error || 'Could not open PDF', 'error');
      } catch {
        showToast('Could not open PDF', 'error');
      }
      return;
    }
    const objUrl = URL.createObjectURL(blob);
    window.open(objUrl, '_blank');
    setTimeout(() => URL.revokeObjectURL(objUrl), 120000);
  } catch (e) {
    showToast(e.message || 'Failed', 'error');
  }
}

/** Download finance PDF. Appends download=1 if missing. */
async function downloadFinancePdf(apiPath, filename) {
  try {
    const token = getToken();
    let path = apiPath.startsWith('/') ? apiPath : '/' + apiPath;
    if (path.indexOf('download=1') < 0) {
      path += (path.indexOf('?') >= 0 ? '&' : '?') + 'download=1';
    }
    const url = `${API_BASE}/api${path}`;
    const res = await fetch(url, { headers: token ? { Authorization: 'Bearer ' + token } : {} });
    if (res.status === 401) {
      clearToken();
      window.location.href = '/login';
      return;
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showToast(err.error || 'Download failed', 'error');
      return;
    }
    const blob = await res.blob();
    if (blob.type && blob.type.indexOf('application/json') === 0) {
      const t = await blob.text();
      try {
        const j = JSON.parse(t);
        showToast(j.error || 'Download failed', 'error');
      } catch {
        showToast('Download failed', 'error');
      }
      return;
    }
    const name = filename || 'report.pdf';
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(a.href);
  } catch (e) {
    showToast(e.message || 'Download failed', 'error');
  }
}

function requireAuth() {
  const token = getToken();
  if (!token) { window.location.href = '/login'; return null; }

  const cached = getUser();
  if (cached) return cached;

  // Fall back to JWT claims so pages still function even if localStorage user is missing.
  const fromToken = getUserFromToken();
  if (fromToken) {
    // Best-effort backfill full user in background
    api('/auth/me').then(u => setUser(u)).catch(() => {});
    return fromToken;
  }

  // Token is present but unreadable; force re-login
  clearToken();
  window.location.href = '/login';
  return null;
}

function ensureLogoutConfirmModal() {
  let modal = document.getElementById('logoutConfirmModal');
  if (modal) return modal;

  modal = document.createElement('div');
  modal.id = 'logoutConfirmModal';
  modal.className = 'modal hidden';
  modal.setAttribute('aria-hidden', 'true');
  modal.innerHTML = '' +
    '<div class="modal-content" style="max-width:760px;border-radius:14px;">' +
      '<div style="padding:10px 4px 8px;">' +
        '<h3 style="margin:0 0 8px;font-size:20px;font-weight:700;">Are you sure you want to log out?</h3>' +
        '<p style="margin:0;color:var(--text-muted);font-size:15px;line-height:1.5;">You will be logged out from your account and redirected to the login page.</p>' +
      '</div>' +
      '<div class="form-actions" style="justify-content:flex-end;gap:10px;margin-top:18px;">' +
        '<button type="button" class="btn btn-secondary" id="logoutConfirmCancel">Cancel</button>' +
        '<button type="button" class="btn btn-dark" id="logoutConfirmOk">Logout</button>' +
      '</div>' +
    '</div>';

  document.body.appendChild(modal);
  return modal;
}

function askLogoutConfirmation() {
  return new Promise((resolve) => {
    const modal = ensureLogoutConfirmModal();
    const btnCancel = modal.querySelector('#logoutConfirmCancel');
    const btnOk = modal.querySelector('#logoutConfirmOk');

    function close(result) {
      modal.classList.add('hidden');
      modal.setAttribute('aria-hidden', 'true');
      resolve(result);
    }

    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');

    btnCancel.onclick = () => close(false);
    btnOk.onclick = () => close(true);
    modal.onclick = (e) => { if (e.target === modal) close(false); };
  });
}

async function logout() {
  const confirmed = await askLogoutConfirmation();
  if (!confirmed) return;
  clearToken();
  window.location.href = '/login';
}
