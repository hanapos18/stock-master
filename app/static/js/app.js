/* StockMaster JS */

// Sidebar toggle
document.getElementById('sidebarToggle')?.addEventListener('click', () => {
  document.getElementById('sidebar')?.classList.toggle('collapsed');
});

// Auto-dismiss alerts after 5s
document.querySelectorAll('.alert-dismissible').forEach(el => {
  setTimeout(() => { el.querySelector('.btn-close')?.click(); }, 5000);
});

/**
 * Product search autocomplete helper
 * Usage: initProductSearch(inputId, resultsId, callback)
 */
function initProductSearch(inputId, resultsId, onSelect) {
  const input = document.getElementById(inputId);
  const results = document.getElementById(resultsId);
  if (!input || !results) return;
  let timer = null;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (q.length < 1) { results.innerHTML = ''; results.style.display = 'none'; return; }
    timer = setTimeout(() => {
      fetch('/products/api/list?search=' + encodeURIComponent(q))
        .then(r => r.json())
        .then(data => {
          if (!data.length) { results.innerHTML = '<div class="p-2 text-muted">No products found</div>'; results.style.display = 'block'; return; }
          results.innerHTML = data.map(p =>
            `<div class="list-group-item" data-id="${p.id}" data-code="${p.code}" data-name="${p.name}" data-unit="${p.unit}" data-price="${p.unit_price}" data-sell="${p.sell_price}">${p.code} - ${p.name} (${p.unit})</div>`
          ).join('');
          results.style.display = 'block';
          results.querySelectorAll('.list-group-item').forEach(item => {
            item.addEventListener('click', () => {
              onSelect({
                id: item.dataset.id,
                code: item.dataset.code,
                name: item.dataset.name,
                unit: item.dataset.unit,
                unit_price: parseFloat(item.dataset.price),
                sell_price: parseFloat(item.dataset.sell),
              });
              input.value = '';
              results.innerHTML = '';
              results.style.display = 'none';
            });
          });
        });
    }, 300);
  });
  document.addEventListener('click', (e) => {
    if (!results.contains(e.target) && e.target !== input) {
      results.style.display = 'none';
    }
  });
}

/**
 * Add item row to a dynamic table
 */
function addItemRow(tbodyId, product, priceField) {
  const tbody = document.getElementById(tbodyId);
  const price = priceField === 'sell' ? product.sell_price : product.unit_price;
  const idx = tbody.children.length;
  const row = document.createElement('tr');
  const hasExpiry = tbody.closest('table').querySelector('th.th-expiry');
  const expiryCell = hasExpiry ? `<td><input type="date" name="item_expiry_date[]" class="form-control form-control-sm"></td>` : '';
  row.innerHTML = `
    <td><input type="hidden" name="item_product_id[]" value="${product.id}">${product.code} - ${product.name}</td>
    <td><input type="number" name="item_quantity[]" class="form-control form-control-sm" value="1" min="0.01" step="0.01" required onchange="calcRowAmount(this)"></td>
    <td><input type="number" name="item_unit_price[]" class="form-control form-control-sm" value="${price}" min="0" step="0.01" onchange="calcRowAmount(this)"></td>
    ${expiryCell}
    <td class="row-amount">${price.toFixed(2)}</td>
    <td><button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('tr').remove();calcTotal();">X</button></td>
  `;
  tbody.appendChild(row);
  calcTotal();
}

function calcRowAmount(el) {
  const row = el.closest('tr');
  const qty = parseFloat(row.querySelector('[name="item_quantity[]"]').value) || 0;
  const price = parseFloat(row.querySelector('[name="item_unit_price[]"]').value) || 0;
  row.querySelector('.row-amount').textContent = (qty * price).toFixed(2);
  calcTotal();
}

function calcTotal() {
  let total = 0;
  document.querySelectorAll('.row-amount').forEach(el => { total += parseFloat(el.textContent) || 0; });
  const totalEl = document.getElementById('grandTotal');
  if (totalEl) totalEl.textContent = total.toFixed(2);
}

/**
 * Export table to CSV (for Excel)
 */
function exportTableToCSV(tableId, filename) {
  const table = document.getElementById(tableId);
  if (!table) return;
  const rows = Array.from(table.querySelectorAll('tr'));
  const csv = rows.map(row =>
    Array.from(row.querySelectorAll('th,td')).map(cell =>
      '"' + cell.textContent.trim().replace(/"/g, '""') + '"'
    ).join(',')
  ).join('\n');
  const bom = '\uFEFF';
  const blob = new Blob([bom + csv], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = filename || 'export.csv';
  link.click();
}
