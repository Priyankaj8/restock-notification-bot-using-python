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
class ProductCreate(BaseModel): # ProductCreate defines what data someone needs to provide when they want to add a new product to monitor
    name: str
    url: str
    selector: str
    expected_txt: str
    email: EmailStr

class ProductResponse(BaseModel):
    id: int
    name: str
    url: str
    selector: str
    expected_txt: str
    email: str
    is_active: str
    last_checked: Optional[str]
    created_at: Optional[str]

class StatusResponse(BaseModel):
    total_products: int
    active_products: int
    monitoring_status: str
    notifications_sent: int

# Global variables for monitoring
monitoring_task = None # Keeps track of our background monitoring process
monitoring_active = False # A flag to start/stop monitoring
bot_instance = None # main bot object

app = FastAPI(title="Restock Bot API", version="1.0.0") # Creates the web application

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def get_bot():
    global bot_instance
    if bot_instance is None:
        bot_instance = RestockBot()
    return bot_instance

@app.on_event("startup") # it runs automatically when the server starts
async def startup_event():
    """Initialize the bot on startup"""
    global bot_instance
    bot_instance = RestockBot()
    logger.info("FastAPI Restock Bot started successfully!")

# API routes
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main dashboard page"""
    return templates.TemplateResponse("dashboard.html",{"request":request})

@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    """Get the current bot status"""
    bot = get_bot()
    products = bot.ab.get_all_products()
    active_products = [p for p in products if p.is_active]

    # get notifications count from database
    with bot.db.get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) as count FROM notifications")
        notifications_count = cursor.fetchone()['count']

    return StatusResponse(
        total_products = len(products),
        active_products = len(active_products),
        monitoring_status ="Running" if monitoring_active else "Stopped",
        notifications_sent = notifications_count
    )