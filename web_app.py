import asyncio
import threading
import time
import json
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pydantic import BaseModel, EmailStr

import uvicorn
import logging

from restock_bot import RestockBot, Product, DatabaseManager, ProductChecker, EmailNotifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models for API Requests
class ProductCreate(BaseModel):
    name: str
    url: str
    selector: str
    expected_text: str
    email: EmailStr

class ProductResponse(BaseModel):
    id: int
    name: str
    url: str
    selector: str
    expected_text: str
    email: str
    is_active: bool
    last_checked: Optional[str]
    created_at: Optional[str]

class StatusResponse(BaseModel):
    total_products: int
    active_products: int
    monitoring_status: str
    notifications_sent: int

# Global variables for monitoring
monitoring_task = None
monitoring_active = False
bot_instance = None

app = FastAPI(title="Restock Bot API", version="1.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def get_bot():
    global bot_instance
    if bot_instance is None:
        bot_instance = RestockBot()
    return bot_instance

@app.on_event("startup")
async def startup_event():
    """Initialize the bot on startup"""
    global bot_instance
    bot_instance = RestockBot()
    logger.info("FastAPI Restock Bot started successfully!")

# API routes
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    """Get the current bot status"""
    bot = get_bot()
    products = bot.db.get_all_products()
    active_products = [p for p in products if p.is_active]

    # get notifications count from database
    with bot.db.get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) as count FROM notifications")
        notifications_count = cursor.fetchone()['count']

    return StatusResponse(
        total_products=len(products),
        active_products=len(active_products),
        monitoring_status="Running" if monitoring_active else "Stopped",
        notifications_sent=notifications_count
    )

@app.get("/api/products", response_model=List[ProductResponse])
async def get_products():
    bot = get_bot()
    products = bot.db.get_all_products()

    return [
        ProductResponse(
            id=p.id,
            name=p.name,
            url=p.url,
            selector=p.selector,
            expected_text=p.expected_text,
            email=p.email,
            is_active=p.is_active,
            last_checked=p.last_checked,
            created_at=p.created_at
        ) for p in products
    ]

