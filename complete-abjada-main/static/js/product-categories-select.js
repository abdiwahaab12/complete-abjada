/**
 * Fills a <select id="productCategory"> from GET /api/categories.
 * option value = category slug (stored as inventory.item_type); label = category name.
 *
 * @param {HTMLSelectElement|null} selectEl
 * @param {string} [preferredSlug] - slug to select after load (e.g. existing item_type)
 */
async function fillProductCategorySelect(selectEl, preferredSlug) {
  if (!selectEl) return;
  var keep =
    preferredSlug != null && preferredSlug !== ''
      ? String(preferredSlug)
      : String(selectEl.value || '');
  selectEl.innerHTML = '';
  var ph = document.createElement('option');
  ph.value = '';
  ph.textContent = 'Choose category';
  selectEl.appendChild(ph);
  try {
    var data = await api('/categories?per_page=500&sort=name&order=asc', { cache: 'no-store' });
    var items = data && data.items ? data.items : [];
    items.forEach(function (c) {
      var slug = c && c.slug != null ? String(c.slug) : '';
      if (!slug) return;
      var opt = document.createElement('option');
      opt.value = slug;
      opt.textContent = c && c.name != null ? String(c.name) : slug;
      selectEl.appendChild(opt);
    });
    if (keep && [].some.call(selectEl.options, function (o) { return o.value === keep; })) {
      selectEl.value = keep;
    }
  } catch (e) {
    if (typeof showToast === 'function') {
      showToast(e.message || 'Could not load categories', 'error');
    }
  }
}
