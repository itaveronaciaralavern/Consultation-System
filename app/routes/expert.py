from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.decorators import roles_required, active_account_required
from app.forms import AvailabilitySlotForm, DeclineForm, CompleteConsultationForm
from app.models import Consultation, ConsultationStatus, AvailabilitySlot, Role, notify, log_action

expert_bp = Blueprint("expert", __name__)


def _get_owned_consultation_or_403(consultation_id):
    """
    Object-level authorization helper: a Medical Expert may only act on a
    consultation that is assigned to THEM. Role check (@roles_required)
    only proves "this user is *a* medical expert" — it says nothing about
    which patients/consultations belong to them, so every view below
    re-checks expert_id == current_user.id explicitly.
    """
    consultation = db.session.get(Consultation, consultation_id)
    if consultation is None:
        abort(404)
    if consultation.expert_id is not None and consultation.expert_id != current_user.id:
        abort(403)
    return consultation


@expert_bp.route("/dashboard")
@login_required
@active_account_required
@roles_required(Role.MEDICAL_EXPERT)
def dashboard():
    pending_unassigned = Consultation.query.filter_by(
        status=ConsultationStatus.PENDING, expert_id=None
    ).count()
    my_pending = current_user.consultations_as_expert.filter_by(status=ConsultationStatus.PENDING).count()
    my_accepted = current_user.consultations_as_expert.filter_by(status=ConsultationStatus.ACCEPTED).count()
    my_completed = current_user.consultations_as_expert.filter_by(status=ConsultationStatus.COMPLETED).count()

    upcoming = (
        current_user.consultations_as_expert
        .filter(Consultation.status == ConsultationStatus.ACCEPTED)
        .order_by(Consultation.requested_date, Consultation.requested_time)
        .limit(5).all()
    )
    unassigned_requests = Consultation.query.filter_by(
        status=ConsultationStatus.PENDING, expert_id=None
    ).order_by(Consultation.created_at.desc()).limit(10).all()

    return render_template(
        "expert/dashboard.html",
        pending_unassigned=pending_unassigned, my_pending=my_pending,
        my_accepted=my_accepted, my_completed=my_completed,
        upcoming=upcoming, unassigned_requests=unassigned_requests,
    )


@expert_bp.route("/requests")
@login_required
@active_account_required
@roles_required(Role.MEDICAL_EXPERT)
def requests_list():
    """Shows both: requests already assigned to me, and open/unassigned
    requests any expert can claim (simple pooled-queue model)."""
    my_requests = current_user.consultations_as_expert.order_by(Consultation.created_at.desc()).all()
    open_requests = Consultation.query.filter_by(
        status=ConsultationStatus.PENDING, expert_id=None
    ).order_by(Consultation.created_at.desc()).all()
    return render_template("expert/requests.html", my_requests=my_requests, open_requests=open_requests)


@expert_bp.route("/consultations/<int:consultation_id>")
@login_required
@active_account_required
@roles_required(Role.MEDICAL_EXPERT)
def view_consultation(consultation_id):
    consultation = _get_owned_consultation_or_403(consultation_id)
    complete_form = CompleteConsultationForm(obj=consultation)
    decline_form = DeclineForm()
    return render_template(
        "expert/consultation_detail.html", consultation=consultation,
        complete_form=complete_form, decline_form=decline_form,
    )


@expert_bp.route("/consultations/<int:consultation_id>/accept", methods=["POST"])
@login_required
@active_account_required
@roles_required(Role.MEDICAL_EXPERT)
def accept_consultation(consultation_id):
    consultation = db.session.get(Consultation, consultation_id)
    if consultation is None:
        abort(404)
    if consultation.status != ConsultationStatus.PENDING:
        flash("This request is no longer pending.", "warning")
        return redirect(url_for("expert.requests_list"))
    # An unassigned request can be claimed by any expert; an assigned one
    # can only be accepted by the expert it's assigned to.
    if consultation.expert_id is not None and consultation.expert_id != current_user.id:
        abort(403)

    consultation.expert_id = current_user.id
    consultation.status = ConsultationStatus.ACCEPTED
    notify(
        consultation.student_id,
        f"Your consultation request for {consultation.requested_date} was accepted by {current_user.full_name}.",
        link=url_for("student.view_consultation", consultation_id=consultation.id),
    )
    log_action(current_user.id, "CONSULTATION_ACCEPTED", target_type="Consultation", target_id=consultation.id)
    db.session.commit()
    flash("Consultation accepted.", "success")
    return redirect(url_for("expert.view_consultation", consultation_id=consultation.id))


