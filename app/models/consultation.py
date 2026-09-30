import enum
from datetime import datetime

from app.extensions import db


class ConsultationCategory(db.Model):
    """
    Managed exclusively by Super Admin. Students pick one of these when
    booking; Medical Experts can optionally be tagged with a specialization
    string (see User.specialization) that maps loosely to category names —
    kept as free text rather than a hard FK so the college can describe an
    expert's specialty in their own words without editing categories.
    """
    __tablename__ = "consultation_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    consultations = db.relationship("Consultation", back_populates="category")

    def __repr__(self):
        return f"<ConsultationCategory {self.name}>"


class ConsultationStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    RESCHEDULE_REQUESTED = "reschedule_requested"


class Consultation(db.Model):
    """
    Core workflow entity: request -> pending -> accepted/declined ->
    completed, with cancellation/reschedule as student-initiated side paths.

    Status transitions are enforced in app/routes (not here) via small
    guard functions, because the *allowed* transitions differ by role
    (e.g. only the assigned expert can move accepted -> completed; only
    the owning student can move pending -> cancelled). Keeping that logic
    in the route/service layer keeps the model a plain data record, which
    is easier to unit-test and reason about.
    """
    __tablename__ = "consultations"

    id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    # Nullable until a Medical Expert accepts the request (or Super Admin
    # assigns one); a pending request may not yet have an owner.
    expert_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("consultation_categories.id"), nullable=False)

    requested_date = db.Column(db.Date, nullable=False)
    requested_time = db.Column(db.Time, nullable=False)

    status = db.Column(
        db.Enum(ConsultationStatus), nullable=False, default=ConsultationStatus.PENDING, index=True
    )

    student_message = db.Column(db.Text, nullable=True)  # reason for the visit
    expert_notes = db.Column(db.Text, nullable=True)      # private clinical notes
    diagnosis = db.Column(db.Text, nullable=True)
    decline_reason = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    student = db.relationship("User", foreign_keys=[student_id], back_populates="consultations_as_student")
    expert = db.relationship("User", foreign_keys=[expert_id], back_populates="consultations_as_expert")
    category = db.relationship("ConsultationCategory", back_populates="consultations")

    def __repr__(self):
        return f"<Consultation #{self.id} {self.status.value}>"
