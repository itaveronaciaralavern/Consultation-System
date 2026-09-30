# Abuyog Community College — Consultation Management System

A role-based web application for managing student consultations with the
college's medical experts, built with Flask (Application Factory +
Blueprints), SQLAlchemy/SQLite, Flask-Login, and server-rendered Jinja2
templates (no frontend framework).

---

## 1. Project Structure

```
consultation_system/
├── app/
│   ├── __init__.py          # Application Factory (create_app)
│   ├── extensions.py        # db, login_manager, migrate, csrf, limiter (singletons)
│   ├── decorators.py        # RBAC decorators (roles_required, active_account_required)
│   ├── forms.py             # All Flask-WTF forms (validation lives here)
│   ├── models/
│   │   ├── user.py          # User + Role enum, password hashing
│   │   ├── consultation.py  # ConsultationCategory, Consultation, ConsultationStatus
│   │   ├── schedule.py      # AvailabilitySlot
│   │   ├── notification.py  # Notification + notify() helper
│   │   └── audit_log.py     # AuditLog + log_action() helper
│   ├── routes/
│   │   ├── main.py          # landing page, notifications (shared across roles)
│   │   ├── auth.py          # login, logout, student self-registration
│   │   ├── admin.py         # Super Admin blueprint  (/admin/...)
│   │   ├── expert.py        # Medical Expert blueprint (/expert/...)
│   │   └── student.py       # Student blueprint (/student/...)
│   ├── templates/           # Jinja2 templates, one subfolder per blueprint
│   └── static/
│       ├── css/style.css
│       └── js/main.js
├── config.py                 # BaseConfig / DevelopmentConfig / ProductionConfig / TestingConfig
├── run.py                    # dev entry point (flask run / python run.py)
├── seed.py                   # creates default test accounts + sample data
├── requirements.txt
├── .env.example               # copy to .env and edit
└── migrations/                 # created by `flask db init` (see setup below)
```

---

## 2. Setup & Run Instructions

### Step 1 — Create and activate a virtual environment
```bash
cd consultation_system
python3 -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows (PowerShell)
venv\Scripts\Activate.ps1
```

### Step 2 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 3 — Configure environment
```bash
cp .env.example .env
# Open .env and set SECRET_KEY to a long random value, e.g.:
python -c "import secrets; print(secrets.token_hex(32))"
```

### Step 4 — Initialize the database with Flask-Migrate
```bash
export FLASK_APP=run.py          # Windows: set FLASK_APP=run.py
flask db init                    # only once, creates migrations/
flask db migrate -m "Initial schema"
flask db upgrade                 # creates instance/dev.db
```
This is what lets the schema evolve later (e.g. adding a column) without
wiping existing data — run `flask db migrate -m "..."` then `flask db upgrade`
again for any future model change.

### Step 5 — Seed default accounts & sample data
```bash
python seed.py
```
This creates one account per role plus sample categories, availability,
and a demo consultation request. It's idempotent — safe to re-run.

### Step 6 — Run the development server
```bash
python run.py
# or: flask run
```
Visit **http://127.0.0.1:5000**

### Default login credentials (created by seed.py)

| Role | Username | Password |
|---|---|---|
| Super Admin | `admin` | `Admin@12345` |
| Medical Expert | `dr.santos` | `Expert@12345` |
| Medical Expert | `dr.reyes` | `Expert@12345` |
| Student | `jstudent` | `Student@12345` |

**Change these before any real deployment.** They exist only to make the
app explorable immediately after setup.

### Running in production
Set `FLASK_ENV=production` in `.env`, provide a real `SECRET_KEY`, and
serve with a WSGI server rather than the Flask dev server, e.g.:
```bash
pip install gunicorn
gunicorn "app:create_app('production')"
```

---

## 3. Database Schema

SQLite via SQLAlchemy ORM. Core tables:

### `users`
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| username, email | unique | login identifiers |
| password_hash | string | Werkzeug `generate_password_hash` (pbkdf2, salted) |
| full_name | string | |
| role | enum | `super_admin` \| `medical_expert` \| `student` — see §5 |
| student_id_number, department, specialization | nullable | role-specific optional fields kept on one table rather than three, since the app is small |
| is_active_account | bool | deactivation flag (Super Admin toggles this) |
| created_at, last_login_at | datetime | |

*(This column effectively serves as the "roles" concept requested in the
brief — see the docstring in `app/models/user.py` for why a Python enum
was chosen over a separate `roles` join table at this scale, and how to
promote it later if permissions need to become dynamic.)*

### `consultation_categories`
`id`, `name` (unique), `description`, `is_active` — managed by Super Admin.

### `consultations`
| Column | Notes |
|---|---|
| id | PK |
| student_id | FK → users.id (required) |
| expert_id | FK → users.id (nullable until accepted/assigned) |
| category_id | FK → consultation_categories.id |
| requested_date, requested_time | |
| status | enum: `pending`, `accepted`, `declined`, `completed`, `cancelled`, `reschedule_requested` |
| student_message | reason for the visit |
| expert_notes, diagnosis | filled in by the expert on completion |
| decline_reason | filled in if declined |
| created_at, updated_at, completed_at | |

### `availability_slots`
`id`, `expert_id` (FK), `day_of_week` (0–6, nullable — for recurring weekly
availability) **or** `specific_date` (nullable — for one-off slots),
`start_time`, `end_time`, `max_bookings`, `is_active`.

