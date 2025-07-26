// Dashboard JavaScript functionality
class RestockDashboard {
    constructor() {
        this.init();
        this.loadData();
        this.setupEventListeners();
        // Auto-refresh every 30 seconds
        this.autoRefreshInterval = setInterval(() => {
            this.loadData();
        }, 30000);
    }

    init() {
        console.log('Restock Dashboard initialized');
    }

    setupEventListeners() {
        // Add product form
        document.getElementById('addProductForm').addEventListener('submit', (e) => {
            this.handleAddProduct(e);
        });

        // Control buttons
        document.getElementById('startMonitoring').addEventListener('click', () => {
            this.startMonitoring();
        });

        document.getElementById('stopMonitoring').addEventListener('click', () => {
            this.stopMonitoring();
        });

        document.getElementById('testEmail').addEventListener('click', () => {
            this.testEmail();
        });

        // Close modal
        document.querySelector('.close').addEventListener('click', () => {
            this.closeModal();
        });

        // Close modal when clicking outside
        window.addEventListener('click', (e) => {
            const modal = document.getElementById('productModal');
            if (e.target === modal) {
                this.closeModal();
            }
        });
    }

    async loadData() {
        try {
            await Promise.all([
                this.loadStatus(),
                this.loadProducts(),
                this.loadLogs()
            ]);
        } catch (error) {
            console.error('Error loading data:', error);
            this.showNotification('Error loading dashboard data', 'error');
        }
    }

    async loadStatus() {
        try {
            const response = await fetch('/api/status');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            
            document.getElementById('totalProducts').textContent = data.total_products;
            document.getElementById('activeProducts').textContent = data.active_products;
            document.getElementById('notificationsSent').textContent = data.notifications_sent;
            document.getElementById('monitoringStatus').textContent = data.monitoring_status;
            
            // Update monitoring status color
            const statusElement = document.getElementById('monitoringStatus');
            statusElement.className = data.monitoring_status === 'Running' ? 'status-running' : 'status-stopped';
            
        } catch (error) {
            console.error('Error loading status:', error);
        }
    }

    async loadProducts() {
        try {
            const response = await fetch('/api/products');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const products = await response.json();
            this.renderProducts(products);
        } catch (error) {
            console.error('Error loading products:', error);
            document.getElementById('productsList').innerHTML = '<p>Error loading products</p>';
        }
    }

    renderProducts(products) {
        const container = document.getElementById('productsList');
        
        if (products.length === 0) {
            container.innerHTML = '<p class="no-products">No products added yet. Add your first product above!</p>';
            return;
        }

        const productsHtml = products.map(product => `
            <div class="product-item ${product.is_active ? 'active' : 'inactive'}">
                <div class="product-header">
                    <h4>${this.escapeHtml(product.name)}</h4>
                    <div class="product-status">
                        ${product.is_active ? '🟢 Active' : '🔴 Inactive'}
                    </div>
                </div>
                <div class="product-details">
                    <p><strong>URL:</strong> <a href="${product.url}" target="_blank" rel="noopener">${this.truncateUrl(product.url)}</a></p>
                    <p><strong>Email:</strong> ${this.escapeHtml(product.email)}</p>
                    <p><strong>Selector:</strong> <code>${this.escapeHtml(product.selector)}</code></p>
                    <p><strong>Expected Text:</strong> "${this.escapeHtml(product.expected_text)}"</p>
                    <p><strong>Last Checked:</strong> ${product.last_checked || 'Never'}</p>
                    <p><strong>Created:</strong> ${this.formatDate(product.created_at)}</p>
                </div>
                <div class="product-actions">
                    <button class="btn btn-info btn-sm" onclick="dashboard.testProduct(${product.id})">
                        🧪 Test
                    </button>
                    <button class="btn btn-secondary btn-sm" onclick="dashboard.viewProduct(${product.id})">
                        👁️ Details
                    </button>
                    ${product.is_active ? `
                        <button class="btn btn-danger btn-sm" onclick="dashboard.deactivateProduct(${product.id})">
                            ⏹️ Deactivate
                        </button>
                    ` : ''}
                </div>
            </div>
        `).join('');

        container.innerHTML = productsHtml;
    }

    async loadLogs() {
        try {
            const response = await fetch('/api/logs');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            this.renderLogs(data.logs);
        } catch (error) {
            console.error('Error loading logs:', error);
        }
    }

    renderLogs(logs) {
        const container = document.getElementById('logsList');
        
        if (!logs || logs.length === 0) {
            container.innerHTML = '<div class="log-entry">No logs available</div>';
            return;
        }

        const logsHtml = logs.slice(-20).reverse().map(log => {
            const logClass = this.getLogClass(log);
            return `<div class="log-entry ${logClass}">${this.escapeHtml(log)}</div>`;
        }).join('');

        container.innerHTML = logsHtml;
    }

    getLogClass(log) {
        if (log.includes('ERROR')) return 'log-error';
        if (log.includes('WARNING')) return 'log-warning';
        if (log.includes('INFO')) return 'log-info';
        return '';
    }

