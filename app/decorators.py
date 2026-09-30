"""
RBAC enforcement: decorator-based, applied per-view.

Why decorators (vs. a single before_request middleware)?
- Explicitness: reading a route's decorator list tells you exactly which
  roles can reach it, right next to the code that handles it. A single
  global middleware would need a growing table mapping URL patterns to
  roles, which drifts out of sync with the blueprints as routes are added.
- Composability: `@login_required` (Flask-Login) and `@roles_required(...)`
  (ours) stack cleanly, and object-level checks (e.g. "is this consultation
  actually assigned to this expert?") are added as a third, explicit guard
  inside the view function itself — RBAC (role) and object-ownership
  authorization are deliberately kept as separate, layered checks.

Every blueprint's routes are also registered under a URL prefix
(/admin, /expert, /student) which gives a second, coarse line of defense
at the routing layer, but the decorators below are the actual enforcement;
the prefixes are just for readability/organization.
"""
from functools import wraps

from flask import abort, flash, redirect, url_for
from flask_login import current_user


def roles_required(*roles):
    """
    Restrict a view to users whose `.role` is in `roles`.
    Must be combined with @login_required (placed below it) since this
    decorator assumes current_user is authenticated when checking .role.
    Anonymous users are redirected to login (via login_manager); an
    authenticated user with the wrong role gets a 403.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if current_user.role not in roles:
                abort(403)
            return view_func(*args, **kwargs)
        return wrapped_view
    return decorator


def active_account_required(view_func):
    """
    Defense-in-depth: Flask-Login's is_active already blocks login for
    deactivated accounts, but a session created before deactivation could
    still be live. This re-checks on every decorated request and force
    logs the user out if Super Admin deactivated them mid-session.
    """
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if current_user.is_authenticated and not current_user.is_active_account:
            from flask_login import logout_user
            logout_user()
            flash("Your account has been deactivated. Contact the administrator.", "danger")
            return redirect(url_for("auth.login"))
        return view_func(*args, **kwargs)
    return wrapped_view
