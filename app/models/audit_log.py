from datetime import datetime, timezone
from typing import Optional

from app import db


class AuditLog(db.Model):
    """Immutable audit trail for security-sensitive operations."""

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    actor_ip = db.Column(db.String(45), nullable=True)
    action = db.Column(db.String(128), nullable=False, index=True)
    resource_type = db.Column(db.String(64), nullable=True)
    resource_id = db.Column(db.String(64), nullable=True)
    old_value = db.Column(db.JSON, nullable=True)
    new_value = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="success")  # success, failure
    error_message = db.Column(db.Text, nullable=True)
    metadata_ = db.Column("metadata", db.JSON, nullable=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    user = db.relationship("User", back_populates="audit_logs")

    @classmethod
    def record(
        cls,
        action: str,
        user_id: Optional[int] = None,
        actor_ip: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        old_value: Optional[dict] = None,
        new_value: Optional[dict] = None,
        status: str = "success",
        error_message: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> "AuditLog":
        from app import db

        entry = cls(
            action=action,
            user_id=user_id,
            actor_ip=actor_ip,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            old_value=old_value,
            new_value=new_value,
            status=status,
            error_message=error_message,
            metadata_=metadata,
        )
        db.session.add(entry)
        return entry

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by user={self.user_id}>"
