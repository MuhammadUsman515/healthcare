// Sidebar toggle
document.getElementById('sidebarToggle')?.addEventListener('click', function () {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('collapsed');
    localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
});

// Restore sidebar state
window.addEventListener('DOMContentLoaded', function () {
    const sidebar = document.getElementById('sidebar');
    if (sidebar && localStorage.getItem('sidebarCollapsed') === 'true') {
        sidebar.classList.add('collapsed');
    }

    // Live clock
    function updateTime() {
        const el = document.getElementById('current-time');
        if (el) {
            el.textContent = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
        }
    }
    updateTime();
    setInterval(updateTime, 1000);

    // Auto-dismiss alerts after 5 seconds
    document.querySelectorAll('.alert').forEach(function (alert) {
        setTimeout(function () {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        }, 5000);
    });
});

// Dynamic prescription rows
function addPrescriptionRow() {
    const tbody = document.getElementById('prescription-tbody');
    if (!tbody) return;
    const row = document.createElement('tr');
    row.innerHTML = `
        <td><input type="text" name="medicine_name[]" class="form-control form-control-sm" placeholder="Medicine name" required></td>
        <td><input type="text" name="dosage[]" class="form-control form-control-sm" placeholder="e.g. 500mg"></td>
        <td><input type="text" name="frequency[]" class="form-control form-control-sm" placeholder="e.g. Twice daily"></td>
        <td><input type="text" name="duration[]" class="form-control form-control-sm" placeholder="e.g. 7 days"></td>
        <td><input type="text" name="instructions[]" class="form-control form-control-sm" placeholder="With food"></td>
        <td><button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('tr').remove()"><i class="fas fa-trash"></i></button></td>
    `;
    tbody.appendChild(row);
}

function addLabTestRow() {
    const tbody = document.getElementById('labtest-tbody');
    if (!tbody) return;
    const row = document.createElement('tr');
    row.innerHTML = `
        <td><input type="text" name="test_name[]" class="form-control form-control-sm" placeholder="Test name" required></td>
        <td><button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('tr').remove()"><i class="fas fa-trash"></i></button></td>
    `;
    tbody.appendChild(row);
}

// Dynamic billing rows
function addBillRow() {
    const tbody = document.getElementById('bill-items-tbody');
    if (!tbody) return;
    const row = document.createElement('tr');
    row.innerHTML = `
        <td><input type="text" name="description[]" class="form-control form-control-sm" placeholder="Service/Item" required></td>
        <td>
            <select name="item_type[]" class="form-select form-select-sm">
                <option value="consultation">Consultation</option>
                <option value="procedure">Procedure</option>
                <option value="medicine">Medicine</option>
                <option value="lab">Lab Test</option>
                <option value="room">Room Charge</option>
                <option value="other">Other</option>
            </select>
        </td>
        <td><input type="number" name="quantity[]" class="form-control form-control-sm bill-qty" value="1" min="0.01" step="0.01"></td>
        <td><input type="number" name="unit_price[]" class="form-control form-control-sm bill-price" value="0" min="0" step="0.01"></td>
        <td class="bill-total fw-bold">$0.00</td>
        <td><button type="button" class="btn btn-sm btn-outline-danger" onclick="removeRow(this)"><i class="fas fa-trash"></i></button></td>
    `;
    tbody.appendChild(row);
    attachBillListeners(row);
    updateBillTotals();
}

function removeRow(btn) {
    btn.closest('tr').remove();
    updateBillTotals();
}

function attachBillListeners(row) {
    row.querySelectorAll('.bill-qty, .bill-price').forEach(function (input) {
        input.addEventListener('input', function () {
            const tr = input.closest('tr');
            const qty = parseFloat(tr.querySelector('.bill-qty').value) || 0;
            const price = parseFloat(tr.querySelector('.bill-price').value) || 0;
            tr.querySelector('.bill-total').textContent = '$' + (qty * price).toFixed(2);
            updateBillTotals();
        });
    });
}

function updateBillTotals() {
    let subtotal = 0;
    document.querySelectorAll('#bill-items-tbody tr').forEach(function (row) {
        const qty = parseFloat(row.querySelector('.bill-qty')?.value) || 0;
        const price = parseFloat(row.querySelector('.bill-price')?.value) || 0;
        subtotal += qty * price;
    });

    const taxRate = parseFloat(document.getElementById('tax_rate')?.value) || 0;
    const discount = parseFloat(document.getElementById('discount')?.value) || 0;
    const tax = subtotal * taxRate / 100;
    const total = subtotal + tax - discount;

    if (document.getElementById('subtotal-display')) {
        document.getElementById('subtotal-display').textContent = '$' + subtotal.toFixed(2);
        document.getElementById('tax-display').textContent = '$' + tax.toFixed(2);
        document.getElementById('total-display').textContent = '$' + total.toFixed(2);
    }
}

// Initialize bill listeners on page load
window.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('#bill-items-tbody tr').forEach(attachBillListeners);
    document.getElementById('tax_rate')?.addEventListener('input', updateBillTotals);
    document.getElementById('discount')?.addEventListener('input', updateBillTotals);
    updateBillTotals();
});

// Confirm delete
function confirmDelete(form) {
    if (confirm('Are you sure you want to perform this action? This cannot be undone.')) {
        form.submit();
    }
}