@app.post("/api/products", response_model=dict)
async def add_product(product: ProductCreate):
    """Add a new product"""
    try:
        logger.info(f"Adding product: {product.name}")
        bot = get_bot()
        
        # Create Product object
        new_product = Product(
            name=product.name,
            url=product.url,
            selector=product.selector,
            expected_text=product.expected_text,
            email=product.email
        )
        
        # Add to database
        try:
            product_id = bot.db.add_product(new_product)
            logger.info(f"Successfully added product with ID: {product_id}")
            
            # Verify it was added
            all_products = bot.db.get_all_products()
            added_product = next((p for p in all_products if p.id == product_id), None)
            
            if added_product:
                logger.info(f"Verified product exists in database: {added_product.name}")
                return {"message": f"Product '{product.name}' added successfully", "id": product_id}
            else:
                logger.error("Product was not found after adding to database")
                raise HTTPException(status_code=500, detail="Product was not saved properly")
                
        except Exception as db_error:
            logger.error(f"Database error: {str(db_error)}")
            if "UNIQUE constraint failed" in str(db_error):
                raise HTTPException(status_code=400, detail=f"Product with URL '{product.url}' already exists")
            else:
                raise HTTPException(status_code=500, detail=f"Database error: {str(db_error)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error adding product: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.delete("/api/products/{product_id}")
async def delete_product(product_id: int):
    """Delete/deactivate a product"""
    try:
        bot = get_bot()
        
        # Check if product exists first
        products = bot.db.get_all_products()
        product = next((p for p in products if p.id == product_id), None)
        
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        bot.db.deactivate_product(product_id)
        logger.info(f"Deactivated product {product_id}: {product.name}")
        return {"message": f"Product '{product.name}' deactivated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating product {product_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/products/{product_id}/test")
async def test_product(product_id: int):
    """Test a specific product"""
    try:
        bot = get_bot()
        products = bot.db.get_all_products()
        product = next((p for p in products if p.id == product_id), None)

        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        logger.info(f"Testing product: {product.name}")
        is_in_stock = bot.checker.check_availability(product)
        bot.db.update_last_checked(product_id)

        return {
            "product_id": product_id,
            "product_name": product.name,
            "in_stock": is_in_stock,
            "status": "IN_STOCK" if is_in_stock else "OUT_OF_STOCK",
            "checked_at": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing product {product_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# MONITORING CONTROL ENDPOINTS

@app.post("/api/monitoring/start")
async def start_monitoring(background_tasks: BackgroundTasks):
    """Start the monitoring process"""
    global monitoring_active, monitoring_task

    if monitoring_active:
        return {"message": "Monitoring is already running"}

    monitoring_active = True
    background_tasks.add_task(monitoring_loop)
    logger.info("Monitoring started via API")
    return {"message": "Monitoring started successfully"}

@app.post("/api/monitoring/stop")
async def stop_monitoring():
    """Stop the monitoring process"""
    global monitoring_active
    monitoring_active = False
    logger.info("Monitoring stopped via API")
    return {"message": "Monitoring stopped successfully"}

# BACKGROUND MONITORING FUNCTION

async def monitoring_loop():
    """Background task for monitoring products"""
    global monitoring_active
    bot = get_bot()
    
    logger.info("Background monitoring started")

    while monitoring_active:
        try:
            products = bot.db.get_active_products()
            logger.info(f"Checking {len(products)} active products")

            if not products:
                logger.info("No active products to monitor")
                await asyncio.sleep(bot.config['check_interval'])
                continue

            for product in products:
                if not monitoring_active:  # Check if we should stop
                    break

                try:
                    logger.info(f"Checking product: {product.name}")
                    is_in_stock = bot.checker.check_availability(product)
                    bot.db.update_last_checked(product.id)

                    if is_in_stock:
                        logger.info(f"🎉 {product.name} is back in stock!")

                        # Send notification
                        try:
                            email_sent = bot.email_notifier.send_notification(
                                product.email, product.name, product.url
                            )
                            
                            if email_sent:
                                bot.db.log_notification(
                                    product.id, "email", f"Stock notification sent to {product.email}"
                                )
                                logger.info(f"Email notification sent for {product.name}")
                                
                                # Deactivate product after successful notification
                                bot.db.deactivate_product(product.id)
                                logger.info(f"Deactivated monitoring for {product.name}")
                            else:
                                logger.error(f"Failed to send email for {product.name}")
                                
                        except Exception as email_error:
                            logger.error(f"Email error for {product.name}: {str(email_error)}")
                    else:
                        logger.info(f"Product {product.name} is still out of stock")

                except Exception as e:
                    logger.error(f"Error processing product {product.name}: {str(e)}")

            logger.info(f"Checked {len(products)} products. Sleeping for {bot.config['check_interval']} seconds...")
            await asyncio.sleep(bot.config['check_interval'])

        except Exception as e:
            logger.error(f"Error in monitoring loop: {str(e)}")
            await asyncio.sleep(30)  # Wait 30 seconds before retrying

    logger.info("Background monitoring stopped")

@app.post("/api/test-email")
async def test_email():
    """Test email configuration"""
    try:
        bot = get_bot()
        logger.info("Testing email configuration...")
        
        # Send a test email to the configured email address
        success = bot.email_notifier.send_notification(
            bot.config['email']['username'],
            "Test Product",
            "https://example.com"
        )

        if success:
            logger.info("Test email sent successfully")
            return {"message": "Test email sent successfully"}
        else:
            logger.error("Failed to send test email")
            raise HTTPException(status_code=500, detail="Failed to send test email")
        
    except Exception as e:
        logger.error(f"Email test failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Email test failed: {str(e)}")

@app.get("/api/logs")
async def get_logs():
    """Get recent log entries"""
    try:
        # Read the last 100 lines from the log file
        with open('restock_bot.log', 'r') as f:
            lines = f.readlines()
            recent_lines = lines[-100:] if len(lines) > 100 else lines

        logs = []
        for line in recent_lines:
            if line.strip():
                logs.append(line.strip())

        return {"logs": logs}
    except FileNotFoundError:
        return {"logs": ["Log file not found"]}
    except Exception as e:
        logger.error(f"Error reading logs: {str(e)}")
        return {"logs": [f"Error reading logs: {str(e)}"]}

# Debug endpoint to check database
@app.get("/api/debug/database")
async def debug_database():
    """Debug endpoint to check database contents"""
    try:
        bot = get_bot()
        products = bot.db.get_all_products()
        
        debug_info = {
            "database_path": bot.db.db_path,
            "total_products": len(products),
            "products": []
        }
        
        for product in products:
            debug_info["products"].append({
                "id": product.id,
                "name": product.name,
                "url": product.url,
                "is_active": product.is_active,
                "created_at": product.created_at,
                "last_checked": product.last_checked
            })
        
        return debug_info
    except Exception as e:
        logger.error(f"Database debug error: {str(e)}")
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run(
        "web_app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )