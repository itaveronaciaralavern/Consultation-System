"""
forms/auth_forms.py
--------------------
Login and self-registration forms.

Design decision: Only Students self-register through the public form.
Medical Expert and Super Admin accounts are provisioned by an existing
Super Admin (see forms/admin_forms.py + routes/admin.py). This mirrors
real institutional practice: clinic staff accounts shouldn't be
self-service, only the student body's accounts should be.
"""

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError

from app.models import User


class LoginForm(FlaskForm):
    username = StringField("Username or Email", validators=[DataRequired(), Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember me")
    submit = SubmitField("Log In")


class StudentRegistrationForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    student_id_number = StringField("Student ID Number", validators=[DataRequired(), Length(max=30)])
    department = StringField("Program / Department", validators=[DataRequired(), Length(max=120)])
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, message="Use at least 8 characters.")])
    confirm_password = PasswordField(
        "Confirm Password", validators=[DataRequired(), EqualTo("password", message="Passwords must match.")]
    )
    submit = SubmitField("Create Account")

    # Custom validators: WTForms auto-calls validate_<field>, keeping
    # uniqueness checks colocated with the field they guard instead of
    # scattered in the route handler.
    def validate_username(self, field):
        if User.query.filter_by(username=field.data.strip()).first():
            raise ValidationError("That username is already taken.")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.strip().lower()).first():
            raise ValidationError("An account with that email already exists.")
