"""
utils/decorators.py
--------------------
RBAC enforcement lives HERE and only here, as view-function decorators.

Design decision (decorator-based RBAC, not middleware):
    We enforce roles with per-view decorators (`@role_required(...)`)
    rather than a single global `before_request` middleware that tries
    to pattern-match every URL to an allowed role. Reasons:

      1. Explicitness: opening any route file, you can see exactly which
         roles may hit it, right above the `def`. A middleware table of
         "url pattern -> allowed roles" becomes an unreadable, easily
         desynced routing table as the app grows.
      2. Composability: a view can combine `@login_required` (Flask-Login,
         "must be authenticated") with `@role_required(...)` ("must be
         THIS role") and with object-level ownership checks inside the
         view body (e.g. "this consultation must belong to you") --
         three independent layers of authorization that a single
         middleware cannot express cleanly.
      3. Fail-closed default: `role_required` itself calls `login_required`
         internally, so a route can NEVER accidentally allow anonymous
         access just because someone forgot to stack `@login_required`
         above it.

    We additionally protect against a still-logged-in-but-deactivated
    account (Super Admin deactivated a user mid-session) by checking
    `current_user.is_active_account` on every protected request, since
    Flask-Login's own `is_active` check only runs at login time.
"""

from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user, login_required

from app.models import ROLE_SUPER_ADMIN, ROLE_MEDICAL_EXPERT, ROLE_STUDENT


def role_required(*roles):
    """
    Restrict a view to users whose Role.name is in `roles`.

    Usage:
        @admin_bp.route("/users")
        @role_required(ROLE_SUPER_ADMIN)
        def manage_users():
            ...

    Stacks its own login_required so a bare @role_required(...) is
    always sufficient -- you never need to remember to add both.
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped(*args, **kwargs):
            # Defense in depth: a session token can outlive an admin
            # deactivating the account. Kill the session immediately.
            if not current_user.is_active_account:
                flash("Your account has been deactivated. Contact the administrator.", "danger")
                return redirect(url_for("auth.logout"))

            if current_user.role.name not in roles:
                # 403, not a redirect: a role mismatch is an authorization
                # failure, not a "please log in" situation, so we don't
                # want to funnel it back through the login page.
                abort(403)
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


# Convenience aliases for the three roles -- reads better at call sites
# than repeating role_required(ROLE_SUPER_ADMIN) everywhere.
super_admin_required = lambda f: role_required(ROLE_SUPER_ADMIN)(f)
medical_expert_required = lambda f: role_required(ROLE_MEDICAL_EXPERT)(f)
student_required = lambda f: role_required(ROLE_STUDENT)(f)


def any_role_required(f):
    """Any authenticated + active user (all three roles). Thin wrapper
    kept for symmetry/readability at call sites that just need
    'logged in and not deactivated', e.g. the shared notifications view."""
    return role_required(ROLE_SUPER_ADMIN, ROLE_MEDICAL_EXPERT, ROLE_STUDENT)(f)
