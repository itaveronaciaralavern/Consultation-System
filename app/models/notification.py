from datetime import datetime

from app.extensions import db


class Notification(db.Model):
    """
    Simple in-app notification, polled/rendered on each page load via the
    base template (see templates/partials/notifications.html) rather than
    pushed over websockets — sufficient for a campus consultation system's
    scale and avoids adding an async stack.
    """
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    message = db.Column(db.String(255), nullable=False)
    link = db.Column(db.String(255), nullable=True)  # optional url_for target
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="notifications")

    def __repr__(self):
        return f"<Notification to={self.user_id} read={self.is_read}>"


def notify(user_id: int, message: str, link: str = None):
    """Helper used throughout routes to create a notification in one line."""
    n = Notification(user_id=user_id, message=message, link=link)
    db.session.add(n)
    return n
