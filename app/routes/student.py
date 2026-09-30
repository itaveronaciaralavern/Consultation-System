from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.extensions import db, limiter
from app.decorators import roles_required, active_account_required
from app.forms import BookConsultationForm, RescheduleForm
from app.models import Consultation, ConsultationStatus, Role, notify, log_action, User

student_bp = Blueprint("student", __name__)


def _get_own_consultation_or_403(consultation_id):
    """Object-level check: a student may only view/act on THEIR OWN
    consultation requests, never another student's."""
    consultation = db.session.get(Consultation, consultation_id)
    if consultation is None:
        abort(404)
    if consultation.student_id != current_user.id:
        abort(403)
    return consultation


@student_bp.route("/dashboard")
@login_required
@active_account_required
@roles_required(Role.STUDENT)
def dashboard():
    upcoming = (
        current_user.consultations_as_student
        .filter(Consultation.status.in_([ConsultationStatus.PENDING, ConsultationStatus.ACCEPTED]))
        .order_by(Consultation.requested_date, Consultation.requested_time)
        .limit(5).all()
    )
    recent_history = (
        current_user.consultations_as_student
        .filter(Consultation.status.in_([ConsultationStatus.COMPLETED, ConsultationStatus.DECLINED, ConsultationStatus.CANCELLED]))
        .order_by(Consultation.updated_at.desc()).limit(5).all()
    )
    total_requests = current_user.consultations_as_student.count()
    return render_template(
        "student/dashboard.html", upcoming=upcoming, recent_history=recent_history,
        total_requests=total_requests,
    )


@student_bp.route("/book", methods=["GET", "POST"])
@login_required
@active_account_required
@roles_required(Role.STUDENT)
@limiter.limit("20 per hour")  # prevent booking-spam
def book():
    form = BookConsultationForm()
    form.set_choices()

    if not form.category_id.choices:
        flash("No consultation categories are available yet. Contact the administrator.", "warning")
    if not form.expert_id.choices:
        flash("No medical experts are available yet. Contact the administrator.", "warning")

    if form.validate_on_submit():
        consultation = Consultation(
            student_id=current_user.id,
            expert_id=form.expert_id.data,
            category_id=form.category_id.data,
            requested_date=form.requested_date.data,
            requested_time=form.requested_time.data,
            student_message=form.student_message.data.strip(),
            status=ConsultationStatus.PENDING,
        )
        db.session.add(consultation)
        db.session.flush()

        notify(
            consultation.expert_id,
            f"New consultation request from {current_user.full_name} for {consultation.requested_date}.",
            link=url_for("expert.view_consultation", consultation_id=consultation.id),
        )
        log_action(current_user.id, "CONSULTATION_REQUESTED", target_type="Consultation", target_id=consultation.id)
        db.session.commit()
        flash("Your consultation request has been submitted.", "success")
        return redirect(url_for("student.history"))

    return render_template("student/book.html", form=form)


@student_bp.route("/history")
@login_required
@active_account_required
@roles_required(Role.STUDENT)
def history():
    items = current_user.consultations_as_student.order_by(Consultation.created_at.desc()).all()
    return render_template("student/history.html", consultations=items)


@student_bp.route("/consultations/<int:consultation_id>")
@login_required
@active_account_required
@roles_required(Role.STUDENT)
def view_consultation(consultation_id):
    consultation = _get_own_consultation_or_403(consultation_id)
    reschedule_form = RescheduleForm(obj=consultation)
    return render_template("student/consultation_detail.html", consultation=consultation, reschedule_form=reschedule_form)


@student_bp.route("/consultations/<int:consultation_id>/cancel", methods=["POST"])
@login_required
@active_account_required
@roles_required(Role.STUDENT)
def cancel_consultation(consultation_id):
    consultation = _get_own_consultation_or_403(consultation_id)
    if consultation.status not in (ConsultationStatus.PENDING, ConsultationStatus.ACCEPTED):
        flash("This consultation can no longer be cancelled.", "warning")
        return redirect(url_for("student.view_consultation", consultation_id=consultation.id))

    consultation.status = ConsultationStatus.CANCELLED
    if consultation.expert_id:
        notify(
            consultation.expert_id,
            f"{current_user.full_name} cancelled their consultation for {consultation.requested_date}.",
            link=url_for("expert.view_consultation", consultation_id=consultation.id),
        )
    log_action(current_user.id, "CONSULTATION_CANCELLED", target_type="Consultation", target_id=consultation.id)
    db.session.commit()
    flash("Consultation cancelled.", "info")
    return redirect(url_for("student.history"))


@student_bp.route("/consultations/<int:consultation_id>/reschedule", methods=["POST"])
@login_required
@active_account_required
@roles_required(Role.STUDENT)
def reschedule_consultation(consultation_id):
    consultation = _get_own_consultation_or_403(consultation_id)
    if consultation.status not in (ConsultationStatus.PENDING, ConsultationStatus.ACCEPTED):
        flash("This consultation can no longer be rescheduled.", "warning")
        return redirect(url_for("student.view_consultation", consultation_id=consultation.id))

    form = RescheduleForm()
    if form.validate_on_submit():
        consultation.requested_date = form.requested_date.data
        consultation.requested_time = form.requested_time.data
        # Rescheduling sends the request back to pending so the expert
        # re-confirms the new slot works for them.
        consultation.status = ConsultationStatus.PENDING
        if consultation.expert_id:
            notify(
                consultation.expert_id,
                f"{current_user.full_name} requested to reschedule to {consultation.requested_date} {consultation.requested_time}.",
                link=url_for("expert.view_consultation", consultation_id=consultation.id),
            )
        log_action(current_user.id, "CONSULTATION_RESCHEDULED", target_type="Consultation", target_id=consultation.id)
        db.session.commit()
        flash("Reschedule request submitted.", "success")
    else:
        flash("Please provide a valid new date and time.", "danger")
    return redirect(url_for("student.view_consultation", consultation_id=consultation.id))
