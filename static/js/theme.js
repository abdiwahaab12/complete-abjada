const THEME_KEY = 'tailor_theme';

function getTheme() {
  return localStorage.getItem(THEME_KEY) || 'dark';
}

function setTheme(theme) {
  theme = theme === 'light' ? 'light' : 'dark';
  localStorage.setItem(THEME_KEY, theme);
  document.documentElement.setAttribute('data-theme', theme);
}

function initTheme() {
  setTheme(getTheme());
}

function toggleTheme() {
  const next = getTheme() === 'light' ? 'dark' : 'light';
  setTheme(next);
  return next;
}

function updateThemeButton(btn) {
  if (!btn) return;
  if (btn.classList && btn.classList.contains('header-icon')) {
    btn.textContent = getTheme() === 'light' ? '🌙' : '☀️';
  } else {
    btn.textContent = getTheme() === 'light' ? '🌙' : '☀️';
  }
  btn.title = getTheme() === 'light' ? 'Switch to dark mode' : 'Switch to light mode';
}

function renderThemeToggle() {
  return '<button type="button" class="btn btn-secondary" id="themeToggle" title="Toggle light/dark mode" aria-label="Theme">' + (getTheme() === 'light' ? '🌙' : '☀️') + '</button>';
}
