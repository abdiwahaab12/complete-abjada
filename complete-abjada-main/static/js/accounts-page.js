/**
 * Financial accounts page (/accounts) — loads /api/finance/* endpoints.
 */
(function () {
  var ICON_SVG = {
    receivable: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    liabilities: '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M6 9h12"/><path d="M6 13h8"/>',
    expenses: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/>',
    net: '<path d="M3 3v18h18"/><path d="M7 16l4-4 4 4"/><path d="M7 8h10"/>',
  };

  function finIcon(paths) {
    return (
      '<span class="fin-sum-card__icon" aria-hidden="true"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">' +
      paths +
      '</svg></span>'
    );
  }

  /** Kenyan Shilling mark for KPI cards (avoids dollar-style currency glyph). */
  function finKshIcon() {
    return '<span class="fin-sum-card__icon fin-sum-card__icon--kes" title="Kenyan Shilling (KES)"><span class="fin-sum-card__kes-text">KSh</span></span>';
  }

  function fmt(n) {
    var x = Number(n);
    if (isNaN(x)) return '0.00';
    return x.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function esc(s) {
    if (s == null || s === '') return '';
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function statusBadge(raw) {
    var t = String(raw || '')
      .trim()
      .toLowerCase();
    var cls = 'fin-badge--unpaid';
    var label = 'Pending';
    if (t === 'paid') {
      cls = 'fin-badge--paid';
      label = 'Paid';
    } else if (t === 'partial') {
      cls = 'fin-badge--partial';
      label = 'Partial';
    } else if (t === 'unpaid') {
      label = 'Pending';
    }
    return '<span class="fin-badge ' + cls + '">' + label + '</span>';
  }

  function methodLabel(m) {
    var x = String(m || 'cash').toLowerCase().replace(' ', '_').replace('-', '');
    if (x === 'cash') return 'Cash';
    if (x === 'mpesa' || x === 'mobile_money' || x === 'digital' || x === 'bank') return 'M-Pesa';
    return 'Cash';
  }

  /** Notes + payment summary for Accounts receivable Details column (matches Received table layout). */
  function receivableDetailsCell(r) {
    var note = (r.details || '').trim();
    var ps = String(r.payment_status || '').toLowerCase();
    var bits = [];
    if (ps === 'paid') bits.push('Paid in full');
    else if (ps === 'partial') bits.push('Partial');
    else if (ps === 'unpaid' || !ps) bits.push('Pending');
    if (r.paid_amount != null && r.paid_amount !== '') bits.push('Collected ' + fmt(r.paid_amount));
    if (r.balance_due != null && Number(r.balance_due) > 0.005) bits.push('Due ' + fmt(r.balance_due));
    var meta = bits.join(' · ');
    var main = note ? note.slice(0, 100) + (note.length > 100 ? '…' : '') : '';
    if (main && meta) return (main + ' · ' + meta).slice(0, 220);
    if (main) return main.slice(0, 120);
    return meta || '—';
  }

  function kpiCard(modClass, iconHtml, label, value) {
    return (
      '<div class="fin-sum-card ' +
      modClass +
      '">' +
      '<div class="fin-sum-card__top">' +
      iconHtml +
      '<div class="fin-sum-card__body">' +
      '<div class="fin-sum-label">' +
      label +
      '</div>' +
      '<div class="fin-sum-val">' +
      fmt(value) +
      '</div>' +
      '<span class="fin-sum-currency">KES</span>' +
      '</div></div></div>'
    );
  }

  async function loadSummary() {
    var s = await api('/finance/summary');
    var el = document.getElementById('finSummary');
    if (!el) return;
    el.innerHTML =
      kpiCard('fin-sum-card--received', finKshIcon(), 'Total received', s.total_received) +
      kpiCard('fin-sum-card--receivable', ICON_SVG.receivable, 'Accounts receivable', s.total_receivable) +
      kpiCard('fin-sum-card--liabilities', ICON_SVG.liabilities, 'Total liabilities', s.total_liabilities) +
      kpiCard('fin-sum-card--expenses', ICON_SVG.expenses, 'Total expenses', s.total_expenses) +
      '<div class="fin-sum-card fin-sum-card--net">' +
      '<div class="fin-sum-card__top">' +
      finIcon(ICON_SVG.net) +
      '<div class="fin-sum-card__body">' +
      '<div class="fin-sum-label">Net business balance</div>' +
      '<div class="fin-sum-val">' +
      fmt(s.net_balance) +
      '</div>' +
      '<span class="fin-sum-currency">KES</span>' +
      '<p class="fin-sum-hint">Received payments minus expenses minus outstanding supplier liabilities.</p>' +
      '</div></div></div>';
  }

  async function loadReceived() {
    var tbody = document.getElementById('tbodyReceived');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="6" class="fin-empty-cell">Loading…</td></tr>';
    var df = document.getElementById('recvDateFrom') && document.getElementById('recvDateFrom').value;
    var dt = document.getElementById('recvDateTo') && document.getElementById('recvDateTo').value;
    var q = [];
    if (df) q.push('date_from=' + encodeURIComponent(df));
    if (dt) q.push('date_to=' + encodeURIComponent(dt));
    var res = await api('/finance/received-payments?' + q.join('&'));
    var rows = res.items || [];
    if (!rows.length) {
      tbody.innerHTML =
        '<tr><td colspan="6" class="fin-empty-cell">No received transactions in this range. Add them under Transactions with account type &ldquo;Account received&rdquo;.</td></tr>';
      return;
    }
    tbody.innerHTML = rows
      .map(function (p) {
        var rawDate = p.transaction_date || p.created_at || '';
        var dline = rawDate ? String(rawDate).replace('T', ' ').slice(0, 19) : '';
        var cust = p.counterparty ? String(p.counterparty).trim() : '';
        return (
          '<tr data-tx-id="' +
          esc(String(p.id)) +
          '"><td class="fin-num">' +
          fmt(p.amount) +
          '</td><td>' +
          methodLabel(p.method) +
          '</td><td>' +
          esc(cust || '—') +
          '</td><td>' +
          esc(dline || '—') +
          '</td><td>' +
          esc((p.details || '—').slice(0, 120)) +
          '</td><td style="text-align:right"><button type="button" class="fin-btn fin-btn-danger-ghost fin-btn-sm fin-del-received" data-tid="' +
          esc(String(p.id)) +
          '">Delete</button></td></tr>'
        );
      })
      .join('');
    tbody.querySelectorAll('.fin-del-received').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var id = btn.getAttribute('data-tid');
        if (!id || !confirm('Delete this received payment from the log?')) return;
        api('/transactions/' + id, { method: 'DELETE' })
          .then(function () {
            showToast('Transaction deleted', 'success');
            loadReceived();
            loadSummary();
          })
          .catch(function (e) {
            showToast(e.message || 'Failed to delete', 'error');
          });
      });
    });
  }

  async function loadReceivable() {
    var tbody = document.getElementById('tbodyReceivable');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="6" class="fin-empty-cell">Loading…</td></tr>';
    var res = await api('/finance/receivable?per_page=200');
    var rows = res.items || [];
    if (!rows.length) {
      tbody.innerHTML =
        '<tr><td colspan="6" class="fin-empty-cell">No receivable transactions. Record them under Transactions with account type &ldquo;Receivable&rdquo;.</td></tr>';
      return;
    }
    tbody.innerHTML = rows
      .map(function (r) {
        var dline = (r.transaction_date || '').replace('T', ' ').slice(0, 19);
        return (
          '<tr data-tx-id="' +
          esc(String(r.id)) +
          '"><td class="fin-num">' +
          fmt(r.amount) +
          '</td><td>' +
          esc(methodLabel(r.method)) +
          '</td><td>' +
          esc(r.customer_name || '—') +
          '</td><td>' +
          esc(dline || '—') +
          '</td><td>' +
          esc(receivableDetailsCell(r)) +
          '</td><td style="text-align:right"><button type="button" class="fin-btn fin-btn-danger-ghost fin-btn-sm fin-del-receivable" data-tid="' +
          esc(String(r.id)) +
          '">Delete</button></td></tr>'
        );
      })
      .join('');
    tbody.querySelectorAll('.fin-del-receivable').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var id = btn.getAttribute('data-tid');
        if (!id || !confirm('Delete this receivable transaction?')) return;
        api('/transactions/' + id, { method: 'DELETE' })
          .then(function () {
            showToast('Transaction deleted', 'success');
            loadReceivable();
            loadSummary();
          })
          .catch(function (e) {
            showToast(e.message || 'Failed to delete', 'error');
          });
      });
    });
  }

  async function loadLiabilities() {
    var tbody = document.getElementById('tbodyLiabilities');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="4" class="fin-empty-cell">Loading…</td></tr>';
    var res = await api('/finance/liabilities?per_page=200');
    var rows = res.items || [];
    if (!rows.length) {
      tbody.innerHTML =
        '<tr><td colspan="4" class="fin-empty-cell">No liability transactions. Record them under Transactions with account type &ldquo;Liability&rdquo;.</td></tr>';
      return;
    }
    tbody.innerHTML = rows
      .map(function (L) {
        var dline = (L.transaction_date || '').replace('T', ' ').slice(0, 19);
        return (
          '<tr><td class="fin-num">' +
          fmt(L.amount) +
          '</td><td>' +
          esc(L.creditor_name) +
          '</td><td>' +
          esc(dline || '—') +
          '</td><td>' +
          statusBadge(L.status) +
          '</td></tr>'
        );
      })
      .join('');
  }

  async function loadExpenses() {
    var tbody = document.getElementById('tbodyExpenses');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="5" class="fin-empty-cell">Loading…</td></tr>';
    var df = document.getElementById('expDateFrom') && document.getElementById('expDateFrom').value;
    var dt = document.getElementById('expDateTo') && document.getElementById('expDateTo').value;
    var q = [];
    if (df) q.push('date_from=' + encodeURIComponent(df));
    if (dt) q.push('date_to=' + encodeURIComponent(dt));
    var res = await api('/finance/expenses?' + q.join('&'));
    var rows = res.items || [];
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="fin-empty-cell">No expenses in this range.</td></tr>';
      return;
    }
    tbody.innerHTML = rows
      .map(function (e) {
        return (
          '<tr><td>' +
          esc(e.category) +
          '</td><td class="fin-num">' +
          fmt(e.amount) +
          '</td><td>' +
          esc((e.expense_date || '').slice(0, 10) || '—') +
          '</td><td>' +
          esc((e.description || '').slice(0, 48)) +
          '</td><td style="text-align:right"><button type="button" class="fin-btn fin-btn-danger-ghost fin-btn-sm fin-del-exp" data-id="' +
          e.id +
          '">Remove</button></td></tr>'
        );
      })
      .join('');
    tbody.querySelectorAll('.fin-del-exp').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (!confirm('Delete this expense?')) return;
        var id = btn.getAttribute('data-id');
        api('/finance/expenses/' + id, { method: 'DELETE' })
          .then(function () {
            showToast('Deleted', 'success');
            loadExpenses();
            loadSummary();
          })
          .catch(function (err) {
            showToast(err.message || 'Failed', 'error');
          });
      });
    });
  }

  async function fillCustomerSelect() {
    var sel = document.getElementById('finCustomerSelect');
    if (!sel) return;
    sel.innerHTML = '<option value="">Select customer…</option>';
    var res = await api('/customers?per_page=500&sort_dir=asc');
    (res.items || []).forEach(function (c) {
      var o = document.createElement('option');
      o.value = c.id;
      o.textContent = c.full_name + ' — ' + (c.phone || '');
      sel.appendChild(o);
    });
  }

  async function loadCustomerProfile() {
    var sel = document.getElementById('finCustomerSelect');
    var box = document.getElementById('finCustomerProfile');
    if (!sel || !box) return;
    var cid = sel.value;
    if (!cid) {
      box.innerHTML = '<p class="fin-note" style="margin:0">Select a customer to load orders, payments, and remaining balance.</p>';
      return;
    }
    box.innerHTML = '<p class="fin-note" style="margin:0">Loading profile…</p>';
    var p = await api('/finance/customers/' + cid + '/profile');
    var ph = (p.payment_history || [])
      .slice(0, 50)
      .map(function (x) {
        return (
          '<tr><td>#' +
          esc(x.order_id) +
          '</td><td class="fin-num">' +
          fmt(x.amount) +
          '</td><td>' +
          esc((x.notes || '').slice(0, 30)) +
          '</td><td>' +
          esc((x.created_at || '').slice(0, 19)) +
          '</td></tr>'
        );
      })
      .join('');
    box.innerHTML =
      '<div class="fin-profile-stats">' +
      '<div class="fin-profile-stat"><div class="fin-sum-label">Total orders</div><div class="fin-sum-val">' +
      (p.total_orders || 0) +
      '</div></div>' +
      '<div class="fin-profile-stat"><div class="fin-sum-label">Total order value</div><div class="fin-sum-val">' +
      fmt(p.total_order_value) +
      '</div><span class="fin-sum-currency">KES</span></div>' +
      '<div class="fin-profile-stat"><div class="fin-sum-label">Total paid</div><div class="fin-sum-val">' +
      fmt(p.total_paid) +
      '</div><span class="fin-sum-currency">KES</span></div>' +
      '<div class="fin-profile-stat"><div class="fin-sum-label">Remaining</div><div class="fin-sum-val">' +
      fmt(p.remaining_balance) +
      '</div><span class="fin-sum-currency">KES</span></div></div>' +
      '<p class="fin-note">Remaining = total order value minus payments recorded on orders.</p>' +
      '<div class="fin-table-wrap"><table class="fin-table"><thead><tr><th>Order</th><th class="fin-num">Amount</th><th>Notes</th><th>Date</th></tr></thead><tbody>' +
      (ph || '<tr><td colspan="4" class="fin-empty-cell">No payments recorded yet.</td></tr>') +
      '</tbody></table></div>';
  }

  function switchTab(name) {
    document.querySelectorAll('.fin-tab').forEach(function (t) {
      t.classList.toggle('is-active', t.getAttribute('data-tab') === name);
    });
    document.querySelectorAll('.fin-panel').forEach(function (p) {
      p.classList.toggle('is-active', p.getAttribute('data-panel') === name);
    });
    if (name === 'received') loadReceived();
    if (name === 'receivable') loadReceivable();
    if (name === 'liabilities') loadLiabilities();
    if (name === 'expenses') loadExpenses();
    if (name === 'customers') {
      fillCustomerSelect();
      loadCustomerProfile();
    }
  }

  function wireModal(id, openBtn, onSubmit) {
    var modal = document.getElementById(id);
    if (!modal) return;
    function close() {
      modal.classList.add('hidden');
      modal.setAttribute('aria-hidden', 'true');
    }
    modal.querySelectorAll('[data-close-modal]').forEach(function (b) {
      b.addEventListener('click', close);
    });
    modal.addEventListener('click', function (e) {
      if (e.target === modal) close();
    });
    if (openBtn) {
      openBtn.addEventListener('click', function () {
        modal.classList.remove('hidden');
        modal.setAttribute('aria-hidden', 'false');
      });
    }
    var form = modal.querySelector('form');
    if (form && onSubmit) {
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        onSubmit(form, close);
      });
    }
  }

  window.initAccountsFinancePage = function () {
    loadSummary().catch(function (e) {
      showToast(e.message || 'Could not load summary', 'error');
    });

    document.querySelectorAll('.fin-tab').forEach(function (tab) {
      tab.addEventListener('click', function () {
        switchTab(tab.getAttribute('data-tab'));
      });
    });

    function receivedReportPdfPath() {
      var q = [];
      var df = document.getElementById('recvDateFrom') && document.getElementById('recvDateFrom').value;
      var dt = document.getElementById('recvDateTo') && document.getElementById('recvDateTo').value;
      if (df) q.push('date_from=' + encodeURIComponent(df));
      if (dt) q.push('date_to=' + encodeURIComponent(dt));
      return '/finance/reports/received.pdf' + (q.length ? '?' + q.join('&') : '');
    }
    function expensesReportPdfPath() {
      var q = [];
      var df = document.getElementById('expDateFrom') && document.getElementById('expDateFrom').value;
      var dt = document.getElementById('expDateTo') && document.getElementById('expDateTo').value;
      if (df) q.push('date_from=' + encodeURIComponent(df));
      if (dt) q.push('date_to=' + encodeURIComponent(dt));
      return '/finance/reports/expenses.pdf' + (q.length ? '?' + q.join('&') : '');
    }
    function wirePdfPair(openId, dlId, pathFn, dlName) {
      var o = document.getElementById(openId);
      var d = document.getElementById(dlId);
      if (o) {
        o.addEventListener('click', function () {
          openFinancePdf(pathFn());
        });
      }
      if (d) {
        d.addEventListener('click', function () {
          downloadFinancePdf(pathFn(), dlName);
        });
      }
    }
    wirePdfPair('btnPdfReceived', 'btnDlReceived', receivedReportPdfPath, 'received_payments_report.pdf');
    wirePdfPair('btnPdfReceivable', 'btnDlReceivable', function () {
      return '/finance/reports/receivable.pdf';
    }, 'accounts_receivable_report.pdf');
    wirePdfPair('btnPdfLiabilities', 'btnDlLiabilities', function () {
      return '/finance/reports/liabilities.pdf';
    }, 'liabilities_report.pdf');
    wirePdfPair('btnPdfExpenses', 'btnDlExpenses', expensesReportPdfPath, 'expenses_report.pdf');

    document.getElementById('recvApply') &&
      document.getElementById('recvApply').addEventListener('click', function () {
        loadReceived();
      });
    document.getElementById('expApply') &&
      document.getElementById('expApply').addEventListener('click', function () {
        loadExpenses();
      });
    document.getElementById('finCustomerSelect') &&
      document.getElementById('finCustomerSelect').addEventListener('change', loadCustomerProfile);

    wireModal('modalExpense', document.getElementById('btnAddExpense'), function (form, close) {
      var fd = new FormData(form);
      var payload = {
        category: fd.get('category'),
        amount: parseFloat(fd.get('amount')),
        expense_date: fd.get('expense_date') || null,
        description: fd.get('description') || '',
      };
      api('/finance/expenses', { method: 'POST', body: JSON.stringify(payload) })
        .then(function () {
          showToast('Expense saved', 'success');
          close();
          form.reset();
          loadExpenses();
          loadSummary();
        })
        .catch(function (e) {
          showToast(e.message || 'Failed', 'error');
        });
    });

    var params = new URLSearchParams(window.location.search || '');
    var preCustomer = params.get('customer');
    if (preCustomer) {
      switchTab('customers');
      fillCustomerSelect().then(function () {
        var sel = document.getElementById('finCustomerSelect');
        if (sel) {
          sel.value = String(preCustomer);
          loadCustomerProfile();
        }
      });
    } else {
      switchTab('received');
    }
  };
})();
