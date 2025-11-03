#!/usr/bin/env python3
"""
Railway deployment wrapper
Redirects to the actual FastAPI application in api/main.py
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the FastAPI app from api/main.py
from api.main import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
