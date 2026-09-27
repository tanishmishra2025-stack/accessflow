from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from accessflow.database import Base


class Audit(Base):
    __tablename__ = "audits"

    id: Mapped[int] = mapped_column(primary_key=True)

    website_id: Mapped[int] = mapped_column(
        ForeignKey("websites.id"),
        nullable=False,
    )

    url: Mapped[str] = mapped_column(String, nullable=False)

    scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="pending",
    )

    total_issues: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    critical: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    serious: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    moderate: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    minor: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    website = relationship(
        "Website",
        back_populates="audits",
    )

    issues = relationship(
        "AccessibilityIssue",
        back_populates="audit",
        cascade="all, delete-orphan",
    )