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
  if (res.status === 401) {
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

function logout() { clearToken(); window.location.href = '/login'; }
