from flask import Blueprint, render_template, redirect, url_for, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Notification, Role

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        if current_user.role == Role.SUPER_ADMIN:
            return redirect(url_for("admin.dashboard"))
        if current_user.role == Role.MEDICAL_EXPERT:
            return redirect(url_for("expert.dashboard"))
        return redirect(url_for("student.dashboard"))
    return render_template("index.html")


@main_bp.route("/notifications")
@login_required
def notifications():
    items = current_user.notifications.order_by(Notification.created_at.desc()).limit(50).all()
    return render_template("notifications.html", notifications=items)


@main_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id):
    # Object-level authorization check: role alone (@login_required) isn't
    # enough here — we must also confirm THIS notification belongs to the
    # logged-in user, or any user could mark anyone else's as read.
    note = db.session.get(Notification, notification_id)
    if note is None or note.user_id != current_user.id:
        abort(403)
    note.is_read = True
    db.session.commit()
    return redirect(url_for("main.notifications"))
