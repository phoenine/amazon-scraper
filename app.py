#!/usr/bin/env python3
"""
Amazon Product Scraper API
Main application file - redirects to app.main for better organization
"""

# Import the main FastAPI app
from app.main import app

# This allows running with: uvicorn app:app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

