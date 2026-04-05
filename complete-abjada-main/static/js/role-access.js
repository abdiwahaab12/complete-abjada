/**
 * Role helpers: Super Admin (admin, super_admin) vs Employee (employee, tailor, cashier).
 * Use with pages that include api.js (getUser, getUserFromToken).
 */
function isSuperAdminUser(user) {
  var r = (user && user.role) || '';
  return r === 'admin' || r === 'super_admin';
}

function isEmployeeUser(user) {
  var r = (user && user.role) || '';
  if (isSuperAdminUser(user)) return false;
  return r === 'employee' || r === 'tailor' || r === 'cashier' || !!r;
}

/** Hide sidebar / util links that employees must not use. */
function applyEmployeeSidebarRestrictions() {
  var user = typeof getUser === 'function' ? getUser() : null;
  if (!user && typeof getUserFromToken === 'function') user = getUserFromToken();
  if (!user || isSuperAdminUser(user)) return;

  var selectors = [
    'a[href="/transactions"]',
    'a[href="/swap"]',
    'a[href="/reports"]',
    'a[href="/settings"]',
    'a[href="/staff"]',
    'a[href="/payments"]',
    'a[href="/category-page"]',
    'a[href="/products"]',
    'a[href="/stock"]',
    'a[href="/store"]',
    'a[href="/orders"]',
    'a[href="/transaction-categories"]',
    'a[href="/user/add"]',
    '.nav-super-admin-only'
  ];
  selectors.forEach(function (sel) {
    try {
      document.querySelectorAll(sel).forEach(function (el) {
        var nav = el.closest('.sidebar-modern-section') || el.closest('.sidebar-modern-inner');
        if (el.closest('.sidebar-modern-util')) {
          el.setAttribute('hidden', '');
          el.style.display = 'none';
        } else if (el.closest('aside.sidebar')) {
          el.setAttribute('hidden', '');
          el.style.display = 'none';
        }
      });
    } catch (e) {}
  });

  // Hide empty FINANCES section if all links gone
  document.querySelectorAll('.sidebar-modern-section').forEach(function (sec) {
    var t = sec.querySelector('.sidebar-modern-section-title');
    if (t && t.textContent.indexOf('FINANCES') !== -1) {
      var links = sec.querySelectorAll('a.sidebar-modern-link:not([hidden])');
      if (!links.length) sec.style.display = 'none';
    }
  });

  var roleEl = document.getElementById('sidebarUserRole');
  if (roleEl) roleEl.textContent = 'Employee';
}

/** Redirect employees away from admin-only routes. */
function guardEmployeeRoute() {
  var user = typeof getUser === 'function' ? getUser() : null;
  if (!user && typeof getUserFromToken === 'function') user = getUserFromToken();
  if (!user || isSuperAdminUser(user)) return;

  var path = (window.location.pathname || '').split('?')[0];
  var forbidden = [
    '/transactions',
    '/swap',
    '/reports',
    '/settings',
    '/staff',
    '/payments',
    '/category-page',
    '/products',
    '/stock',
    '/store',
    '/orders',
    '/transaction-categories',
    '/user/add'
  ];
  for (var i = 0; i < forbidden.length; i++) {
    var p = forbidden[i];
    if (path === p || path.indexOf(p + '/') === 0) {
      window.location.replace('/dashboard');
      return;
    }
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', function () {
    guardEmployeeRoute();
    applyEmployeeSidebarRestrictions();
  });
} else {
  guardEmployeeRoute();
  applyEmployeeSidebarRestrictions();
}
