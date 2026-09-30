"""
Re-export all models from one place so both `flask db migrate` (via
app/__init__.py importing app.models) and application code can simply do
`from app.models import User, Role, Consultation, ...`.
"""
from app.models.user import User, Role
from app.models.consultation import ConsultationCategory, Consultation, ConsultationStatus
from app.models.schedule import AvailabilitySlot
from app.models.notification import Notification, notify
from app.models.audit_log import AuditLog, log_action

__all__ = [
    "User", "Role",
    "ConsultationCategory", "Consultation", "ConsultationStatus",
    "AvailabilitySlot",
    "Notification", "notify",
    "AuditLog", "log_action",
]
