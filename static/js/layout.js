// Shared layout functions
function initLayout(user) {
  if (!user) return;
  
  // Update user info in header
  const userNameEl = document.getElementById('userName');
  const userRoleEl = document.getElementById('userRole');
  const userAvatarEl = document.getElementById('userAvatar');
  
  if (userNameEl) userNameEl.textContent = user.full_name || user.username || 'User';
  if (userRoleEl) userRoleEl.textContent = user.role === 'admin' ? 'Administrator' : user.role.charAt(0).toUpperCase() + user.role.slice(1);
  if (userAvatarEl) {
    const initials = (user.full_name || user.username || 'U').split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
    userAvatarEl.textContent = initials;
  }
  
  // Hide admin-only nav
  if (user.role !== 'admin') {
    document.querySelectorAll('.nav-admin-only').forEach(el => el.classList.add('hidden'));
  }
  
  // Menu toggle
  const menuToggle = document.getElementById('menuToggle');
  const sidebar = document.getElementById('sidebar');
  if (menuToggle && sidebar) {
    menuToggle.onclick = () => sidebar.classList.toggle('open');
  }
  
  // Logout
  const logoutBtn = document.getElementById('logout');
  if (logoutBtn) {
    logoutBtn.onclick = (e) => { e.preventDefault(); logout(); };
  }
  
  // Theme toggle
  const themeToggle = document.getElementById('themeToggle');
  if (themeToggle) {
    themeToggle.onclick = () => {
      toggleTheme();
      updateThemeButton(themeToggle);
    };
    initTheme();
    updateThemeButton(themeToggle);
  }
}

function renderHeader() {
  return `
    <header class="top-header">
      <div class="top-header-left">
        <button class="menu-toggle" id="menuToggle">☰</button>
        <div class="logo">Tailor Shop</div>
        <div class="search-bar">
          <input type="text" placeholder="Search anything..." id="globalSearch">
        </div>
      </div>
      <div class="top-header-right">
        <button class="header-icon" title="Language">🇺🇸</button>
        <button class="header-icon" title="Apps">⊞</button>
        <button class="header-icon" id="themeToggle" title="Toggle theme">🌙</button>
        <button class="header-icon" title="Notifications">
          🔔
          <span class="notification-badge">3</span>
        </button>
        <div class="user-profile" id="userProfile">
          <div class="user-avatar" id="userAvatar">JD</div>
          <div class="user-info">
            <div class="user-name" id="userName">John Doe</div>
            <div class="user-role" id="userRole">Administrator</div>
          </div>
        </div>
      </div>
    </header>
  `;
}

function renderSidebar(activePage) {
  const pages = [
    { href: '/dashboard', icon: '📊', label: 'Dashboard' },
    { href: '/customers', icon: '👥', label: 'Customers' },
    { href: '/orders', icon: '📦', label: 'Orders' },
    { href: '/measurements', icon: '📏', label: 'Measurements' },
    { href: '/payments', icon: '💳', label: 'Payments' },
    { href: '/stock', icon: '📦', label: 'Stock' },
    { href: '/tasks', icon: '✅', label: 'Tasks' },
    { href: '/reports', icon: '📈', label: 'Reports' },
    { href: '/staff', icon: '👤', label: 'Staff', adminOnly: true }
  ];
  
  return `
    <aside class="sidebar" id="sidebar">
      <h2>Tailor Shop</h2>
      <nav>
        ${pages.map(p => `
          <a href="${p.href}" class="${activePage === p.href ? 'active' : ''} ${p.adminOnly ? 'nav-admin-only' : ''}">
            ${p.icon} ${p.label}
          </a>
        `).join('')}
      </nav>
      <div class="sidebar-bottom">
        <a href="#" id="logout" style="display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem 1rem; border-radius: 8px; color: rgba(255,255,255,0.8); transition: all 0.15s;">
          🚪 Logout
        </a>
      </div>
    </aside>
  `;
}
