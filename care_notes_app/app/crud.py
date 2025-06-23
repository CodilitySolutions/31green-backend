from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from app.models import CareNote
from faker import Faker
from datetime import datetime, timedelta
import random
from sqlalchemy import select, func, case
from typing import Optional, List, Dict

fake = Faker()

CATEGORIES = ['medication', 'observation', 'treatment']
PRIORITIES = [1, 2, 3, 4, 5]

# 🔁 In-memory cache (simple dict)
# Key: string generated from tenant, date, and facility_ids
# Value: Aggregated stats dict
cache_store: Dict[str, Dict] = {}

async def create_test_data(db: AsyncSession, total_records: int = 100_000):
    """
    Generate and insert a large number of CareNote records for testing.
    """
    tenants = [1, 2, 3]
    facilities_per_tenant = 5
    total_facilities = len(tenants) * facilities_per_tenant
    patients = [f"patient_{i}" for i in range(1, 2000)]
    start_date = datetime.utcnow() - timedelta(days=30)
    batch_size = 5000
    buffer = []

    for i in range(total_records):
        note = CareNote(
            tenant_id=random.choice(tenants),
            facility_id=random.randint(1, total_facilities),
            patient_id=random.choice(patients),
            category=random.choice(CATEGORIES),
            priority=random.choice(PRIORITIES),
            created_at=start_date + timedelta(days=random.randint(0, 30)),
            created_by=fake.user_name()
        )
        buffer.append(note)

        # Bulk insert in batches for efficiency
        if len(buffer) >= batch_size:
            db.add_all(buffer)
            await db.commit()
            buffer.clear()

    if buffer:
        db.add_all(buffer)
        await db.commit()


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

# from sqlalchemy import select, func, case

# async def get_daily_care_stats_optimized(
#     db: AsyncSession,
#     tenant_id: int,
#     facility_ids: Optional[List[int]] = None,
#     date: Optional[datetime] = None
# ):
#     if date is None:
#         date = datetime.utcnow()
#     query_date = date.date()

#     filters = [
#         CareNote.tenant_id == tenant_id,
#         func.date(CareNote.created_at) == query_date
#     ]
#     if facility_ids:
#         filters.append(CareNote.facility_id.in_(facility_ids))

#     # Single query for all aggregations
#     stmt = select(
#         func.count().label("total_notes"),
#         func.count(func.distinct(CareNote.patient_id)).label("unique_patients"),
#         *[
#             func.sum(case((CareNote.category == cat, 1), else_=0)).label(f"cat_{cat}")
#             for cat in ['medication', 'observation', 'treatment']
#         ],
#         *[
#             func.sum(case((CareNote.priority == p, 1), else_=0)).label(f"priority_{p}")
#             for p in range(1, 6)
#         ]
#     ).where(*filters)

#     result = await db.execute(stmt)
#     row = result.one()

#     # Extract results
#     total_notes = row.total_notes
#     unique_patients = row.unique_patients
#     avg_notes_per_patient = total_notes / unique_patients if unique_patients else 0

#     by_category = {
#         cat: getattr(row, f"cat_{cat}")
#         for cat in ['medication', 'observation', 'treatment']
#     }
#     by_priority = {
#         p: getattr(row, f"priority_{p}")
#         for p in range(1, 6)
#     }

#     # By facility (still needs a separate query if you want per-facility breakdown)
#     by_facility_result = await db.execute(
#         select(CareNote.facility_id, func.count())
#         .where(*filters)
#         .group_by(CareNote.facility_id)
#     )
#     by_facility = dict(by_facility_result.all())

#     return {
#         "total_notes": total_notes,
#         "avg_notes_per_patient": round(avg_notes_per_patient, 2),
#         "by_category": by_category,
#         "by_priority": by_priority,
#         "by_facility": by_facility
#     }