/**
 * Low stock alert notifications: badge count, panel list, mark as read.
 * Depends on api.js (getToken, api, showToast).
 */
(function() {
  var LOW_STOCK_THRESHOLD = 5;
  var POLL_INTERVAL_MS = 60000;
  var pollTimer = null;
  var SETTINGS_KEY = 'abjad_settings_notifications';

  function getSettings() {
    try {
      return JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}') || {};
    } catch (e) {
      return {};
    }
  }

  function getBadgeEl() {
    return document.getElementById('notificationBadge');
  }
  function getListEl() {
    return document.getElementById('notificationList');
  }
  function getPanelEl() {
    return document.getElementById('notificationPanel');
  }
  function getBtnEl() {
    return document.getElementById('notificationBtn');
  }

  function updateBadge(count) {
    var badge = getBadgeEl();
    if (!badge) return;
    if (count === 0) {
      badge.style.display = 'none';
      badge.textContent = '0';
    } else {
      badge.style.display = 'inline';
      badge.textContent = count > 99 ? '99+' : String(count);
    }
  }

  function renderPanel(alerts) {
    var listEl = getListEl();
    if (!listEl) return;
    var unread = alerts.filter(function(a) { return !a.read; });
    if (alerts.length === 0) {
      listEl.innerHTML = '<div class="notification-panel-empty">No low stock alerts. Items are tracked when quantity is 5 or below.</div>';
      listEl.classList.add('notification-panel-empty');
      return;
    }
    listEl.classList.remove('notification-panel-empty');
    var html = alerts.map(function(a) {
      var name = escapeHtml(a.name || 'Item');
      var qty = Number(a.quantity);
      var unit = escapeHtml(a.unit || 'pcs');
      var readClass = a.read ? ' notification-item-read' : '';
      var markReadBtn = a.read
        ? ''
        : '<button type="button" class="notification-item-mark-read" data-id="' + a.id + '">Mark as read</button>';
      return (
        '<div class="notification-item' + readClass + '" data-id="' + a.id + '">' +
          '<div class="notification-item-name">' + name + '</div>' +
          '<div class="notification-item-qty">' + qty + ' ' + unit + ' remaining</div>' +
          markReadBtn +
        '</div>'
      );
    }).join('');
    var readAllHtml = unread.length > 0
      ? '<div class="notification-panel-actions"><button type="button" class="btn btn-secondary btn-sm" id="notificationMarkAllRead">Mark all as read</button></div>'
      : '';
    listEl.innerHTML = html + readAllHtml;

    listEl.querySelectorAll('.notification-item-mark-read').forEach(function(btn) {
      btn.addEventListener('click', function() {
        var id = btn.getAttribute('data-id');
        if (id) markRead(id);
      });
    });
    var markAll = document.getElementById('notificationMarkAllRead');
    if (markAll) markAll.addEventListener('click', markAllRead);
  }

  function escapeHtml(s) {
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function markRead(inventoryId) {
    if (typeof api !== 'function') return;
    api('/notifications/low-stock/' + inventoryId + '/read', { method: 'POST' })
      .then(function() {
        if (typeof showToast === 'function') showToast('Marked as read', 'success');
        fetchAlerts(true);
      })
      .catch(function(e) {
        if (typeof showToast === 'function') showToast(e.message || 'Failed to mark as read', 'error');
      });
  }

  function markAllRead() {
    if (typeof api !== 'function') return;
    api('/notifications/low-stock/read-all', { method: 'POST' })
      .then(function() {
        if (typeof showToast === 'function') showToast('All marked as read', 'success');
        fetchAlerts(true);
      })
      .catch(function(e) {
        if (typeof showToast === 'function') showToast(e.message || 'Failed', 'error');
      });
  }

  function fetchAlerts(updatePanel) {
    // Respect user settings: if low-stock notifications are disabled, clear UI and skip polling.
    var prefs = getSettings();
    if (prefs && prefs.lowStock === false) {
      updateBadge(0);
      if (updatePanel && getListEl()) {
        getListEl().innerHTML = '<div class="notification-panel-empty">Low stock alerts are turned off in Settings.</div>';
        getListEl().classList.add('notification-panel-empty');
      }
      return;
    }

    if (typeof getToken !== 'function' || !getToken()) return;
    if (typeof api !== 'function') return;
    api('/notifications/low-stock')
      .then(function(data) {
        var alerts = data.alerts || [];
        var unreadCount = data.unread_count != null ? data.unread_count : alerts.filter(function(a) { return !a.read; }).length;
        updateBadge(unreadCount);
        if (updatePanel && getPanelEl() && getPanelEl().classList.contains('show')) {
          renderPanel(alerts);
        }
        window.__lowStockAlerts = alerts;
        window.__lowStockUnreadCount = unreadCount;
      })
      .catch(function() {
        updateBadge(0);
        if (updatePanel && getListEl()) {
          getListEl().innerHTML = '<div class="notification-panel-empty">Unable to load alerts.</div>';
          getListEl().classList.add('notification-panel-empty');
        }
      });
  }

  function onPanelOpened() {
    fetchAlerts(true);
  }

  function startPolling() {
    if (pollTimer) return;
    pollTimer = setInterval(function() {
      if (getToken()) fetchAlerts(false);
    }, POLL_INTERVAL_MS);
  }

  function init() {
    if (!getToken()) return;
    fetchAlerts(false);
    startPolling();
    var btn = getBtnEl();
    var panel = getPanelEl();
    if (btn && panel) {
      btn.addEventListener('click', function() {
        setTimeout(function() {
          if (panel.classList.contains('show')) onPanelOpened();
        }, 150);
      });
    }
  }

  if (typeof getToken === 'function' && getToken()) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', init);
    } else {
      init();
    }
  }
  window.refreshLowStockNotifications = function() {
    fetchAlerts(true);
  };
})();
