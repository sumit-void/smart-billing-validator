/*
 * script.js — Frontend logic for Smart Billing Validator
 *
 * Handles: Tab switching, API calls (fetch), DOM updates,
 *          Bill form, Product CRUD, Reports, Bill detail modal
 */

// ═══════════════════════════════════════════════════════════════
//  STATE
// ═══════════════════════════════════════════════════════════════

let lineItems = [];        // Current bill's line items
let productsList = [];     // Cached products for dropdown
let editingProductId = null;  // Product being edited (null = adding)

// ═══════════════════════════════════════════════════════════════
//  TAB NAVIGATION
// ═══════════════════════════════════════════════════════════════

document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', e => {
        e.preventDefault();
        const tabId = link.dataset.tab;

        // Update nav
        document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
        link.classList.add('active');

        // Show tab
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.getElementById('tab-' + tabId).classList.add('active');

        // Load data for that tab
        if (tabId === 'dashboard') loadDashboard();
        if (tabId === 'add-bill') loadProductDropdown();
        if (tabId === 'products') loadProducts();
        if (tabId === 'reports') loadReport('category');
    });
});


// ═══════════════════════════════════════════════════════════════
//  HELPER — fetch wrapper
// ═══════════════════════════════════════════════════════════════

async function api(url, method = 'GET', body = null) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    return res.json();
}

function statusBadge(status) {
    const cls = status.toLowerCase();
    return `<span class="badge badge-${cls}">${status}</span>`;
}

function fmt(amount) {
    if (!amount && amount !== 0) return '₹0.00';
    return '₹' + Number(amount).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}


// ═══════════════════════════════════════════════════════════════
//  DASHBOARD
// ═══════════════════════════════════════════════════════════════

async function loadDashboard() {
    const data = await api('/api/dashboard');

    // Stats cards
    document.getElementById('stats-cards').innerHTML = `
        <div class="stat-card">
            <div class="stat-label">📄 Total Bills</div>
            <div class="stat-value">${data.stats.total_bills}</div>
        </div>
        <div class="stat-card green">
            <div class="stat-label">💰 Total Amount</div>
            <div class="stat-value">${data.stats.total_amount_fmt}</div>
        </div>
        <div class="stat-card red">
            <div class="stat-label">⚠️ Errors Found</div>
            <div class="stat-value">${data.stats.total_errors}</div>
        </div>
        <div class="stat-card amber">
            <div class="stat-label">💡 Savings</div>
            <div class="stat-value">${data.stats.total_savings_fmt}</div>
        </div>
    `;

    // Recent bills table
    const tbody = document.querySelector('#recent-bills-table tbody');
    tbody.innerHTML = data.recent_bills.map(b => `
        <tr>
            <td>${b.bill_number}</td>
            <td>${b.vendor_name}</td>
            <td>${b.bill_date}</td>
            <td>${fmt(b.total_amount)}</td>
            <td>${statusBadge(b.status)}</td>
            <td>
                <button class="btn btn-primary btn-sm" onclick="viewBill(${b.bill_id})">View</button>
            </td>
        </tr>
    `).join('');

    // Recommendations
    document.getElementById('recommendations').innerHTML = data.recommendations.map(r => `
        <div class="reco-card ${r.priority.toLowerCase()}">
            <div class="reco-title">${r.icon} ${r.title}</div>
            <div class="reco-msg">${r.msg}</div>
            <div class="reco-impact" style="color: ${r.priority === 'HIGH' ? 'var(--error)' : 'var(--text-secondary)'}">
                Impact: ${r.impact}
            </div>
        </div>
    `).join('');

    // Status breakdown
    const sb = data.stats.status_breakdown;
    const total = Object.values(sb).reduce((a, b) => a + b, 0) || 1;
    const statusColors = { Pending: '#f59e0b', Validated: '#22c55e', Flagged: '#ef4444', Approved: '#3b82f6', Rejected: '#6b7280' };

    document.getElementById('status-breakdown').innerHTML = Object.entries(sb).map(([s, c]) => `
        <div class="status-row">
            <div class="status-dot" style="background:${statusColors[s] || '#888'}"></div>
            <span>${s}</span>
            <span style="margin-left:auto; color:${statusColors[s]}; font-weight:600">${c} (${Math.round(c/total*100)}%)</span>
        </div>
    `).join('');
}


