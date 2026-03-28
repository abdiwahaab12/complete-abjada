/**
 * Dashboard avatar: displays logged-in user's initials or neutral fallback.
 * Fetches user from /api/auth/me (database). Never shows placeholders like "AU" or "JD".
 * When user data is missing, shows a clean neutral person icon.
 */
(function() {
  const PERSON_ICON_SVG = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';

  function getInitials(fullName, username) {
    const name = (fullName || '').trim();
    if (name) {
      const parts = name.split(/\s+/).filter(Boolean);
      if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase().slice(0, 2);
      if (parts[0]) return parts[0].slice(0, 2).toUpperCase();
    }
    const un = (username || '').trim();
    if (un) return un.slice(0, 2).toUpperCase();
    return null;
  }

  function getDisplayName(fullName, username) {
    const name = (fullName || '').trim();
    if (name) return name;
    const un = (username || '').trim();
    if (un) return un;
    return null;
  }

  function renderAvatar(el, initials, isNeutral) {
    if (!el) return;
    el.textContent = '';
    el.classList.remove('avatar-neutral', 'avatar-initials');
    if (isNeutral) {
      el.classList.add('avatar-neutral');
      el.innerHTML = PERSON_ICON_SVG;
    } else {
      el.classList.add('avatar-initials');
      el.textContent = initials;
    }
  }

  window.initAvatar = function(user) {
    const fullName = user && user.full_name;
    const username = user && user.username;
    const displayName = getDisplayName(fullName, username);
    const initials = getInitials(fullName, username);
    const useNeutral = !initials;
    const roleLabel = (user && user.role ? user.role : 'user').replace(/^\w/, c => c.toUpperCase());

    const headerAvatar = document.getElementById('userAvatar');
    const sidebarAvatar = document.getElementById('sidebarUserAvatar');
    const headerUserName = document.getElementById('headerUserName');
    const sidebarUserName = document.getElementById('sidebarUserName');
    const sidebarUserRole = document.getElementById('sidebarUserRole');

    renderAvatar(headerAvatar, initials, useNeutral);
    renderAvatar(sidebarAvatar, initials, useNeutral);
    if (headerUserName) headerUserName.textContent = displayName || '';
    if (sidebarUserName) sidebarUserName.textContent = displayName || '';
    if (sidebarUserRole) sidebarUserRole.textContent = roleLabel;
  };

  /**
   * Fetches current user from API (database), then initializes avatar.
   * Falls back to cached user if API fails.
   */
  window.initAvatarFromApi = function(cachedUser, onReady) {
    const done = function(u) {
      if (u) setUser(u);
      initAvatar(u || cachedUser);
      if (typeof onReady === 'function') onReady(u || cachedUser);
    };
    api('/auth/me').then(done).catch(function() { done(cachedUser); });
  };
})();
