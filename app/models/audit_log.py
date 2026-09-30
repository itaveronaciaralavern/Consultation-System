from datetime import datetime

from app.extensions import db


class AuditLog(db.Model):
    """
    Append-only trail of sensitive actions (account creation/deactivation,
    role changes, consultation status changes) reviewed by Super Admin.
    We never UPDATE or DELETE rows here from application code — only INSERT
    — so the log stays trustworthy as a record of "what happened".
    """
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    action = db.Column(db.String(80), nullable=False)       # e.g. "USER_CREATED"
    target_type = db.Column(db.String(50), nullable=True)   # e.g. "User", "Consultation"
    target_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.String(500), nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    actor = db.relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog {self.action} by={self.actor_id} at={self.created_at}>"


def log_action(actor_id, action, target_type=None, target_id=None, details=None, ip_address=None):
    entry = AuditLog(
        actor_id=actor_id, action=action, target_type=target_type,
        target_id=target_id, details=details, ip_address=ip_address,
    )
    db.session.add(entry)
    return entry
