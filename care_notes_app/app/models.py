from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, DateTime, Index

# Base class for all ORM models
class Base(DeclarativeBase):
    pass

class CareNote(Base):
    """
    ORM model for the 'care_notes' table.
    Represents a single care note entry for a patient in a facility.
    """
    __tablename__ = "care_notes"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)
    # Tenant/organization ID
    tenant_id: Mapped[int] = mapped_column(Integer)
    # Facility ID within the tenant
    facility_id: Mapped[int] = mapped_column(Integer)
    # Patient identifier
    patient_id: Mapped[str] = mapped_column(String)
    # Category of care note (e.g., medication, observation)
    category: Mapped[str] = mapped_column(String)
    # Priority level (1-5)
    priority: Mapped[int] = mapped_column(Integer)
    # Timestamp when the note was created
    created_at: Mapped[DateTime] = mapped_column(DateTime)
    # User who created the note
    created_by: Mapped[str] = mapped_column(String)

    # Table indexes for efficient querying by tenant/date, facility/date, and patient
    __table_args__ = (
        Index("ix_tenant_created", "tenant_id", "created_at"),  # For fast queries by tenant and date
        Index("ix_facility_created", "facility_id", "created_at"),  # For fast queries by facility and date
        Index("ix_patient_id", "patient_id"),  # For fast queries by patient
    )