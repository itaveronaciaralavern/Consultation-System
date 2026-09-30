from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db, limiter
from app.forms import LoginForm, StudentRegistrationForm, ChangePasswordForm
from app.models import User, Role, log_action

auth_bp = Blueprint("auth", __name__)


def _redirect_for_role(user):
    if user.role == Role.SUPER_ADMIN:
        return redirect(url_for("admin.dashboard"))
    if user.role == Role.MEDICAL_EXPERT:
        return redirect(url_for("expert.dashboard"))
    return redirect(url_for("student.dashboard"))


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")  # basic brute-force mitigation on login
def login():
    if current_user.is_authenticated:
        return _redirect_for_role(current_user)

    form = LoginForm()
    if form.validate_on_submit():
        identifier = form.username.data.strip()
        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()

        # Deliberately identical error message whether the username doesn't
        # exist or the password is wrong, so login can't be used to
        # enumerate valid usernames.
        if user is None or not user.check_password(form.password.data):
            flash("Invalid username or password.", "danger")
            return render_template("auth/login.html", form=form)

        if not user.is_active_account:
            flash("Your account has been deactivated. Contact the administrator.", "danger")
            return render_template("auth/login.html", form=form)

        login_user(user)
        user.last_login_at = datetime.utcnow()
        log_action(user.id, "LOGIN", target_type="User", target_id=user.id, ip_address=request.remote_addr)
        db.session.commit()

        flash(f"Welcome back, {user.full_name}!", "success")
        next_page = request.args.get("next")
        if next_page and next_page.startswith("/"):  # avoid open-redirect
            return redirect(next_page)
        return _redirect_for_role(user)

    return render_template("auth/login.html", form=form)


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def register():
    """
    Public self-registration is Student-only by design (see forms.py
    docstring) — this is a key RBAC boundary: privilege escalation via
    open registration is impossible because this route can only ever
    construct a User with role=Role.STUDENT.
    """
    form = StudentRegistrationForm()
    if form.validate_on_submit():
        user = User(
            full_name=form.full_name.data.strip(),
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            student_id_number=form.student_id_number.data.strip(),
            department=form.department.data.strip(),
            role=Role.STUDENT,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()
        log_action(user.id, "SELF_REGISTERED", target_type="User", target_id=user.id, ip_address=request.remote_addr)
        db.session.commit()
        flash("Account created. You may now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    log_action(current_user.id, "LOGOUT", target_type="User", target_id=current_user.id, ip_address=request.remote_addr)
    db.session.commit()
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Current password is incorrect.", "danger")
        else:
            current_user.set_password(form.new_password.data)
            log_action(current_user.id, "PASSWORD_CHANGED", target_type="User", target_id=current_user.id)
            db.session.commit()
            flash("Password updated successfully.", "success")
            return _redirect_for_role(current_user)
    return render_template("auth/change_password.html", form=form)