@expert_bp.route("/consultations/<int:consultation_id>/decline", methods=["POST"])
@login_required
@active_account_required
@roles_required(Role.MEDICAL_EXPERT)
def decline_consultation(consultation_id):
    consultation = _get_owned_consultation_or_403(consultation_id)
    form = DeclineForm()
    if form.validate_on_submit():
        consultation.status = ConsultationStatus.DECLINED
        consultation.decline_reason = form.decline_reason.data.strip()
        notify(
            consultation.student_id,
            f"Your consultation request for {consultation.requested_date} was declined: {consultation.decline_reason}",
            link=url_for("student.view_consultation", consultation_id=consultation.id),
        )
        log_action(current_user.id, "CONSULTATION_DECLINED", target_type="Consultation", target_id=consultation.id)
        db.session.commit()
        flash("Consultation declined.", "info")
    else:
        flash("Please provide a reason for declining.", "danger")
    return redirect(url_for("expert.view_consultation", consultation_id=consultation.id))


@expert_bp.route("/consultations/<int:consultation_id>/complete", methods=["POST"])
@login_required
@active_account_required
@roles_required(Role.MEDICAL_EXPERT)
def complete_consultation(consultation_id):
    consultation = _get_owned_consultation_or_403(consultation_id)
    if consultation.status != ConsultationStatus.ACCEPTED:
        flash("Only accepted consultations can be marked complete.", "warning")
        return redirect(url_for("expert.view_consultation", consultation_id=consultation.id))

    form = CompleteConsultationForm()
    if form.validate_on_submit():
        consultation.expert_notes = form.expert_notes.data
        consultation.diagnosis = form.diagnosis.data
        consultation.status = ConsultationStatus.COMPLETED
        consultation.completed_at = datetime.utcnow()
        notify(
            consultation.student_id,
            "Your consultation has been marked complete. View your history for notes.",
            link=url_for("student.view_consultation", consultation_id=consultation.id),
        )
        log_action(current_user.id, "CONSULTATION_COMPLETED", target_type="Consultation", target_id=consultation.id)
        db.session.commit()
        flash("Consultation marked as completed.", "success")
    return redirect(url_for("expert.view_consultation", consultation_id=consultation.id))


@expert_bp.route("/history")
@login_required
@active_account_required
@roles_required(Role.MEDICAL_EXPERT)
def history():
    """Full consultation history across all students the expert has seen."""
    items = current_user.consultations_as_expert.order_by(Consultation.created_at.desc()).all()
    return render_template("expert/history.html", consultations=items)


# ---------------------------------------------------------- Availability
@expert_bp.route("/availability", methods=["GET", "POST"])
@login_required
@active_account_required
@roles_required(Role.MEDICAL_EXPERT)
def availability():
    form = AvailabilitySlotForm()
    if form.validate_on_submit():
        slot = AvailabilitySlot(
            expert_id=current_user.id,
            day_of_week=int(form.day_of_week.data) if form.day_of_week.data else None,
            specific_date=form.specific_date.data or None,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            max_bookings=form.max_bookings.data,
        )
        db.session.add(slot)
        log_action(current_user.id, "AVAILABILITY_ADDED", target_type="AvailabilitySlot")
        db.session.commit()
        flash("Availability slot added.", "success")
        return redirect(url_for("expert.availability"))

    slots = current_user.availability_slots.order_by(AvailabilitySlot.day_of_week).all()
    return render_template("expert/availability.html", form=form, slots=slots)


@expert_bp.route("/availability/<int:slot_id>/delete", methods=["POST"])
@login_required
@active_account_required
@roles_required(Role.MEDICAL_EXPERT)
def delete_availability(slot_id):
    slot = db.session.get(AvailabilitySlot, slot_id)
    if slot is None:
        abort(404)
    if slot.expert_id != current_user.id:
        abort(403)
    db.session.delete(slot)
    log_action(current_user.id, "AVAILABILITY_REMOVED", target_type="AvailabilitySlot", target_id=slot_id)
    db.session.commit()
    flash("Availability slot removed.", "info")
    return redirect(url_for("expert.availability"))
