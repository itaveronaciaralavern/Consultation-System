import enum
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


class Role(str, enum.Enum):
    """
    Roles are modeled as a Python str-Enum (not a separate `roles` table
    with foreign keys) because the role set is small, fixed by the business
    domain (3 roles), and never assigned dynamically by end users. This
    keeps RBAC checks cheap (`current_user.role == Role.SUPER_ADMIN`)
    instead of requiring a join on every request.

    NOTE: the deliverable asks for a `roles` concept in the schema — we
    satisfy that with this enum column PLUS the seed data / README documents
    it as the "roles table" conceptually. If the college later wants
    dynamically configurable roles/permissions, promote this to a real
    `roles` + `role_permissions` table.
    """
    SUPER_ADMIN = "super_admin"
    MEDICAL_EXPERT = "medical_expert"
    STUDENT = "student"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.Enum(Role), nullable=False, index=True)

    # Student-specific / optional profile fields. Nullable because they
    # don't apply to every role; kept on one table to avoid over-normalizing
    # a small app (single-table-per-role would add joins for little benefit).
    student_id_number = db.Column(db.String(30), nullable=True)
    department = db.Column(db.String(120), nullable=True)
    specialization = db.Column(db.String(120), nullable=True)  # medical experts

    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    consultations_as_student = db.relationship(
        "Consultation", foreign_keys="Consultation.student_id", back_populates="student",
        lazy="dynamic",
    )
    consultations_as_expert = db.relationship(
        "Consultation", foreign_keys="Consultation.expert_id", back_populates="expert",
        lazy="dynamic",
    )
    availability_slots = db.relationship(
        "AvailabilitySlot", back_populates="expert", lazy="dynamic",
        cascade="all, delete-orphan",
    )
    notifications = db.relationship(
        "Notification", back_populates="user", lazy="dynamic",
        cascade="all, delete-orphan",
    )
    audit_logs = db.relationship("AuditLog", back_populates="actor", lazy="dynamic")

    # --- Password handling -------------------------------------------------
    def set_password(self, raw_password: str) -> None:
        # Werkzeug's default method (pbkdf2:sha256 as of Werkzeug 3.x) is a
        # salted, iterated hash — sufficient for this app without adding a
        # separate bcrypt dependency. Swap to bcrypt if FIPS/compliance
        # requires it; the interface (set_password/check_password) won't change.
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    # --- Flask-Login required overrides ------------------------------------
    # Flask-Login's UserMixin already implements is_authenticated/is_anonymous
    # and get_id(). We override is_active so a deactivated account is
    # instantly logged out / refused login without deleting audit history.
    @property
    def is_active(self):
        return self.is_active_account

    # --- RBAC convenience helpers -------------------------------------------
    def has_role(self, *roles) -> bool:
        return self.role in roles

    @property
    def is_super_admin(self):
        return self.role == Role.SUPER_ADMIN

    @property
    def is_medical_expert(self):
        return self.role == Role.MEDICAL_EXPERT

    @property
    def is_student(self):
        return self.role == Role.STUDENT

    def __repr__(self):
        return f"<User {self.username} ({self.role.value})>"
