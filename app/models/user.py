import hashlib
import secrets
from datetime import datetime, timezone

from app import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), nullable=False, default="user")  # user, admin, support
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    verification_token = db.Column(db.String(128), unique=True, nullable=True)
    password_reset_token = db.Column(db.String(128), unique=True, nullable=True)
    password_reset_expires = db.Column(db.DateTime, nullable=True)
    mfa_secret = db.Column(db.String(32), nullable=True)
    mfa_enabled = db.Column(db.Boolean, default=False, nullable=False)
    stripe_customer_id = db.Column(db.String(64), nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    last_login_ip = db.Column(db.String(45), nullable=True)
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    deleted_at = db.Column(db.DateTime, nullable=True)  # soft delete

    orders = db.relationship("Order", back_populates="user", lazy="dynamic")
    subscriptions = db.relationship("Subscription", back_populates="user", lazy="dynamic")
    audit_logs = db.relationship("AuditLog", back_populates="user", lazy="dynamic")

    def set_password(self, password: str) -> None:
        from flask_bcrypt import generate_password_hash
        self.password_hash = generate_password_hash(password).decode("utf-8")

    def check_password(self, password: str) -> bool:
        from flask_bcrypt import check_password_hash
        return check_password_hash(self.password_hash, password)

    def generate_verification_token(self) -> str:
        token = secrets.token_urlsafe(48)
        self.verification_token = token
        return token

    def generate_password_reset_token(self) -> str:
        from datetime import timedelta
        token = secrets.token_urlsafe(48)
        self.password_reset_token = hashlib.sha256(token.encode()).hexdigest()
        self.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        return token

    def is_password_reset_valid(self, token: str) -> bool:
        if not self.password_reset_token or not self.password_reset_expires:
            return False
        hashed = hashlib.sha256(token.encode()).hexdigest()
        expires = self.password_reset_expires.replace(tzinfo=timezone.utc)
        not_expired = datetime.now(timezone.utc) < expires
        return hashed == self.password_reset_token and not_expired

    def is_locked(self) -> bool:
        if self.locked_until is None:
            return False
        return datetime.now(timezone.utc) < self.locked_until.replace(tzinfo=timezone.utc)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "role": self.role,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "mfa_enabled": self.mfa_enabled,
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<User {self.email}>"
