from app.extensions import db


class AvailabilitySlot(db.Model):
    """
    A single bookable window a Medical Expert has opened up. Students choose
    a date/time when booking (app/routes/student.py) that is cross-checked
    against slots that are (a) owned by the target expert, (b) matching
    day-of-week/date, and (c) not already fully booked — see
    AvailabilitySlot.is_full below.

    Design decision: we store `day_of_week` for *recurring* weekly
    availability (e.g. "Mondays 9-11am, every week") and an optional
    `specific_date` for one-off slots/overrides. This covers the common
    clinic pattern (a standing weekly schedule) without forcing the expert
    to manually create a row for every single week.
    """
    __tablename__ = "availability_slots"

    id = db.Column(db.Integer, primary_key=True)
    expert_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # 0=Monday .. 6=Sunday, for recurring weekly availability.
    day_of_week = db.Column(db.Integer, nullable=True)
    # If set, this slot applies to one specific calendar date only
    # (overrides/extra availability, or simply a non-recurring clinic).
    specific_date = db.Column(db.Date, nullable=True)

    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

    max_bookings = db.Column(db.Integer, default=1, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    expert = db.relationship("User", back_populates="availability_slots")

    def __repr__(self):
        target = self.specific_date or f"weekday {self.day_of_week}"
        return f"<AvailabilitySlot expert={self.expert_id} {target} {self.start_time}-{self.end_time}>"
