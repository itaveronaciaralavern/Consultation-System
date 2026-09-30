"""
routes/notifications.py
-------------------------
Shared, role-agnostic notification list + "mark as read" endpoints.
Uses `@any_role_required` (any authenticated, active user) since every
role has notifications, and object-level scoping (a user can only ever
touch THEIR OWN notifications) is enforced inside each view rather than
via the role decorator, which only checks role, not row ownership.
"""

from flask import Blueprint, render_template, redirect, url_for, abort, flash
from flask_login import current_user

from app.extensions import db
from app.models import Notification
from app.utils.decorators import any_role_required

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/")
@any_role_required
def index():
    items = current_user.notifications.order_by(Notification.created_at.desc()).all()
    return render_template("notifications.html", notifications=items)


@notifications_bp.route("/<int:notification_id>/read", methods=["POST"])
@any_role_required
def mark_read(notification_id):
    n = Notification.query.get_or_404(notification_id)
    if n.user_id != current_user.id:
        abort(403)  # object-level check: never let a user mark someone else's notification
    n.is_read = True
    db.session.commit()
    if n.link:
        return redirect(n.link)
    return redirect(url_for("notifications.index"))


@notifications_bp.route("/mark-all-read", methods=["POST"])
@any_role_required
def mark_all_read():
    current_user.notifications.filter_by(is_read=False).update({"is_read": True})
    db.session.commit()
    flash("All notifications marked as read.", "info")
    return redirect(url_for("notifications.index"))
