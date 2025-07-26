#!/usr/bin/env python3
"""
Restock Notification Bot
A real-time product availability notifier with CLI interface and SMTP integration
"""

import sqlite3
import smtplib
import requests
from bs4 import BeautifulSoup
import logging
import time
import argparse
import sys
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional
import re
from urllib.parse import urljoin, urlparse
import json
import os
from dataclasses import dataclass
from contextlib import contextmanager


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('restock_bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


@dataclass
class Product:
    """Data class for product information"""
    id: Optional[int] = None
    name: str = ""
    url: str = ""
    selector: str = ""
    expected_text: str = ""
    email: str = ""
    is_active: bool = True
    last_checked: Optional[str] = None
    created_at: Optional[str] = None


class DatabaseManager:
    """Handles all database operations"""
    
    def __init__(self, db_path: str = "restock_bot.db"):
        self.db_path = db_path
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def init_database(self):
        """Initialize the database with required tables"""
        with self.get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    selector TEXT NOT NULL,
                    expected_text TEXT NOT NULL,
                    email TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    last_checked DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER,
                    notification_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products (id)
                )
            ''')
            
            conn.commit()
            logger.info("Database initialized successfully")

    def add_product(self, product: Product):
        try:
            print(f"DEBUG: About to insert: {product.name}, {product.url}, {product.selector}, {product.expected_text}, {product.email}")
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO products (name, url, selector, expected_text, email)
                    VALUES (?, ?, ?, ?, ?)
                """, (product.name, product.url, product.selector, product.expected_text, product.email))
                print(f"DEBUG: Insert completed, row ID: {cursor.lastrowid}")
                conn.commit()
                print(f"DEBUG: Transaction committed")
                return cursor.lastrowid  # Return the new product ID
        except Exception as e:
            print(f"DEBUG: Database error: {str(e)}")
            raise e
    
    def get_active_products(self) -> List[Product]:
        """Get all active products for monitoring"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM products WHERE is_active = 1
            ''')
            products = []
            for row in cursor.fetchall():
                product = Product(
                    id=row['id'],
                    name=row['name'],
                    url=row['url'],
                    selector=row['selector'],
                    expected_text=row['expected_text'],
                    email=row['email'],
                    is_active=bool(row['is_active']),
                    last_checked=row['last_checked'],
                    created_at=row['created_at']
                )
                products.append(product)
            return products
    
    def update_last_checked(self, product_id: int):
        """Update the last checked timestamp for a product"""
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE products SET last_checked = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (product_id,))
            conn.commit()
    
    def deactivate_product(self, product_id: int):
        """Deactivate a product (stop monitoring)"""
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE products SET is_active = 0 WHERE id = ?
            ''', (product_id,))
            conn.commit()
    
    def log_notification(self, product_id: int, notification_type: str, message: str):
        """Log a notification to the database"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO notifications (product_id, notification_type, message)
                VALUES (?, ?, ?)
            ''', (product_id, notification_type, message))
            conn.commit()
    
    def get_all_products(self) -> List[Product]:
        """Get all products (active and inactive)"""
        with self.get_connection() as conn:
            cursor = conn.execute('SELECT * FROM products ORDER BY created_at DESC')
            products = []
            for row in cursor.fetchall():
                product = Product(
                    id=row['id'],
                    name=row['name'],
                    url=row['url'],
                    selector=row['selector'],
                    expected_text=row['expected_text'],
                    email=row['email'],
                    is_active=bool(row['is_active']),
                    last_checked=row['last_checked'],
                    created_at=row['created_at']
                )
                products.append(product)
            return products