// ═══════════════════════════════════════════════════════════════
//  BILL ENTRY
// ═══════════════════════════════════════════════════════════════

async function loadProductDropdown() {
    const data = await api('/api/products');
    productsList = data.products;
    const sel = document.getElementById('item-product');
    sel.innerHTML = '<option value="">-- Select Product --</option>' +
        productsList.map(p => `<option value="${p.product_id}" data-price="${p.unit_price}" data-tax="${p.tax_rate}">${p.name}</option>`).join('');

    // Auto-fill price/tax on select
    sel.onchange = () => {
        const opt = sel.options[sel.selectedIndex];
        if (opt.value) {
            document.getElementById('item-price').value = opt.dataset.price;
            const qty = parseInt(document.getElementById('item-qty').value) || 1;
            const tax = (parseFloat(opt.dataset.price) * qty * parseFloat(opt.dataset.tax) / 100).toFixed(2);
            document.getElementById('item-tax').value = tax;
        }
    };

    // Set today's date
    document.getElementById('bill-date').value = new Date().toISOString().split('T')[0];
}

function addLineItem() {
    const sel = document.getElementById('item-product');
    const opt = sel.options[sel.selectedIndex];
    if (!opt.value) return alert('Select a product first');

    const qty = parseInt(document.getElementById('item-qty').value) || 1;
    const price = parseFloat(document.getElementById('item-price').value) || 0;
    const tax = parseFloat(document.getElementById('item-tax').value) || 0;
    const total = (price * qty + tax);

    lineItems.push({
        product_id: parseInt(opt.value),
        product_name: opt.text,
        quantity: qty,
        unit_price: price,
        tax_amount: tax,
        line_total: Math.round(total * 100) / 100
    });

    renderLineItems();
    sel.value = '';
    document.getElementById('item-qty').value = '1';
    document.getElementById('item-price').value = '';
    document.getElementById('item-tax').value = '';
}

function removeLastItem() {
    lineItems.pop();
    renderLineItems();
}

function renderLineItems() {
    const tbody = document.querySelector('#line-items-table tbody');
    tbody.innerHTML = lineItems.map(i => `
        <tr>
            <td>${i.product_name}</td>
            <td>${i.quantity}</td>
            <td>${fmt(i.unit_price)}</td>
            <td>${fmt(i.tax_amount)}</td>
            <td>${fmt(i.line_total)}</td>
        </tr>
    `).join('');

    const total = lineItems.reduce((s, i) => s + i.line_total, 0);
    document.getElementById('items-total').textContent = `Items Total: ${fmt(total)}`;
}

async function submitBill() {
    const billNumber = document.getElementById('bill-number').value.trim();
    const vendor = document.getElementById('bill-vendor').value.trim();
    const date = document.getElementById('bill-date').value;
    const totalStr = document.getElementById('bill-total').value;

    if (!billNumber) return alert('Enter a bill number');
    if (!vendor) return alert('Enter a vendor name');
    if (lineItems.length === 0) return alert('Add at least one line item');

    const total = totalStr ? parseFloat(totalStr) : lineItems.reduce((s, i) => s + i.line_total, 0);

    const body = {
        bill_number: billNumber,
        vendor_name: vendor,
        bill_date: date,
        total_amount: total,
        items: lineItems
    };

    try {
        const data = await api('/api/bills', 'POST', body);
        if (data.error) return alert('Error: ' + data.error);

        // Show validation results
        const v = data.validation;
        const container = document.getElementById('validation-results');
        container.innerHTML = `
            <div class="alert ${v.passed ? 'alert-success' : 'alert-error'}">
                ${v.summary} — ${v.passed_count}/${v.total} checks passed
            </div>
            ${v.results.filter(r => !r.passed).map(r => `
                <div class="alert alert-${r.severity === 'WARNING' ? 'warning' : 'error'}">
                    ${r.check}: ${r.message}
                </div>
            `).join('')}
        `;

        alert(v.passed ? '✓ Bill saved and validated!' : '⚠️ Bill saved but flagged with issues');
        clearBillForm();
    } catch (e) {
        alert('Failed to save: ' + e.message);
    }
}

