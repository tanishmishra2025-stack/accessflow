from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from accessflow.database import Base


class AccessibilityIssue(Base):
    __tablename__ = "accessibility_issues"

    id: Mapped[int] = mapped_column(primary_key=True)

    audit_id: Mapped[int] = mapped_column(
        ForeignKey("audits.id"),
        nullable=False,
    )

    rule: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    severity: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    element_html: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    wcag_ref: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    audit = relationship(
        "Audit",
        back_populates="issues",
    )