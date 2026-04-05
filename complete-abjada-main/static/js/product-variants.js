/**
 * Product variant rows: stored in notes as
 *   Variant: <color>||| <size>||| <sku>||| <stock>
 * Legacy lines still supported:
 *   Variant: name — detail  → color=name, sku=detail, size/stock empty
 */
(function (global) {
  var TRASH_SVG =
    '<svg class="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>';

  function escDelim(s) {
    return String(s == null ? '' : s).replace(/\|\|\|/g, ' ');
  }

  function serializeLine(color, size, sku, stock) {
    return 'Variant: ' + [escDelim(color), escDelim(size), escDelim(sku), escDelim(stock)].join('|||');
  }

  function parseRest(rest) {
    if (!rest) {
      return { color: '', size: '', sku: '', stock: '' };
    }
    if (rest.indexOf('|||') >= 0) {
      var p = rest.split('|||');
      return {
        color: (p[0] || '').trim(),
        size: (p[1] || '').trim(),
        sku: (p[2] || '').trim(),
        stock: (p[3] || '').trim()
      };
    }
    var sep = rest.indexOf(' — ');
    return {
      color: sep >= 0 ? rest.slice(0, sep).trim() : rest.trim(),
      size: '',
      sku: sep >= 0 ? rest.slice(sep + 3).trim() : '',
      stock: ''
    };
  }

  function parseAllFromNotes(notes) {
    var out = [];
    if (!notes) return out;
    var lines = notes.split(/\r?\n/);
    for (var i = 0; i < lines.length; i++) {
      var m = lines[i].match(/^Variant:\s*(.+)$/i);
      if (m) out.push(parseRest(m[1]));
    }
    return out;
  }

  function variantCardHTML() {
    return (
      '<div class="variant-dynamic rounded-xl border border-gray-200 bg-white p-4 shadow-sm space-y-4">' +
      '<div>' +
      '<label class="block text-xs font-semibold text-gray-900 mb-1.5">Variant Color</label>' +
      '<input type="text" class="variant-color w-full rounded-md border border-gray-200 p-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500/25 focus:border-blue-500" placeholder="e.g. White" />' +
      '</div>' +
      '<div class="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)_minmax(0,1fr)_auto] gap-3 sm:items-end">' +
      '<div class="min-w-0">' +
      '<label class="block text-xs font-semibold text-gray-900 mb-1.5">Size</label>' +
      '<input type="text" class="variant-size w-full rounded-md border border-gray-200 p-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500/25 focus:border-blue-500" placeholder="Size" />' +
      '</div>' +
      '<div class="min-w-0">' +
      '<label class="block text-xs font-semibold text-gray-900 mb-1.5">SKU</label>' +
      '<input type="text" class="variant-sku w-full rounded-md border border-gray-200 p-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500/25 focus:border-blue-500" placeholder="SKU" />' +
      '</div>' +
      '<div class="min-w-0">' +
      '<label class="block text-xs font-semibold text-gray-900 mb-1.5">Stock Quantity</label>' +
      '<input type="text" class="variant-stock w-full rounded-md border border-gray-200 p-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500/25 focus:border-blue-500" inputmode="decimal" placeholder="0" />' +
      '</div>' +
      '<button type="button" class="variant-remove-inline flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-red-600 text-white hover:bg-red-700 self-end" aria-label="Remove variant">' +
      TRASH_SVG +
      '</button>' +
      '</div>' +
      '<button type="button" class="variant-remove-block inline-flex items-center gap-2 rounded-md bg-red-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-700">' +
      TRASH_SVG +
      ' Remove Variant</button>' +
      '</div>'
    );
  }

  function bindCard(div) {
    var remove = function () {
      div.remove();
    };
    var ri = div.querySelector('.variant-remove-inline');
    var rb = div.querySelector('.variant-remove-block');
    if (ri) ri.addEventListener('click', remove);
    if (rb) rb.addEventListener('click', remove);
  }

  function appendCard(container, color, size, sku, stock) {
    var wrap = document.createElement('div');
    wrap.innerHTML = variantCardHTML().trim();
    var div = wrap.firstElementChild;
    container.appendChild(div);
    var c = div.querySelector('.variant-color');
    var si = div.querySelector('.variant-size');
    var k = div.querySelector('.variant-sku');
    var st = div.querySelector('.variant-stock');
    if (color && c) c.value = color;
    if (size && si) si.value = size;
    if (sku && k) k.value = sku;
    if (stock && st) st.value = stock;
    bindCard(div);
    return div;
  }

  global.ProductVariants = {
    serializeLine: serializeLine,
    parseRest: parseRest,
    parseAllFromNotes: parseAllFromNotes,
    appendCard: appendCard
  };
})(typeof window !== 'undefined' ? window : this);
