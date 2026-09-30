"""
forms/consultation_forms.py
-----------------------------
Forms for the booking workflow: a Student requesting a consultation,
and a Medical Expert accepting/declining/completing one.
"""

from datetime import date

from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, SelectField, DateField, SubmitField, HiddenField, TimeField
)
from wtforms.validators import DataRequired, Length, ValidationError, Optional

from app.models import ConsultationCategory, User, ROLE_MEDICAL_EXPERT


class ConsultationRequestForm(FlaskForm):
    """Used by a Student to book a NEW consultation, and also reused
    (pre-filled) for the 'reschedule' action on an existing one."""

    category_id = SelectField("Consultation Type", coerce=int, validators=[DataRequired()])
    expert_id = SelectField("Preferred Medical Expert (optional)", coerce=int, validators=[Optional()])
    requested_date = DateField("Preferred Date", validators=[DataRequired()], format="%Y-%m-%d")
    requested_time = TimeField("Preferred Time", validators=[DataRequired()])
    reason = TextAreaField(
        "Reason for Consultation",
        validators=[DataRequired(), Length(min=5, max=1000)],
        render_kw={"rows": 4, "placeholder": "Briefly describe your concern..."},
    )
    submit = SubmitField("Submit Request")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.category_id.choices = [
            (c.id, c.name) for c in ConsultationCategory.query.filter_by(is_active=True).order_by(ConsultationCategory.name)
        ]
        # 0 == "No preference"; route layer treats 0 as None.
        experts = User.query.join(User.role).filter_by(name=ROLE_MEDICAL_EXPERT).filter(
            User.is_active_account.is_(True)
        ).order_by(User.full_name)
        self.expert_id.choices = [(0, "No preference / any available")] + [
            (e.id, e.full_name) for e in experts
        ]

    def validate_requested_date(self, field):
        if field.data < date.today():
            raise ValidationError("Please choose today or a future date.")


class ConsultationDecisionForm(FlaskForm):
    """Medical Expert accepts or declines a pending request."""

    decision = HiddenField(validators=[DataRequired()])  # "accept" | "decline"
    decline_reason = TextAreaField(
        "Reason (required if declining)", validators=[Optional(), Length(max=255)], render_kw={"rows": 2}
    )
    submit = SubmitField("Submit Decision")

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False
        if self.decision.data == "decline" and not self.decline_reason.data.strip():
            self.decline_reason.errors.append("Please provide a reason for declining.")
            return False
        return True


class ConsultationCompleteForm(FlaskForm):
    """Medical Expert writes notes/diagnosis and marks a session complete."""

    expert_notes = TextAreaField(
        "Consultation Notes / Diagnosis",
        validators=[DataRequired(), Length(min=5, max=4000)],
        render_kw={"rows": 6},
    )
    submit = SubmitField("Mark Complete")


class CancelConsultationForm(FlaskForm):
    """CSRF-protected empty form backing the 'Cancel' button (no user
    input needed, but Flask-WTF still requires a form for the CSRF
    token on any state-changing POST)."""

    submit = SubmitField("Cancel Consultation")
