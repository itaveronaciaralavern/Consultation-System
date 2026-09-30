"""
forms/admin_forms.py
----------------------
Forms used exclusively by the Super Admin: provisioning Medical Expert
/ Student accounts by hand, managing categories, and setting an
expert's weekly availability.
"""

from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, SubmitField, SelectField, BooleanField, TextAreaField, TimeField
)
from wtforms.validators import DataRequired, Email, Length, Optional, ValidationError

from app.models import User, ROLE_MEDICAL_EXPERT, ROLE_STUDENT, ROLE_SUPER_ADMIN


class UserCreateForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    department = StringField("Program / Department / Specialty", validators=[Optional(), Length(max=120)])
    student_id_number = StringField("Student ID Number (students only)", validators=[Optional(), Length(max=30)])
    role_name = SelectField(
        "Role",
        choices=[(ROLE_MEDICAL_EXPERT, "Medical Expert"), (ROLE_STUDENT, "Student"), (ROLE_SUPER_ADMIN, "Super Admin")],
        validators=[DataRequired()],
    )
    password = PasswordField("Initial Password", validators=[DataRequired(), Length(min=8)])
    submit = SubmitField("Create Account")

    def validate_username(self, field):
        if User.query.filter_by(username=field.data.strip()).first():
            raise ValidationError("That username is already taken.")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.strip().lower()).first():
            raise ValidationError("An account with that email already exists.")


class UserEditForm(FlaskForm):
    """Edit an existing account. Username/email uniqueness checks
    exclude the record being edited (see routes/admin.py for how
    `original_id` is used)."""

    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    department = StringField("Program / Department / Specialty", validators=[Optional(), Length(max=120)])
    student_id_number = StringField("Student ID Number", validators=[Optional(), Length(max=30)])
    is_active_account = BooleanField("Account Active")
    new_password = PasswordField(
        "Reset Password (leave blank to keep current)", validators=[Optional(), Length(min=8)]
    )
    submit = SubmitField("Save Changes")


class CategoryForm(FlaskForm):
    name = StringField("Category Name", validators=[DataRequired(), Length(max=100)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=255)], render_kw={"rows": 2})
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save Category")


class AvailabilityForm(FlaskForm):
    """Used by BOTH the Super Admin (managing any expert's schedule)
    and the Medical Expert (managing their own) -- see routes for how
    `expert_id` choices are populated/hidden depending on caller."""

    expert_id = SelectField("Medical Expert", coerce=int, validators=[DataRequired()])
    day_of_week = SelectField(
        "Day of Week",
        coerce=int,
        choices=[(0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"),
                 (4, "Friday"), (5, "Saturday"), (6, "Sunday")],
        validators=[DataRequired()],
    )
    start_time = TimeField("Start Time", validators=[DataRequired()])
    end_time = TimeField("End Time", validators=[DataRequired()])
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save Availability")

    def validate_end_time(self, field):
        if self.start_time.data and field.data <= self.start_time.data:
            raise ValidationError("End time must be after start time.")
