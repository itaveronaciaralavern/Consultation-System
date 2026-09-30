"""
Seed script: creates one account per role plus sample categories,
availability, and a couple of demo consultations so the app is immediately
explorable after setup.

Usage:  flask --app run.py shell -c "exec(open('seed.py').read())"
    or: python seed.py     (see __main__ block below)

Idempotent: safe to run more than once — it checks for existing rows
before inserting so it won't create duplicates or crash on a unique
constraint.
"""
from datetime import date, time, timedelta

from app import create_app
from app.extensions import db
from app.models import User, Role, ConsultationCategory, AvailabilitySlot, Consultation, ConsultationStatus


DEFAULT_ACCOUNTS = [
    dict(
        username="admin", email="admin@abuyogcc.edu.ph", full_name="Sofia Mercado",
        role=Role.SUPER_ADMIN, password="Admin@12345",
    ),
    dict(
        username="dr.santos", email="santos@abuyogcc.edu.ph", full_name="Dr. Ramon Santos",
        role=Role.MEDICAL_EXPERT, password="Expert@12345", specialization="General Medicine",
    ),
    dict(
        username="dr.reyes", email="reyes@abuyogcc.edu.ph", full_name="Dr. Liza Reyes",
        role=Role.MEDICAL_EXPERT, password="Expert@12345", specialization="Mental Health Counseling",
    ),
    dict(
        username="jstudent", email="juan.delacruz@students.abuyogcc.edu.ph", full_name="Juan Dela Cruz",
        role=Role.STUDENT, password="Student@12345", student_id_number="2024-00123", department="BS Information Technology",
    ),
]

DEFAULT_CATEGORIES = [
    ("General Checkup", "Routine physical health consultation."),
    ("Mental Health Counseling", "Confidential counseling for stress, anxiety, and personal concerns."),
    ("Dental Referral", "Initial screening and referral for dental concerns."),
    ("Vaccination Inquiry", "Questions about immunization records and schedules."),
]


def seed():
    created_users = {}
    for acct in DEFAULT_ACCOUNTS:
        existing = User.query.filter_by(username=acct["username"]).first()
        if existing:
            created_users[acct["username"]] = existing
            continue
        user = User(
            username=acct["username"], email=acct["email"], full_name=acct["full_name"],
            role=acct["role"], student_id_number=acct.get("student_id_number"),
            department=acct.get("department"), specialization=acct.get("specialization"),
        )
        user.set_password(acct["password"])
        db.session.add(user)
        created_users[acct["username"]] = user
        print(f"  + created user: {acct['username']} ({acct['role'].value})")

    db.session.flush()

    for name, description in DEFAULT_CATEGORIES:
        if not ConsultationCategory.query.filter_by(name=name).first():
            db.session.add(ConsultationCategory(name=name, description=description, is_active=True))
            print(f"  + created category: {name}")

    db.session.flush()

    dr_santos = created_users["dr.santos"]
    dr_reyes = created_users["dr.reyes"]

    if dr_santos.availability_slots.count() == 0:
        db.session.add_all([
            AvailabilitySlot(expert_id=dr_santos.id, day_of_week=0, start_time=time(9, 0), end_time=time(12, 0), max_bookings=4),
            AvailabilitySlot(expert_id=dr_santos.id, day_of_week=2, start_time=time(13, 0), end_time=time(16, 0), max_bookings=4),
        ])
        print("  + added availability for Dr. Santos")

    if dr_reyes.availability_slots.count() == 0:
        db.session.add_all([
            AvailabilitySlot(expert_id=dr_reyes.id, day_of_week=1, start_time=time(10, 0), end_time=time(15, 0), max_bookings=3),
        ])
        print("  + added availability for Dr. Reyes")

    db.session.flush()

    student = created_users["jstudent"]
    general_checkup = ConsultationCategory.query.filter_by(name="General Checkup").first()
    if student.consultations_as_student.count() == 0 and general_checkup:
        demo = Consultation(
            student_id=student.id, expert_id=dr_santos.id, category_id=general_checkup.id,
            requested_date=date.today() + timedelta(days=3), requested_time=time(9, 30),
            student_message="Follow-up checkup for recurring headaches.",
            status=ConsultationStatus.PENDING,
        )
        db.session.add(demo)
        print("  + added a sample pending consultation request")

    db.session.commit()
    print("\nSeed complete.\n")
    print("Default login credentials:")
    print("  Super Admin    -> username: admin        password: Admin@12345")
    print("  Medical Expert -> username: dr.santos     password: Expert@12345")
    print("  Medical Expert -> username: dr.reyes      password: Expert@12345")
    print("  Student        -> username: jstudent      password: Student@12345")
    print("\nIMPORTANT: change these passwords before any real deployment.")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed()
