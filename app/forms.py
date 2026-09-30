"""
All forms in one module for a project this size. Each uses Flask-WTF, which
gives us: CSRF tokens automatically, server-side validation (never trust
client-side JS alone), and clean re-rendering of field-level errors.
"""
from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, SelectField, TextAreaField, DateField,
    TimeField, IntegerField, BooleanField, SubmitField,
)
from wtforms.validators import (
    DataRequired, Email, Length, EqualTo, ValidationError, Optional, NumberRange,
)

from app.models import User, ConsultationCategory


class LoginForm(FlaskForm):
    username = StringField("Username or Email", validators=[DataRequired(), Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log In")


class StudentRegistrationForm(FlaskForm):
    """Public self-registration is intentionally limited to the Student
    role. Medical Expert and Super Admin accounts are created only by an
    existing Super Admin (see admin routes) — this prevents privilege
    escalation via open registration."""
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    student_id_number = StringField("Student ID Number", validators=[DataRequired(), Length(max=30)])
    department = StringField("Department / Program", validators=[DataRequired(), Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField(
        "Confirm Password", validators=[DataRequired(), EqualTo("password", message="Passwords must match.")]
    )
    submit = SubmitField("Register")

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError("That username is already taken.")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError("That email is already registered.")


class AdminCreateUserForm(FlaskForm):
    """Used by Super Admin to create Medical Expert or Student accounts."""
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    role = SelectField(
        "Role",
        choices=[("medical_expert", "Medical Expert"), ("student", "Student"), ("super_admin", "Super Admin")],
        validators=[DataRequired()],
    )
    department = StringField("Department / Program", validators=[Optional(), Length(max=120)])
    student_id_number = StringField("Student ID Number", validators=[Optional(), Length(max=30)])
    specialization = StringField("Specialization (Medical Expert)", validators=[Optional(), Length(max=120)])
    password = PasswordField("Temporary Password", validators=[DataRequired(), Length(min=8)])
    submit = SubmitField("Create Account")

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError("That username is already taken.")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError("That email is already registered.")


class EditUserForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    department = StringField("Department / Program", validators=[Optional(), Length(max=120)])
    student_id_number = StringField("Student ID Number", validators=[Optional(), Length(max=30)])
    specialization = StringField("Specialization", validators=[Optional(), Length(max=120)])
    is_active_account = BooleanField("Account Active")
    submit = SubmitField("Save Changes")


class CategoryForm(FlaskForm):
    name = StringField("Category Name", validators=[DataRequired(), Length(max=100)])
    description = StringField("Description", validators=[Optional(), Length(max=255)])
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save Category")


class AvailabilitySlotForm(FlaskForm):
    day_of_week = SelectField(
        "Recurring Day of Week",
        choices=[
            ("", "-- one-off date instead --"),
            ("0", "Monday"), ("1", "Tuesday"), ("2", "Wednesday"),
            ("3", "Thursday"), ("4", "Friday"), ("5", "Saturday"), ("6", "Sunday"),
        ],
        validators=[Optional()],
    )
    specific_date = DateField("...or a specific date", validators=[Optional()])
    start_time = TimeField("Start Time", validators=[DataRequired()])
    end_time = TimeField("End Time", validators=[DataRequired()])
    max_bookings = IntegerField("Max Bookings in this Slot", validators=[DataRequired(), NumberRange(min=1, max=50)], default=1)
    submit = SubmitField("Add Availability")

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators=extra_validators)
        if not ok:
            return False
        if not self.day_of_week.data and not self.specific_date.data:
            self.specific_date.errors.append("Choose a recurring day OR a specific date.")
            return False
        if self.start_time.data and self.end_time.data and self.start_time.data >= self.end_time.data:
            self.end_time.errors.append("End time must be after start time.")
            return False
        return True


class BookConsultationForm(FlaskForm):
    category_id = SelectField("Consultation Type", coerce=int, validators=[DataRequired()])
    expert_id = SelectField("Preferred Medical Expert", coerce=int, validators=[DataRequired()])
    requested_date = DateField("Preferred Date", validators=[DataRequired()])
    requested_time = TimeField("Preferred Time", validators=[DataRequired()])
    student_message = TextAreaField("Reason for Visit", validators=[DataRequired(), Length(max=1000)])
    submit = SubmitField("Submit Request")

    def set_choices(self):
        self.category_id.choices = [
            (c.id, c.name) for c in ConsultationCategory.query.filter_by(is_active=True).order_by(ConsultationCategory.name)
        ]
        self.expert_id.choices = [
            (u.id, u.full_name) for u in User.query.filter_by(role="medical_expert", is_active_account=True).order_by(User.full_name)
        ]


class RescheduleForm(FlaskForm):
    requested_date = DateField("New Date", validators=[DataRequired()])
    requested_time = TimeField("New Time", validators=[DataRequired()])
    submit = SubmitField("Request Reschedule")


class DeclineForm(FlaskForm):
    decline_reason = StringField("Reason for Declining", validators=[DataRequired(), Length(max=255)])
    submit = SubmitField("Decline Request")


class CompleteConsultationForm(FlaskForm):
    expert_notes = TextAreaField("Consultation Notes", validators=[Optional(), Length(max=4000)])
    diagnosis = TextAreaField("Diagnosis / Findings", validators=[Optional(), Length(max=4000)])
    submit = SubmitField("Mark as Completed")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current Password", validators=[DataRequired()])
    new_password = PasswordField("New Password", validators=[DataRequired(), Length(min=8)])
    confirm_new_password = PasswordField(
        "Confirm New Password", validators=[DataRequired(), EqualTo("new_password", message="Passwords must match.")]
    )
    submit = SubmitField("Change Password")
