from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from sqlalchemy import func

from app.extensions import db
from app.decorators import roles_required, active_account_required
from app.forms import AdminCreateUserForm, EditUserForm, CategoryForm
from app.models import (
    User, Role, ConsultationCategory, Consultation, ConsultationStatus,
    AuditLog, log_action, notify,
)

admin_bp = Blueprint("admin", __name__)


# Every view in this blueprint is guarded by BOTH decorators:
#   @login_required          -> must be authenticated at all
#   @roles_required(SUPER_ADMIN) -> must specifically be a Super Admin
# This is the RBAC enforcement pattern described in decorators.py, applied
# consistently across the whole blueprint.

@admin_bp.route("/dashboard")
@login_required
@active_account_required
@roles_required(Role.SUPER_ADMIN)
def dashboard():
    total_students = User.query.filter_by(role=Role.STUDENT).count()
    total_experts = User.query.filter_by(role=Role.MEDICAL_EXPERT).count()
    total_consultations = Consultation.query.count()

    status_counts = dict(
        db.session.query(Consultation.status, func.count(Consultation.id))
        .group_by(Consultation.status).all()
    )
    # Normalize enum keys to plain strings for the template.
    status_counts = {k.value: v for k, v in status_counts.items()}

    recent_consultations = Consultation.query.order_by(Consultation.created_at.desc()).limit(8).all()

    return render_template(
        "admin/dashboard.html",
        total_students=total_students,
        total_experts=total_experts,
        total_consultations=total_consultations,
        status_counts=status_counts,
        recent_consultations=recent_consultations,
    )


# ---------------------------------------------------------------- Users ---
@admin_bp.route("/users")
@login_required
@active_account_required
@roles_required(Role.SUPER_ADMIN)
def manage_users():
    role_filter = request.args.get("role")
    query = User.query
    if role_filter in (Role.STUDENT.value, Role.MEDICAL_EXPERT.value, Role.SUPER_ADMIN.value):
        query = query.filter_by(role=Role(role_filter))
    users = query.order_by(User.created_at.desc()).all()
    return render_template("admin/manage_users.html", users=users, role_filter=role_filter)


@admin_bp.route("/users/create", methods=["GET", "POST"])
@login_required
@active_account_required
@roles_required(Role.SUPER_ADMIN)
def create_user():
    form = AdminCreateUserForm()
    if form.validate_on_submit():
        user = User(
            full_name=form.full_name.data.strip(),
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            role=Role(form.role.data),
            department=form.department.data.strip() or None,
            student_id_number=form.student_id_number.data.strip() or None,
            specialization=form.specialization.data.strip() or None,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()
        log_action(
            current_user.id, "USER_CREATED", target_type="User", target_id=user.id,
            details=f"role={user.role.value}", ip_address=request.remote_addr,
        )
        db.session.commit()
        flash(f"Account for {user.full_name} ({user.role.value}) created.", "success")
        return redirect(url_for("admin.manage_users"))
    return render_template("admin/user_form.html", form=form, mode="create")


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@active_account_required
@roles_required(Role.SUPER_ADMIN)
def edit_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    form = EditUserForm(obj=user)
    if form.validate_on_submit():
        was_active = user.is_active_account
        user.full_name = form.full_name.data.strip()
        user.email = form.email.data.strip().lower()
        user.department = form.department.data.strip() or None
        user.student_id_number = form.student_id_number.data.strip() or None
        user.specialization = form.specialization.data.strip() or None
        user.is_active_account = form.is_active_account.data

        action = "USER_UPDATED"
        if was_active and not user.is_active_account:
            action = "USER_DEACTIVATED"
        elif not was_active and user.is_active_account:
            action = "USER_REACTIVATED"

        log_action(current_user.id, action, target_type="User", target_id=user.id, ip_address=request.remote_addr)
        db.session.commit()
        flash(f"{user.full_name}'s account updated.", "success")
        return redirect(url_for("admin.manage_users"))
    return render_template("admin/user_form.html", form=form, mode="edit", target_user=user)


@admin_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@active_account_required
@roles_required(Role.SUPER_ADMIN)
def toggle_active(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    if user.id == current_user.id:
        flash("You cannot deactivate your own account.", "warning")
        return redirect(url_for("admin.manage_users"))

    user.is_active_account = not user.is_active_account
    action = "USER_DEACTIVATED" if not user.is_active_account else "USER_REACTIVATED"
    log_action(current_user.id, action, target_type="User", target_id=user.id, ip_address=request.remote_addr)
    db.session.commit()
    flash(f"{user.full_name} is now {'active' if user.is_active_account else 'deactivated'}.", "info")
    return redirect(url_for("admin.manage_users"))


# ----------------------------------------------------------- Categories ---
@admin_bp.route("/categories", methods=["GET", "POST"])
@login_required
@active_account_required
@roles_required(Role.SUPER_ADMIN)
def categories():
    form = CategoryForm()
    if form.validate_on_submit():
        cat = ConsultationCategory(
            name=form.name.data.strip(), description=form.description.data.strip() or None,
            is_active=form.is_active.data,
        )
        db.session.add(cat)
        db.session.flush()
        log_action(current_user.id, "CATEGORY_CREATED", target_type="ConsultationCategory", target_id=cat.id)
        db.session.commit()
        flash(f"Category '{cat.name}' created.", "success")
        return redirect(url_for("admin.categories"))
    all_categories = ConsultationCategory.query.order_by(ConsultationCategory.name).all()
    return render_template("admin/categories.html", form=form, categories=all_categories)


@admin_bp.route("/categories/<int:category_id>/toggle", methods=["POST"])
@login_required
@active_account_required
@roles_required(Role.SUPER_ADMIN)
def toggle_category(category_id):
    cat = db.session.get(ConsultationCategory, category_id)
    if cat is None:
        abort(404)
    cat.is_active = not cat.is_active
    log_action(current_user.id, "CATEGORY_TOGGLED", target_type="ConsultationCategory", target_id=cat.id)
    db.session.commit()
    flash(f"Category '{cat.name}' is now {'active' if cat.is_active else 'inactive'}.", "info")
    return redirect(url_for("admin.categories"))


# ------------------------------------------------------- All Consultations
@admin_bp.route("/consultations")
@login_required
@active_account_required
@roles_required(Role.SUPER_ADMIN)
def all_consultations():
    """System-wide view across every consultation, regardless of expert."""
    status_filter = request.args.get("status")
    query = Consultation.query
    if status_filter:
        try:
            query = query.filter_by(status=ConsultationStatus(status_filter))
        except ValueError:
            pass
    items = query.order_by(Consultation.created_at.desc()).all()
    return render_template("admin/all_consultations.html", consultations=items, status_filter=status_filter)


# --------------------------------------------------------------- Audit ---
@admin_bp.route("/audit-logs")
@login_required
@active_account_required
@roles_required(Role.SUPER_ADMIN)
def audit_logs():
    page = request.args.get("page", 1, type=int)
    pagination = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=25, error_out=False)
    return render_template("admin/audit_logs.html", pagination=pagination)
