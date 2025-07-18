// Sample data - in a real implementation, this would come from your Python backend
let products = [
    {
        id: 1,
        name: "MacBook Pro M1",
        url: "https://www.amazon.in/Apple-MacBook-Chip-13-inch-512GB/dp/B08N5WRWNW",
        selector: ".a-color-price",
        expectedText: "Currently unavailable",
        email: "user@example.com",
        isActive: true,
        lastChecked: "2024-01-15 14:25:00",
        createdAt: "2024-01-15 10:00:00"
    },
    {
        id: 2,
        name: "Google Test",
        url: "https://www.google.com",
        selector: "title",
        expectedText: "NonExistentText",
        email: "user@example.com",
        isActive: false,
        lastChecked: "2024-01-15 14:20:00",
        createdAt: "2024-01-15 12:00:00"
    }
];

let monitoringActive = false;
let monitoringInterval;

// Initialize the dashboard
document.addEventListener('DOMContentLoaded', function() {
    loadProducts();
    updateStats();
    setupEventListeners();
});

function setupEventListeners() {
    // Add product form
    document.getElementById('addProductForm').addEventListener('submit', function(e) {
        e.preventDefault();
        addProduct();
    });

    // Bot controls
    document.getElementById('startMonitoring').addEventListener('click', startMonitoring);
    document.getElementById('stopMonitoring').addEventListener('click', stopMonitoring);
    document.getElementById('testEmail').addEventListener('click', testEmail);

    // Modal
    document.querySelector('.close').addEventListener('click', closeModal);
    window.addEventListener('click', function(e) {
        if (e.target === document.getElementById('productModal')) {
            closeModal();
        }
    });
}

function loadProducts() {
    const productsList = document.getElementById('productsList');
    productsList.innerHTML = '';

    if (products.length === 0) {
        productsList.innerHTML = '<p style="text-align: center; color: #7f8c8d; padding: 20px;">No products added yet. Add your first product above!</p>';
        return;
    }

    products.forEach(product => {
        const productDiv = document.createElement('div');
        productDiv.className = `product-item ${product.isActive ? '' : 'inactive'}`;
        
        productDiv.innerHTML = `
            <div class="product-header">
                <div class="product-name">${product.name}</div>
                <div class="product-status ${product.isActive ? 'status-active' : 'status-inactive'}">
                    ${product.isActive ? '🟢 Active' : '🔴 Inactive'}
                </div>
            </div>
            <div class="product-details">
                <div><strong>URL:</strong> ${product.url}</div>
                <div><strong>Email:</strong> ${product.email}</div>
                <div><strong>Last Checked:</strong> ${product.lastChecked || 'Never'}</div>
            </div>
            <div class="product-actions">
                <button class="btn btn-primary btn-sm" onclick="testProduct(${product.id})">
                    🧪 Test
                </button>
                <button class="btn btn-warning btn-sm" onclick="viewProduct(${product.id})">
                    👁️ View
                </button>
                <button class="btn btn-danger btn-sm" onclick="deleteProduct(${product.id})">
                    🗑️ Delete
                </button>
            </div>
        `;
        
        productsList.appendChild(productDiv);
    });
}

function updateStats() {
    const totalProducts = products.length;
    const activeProducts = products.filter(p => p.isActive).length;
    const notificationsSent = products.filter(p => !p.isActive).length; // Simplified

    document.getElementById('totalProducts').textContent = totalProducts;
    document.getElementById('activeProducts').textContent = activeProducts;
    document.getElementById('notificationsSent').textContent = notificationsSent;
}

function addProduct() {
    const form = document.getElementById('addProductForm');
    const formData = new FormData(form);
    
    const newProduct = {
        id: Date.now(),
        name: formData.get('productName'),
        url: formData.get('productUrl'),
        selector: formData.get('productSelector'),
        expectedText: formData.get('expectedText'),
        email: formData.get('productEmail'),
        isActive: true,
        lastChecked: null,
        createdAt: new Date().toISOString().slice(0, 19).replace('T', ' ')
    };

    products.push(newProduct);
    loadProducts();
    updateStats();
    form.reset();
    
    showNotification('Product added successfully!', 'success');
}

