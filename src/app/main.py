"""
FastAPI应用主入口
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from typing import Optional, List

from .config import settings
from .modules.models import ScrapeItem, ProductResponse, ScrapeRequest, TaskResponse
from .modules.scraper import ScraperService
from .modules.store import DatabaseService
from .modules.workers import WorkerManager

from pydantic import BaseModel

# Global instances
scraper_service = None
db_service = None
worker_manager = None
task_queue = asyncio.Queue()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global scraper_service, db_service, worker_manager

    # Startup
    db_service = DatabaseService()
    scraper_service = ScraperService(db_service)
    worker_manager = WorkerManager(task_queue, scraper_service, db_service)

    # Start background workers
    await worker_manager.start_workers()

    yield

    # Shutdown
    await worker_manager.stop_workers()


app = FastAPI(
    title="Amazon Product Scraper API",
    description="API for scraping Amazon product information",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "service": "amazon-scraper"}


@app.get("/asin/{asin}", response_model=ProductResponse)
async def get_product(
    asin: str,
    marketplace: str = Query(default="amazon.com", description="Amazon marketplace"),
    force: bool = Query(default=False, description="Force refresh from source"),
    wait: bool = Query(default=False, description="Wait for scraping to complete"),
):
    """
    Get product information by ASIN

    - **asin**: Amazon Standard Identification Number
    - **marketplace**: Amazon marketplace (e.g., amazon.com, amazon.co.jp)
    - **force**: Force refresh from source, ignoring cache
    - **wait**: Wait for scraping to complete if needed
    """
    try:
        # Check if product exists and is fresh
        product = await db_service.get_product(asin, marketplace)

        # Determine if we need to scrape
        needs_scraping = await scraper_service.needs_scraping(asin, marketplace, force)

        if needs_scraping:
            # Add to queue
            await task_queue.put((asin, marketplace))

            if wait:
                # Wait for completion (with timeout)
                product = await scraper_service.wait_for_completion(
                    asin, marketplace, timeout=30
                )
            else:
                # Return existing data or indicate scraping in progress
                if not product:
                    raise HTTPException(
                        status_code=202,
                        detail="Scraping in progress. Check back later or use wait=true",
                    )

        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        return product

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/asin/scrape", response_model=List[TaskResponse])
async def scrape_products(request: ScrapeRequest):
    """
    Batch scrape multiple products

    - **items**: List of products to scrape
    - **async**: Return immediately with task IDs
    """
    try:
        tasks = []

        for item in request.items:
            # Create task record
            task_id = await db_service.create_task(item.asin, item.marketplace)

            # Add to queue
            await task_queue.put((item.asin, item.marketplace, task_id))

            # Get the complete task from database instead of manually creating
            task = await db_service.get_task(task_id)
            if task:
                tasks.append(task)

        return tasks

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task_status(task_id: str):
    """Get task status by ID"""
    try:
        task = await db_service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    """Get scraping statistics"""
    try:
        stats = await db_service.get_stats()
        return {
            "queue_size": task_queue.qsize(),
            "active_workers": worker_manager.active_workers if worker_manager else 0,
            **stats,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