    async handleAddProduct(e) {
        e.preventDefault();
        
        const form = e.target;
        const formData = new FormData(form);
        
        const productData = {
            name: formData.get('productName').trim(),
            url: formData.get('productUrl').trim(),
            selector: formData.get('productSelector').trim(),
            expected_text: formData.get('expectedText').trim(),
            email: formData.get('productEmail').trim()
        };

        // Validate required fields
        if (!productData.name || !productData.url || !productData.selector || 
            !productData.expected_text || !productData.email) {
            this.showNotification('Please fill in all fields', 'error');
            return;
        }

        // Validate URL format
        try {
            new URL(productData.url);
        } catch {
            this.showNotification('Please enter a valid URL', 'error');
            return;
        }

        // Validate email format
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(productData.email)) {
            this.showNotification('Please enter a valid email address', 'error');
            return;
        }

        try {
            const submitButton = form.querySelector('button[type="submit"]');
            const originalText = submitButton.textContent;
            submitButton.textContent = 'Adding...';
            submitButton.disabled = true;

            const response = await fetch('/api/products', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(productData)
            });

            const result = await response.json();

            if (response.ok) {
                this.showNotification(result.message, 'success');
                form.reset();
                // Reload data to show the new product
                await this.loadData();
            } else {
                this.showNotification(result.detail || 'Error adding product', 'error');
            }

        } catch (error) {
            console.error('Error adding product:', error);
            this.showNotification('Network error. Please try again.', 'error');
        } finally {
            const submitButton = form.querySelector('button[type="submit"]');
            submitButton.textContent = 'Add Product';
            submitButton.disabled = false;
        }
    }

    async testProduct(productId) {
        try {
            this.showNotification('Testing product...', 'info');
            
            const response = await fetch(`/api/products/${productId}/test`, {
                method: 'POST'
            });

            const result = await response.json();

            if (response.ok) {
                const status = result.in_stock ? 'IN STOCK ✅' : 'OUT OF STOCK ❌';
                this.showNotification(`${result.product_name}: ${status}`, 'info');
                // Reload data to update last checked time
                await this.loadData();
            } else {
                this.showNotification(result.detail || 'Error testing product', 'error');
            }

        } catch (error) {
            console.error('Error testing product:', error);
            this.showNotification('Error testing product', 'error');
        }
    }

    async deactivateProduct(productId) {
        if (!confirm('Are you sure you want to deactivate this product?')) {
            return;
        }

        try {
            const response = await fetch(`/api/products/${productId}`, {
                method: 'DELETE'
            });

            const result = await response.json();

            if (response.ok) {
                this.showNotification(result.message, 'success');
                await this.loadData();
            } else {
                this.showNotification(result.detail || 'Error deactivating product', 'error');
            }

        } catch (error) {
            console.error('Error deactivating product:', error);
            this.showNotification('Error deactivating product', 'error');
        }
    }

    async startMonitoring() {
        try {
            const response = await fetch('/api/monitoring/start', {
                method: 'POST'
            });

            const result = await response.json();
            this.showNotification(result.message, 'success');
            await this.loadStatus();

        } catch (error) {
            console.error('Error starting monitoring:', error);
            this.showNotification('Error starting monitoring', 'error');
        }
    }

    async stopMonitoring() {
        try {
            const response = await fetch('/api/monitoring/stop', {
                method: 'POST'
            });

            const result = await response.json();
            this.showNotification(result.message, 'info');
            await this.loadStatus();

        } catch (error) {
            console.error('Error stopping monitoring:', error);
            this.showNotification('Error stopping monitoring', 'error');
        }
    }

    async testEmail() {
        try {
            this.showNotification('Sending test email...', 'info');
            
            const response = await fetch('/api/test-email', {
                method: 'POST'
            });

            const result = await response.json();

            if (response.ok) {
                this.showNotification(result.message, 'success');
            } else {
                this.showNotification(result.detail || 'Email test failed', 'error');
            }

        } catch (error) {
            console.error('Error testing email:', error);
            this.showNotification('Error testing email', 'error');
        }
    }

    viewProduct(productId) {
        // This would show product details in a modal
        console.log('View product:', productId);
        // For now, just show a simple alert
        this.showNotification('Product details feature coming soon!', 'info');
    }

    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <span>${this.escapeHtml(message)}</span>
            <button class="notification-close" onclick="this.parentElement.remove()">&times;</button>
        `;

        // Add to page
        document.body.appendChild(notification);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 5000);
    }

    closeModal() {
        document.getElementById('productModal').style.display = 'none';
    }

    // Utility functions
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    truncateUrl(url, maxLength = 50) {
        return url.length > maxLength ? url.substring(0, maxLength) + '...' : url;
    }

    formatDate(dateString) {
        if (!dateString) return 'Unknown';
        try {
            return new Date(dateString).toLocaleString();
        } catch {
            return dateString;
        }
    }

    // Cleanup
    destroy() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
        }
    }
}

// Initialize dashboard when page loads
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new RestockDashboard();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (dashboard) {
        dashboard.destroy();
    }
});