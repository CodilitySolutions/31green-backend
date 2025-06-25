from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from app.models import CareNote
from concurrent.futures import ThreadPoolExecutor
from faker import Faker
from datetime import datetime, timedelta
import random
from sqlalchemy import select, func, case, distinct
from typing import Optional, List, Dict

fake = Faker()

CATEGORIES = ['medication', 'observation', 'treatment']
PRIORITIES = [1, 2, 3, 4, 5]

def generate_batch_records(start_index, batch_size, tenants, facilities_per_tenant, patients, start_date) -> List[CareNote]:
    records = []
    for _ in range(batch_size):
        tenant_id = random.choice(tenants)
        facility_start = (tenant_id - 1) * facilities_per_tenant + 1
        facility_end = facility_start + facilities_per_tenant - 1
        facility_id = random.randint(facility_start, facility_end)

        note = CareNote(
            tenant_id=tenant_id,
            facility_id=facility_id,
            patient_id=random.choice(patients),
            category=random.choice(CATEGORIES),
            priority=random.choice(PRIORITIES),
            created_at=start_date + timedelta(days=random.randint(0, 30)),
            created_by=fake.user_name()
        )
        records.append(note)
    return records

async def create_test_data(
    db: AsyncSession,
    total_records: int = 1000000,
    tenant_count: int = 5000,
    facilities_per_tenant: int = 5,
    max_threads: int = 10
):
    tenants = list(range(1, tenant_count + 1))
    patients = [f"patient_{i}" for i in range(1, 2000)]
    start_date = datetime.utcnow() - timedelta(days=30)

    batch_size = 5000
    total_batches = total_records // batch_size

    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        for batch_index in range(total_batches):
            # Generate batch in a separate thread
            batch = await asyncio.get_event_loop().run_in_executor(
                executor,
                generate_batch_records,
                batch_index * batch_size,
                batch_size,
                tenants,
                facilities_per_tenant,
                patients,
                start_date
            )

            # Insert generated records in the main async DB session
            await db.run_sync(lambda sync_db: sync_db.bulk_save_objects(batch))
            await db.commit()
            print(f"Inserted batch {batch_index + 1}/{total_batches}")

    print("Data generation completed.")


def cache_key(tenant_id: int, date: datetime, facility_ids: Optional[List[int]]) -> str:
    """
    Generate a unique cache key based on tenant, date, and facility_ids.
    """
    facilities = ",".join(map(str, sorted(facility_ids))) if facility_ids else "all"
    return f"{tenant_id}-{date.date()}-{facilities}"


async def get_daily_care_stats_optimized(
    db: AsyncSession,
    tenant_id: int,
    facility_ids: Optional[List[int]] = None,
    date: Optional[datetime] = None
):
    """
    Optimized version of care stats aggregation with in-memory caching.
    - Returns cached result if available.
    - Uses SQL GROUP BY for fast in-db aggregation.
    - Calculates total notes, avg per patient, breakdowns by category, priority, facility.
    """
    if date is None:
        date = datetime.utcnow()

    # Generate cache key and check cache first
    key = cache_key(tenant_id, date, facility_ids)
    if key in cache_store:
        return cache_store[key]  # ✅ Return cached result instantly

    query_date = date.date()
    # Build SQLAlchemy filters
    filters = [
        CareNote.tenant_id == tenant_id,
        func.date(CareNote.created_at) == query_date
    ]
    if facility_ids:
        filters.append(CareNote.facility_id.in_(facility_ids))

    # 🔹 Aggregated query: group by category, priority, facility
    stmt = select(
        func.count().label("total_notes"),
        func.count(func.distinct(CareNote.patient_id)).label("unique_patients"),
        CareNote.category,
        CareNote.priority,
        CareNote.facility_id
    ).where(*filters).group_by(
        CareNote.category, CareNote.priority, CareNote.facility_id
    )

    result = await db.execute(stmt)
    rows = result.fetchall()

    # Initialize aggregation containers
    total_notes = 0
    by_category = {}
    by_priority = {p: 0 for p in range(1, 6)}
    by_facility = {}

    # Aggregate results from grouped query
    for row in rows:
        count = row.total_notes
        total_notes += count
        by_category[row.category] = by_category.get(row.category, 0) + count
        by_priority[row.priority] = by_priority.get(row.priority, 0) + count
        by_facility[row.facility_id] = by_facility.get(row.facility_id, 0) + count

    # 🔹 Unique patients count (indexed, separate query for accuracy)
    unique_patients_count = await db.scalar(
        select(func.count(func.distinct(CareNote.patient_id))).where(*filters)
    )

    # Calculate average notes per patient
    avg_notes_per_patient = total_notes / unique_patients_count if unique_patients_count else 0

    # Prepare result dict
    result_data = {
        "total_notes": total_notes,
        "avg_notes_per_patient": round(avg_notes_per_patient, 2),
        "by_category": by_category,
        "by_priority": by_priority,
        "by_facility": by_facility
    }

    # ✅ Cache result for future identical queries
    cache_store[key] = result_data
    return result_data