### `notifications`
`id`, `user_id` (FK), `message`, `link`, `is_read`, `created_at`.

### `audit_logs`
`id`, `actor_id` (FK, nullable), `action` (e.g. `USER_CREATED`,
`CONSULTATION_ACCEPTED`), `target_type`, `target_id`, `details`,
`ip_address`, `created_at`. Append-only — the app never updates or deletes
rows here.

### Relationships (ERD summary)
```
users (1) ───< consultations >─── (1) consultation_categories
  │  (as student)      (as expert, nullable)
  │
  ├──< availability_slots        (expert only)
  ├──< notifications
  └──< audit_logs (as actor)
```

---

## 4. Consultation Workflow

```
  student books  →  PENDING  ──accept──→  ACCEPTED  ──complete──→  COMPLETED
                        │                     │
                        ├──decline──→ DECLINED│
                        │                     │
                        ├──cancel (student)───┴──→ CANCELLED
                        │
                        └──reschedule (student)──→ back to PENDING
```
- A request starts **unassigned** (`expert_id = NULL`) and appears in every
  expert's "Open Requests" pool, OR the student can pick a preferred expert
  up front (both are supported — see `student/book.html`).
- Any medical expert may **accept** an unassigned pending request; only the
  assigned expert may accept/decline/complete their own.
- Only the owning **student** may cancel or reschedule their own request,
  and only while it is `pending` or `accepted`.
- Rescheduling sends the request back to `pending` so the expert re-confirms.

---

## 5. How RBAC Is Enforced

**Decorator-based, applied per-view** (not a single global middleware).
See `app/decorators.py` for the full rationale; summary:

1. **`@login_required`** (Flask-Login) — must be authenticated at all.
2. **`@roles_required(Role.SUPER_ADMIN)`** (custom) — must hold a specific
   role. Every view in `admin.py`, `expert.py`, and `student.py` stacks
   both decorators, e.g.:
   ```python
   @admin_bp.route("/users")
   @login_required
   @active_account_required
   @roles_required(Role.SUPER_ADMIN)
   def manage_users():
       ...
   ```
3. **`@active_account_required`** (custom) — defense-in-depth: if a Super
   Admin deactivates a user mid-session, this catches it on the very next
   request and force-logs them out, rather than relying only on the login
   check (which only runs at login time).
4. **Object-level authorization** (separate from role checks) — a role
   check alone proves "this user is *a* medical expert / student", not
   "this record belongs to them". Every route that operates on a specific
   `Consultation` or `AvailabilitySlot` re-checks ownership explicitly,
   e.g. `app/routes/student.py`:
   ```python
   def _get_own_consultation_or_403(consultation_id):
       consultation = db.session.get(Consultation, consultation_id)
       if consultation is None:
           abort(404)
       if consultation.student_id != current_user.id:
           abort(403)
       return consultation
   ```
   The equivalent exists in `expert.py` (`_get_owned_consultation_or_403`)
   and in `main.py` for notifications.
5. **No open privilege escalation path** — public self-registration
   (`auth.register`) can only ever construct a `User` with
   `role=Role.STUDENT`; Medical Expert and Super Admin accounts can only be
   created by an existing Super Admin via `admin.create_user`.

Blueprints are also mounted under role-named prefixes (`/admin`, `/expert`,
`/student`) purely for URL readability — the prefixes are **not** the
enforcement mechanism; the decorators are.

---

## 6. Security & Hardening Notes

- **Password hashing**: Werkzeug's `generate_password_hash`
  (pbkdf2:sha256, salted) via `User.set_password()` /
  `User.check_password()`.
- **CSRF protection**: Flask-WTF's `CSRFProtect` is initialized globally in
  `app/extensions.py`; every form includes `{{ form.hidden_tag() }}`.
- **Session cookies**: `HttpOnly`, `SameSite=Lax`, and `Secure` in
  production (`config.py`).
- **Rate limiting**: `Flask-Limiter` is applied to the most sensitive
  endpoints — login (10/min), registration (5/min), and booking (20/hour)
  — using in-memory storage by default. **For a real multi-worker
  deployment, point `RATELIMIT_STORAGE_URI` at Redis** (e.g.
  `redis://localhost:6379`) in `.env`, since in-memory storage doesn't
  share state across worker processes.
- **Login enumeration**: the login view returns an identical error message
  whether the username doesn't exist or the password is wrong.
- **Open-redirect guard**: the post-login `next` parameter is only honored
  if it starts with `/`.
- **Audit log**: append-only; login, logout, account creation/
  deactivation, category changes, and every consultation status change are
  recorded with actor, action, target, and IP address.

### Not implemented (flagged, not silently skipped)
- Email verification / password-reset flows (would need an email/SMTP
  integration — out of scope for this deliverable but the `User` model
  and routes are structured so it's a straightforward addition).
- Distributed rate-limit storage (documented above — swap in Redis for
  production).
- HTTPS termination (handled by the reverse proxy/hosting layer, not the
  app itself).

---

## 7. Running Tests / Shell Access

```bash
flask --app run.py shell
```
The shell context is pre-populated (see `_register_cli_and_context` in
`app/__init__.py`) with `db`, `User`, `Role`, `ConsultationCategory`,
`Consultation`, `AvailabilitySlot`, `Notification`, `AuditLog`.

To reset the database from scratch during development:
```bash
rm instance/dev.db
flask db upgrade
python seed.py
```