function clearBillForm() {
    document.getElementById('bill-number').value = '';
    document.getElementById('bill-vendor').value = '';
    document.getElementById('bill-date').value = new Date().toISOString().split('T')[0];
    document.getElementById('bill-total').value = '';
    lineItems = [];
    renderLineItems();
    document.getElementById('validation-results').innerHTML = '';
}


// ═══════════════════════════════════════════════════════════════
//  BILL DETAIL MODAL
// ═══════════════════════════════════════════════════════════════

async function viewBill(billId) {
    const data = await api(`/api/bills/${billId}`);
    const bill = data.bill;
    const logs = data.logs;

    document.getElementById('modal-title').textContent = `Bill #${bill.bill_number}`;
    document.getElementById('bill-modal').style.display = 'flex';

    document.getElementById('modal-body').innerHTML = `
        <div class="info-grid">
            <div class="info-item"><label>Bill Number</label><span>${bill.bill_number}</span></div>
            <div class="info-item"><label>Vendor</label><span>${bill.vendor_name}</span></div>
            <div class="info-item"><label>Date</label><span>${bill.bill_date}</span></div>
            <div class="info-item"><label>Status</label><span>${statusBadge(bill.status)}</span></div>
            <div class="info-item"><label>Stated Total</label><span>${fmt(bill.total_amount)}</span></div>
            <div class="info-item"><label>Calculated Total</label><span>${fmt(bill.calculated_total)}</span></div>
            <div class="info-item"><label>Discrepancy</label><span style="color:${bill.discrepancy !== 0 ? 'var(--error)' : 'inherit'}">${fmt(bill.discrepancy)}</span></div>
            <div class="info-item"><label>Items</label><span>${bill.item_count}</span></div>
        </div>

        <h3 class="section-title">📦 Line Items</h3>
        <table class="data-table">
            <thead><tr><th>Product</th><th>Qty</th><th>Price</th><th>Tax</th><th>Total</th></tr></thead>
            <tbody>
                ${bill.items.map(i => `
                    <tr>
                        <td>${i.product_name}</td>
                        <td>${i.quantity}</td>
                        <td>${fmt(i.unit_price)}</td>
                        <td>${fmt(i.tax_amount)}</td>
                        <td>${fmt(i.line_total)}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>

        <h3 class="section-title" style="margin-top:16px;">🔍 Validation Logs</h3>
        ${logs.length === 0 ? '<p style="color:var(--text-secondary)">No validation run yet.</p>' :
            logs.map(l => `
                <div class="alert alert-${l.severity === 'WARNING' ? 'warning' : 'error'}">
                    [${l.error_type}] ${l.message}
                </div>
            `).join('')
        }

        <div class="btn-row" style="margin-top:16px;">
            <button class="btn btn-primary" onclick="validateBill(${bill.bill_id})">🔍 Run Validation</button>
            <button class="btn btn-success" onclick="setBillStatus(${bill.bill_id}, 'Approved')">✓ Approve</button>
            <button class="btn btn-danger" onclick="setBillStatus(${bill.bill_id}, 'Rejected')">✗ Reject</button>
            <button class="btn btn-danger" onclick="deleteBill(${bill.bill_id})">🗑️ Delete</button>
        </div>
    `;
}

function closeModal() {
    document.getElementById('bill-modal').style.display = 'none';
}

async function validateBill(billId) {
    const data = await api(`/api/bills/${billId}/validate`, 'POST');
    alert(data.validation.summary);
    viewBill(billId);  // Refresh modal
    loadDashboard();   // Refresh dashboard
}

async function setBillStatus(billId, status) {
    await api(`/api/bills/${billId}/status`, 'PUT', { status });
    alert(`Bill marked as ${status}`);
    viewBill(billId);
    loadDashboard();
}

async function deleteBill(billId) {
    if (!confirm('Delete this bill? This cannot be undone.')) return;
    await api(`/api/bills/${billId}`, 'DELETE');
    closeModal();
    loadDashboard();
}


// ═══════════════════════════════════════════════════════════════
//  PRODUCTS
// ═══════════════════════════════════════════════════════════════

async function loadProducts(query = '', category = '') {
    let url = '/api/products';
    const params = [];
    if (query) params.push(`q=${encodeURIComponent(query)}`);
    if (category) params.push(`category=${encodeURIComponent(category)}`);
    if (params.length) url += '?' + params.join('&');

    const data = await api(url);
    const tbody = document.querySelector('#products-table tbody');
    tbody.innerHTML = data.products.map(p => `
        <tr>
            <td>${p.product_id}</td>
            <td>${p.name}</td>
            <td>${p.category}</td>
            <td>${fmt(p.unit_price)}</td>
            <td>${p.tax_rate}%</td>
            <td>
                <button class="btn btn-primary btn-sm" onclick="editProduct(${p.product_id}, '${p.name.replace(/'/g, "\\'")}', '${p.category.replace(/'/g, "\\'")}', ${p.unit_price}, ${p.tax_rate})">✏️</button>
                <button class="btn btn-danger btn-sm" onclick="deleteProduct(${p.product_id}, '${p.name.replace(/'/g, "\\'")}')">🗑️</button>
            </td>
        </tr>
    `).join('');

    // Update category filter
    const catFilter = document.getElementById('product-cat-filter');
    const current = catFilter.value;
    catFilter.innerHTML = '<option value="">All Categories</option>' +
        data.categories.map(c => `<option value="${c}" ${c === current ? 'selected' : ''}>${c}</option>`).join('');
}

function searchProducts() {
    const q = document.getElementById('product-search').value;
    loadProducts(q);
}

function filterProductsCat() {
    const cat = document.getElementById('product-cat-filter').value;
    loadProducts('', cat);
}

function editProduct(id, name, category, price, tax) {
    editingProductId = id;
    document.getElementById('product-form-title').textContent = `✏️ Editing: ${name}`;
    document.getElementById('prod-name').value = name;
    document.getElementById('prod-category').value = category;
    document.getElementById('prod-price').value = price;
    document.getElementById('prod-tax').value = tax;
    document.getElementById('cancel-edit-btn').style.display = 'inline-block';
}

function cancelProductEdit() {
    editingProductId = null;
    document.getElementById('product-form-title').textContent = '➕ Add New Product';
    document.getElementById('prod-name').value = '';
    document.getElementById('prod-category').value = '';
    document.getElementById('prod-price').value = '';
    document.getElementById('prod-tax').value = '';
    document.getElementById('cancel-edit-btn').style.display = 'none';
}

async function saveProduct() {
    const name = document.getElementById('prod-name').value.trim();
    if (!name) return alert('Product name is required');

    const body = {
        name,
        category: document.getElementById('prod-category').value.trim(),
        unit_price: parseFloat(document.getElementById('prod-price').value) || 0,
        tax_rate: parseFloat(document.getElementById('prod-tax').value) || 0
    };

    if (editingProductId) {
        await api(`/api/products/${editingProductId}`, 'PUT', body);
        alert(`Product '${name}' updated`);
    } else {
        await api('/api/products', 'POST', body);
        alert(`Product '${name}' added`);
    }

    cancelProductEdit();
    loadProducts();
}

async function deleteProduct(id, name) {
    if (!confirm(`Delete product '${name}'?`)) return;
    await api(`/api/products/${id}`, 'DELETE');
    loadProducts();
}


// ═══════════════════════════════════════════════════════════════
//  REPORTS
// ═══════════════════════════════════════════════════════════════

async function loadReport(type, btn = null) {
    // Update active tab button
    if (btn) {
        document.querySelectorAll('.report-tab').forEach(t => t.classList.remove('active'));
        btn.classList.add('active');
    }

    const container = document.getElementById('report-content');
    container.innerHTML = '<p style="color:var(--text-secondary)">Loading...</p>';

    try {
        const data = await api(`/api/reports/${type}`);

        if (type === 'category') {
            const total = data.reduce((s, r) => s + (r.total || 0), 0);
            const maxVal = data.length ? Math.max(...data.map(r => r.total || 0)) : 1;
            container.innerHTML = `
                <h3 class="section-title">💰 Spending by Category — Total: ${fmt(total)}</h3>
                ${data.map(r => `
                    <div class="bar-row">
                        <div class="bar-label">${r.category}</div>
                        <div class="bar-fill" style="width:${Math.max(4, r.total/maxVal*300)}px"></div>
                        <div class="bar-value">${r.total_fmt} (${r.pct}%) — ${r.bills} bills</div>
                    </div>
                `).join('')}
            `;
        }

        else if (type === 'vendor') {
            container.innerHTML = `
                <h3 class="section-title">🏪 Vendor Analysis</h3>
                <table class="data-table">
                    <thead><tr><th>Vendor</th><th>Bills</th><th>Total</th><th>Avg</th><th>Errors</th><th>Reliability</th><th>Rating</th></tr></thead>
                    <tbody>
                        ${data.map(v => `
                            <tr>
                                <td>${v.vendor}</td>
                                <td>${v.bills}</td>
                                <td>${v.total_fmt}</td>
                                <td>${v.avg_fmt}</td>
                                <td>${v.errors}</td>
                                <td>${v.reliability}%</td>
                                <td>${v.rating}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        }

        else if (type === 'monthly') {
            if (data.length === 0) {
                container.innerHTML = '<p style="color:var(--text-secondary)">No monthly data yet.</p>';
                return;
            }
            container.innerHTML = `
                <h3 class="section-title">📈 Monthly Spending Trend</h3>
                ${data.map(m => `
                    <div class="bar-row">
                        <div class="bar-label">${m.month}</div>
                        <div class="bar-fill green" style="width:${Math.max(4, m.bar_pct * 3)}px"></div>
                        <div class="bar-value">${m.total_fmt} (${m.bills} bills)</div>
                    </div>
                `).join('')}
            `;
        }

        else if (type === 'errors') {
            container.innerHTML = `
                <h3 class="section-title">🔴 Error Log — Total: ${data.total}</h3>
                ${data.breakdown.length === 0 ? '<p style="color:var(--text-secondary)">No errors recorded.</p>' :
                    data.breakdown.map(e => `
                        <div class="bar-row">
                            <div class="bar-label">${e.type}</div>
                            <div class="bar-fill red" style="width:${Math.max(4, e.pct * 3)}px"></div>
                            <div class="bar-value">${e.count} (${e.pct}%)</div>
                        </div>
                    `).join('')
                }
            `;
        }

        else if (type === 'price') {
            container.innerHTML = `
                <h3 class="section-title">💡 Price Analysis</h3>
                <table class="data-table">
                    <thead><tr><th>Product</th><th>Category</th><th>Catalog</th><th>Min</th><th>Max</th><th>Avg</th><th>Volatility</th><th>Status</th></tr></thead>
                    <tbody>
                        ${data.map(p => `
                            <tr>
                                <td>${p.product}</td>
                                <td>${p.category}</td>
                                <td>${p.catalog_fmt}</td>
                                <td>${p.min_fmt}</td>
                                <td>${p.max_fmt}</td>
                                <td>${p.avg_fmt}</td>
                                <td>${p.volatility}%</td>
                                <td>${p.flag ? '<span style="color:var(--error)">⚠️ High</span>' : '<span style="color:var(--success)">✓ OK</span>'}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        }
    } catch (e) {
        container.innerHTML = `<p style="color:var(--error)">Error: ${e.message}</p>`;
    }
}


// ═══════════════════════════════════════════════════════════════
//  VALIDATE ALL
// ═══════════════════════════════════════════════════════════════

async function validateAll() {
    const data = await api('/api/validate-all', 'POST');
    alert(`Validated ${data.total} bills:\n✓ ${data.validated} passed\n⚠️ ${data.flagged} flagged`);
    loadDashboard();
}


// ═══════════════════════════════════════════════════════════════
//  INIT — Load dashboard on page load
// ═══════════════════════════════════════════════════════════════

loadDashboard();
