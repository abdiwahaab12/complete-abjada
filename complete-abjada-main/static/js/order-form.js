/**
 * Full-page new/edit order form (used by order_form.html).
 */
(function () {
  var LINES_PREFIX = 'ABJAD_LINES_JSON:';
  var inventoryCatalog = [];
  var orderLineIdSeq = 0;
  var loadedOrderForEdit = null;

  function escapeHtml(s) {
    if (s == null || s === '') return '';
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function formatOrderId(id) {
    return 'ORD-' + String(id).padStart(4, '0');
  }

  function loadInventory() {
    return api('/inventory?per_page=500')
      .then(function (res) {
        inventoryCatalog = res.items || [];
      })
      .catch(function () {
        inventoryCatalog = [];
      });
  }

  function loadAccounts() {
    var sel = document.getElementById('order_account_id');
    if (!sel) return Promise.resolve();
    sel.innerHTML =
      '<option value="KES">KES (Default)</option>' +
      '<option value="USD">USD</option>';
    return api('/banks?per_page=100')
      .then(function (res) {
        var items = res.items || [];
        items.forEach(function (b) {
          var opt = document.createElement('option');
          opt.value = 'bank:' + b.id;
          opt.textContent = (b.name || 'Account') + ' — ' + (b.account_number || '');
          sel.appendChild(opt);
        });
      })
      .catch(function () {});
  }

  function getAccountSelection() {
    var sel = document.getElementById('order_account_id');
    if (!sel) return { value: 'KES', label: 'KES (Default)' };
    var opt = sel.options[sel.selectedIndex];
    return {
      value: sel.value,
      label: opt ? opt.textContent.trim() : 'KES (Default)'
    };
  }

  function productSelectOptions() {
    var opts = '<option value="">Select Product</option>';
    opts += '<option value="__other__">Other (custom)</option>';
    inventoryCatalog.forEach(function (inv) {
      opts += '<option value="' + inv.id + '">' + escapeHtml(inv.name) + '</option>';
    });
    return opts;
  }

  function variantOptionsForInv(inv) {
    if (!inv) return '<option value="Standard">Standard</option>';
    var seen = {};
    var list = ['Default'];
    [inv.unit, inv.item_type].forEach(function (x) {
      if (x && !seen[x]) {
        seen[x] = true;
        list.push(x);
      }
    });
    return list
      .map(function (v) {
        return '<option value="' + escapeHtml(v) + '">' + escapeHtml(v) + '</option>';
      })
      .join('');
  }

  function skuOptionsForInv(inv) {
    if (!inv) return '<option value="—">—</option>';
    var sku = 'INV-' + inv.id;
    return '<option value="' + escapeHtml(sku) + '">' + escapeHtml(sku) + '</option>';
  }

  function otherVariantOptions() {
    return ['Standard', 'S', 'M', 'L', 'XL', 'Custom']
      .map(function (v) {
        return '<option value="' + v + '">' + v + '</option>';
      })
      .join('');
  }

  function addOrderLine(prefill) {
    var tbody = document.getElementById('orderLinesBody');
    var rid = 'ln-' + ++orderLineIdSeq;
    var tr = document.createElement('tr');
    tr.dataset.rowId = rid;
    tr.innerHTML =
      '<td><div class="line-product-cell"><select class="line-product" data-rid="' +
      rid +
      '">' +
      productSelectOptions() +
      '</select>' +
      '<input type="text" class="line-custom-name" data-rid="' +
      rid +
      '" placeholder="Item name" autocomplete="off"></div></td>' +
      '<td><select class="line-variant" data-rid="' +
      rid +
      '"></select></td>' +
      '<td><select class="line-sku" data-rid="' +
      rid +
      '"></select></td>' +
      '<td><input type="number" class="line-price" data-rid="' +
      rid +
      '" step="0.01" min="0" value="0"></td>' +
      '<td><input type="number" class="line-qty" data-rid="' +
      rid +
      '" step="1" min="1" value="1"></td>' +
      '<td><span class="line-total" data-rid="' +
      rid +
      '">0.00</span></td>' +
      '<td><button type="button" class="order-line-remove" data-line-remove data-rid="' +
      rid +
      '" aria-label="Remove row">&times;</button></td>';
    tbody.appendChild(tr);
    var invId = prefill && prefill.invId != null && prefill.invId !== '' ? String(prefill.invId) : '';
    if (invId && inventoryCatalog.some(function (i) { return String(i.id) === invId; })) {
      tr.querySelector('.line-product').value = invId;
      syncLineRow(tr);
      if (prefill) {
        if (prefill.variant) tr.querySelector('.line-variant').value = prefill.variant;
        if (prefill.sku) tr.querySelector('.line-sku').value = prefill.sku;
        if (prefill.price != null) tr.querySelector('.line-price').value = prefill.price;
        if (prefill.qty != null) tr.querySelector('.line-qty').value = prefill.qty;
      }
    } else if (prefill) {
      tr.querySelector('.line-product').value = '__other__';
      syncLineRow(tr);
      if (prefill.product) tr.querySelector('.line-custom-name').value = prefill.product;
      tr.querySelector('.line-variant').value = prefill.variant || 'Standard';
      tr.querySelector('.line-sku').innerHTML =
        '<option value="' + escapeHtml(prefill.sku || '—') + '">' + escapeHtml(prefill.sku || '—') + '</option>';
      tr.querySelector('.line-price').value = prefill.price != null ? prefill.price : 0;
      tr.querySelector('.line-qty').value = prefill.qty != null ? prefill.qty : 1;
    } else {
      syncLineRow(tr);
    }
    recalcLineRow(tr);
    recalcSubtotal();
  }

  function syncLineRow(tr) {
    var sel = tr.querySelector('.line-product');
    var vSel = tr.querySelector('.line-variant');
    var sSel = tr.querySelector('.line-sku');
    var customInp = tr.querySelector('.line-custom-name');
    var val = sel.value;
    if (val === '__other__') {
      customInp.classList.add('is-visible');
      vSel.innerHTML = otherVariantOptions();
      sSel.innerHTML = '<option value="—">—</option>';
    } else if (val) {
      customInp.classList.remove('is-visible');
      customInp.value = '';
      var inv = inventoryCatalog.find(function (i) { return String(i.id) === val; });
      vSel.innerHTML = variantOptionsForInv(inv);
      sSel.innerHTML = skuOptionsForInv(inv);
    } else {
      customInp.classList.remove('is-visible');
      customInp.value = '';
      vSel.innerHTML = '<option value="">Select Vari…</option>';
      sSel.innerHTML = '<option value="">Select S…</option>';
    }
  }

  function getProductLabel(tr) {
    var sel = tr.querySelector('.line-product');
    if (sel.value === '__other__') {
      var cn = tr.querySelector('.line-custom-name').value.trim();
      return cn || 'Custom item';
    }
    if (!sel.value) return '';
    var inv = inventoryCatalog.find(function (i) { return String(i.id) === sel.value; });
    return inv ? inv.name : '';
  }

  function recalcLineRow(tr) {
    var p = parseFloat(tr.querySelector('.line-price').value) || 0;
    var q = parseInt(tr.querySelector('.line-qty').value, 10) || 0;
    if (q < 1) q = 1;
    tr.querySelector('.line-qty').value = q;
    var tot = (p * q).toFixed(2);
    tr.querySelector('.line-total').textContent = tot;
    return parseFloat(tot);
  }

  function recalcSubtotal() {
    var tbody = document.getElementById('orderLinesBody');
    var sum = 0;
    tbody.querySelectorAll('tr').forEach(function (tr) {
      sum += recalcLineRow(tr);
    });
    var el = document.getElementById('orderSubtotalDisplay');
    if (el) el.textContent = sum.toFixed(2);
    return sum;
  }

  function collectLines() {
    var rows = document.getElementById('orderLinesBody').querySelectorAll('tr');
    var lines = [];
    rows.forEach(function (tr) {
      var prodSel = tr.querySelector('.line-product');
      var label = getProductLabel(tr);
      if (!prodSel.value) return;
      var variant = tr.querySelector('.line-variant').value || '';
      var sku = tr.querySelector('.line-sku').value || '';
      var price = parseFloat(tr.querySelector('.line-price').value) || 0;
      var qty = parseInt(tr.querySelector('.line-qty').value, 10) || 1;
      var invId = prodSel.value === '__other__' ? null : parseInt(prodSel.value, 10);
      lines.push({
        invId: invId,
        product: label,
        variant: variant,
        sku: sku,
        price: price,
        qty: qty
      });
    });
    return lines;
  }

  function buildFabricDetailsHuman(lines) {
    return lines
      .map(function (L, i) {
        var lineTot = (L.qty * L.price).toFixed(2);
        return (
          'Line ' +
          (i + 1) +
          ': ' +
          L.product +
          ' (' +
          L.variant +
          ') [' +
          L.sku +
          '] ×' +
          L.qty +
          ' @ ' +
          L.price +
          ' = ' +
          lineTot
        );
      })
      .join('\n');
  }

  function tryParseStoredLines(fabricDetails) {
    if (!fabricDetails || fabricDetails.indexOf(LINES_PREFIX) === -1) return null;
    try {
      var raw = fabricDetails.split(LINES_PREFIX)[1].trim();
      return JSON.parse(raw);
    } catch (e) {
      return null;
    }
  }

  function clearOrderLines() {
    document.getElementById('orderLinesBody').innerHTML = '';
  }

  function applyFormNew() {
    document.getElementById('orderId').value = '';
    document.getElementById('btnSubmitOrder').textContent = 'Create Order';
    document.getElementById('cash_amount').disabled = false;
    document.getElementById('digital_amount').disabled = false;
    document.getElementById('cash_amount').removeAttribute('title');
    document.getElementById('digital_amount').removeAttribute('title');
    document.getElementById('customer_id').value =
      new URLSearchParams(location.search).get('customer_id') || '';
    document.getElementById('cash_amount').value = '';
    document.getElementById('digital_amount').value = '';
    document.getElementById('delivery_date').value = '';
    document.getElementById('design_description').value = '';
    document.getElementById('design_image').value = '';
    var accSel = document.getElementById('order_account_id');
    if (accSel) accSel.value = 'KES';
    var sub = document.getElementById('orderFormSubtitle');
    if (sub) sub.textContent = '';
    clearOrderLines();
    addOrderLine(null);
    recalcSubtotal();
  }

  function applyFormEdit(order) {
    loadedOrderForEdit = order;
    document.getElementById('orderId').value = String(order.id);
    document.getElementById('btnSubmitOrder').textContent = 'Save changes';
    document.getElementById('cash_amount').disabled = true;
    document.getElementById('digital_amount').disabled = true;
    document.getElementById('cash_amount').title = 'Payments are managed from the Payments page when editing';
    document.getElementById('digital_amount').title = 'Payments are managed from the Payments page when editing';
    document.getElementById('customer_id').value = String(order.customer_id);
    var parsed = tryParseStoredLines(order.fabric_details || '');
    document.getElementById('delivery_date').value = order.delivery_date || '';
    document.getElementById('design_description').value = order.design_description || '';
    document.getElementById('design_image').value = order.design_image || '';
    if (parsed) {
      document.getElementById('cash_amount').value = parsed.cash != null && parsed.cash !== '' ? parsed.cash : '';
      document.getElementById('digital_amount').value = parsed.digital != null && parsed.digital !== '' ? parsed.digital : '';
    } else {
      document.getElementById('cash_amount').value = '';
      document.getElementById('digital_amount').value = '';
    }
    clearOrderLines();
    if (parsed && parsed.lines && parsed.lines.length) {
      parsed.lines.forEach(function (L) {
        addOrderLine(L);
      });
    } else {
      addOrderLine({
        invId: null,
        product: order.clothing_type || 'Item',
        variant: 'Standard',
        sku: '—',
        price: Number(order.total_price || 0),
        qty: 1
      });
    }
    var accSel = document.getElementById('order_account_id');
    if (accSel) {
      var av = parsed && parsed.account != null ? String(parsed.account) : 'KES';
      var found = false;
      for (var ai = 0; ai < accSel.options.length; ai++) {
        if (accSel.options[ai].value === av) {
          accSel.selectedIndex = ai;
          found = true;
          break;
        }
      }
      if (!found) accSel.value = 'KES';
    }
    var sub = document.getElementById('orderFormSubtitle');
    if (sub) sub.textContent = 'Editing · ' + formatOrderId(order.id);
    recalcSubtotal();
  }

  function wireFormEvents() {
    var tbody = document.getElementById('orderLinesBody');
    tbody.addEventListener('change', function (e) {
      var t = e.target;
      if (t.classList && t.classList.contains('line-product')) {
        syncLineRow(t.closest('tr'));
        recalcSubtotal();
      }
    });
    tbody.addEventListener('input', function (e) {
      if (e.target.matches && e.target.matches('.line-price, .line-qty, .line-custom-name')) recalcSubtotal();
    });
    tbody.addEventListener('click', function (e) {
      if (e.target.hasAttribute('data-line-remove')) {
        var tr = e.target.closest('tr');
        if (tr && tbody.querySelectorAll('tr').length > 1) {
          tr.remove();
          recalcSubtotal();
        } else if (tr) {
          showToast('At least one line is required', 'error');
        }
      }
    });

    document.getElementById('btnAddProduct').addEventListener('click', function () {
      addOrderLine(null);
    });

    document.getElementById('cancelBtn').addEventListener('click', function () {
      window.location.href = '/orders';
    });

    var designFileEl = document.getElementById('design_file');
    if (designFileEl) {
      designFileEl.onchange = async function (e) {
        var f = e.target.files[0];
        if (!f) return;
        var fd = new FormData();
        fd.append('file', f);
        var token = getToken();
        var r = await fetch(window.location.origin + '/api/orders/upload-design', {
          method: 'POST',
          headers: token ? { Authorization: 'Bearer ' + token } : {},
          body: fd
        });
        var j = await r.json();
        if (j.design_image) document.getElementById('design_image').value = j.design_image;
      };
    }

    document.getElementById('form').onsubmit = async function (e) {
      e.preventDefault();
      var id = document.getElementById('orderId').value;
      var rawCid = document.getElementById('customer_id').value.trim();
      var customerId = null;
      if (rawCid) {
        customerId = parseInt(rawCid, 10);
        if (isNaN(customerId)) {
          showToast('Invalid customer reference', 'error');
          return;
        }
      }
      var lines = collectLines();
      if (!lines.length) {
        showToast('Add at least one product line', 'error');
        return;
      }
      var subtotal = lines.reduce(function (s, L) { return s + L.price * L.qty; }, 0);
      var payModeEl = document.getElementById('payment_status_mode');
      var payMode = payModeEl ? payModeEl.value : 'partial';
      var cash = parseFloat(document.getElementById('cash_amount').value) || 0;
      var digital = parseFloat(document.getElementById('digital_amount').value) || 0;
      if (payMode === 'paid') {
        cash = subtotal;
        digital = 0;
      } else if (payMode === 'unpaid') {
        cash = 0;
        digital = 0;
      }
      var paidTotal = cash + digital;
      if (payMode === 'partial' && paidTotal <= 0) {
        showToast('Enter a cash or digital amount for partial payment, or change payment status.', 'error');
        return;
      }
      if (paidTotal > subtotal + 0.01) {
        showToast('Payments cannot exceed order total (' + subtotal.toFixed(2) + ')', 'error');
        return;
      }
      var clothing_type = lines[0].product || 'Order';
      var acct = getAccountSelection();
      var human = 'Account: ' + acct.label + '\n' + buildFabricDetailsHuman(lines);
      var jsonPayload = {
        v: 1,
        lines: lines,
        cash: cash,
        digital: digital,
        account: acct.value,
        accountLabel: acct.label
      };
      var fabric_details = human + '\n' + LINES_PREFIX + JSON.stringify(jsonPayload);
      var payload = {
        customer_id: customerId,
        clothing_type: clothing_type,
        fabric_details: fabric_details,
        design_description: document.getElementById('design_description').value || '',
        delivery_date: document.getElementById('delivery_date').value || null,
        total_price: subtotal,
        advance_paid: 0,
        design_image: document.getElementById('design_image').value || null
      };

      try {
        if (id) {
          var existing = loadedOrderForEdit;
          var prevParsed = existing ? tryParseStoredLines(existing.fabric_details || '') : null;
          jsonPayload.cash = prevParsed && prevParsed.cash != null ? prevParsed.cash : 0;
          jsonPayload.digital = prevParsed && prevParsed.digital != null ? prevParsed.digital : 0;
          jsonPayload.account = acct.value;
          jsonPayload.accountLabel = acct.label;
          fabric_details = human + '\n' + LINES_PREFIX + JSON.stringify(jsonPayload);
          await api('/orders/' + id, {
            method: 'PUT',
            body: JSON.stringify({
              clothing_type: clothing_type,
              fabric_details: fabric_details,
              design_description: payload.design_description,
              delivery_date: payload.delivery_date,
              total_price: subtotal,
              design_image: payload.design_image
            })
          });
          showToast('Order updated', 'success');
        } else {
          var created = await api('/orders', { method: 'POST', body: JSON.stringify(payload) });
          var oid = created.id;
          if (payMode === 'paid') {
            await api('/payments', {
              method: 'POST',
              body: JSON.stringify({
                order_id: oid,
                amount: subtotal,
                payment_type: 'paid',
                notes: 'Paid in full'
              })
            });
          } else if (payMode === 'partial') {
            if (cash > 0) {
              await api('/payments', {
                method: 'POST',
                body: JSON.stringify({ order_id: oid, amount: cash, payment_type: 'partial', notes: 'Cash' })
              });
            }
            if (digital > 0) {
              await api('/payments', {
                method: 'POST',
                body: JSON.stringify({ order_id: oid, amount: digital, payment_type: 'partial', notes: 'Digital' })
              });
            }
          }
          showToast('Order created', 'success');
        }
        window.location.href = '/orders';
      } catch (err) {
        showToast(err.message || 'Failed to save order', 'error');
      }
    };
  }

  window.initOrderFormPage = function (config) {
    config = config || { mode: 'new' };
    loadedOrderForEdit = null;
    orderLineIdSeq = 0;

    wireFormEvents();

    Promise.all([loadInventory(), loadAccounts()])
      .then(function () {
        if (config.mode === 'edit' && config.orderId) {
          return api('/orders/' + config.orderId).then(function (order) {
            applyFormEdit(order);
          });
        }
        applyFormNew();
      })
      .catch(function (err) {
        showToast(err.message || 'Failed to load form', 'error');
      });
  };
})();
