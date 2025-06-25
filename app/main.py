from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from app.database import get_db, init_db
from app.crud import create_test_data , get_daily_care_stats_optimized
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional
from typing import Optional, List
from app.performance import run_performance_test

# Initialize FastAPI application
app = FastAPI()

# Add CORS middleware to allow all origins (for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

@app.on_event("startup")
async def startup_event():
    """
    Event handler that runs on application startup.
    Initializes the database (creates tables if needed).
    """
    await init_db()

@app.post("/generate-data")
async def generate_data(db: AsyncSession = Depends(get_db)):
    """
    Endpoint to generate and insert test data into the database.
    Triggers the creation of a large number of CareNote records.
    """
    await create_test_data(db)
    return {"message": "Test data inserted!"}

@app.get("/test-performance")
async def test_performance():
    """
    Endpoint to run the performance test comparing original and optimized stats queries.
    Results are printed to the server logs.
    """
    await run_performance_test()
    return {"message": "Performance test completed. Check server logs."}