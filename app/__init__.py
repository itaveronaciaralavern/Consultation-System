"""
Application Factory pattern.

Why: create_app() builds a fresh Flask app from a config object rather than
a module-level `app = Flask(__name__)`. This lets us:
  1. Instantiate multiple configurations (dev/test/prod) from the same
     codebase, which is essential for running the test suite against an
     in-memory DB without touching dev.db.
  2. Avoid circular imports: extensions (db, login_manager, ...) are
     created empty in app/extensions.py and only *bound* to the app here,
     after all blueprints/models have been imported.
"""
import os
from flask import Flask, render_template

from config import config_by_name
from app.extensions import db, migrate, login_manager, csrf, limiter


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_by_name.get(config_name, config_by_name["default"]))

    # Ensure instance/ (holds the SQLite file) exists.
    os.makedirs(app.instance_path, exist_ok=True)

    _register_extensions(app)
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_cli_and_context(app)

    return app


def _register_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))


def _register_blueprints(app):
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.expert import expert_bp
    from app.routes.student import student_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(expert_bp, url_prefix="/expert")
    app.register_blueprint(student_bp, url_prefix="/student")


def _register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(429)
    def rate_limited(e):
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template("errors/500.html"), 500


def _register_cli_and_context(app):
    from app.models import User, Role, ConsultationCategory, Consultation, AvailabilitySlot, Notification, AuditLog

    @app.shell_context_processor
    def make_shell_context():
        return dict(
            db=db, User=User, Role=Role, ConsultationCategory=ConsultationCategory,
            Consultation=Consultation, AvailabilitySlot=AvailabilitySlot,
            Notification=Notification, AuditLog=AuditLog,
        )

    @app.context_processor
    def inject_notification_count():
        # Makes an unread-notification badge available in base.html on
        # every page without every view having to pass it explicitly.
        from flask_login import current_user
        if current_user.is_authenticated:
            unread = current_user.notifications.filter_by(is_read=False).count()
            return dict(unread_notification_count=unread)
        return dict(unread_notification_count=0)
