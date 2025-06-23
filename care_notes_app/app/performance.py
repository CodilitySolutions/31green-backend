import asyncio
import time
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import CareNote
from app.crud import get_daily_care_stats_optimized
from app.database import get_db
from sqlalchemy import select, func, case, distinct

# Compatibility for Python <3.10
# Provides an async version of 'anext' if not available (for async generator usage)
try:
    anext = anext
except NameError:
    async def anext(ait, default=None):
        try:
            return await ait.__anext__()
        except StopAsyncIteration:
            if default is not None:
                return default
            raise

# 🔁 Old (inefficient) version - to compare
async def get_daily_care_stats(db: AsyncSession, tenant_id: int, date: datetime):
    """
    Legacy stats function: loads all notes for a tenant and date, then aggregates in Python.
    Used as a baseline for performance comparison.
    """
    query = select(CareNote).where(
        CareNote.tenant_id == tenant_id,
        CareNote.created_at.between(
            datetime(date.year, date.month, date.day),
            datetime(date.year, date.month, date.day, 23, 59, 59)
        )
    )
    result = await db.execute(query)
    notes = result.scalars().all()

    stats = {
        "total_notes": len(notes),
        "by_category": {},
        "by_priority": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
        "by_facility": {},
        "avg_notes_per_patient": 0,
    }

    patient_ids = set()
    for note in notes:
        stats["by_category"][note.category] = stats["by_category"].get(note.category, 0) + 1
        stats["by_priority"][note.priority] += 1
        stats["by_facility"][note.facility_id] = stats["by_facility"].get(note.facility_id, 0) + 1
        patient_ids.add(note.patient_id)

    stats["avg_notes_per_patient"] = round(len(notes) / len(patient_ids), 2) if patient_ids else 0
    return stats


# 🚀 Performance test runner
async def run_performance_test():
    """
    Compare legacy vs optimized care stats functions:
    - Logs time taken by each
    - Tests concurrent handling
    - Outputs % improvement
    """
    print("🚀 Starting performance test...\n")

    tenant_id = 227 # Test tenant ID (change as needed)
    test_date = datetime.utcnow()

    # Get DB session (using async generator)
    db_gen = get_db()
    db = await anext(db_gen)

    # 🔹 Step 1: Original version timing
    print("🔸 Running original (inefficient) query...")
    start_old = time.perf_counter()
    await get_daily_care_stats(db, tenant_id, test_date)
    duration_old = time.perf_counter() - start_old
    print(f"❌ Original query time: {duration_old:.4f} seconds")

    # 🔹 Step 2: Optimized version timing
    print("🔸 Running optimized query...")
    start_opt = time.perf_counter()
    await get_daily_care_stats_optimized(db, tenant_id, date=test_date)
    duration_opt = time.perf_counter() - start_opt
    print(f"✅ Optimized query time: {duration_opt:.4f} seconds")

    # 🔹 Step 3: Calculate improvement and comparison
    improvement = ((duration_old - duration_opt) / duration_old) * 100 if duration_old else 0
    print(f"\n--- Comparison Result ---")
    if duration_old > duration_opt:
        print(f"Optimized function is faster by {improvement:.2f}%.")
    elif duration_old < duration_opt:
        print(f"Legacy function is faster by {abs(improvement):.2f}% (unexpected!).")
    else:
        print("Both functions took the same amount of time.")
    print(f"------------------------\n")

    # 🔹 Step 4: Concurrency test (run 10 optimized queries in parallel)
    print("🔸 Running 10 parallel optimized queries...")
    start_concurrent = time.perf_counter()
    await asyncio.gather(*[
        get_daily_care_stats_optimized(db, tenant_id, date=test_date)
        for _ in range(10)
    ])
    duration_concurrent = time.perf_counter() - start_concurrent
    print(f"⚡ 10 concurrent optimized queries completed in: {duration_concurrent:.4f} seconds\n")

    print("✅ Performance test completed.\n")