class EmailNotifier:
    """Handles email notifications"""
    
    def __init__(self, smtp_server: str, smtp_port: int, username: str, password: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
    
    def send_notification(self, to_email: str, product_name: str, product_url: str):
        """Send restock notification email"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.username
            msg['To'] = to_email
            msg['Subject'] = f"🎉 {product_name} is back in stock!"
            
            body = f"""
            Great news! The product you've been waiting for is back in stock:
            
            Product: {product_name}
            URL: {product_url}
            
            Don't wait too long - it might go out of stock again!
            
            Happy shopping!
            
            ---
            Restock Notification Bot
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email} for {product_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False


class ProductChecker:
    """Handles web scraping and product availability checking"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def check_availability(self, product: Product) -> bool:
        """Check if product is available"""
        try:
            response = self.session.get(product.url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find element using CSS selector
            element = soup.select_one(product.selector)
            
            if element:
                element_text = element.get_text(strip=True).lower()
                expected_text = product.expected_text.lower()
                
                # Check if expected text is NOT in the element (meaning it's in stock)
                is_in_stock = expected_text not in element_text
                
                logger.info(f"Product {product.name}: {'IN STOCK' if is_in_stock else 'OUT OF STOCK'}")
                return is_in_stock
            else:
                logger.warning(f"Could not find element with selector '{product.selector}' for {product.name}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"Network error checking {product.name}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error checking {product.name}: {str(e)}")
            return False


class RestockBot:
    """Main bot class that orchestrates all components"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config = self.load_config(config_file)
        self.db = DatabaseManager()
        self.email_notifier = EmailNotifier(
            self.config['email']['smtp_server'],
            self.config['email']['smtp_port'],
            self.config['email']['username'],
            self.config['email']['password']
        )
        self.checker = ProductChecker()
    
    def load_config(self, config_file: str) -> dict:
        """Load configuration from JSON file"""
        default_config = {
            "email": {
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "username": "your_email@gmail.com",
                "password": "your_app_password"
            },
            "check_interval": 300,  # 5 minutes
            "max_retries": 3
        }
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    # Merge with default config
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            except Exception as e:
                logger.error(f"Error loading config file: {str(e)}")
                return default_config
        else:
            # Create default config file
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            logger.info(f"Created default config file: {config_file}")
            return default_config
    
    def add_product(self, name: str, url: str, selector: str, expected_text: str, email: str):
        """Add a new product to monitor"""
        try:
            product = Product(
                name=name,
                url=url,
                selector=selector,
                expected_text=expected_text,
                email=email
            )
            
            product_id = self.db.add_product(product)
            logger.info(f"Added product '{name}' with ID {product_id}")
            print(f"✅ Successfully added product '{name}' for monitoring")
            
        except sqlite3.IntegrityError:
            logger.error(f"Product with URL '{url}' already exists")
            print(f"❌ Product with URL '{url}' already exists")
        except Exception as e:
            logger.error(f"Error adding product: {str(e)}")
            print(f"❌ Error adding product: {str(e)}")
    
    def list_products(self):
        """List all products"""
        products = self.db.get_all_products()
        
        if not products:
            print("No products found.")
            return
        
        print("\n" + "="*80)
        print("MONITORED PRODUCTS")
        print("="*80)
        
        for product in products:
            status = "🟢 ACTIVE" if product.is_active else "🔴 INACTIVE"
            print(f"\nID: {product.id}")
            print(f"Name: {product.name}")
            print(f"URL: {product.url}")
            print(f"Status: {status}")
            print(f"Email: {product.email}")
            print(f"Created: {product.created_at}")
            print(f"Last Checked: {product.last_checked or 'Never'}")
            print("-" * 40)
    
    def run_monitor(self):
        """Run the monitoring loop"""
        logger.info("Starting restock monitoring...")
        print("🤖 Restock bot is now monitoring products...")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                products = self.db.get_active_products()
                
                if not products:
                    logger.info("No active products to monitor")
                    time.sleep(self.config['check_interval'])
                    continue
                
                for product in products:
                    try:
                        is_in_stock = self.checker.check_availability(product)
                        self.db.update_last_checked(product.id)
                        
                        if is_in_stock:
                            logger.info(f"🎉 {product.name} is back in stock!")
                            
                            # Send notification
                            if self.email_notifier.send_notification(
                                product.email, product.name, product.url
                            ):
                                self.db.log_notification(
                                    product.id, "email", f"Stock notification sent to {product.email}"
                                )
                                
                                # Deactivate product after successful notification
                                self.db.deactivate_product(product.id)
                                logger.info(f"Deactivated monitoring for {product.name}")
                        
                    except Exception as e:
                        logger.error(f"Error processing product {product.name}: {str(e)}")
                
                logger.info(f"Checked {len(products)} products. Sleeping for {self.config['check_interval']} seconds...")
                time.sleep(self.config['check_interval'])
                
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
            print("\n👋 Monitoring stopped. Goodbye!")
    
    def test_product(self, product_id: int):
        """Test a specific product for debugging"""
        products = self.db.get_all_products()
        product = next((p for p in products if p.id == product_id), None)
        
        if not product:
            print(f"❌ Product with ID {product_id} not found")
            return
        
        print(f"🧪 Testing product: {product.name}")
        print(f"URL: {product.url}")
        print(f"Selector: {product.selector}")
        print(f"Expected text: {product.expected_text}")
        print("\nChecking availability...")
        
        is_in_stock = self.checker.check_availability(product)
        
        if is_in_stock:
            print("✅ Product is IN STOCK")
        else:
            print("❌ Product is OUT OF STOCK")


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description="Restock Notification Bot")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Add product command
    add_parser = subparsers.add_parser('add', help='Add a new product to monitor')
    add_parser.add_argument('--name', required=True, help='Product name')
    add_parser.add_argument('--url', required=True, help='Product URL')
    add_parser.add_argument('--selector', required=True, help='CSS selector for stock status')
    add_parser.add_argument('--expected-text', required=True, help='Text that indicates out of stock')
    add_parser.add_argument('--email', required=True, help='Email to notify')
    
    # List products command
    subparsers.add_parser('list', help='List all products')
    
    # Monitor command
    subparsers.add_parser('monitor', help='Start monitoring products')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Test a specific product')
    test_parser.add_argument('--id', type=int, required=True, help='Product ID to test')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        bot = RestockBot()
        
        if args.command == 'add':
            bot.add_product(
                args.name, args.url, args.selector, 
                args.expected_text, args.email
            )
        elif args.command == 'list':
            bot.list_products()
        elif args.command == 'monitor':
            bot.run_monitor()
        elif args.command == 'test':
            bot.test_product(args.id)
            
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        print(f"❌ Application error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()