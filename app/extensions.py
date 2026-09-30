"""
Extension instances live in their own module (rather than inside
app/__init__.py) so that models.py, routes, and forms can import `db`,
`login_manager`, etc. without triggering a circular import back into the
application factory.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

# Rate limiting: keyed by remote address. Applied selectively to
# sensitive endpoints (login, registration, booking) via @limiter.limit(...)
# in the route modules rather than globally, so normal browsing isn't throttled.
limiter = Limiter(key_func=get_remote_address)

login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"