function testProduct(productId) {
    const product = products.find(p => p.id === productId);
    if (!product) return;

    showNotification(`Testing ${product.name}...`, 'info');
    
    // Simulate testing
    setTimeout(() => {
        const isInStock = Math.random() > 0.5;
        const message = isInStock ? 
            `${product.name} is IN STOCK! 🎉` : 
            `${product.name} is out of stock.`;
        
        showNotification(message, isInStock ? 'success' : 'info');
        addLogEntry(`Tested ${product.name}: ${isInStock ? 'IN STOCK' : 'OUT OF STOCK'}`);
        
        // Update last checked
        product.lastChecked = new Date().toISOString().slice(0, 19).replace('T', ' ');
        loadProducts();
    }, 2000);
}

function viewProduct(productId) {
    const product = products.find(p => p.id === productId);
    if (!product) return;

    document.getElementById('modalTitle').textContent = product.name;
    document.getElementById('modalContent').innerHTML = `
        <div style="margin-bottom: 15px;"><strong>URL:</strong> <a href="${product.url}" target="_blank">${product.url}</a></div>
        <div style="margin-bottom: 15px;"><strong>CSS Selector:</strong> <code>${product.selector}</code></div>
        <div style="margin-bottom: 15px;"><strong>Expected Text:</strong> "${product.expectedText}"</div>
        <div style="margin-bottom: 15px;"><strong>Email:</strong> ${product.email}</div>
        <div style="margin-bottom: 15px;"><strong>Status:</strong> ${product.isActive ? '🟢 Active' : '🔴 Inactive'}</div>
        <div style="margin-bottom: 15px;"><strong>Created:</strong> ${product.createdAt}</div>
        <div style="margin-bottom: 15px;"><strong>Last Checked:</strong> ${product.lastChecked || 'Never'}</div>
    `;
    
    document.getElementById('productModal').style.display = 'block';
}

function deleteProduct(productId) {
    if (confirm('Are you sure you want to delete this product?')) {
        products = products.filter(p => p.id !== productId);
        loadProducts();
        updateStats();
        showNotification('Product deleted successfully!', 'success');
    }
}

function startMonitoring() {
    if (monitoringActive) return;
    
    monitoringActive = true;
    document.getElementById('monitoringStatus').textContent = '🟢 Running';
    document.getElementById('monitoringStatus').style.color = '#27ae60';
    
    showNotification('Monitoring started!', 'success');
    addLogEntry('Bot monitoring started');
    
    // Simulate monitoring
    monitoringInterval = setInterval(() => {
        const activeProducts = products.filter(p => p.isActive);
        if (activeProducts.length > 0) {
            const product = activeProducts[Math.floor(Math.random() * activeProducts.length)];
            addLogEntry(`Checked ${product.name}: OUT OF STOCK`);
            product.lastChecked = new Date().toISOString().slice(0, 19).replace('T', ' ');
            loadProducts();
        }
    }, 10000); // Check every 10 seconds for demo
}

function stopMonitoring() {
    if (!monitoringActive) return;
    
    monitoringActive = false;
    document.getElementById('monitoringStatus').textContent = '🔴 Stopped';
    document.getElementById('monitoringStatus').style.color = '#e74c3c';
    
    if (monitoringInterval) {
        clearInterval(monitoringInterval);
    }
    
    showNotification('Monitoring stopped!', 'info');
    addLogEntry('Bot monitoring stopped');
}

function testEmail() {
    showNotification('Sending test email...', 'info');
    
    // Simulate email test
    setTimeout(() => {
        showNotification('Test email sent successfully! 📧', 'success');
        addLogEntry('Test email sent successfully');
    }, 2000);
}

function closeModal() {
    document.getElementById('productModal').style.display = 'none';
}

function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 4000);
}

function addLogEntry(message) {
    const logsList = document.getElementById('logsList');
    const logEntry = document.createElement('div');
    logEntry.className = 'log-entry';
    
    const now = new Date().toISOString().slice(0, 19).replace('T', ' ');
    logEntry.innerHTML = `<span class="log-time">${now}</span> - ${message}`;
    
    logsList.insertBefore(logEntry, logsList.firstChild);
    
    // Keep only last 20 entries
    while (logsList.children.length > 20) {
        logsList.removeChild(logsList.lastChild);
    }
}

// Initialize with some sample log entries
setTimeout(() => {
    addLogEntry('Dashboard loaded successfully');
    addLogEntry('Ready to monitor products');
}, 1000);