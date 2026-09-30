"""
utils/helpers.py
-----------------
Small shared functions used across route blueprints. Centralizing
"create a notification" / "write an audit log row" in one place means
every call site gets the same shape of record, and a future change
(e.g. also emailing on notification creation) touches one function.
"""

from flask import abort
from flask_login import current_user

from app.extensions import db
from app.models import Notification, AuditLog


def notify(user, message, link=None):
    """Create an in-app notification for `user`. Commits immediately so
    a notification is never lost if the caller's transaction later
    rolls back for an unrelated reason."""
    n = Notification(user_id=user.id, message=message, link=link)
    db.session.add(n)
    db.session.commit()
    return n


def log_action(action, target_type=None, target_id=None, details=None):
    """Append an audit log row attributed to the current actor (or None
    for system/seed actions run outside a request context)."""
    actor_id = current_user.id if current_user and current_user.is_authenticated else None
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def object_belongs_to_current_user_or_403(owner_user_id):
    """
    Object-level authorization helper (the third layer discussed in
    decorators.py): even once a role check passes a *role*, we still
    must confirm the *specific row* requested belongs to that user.
    E.g. a Medical Expert can only open consultations assigned to
    THEM, not every expert's queue; a Student can only see their own
    consultation history.
    """
    if current_user.is_super_admin:
        return  # Super Admin can view everything system-wide, by design
    if owner_user_id != current_user.id:
        abort(403)
