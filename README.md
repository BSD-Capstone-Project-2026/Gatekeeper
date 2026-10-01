# Gatekeeper

A secure, local-first residential access management system that replaces traditional physical keys and fobs with encrypted virtual keys stored on residents' devices. Access is granted only when strict security conditions are met — proximity validation and connection to a secured local network — with no reliance on external cloud services.

> Capstone project — Bachelor of Software Development, Seneca Polytechnic.

---

## Team

| Name | GitHub | Seneca Email | Role |
|------|--------|--------------|------|
| Navish | [Navish7](https://github.com/Navish7) | navish@myseneca.ca | Back-End Developer |
| Gurjeet Singh Sodhi | gssodhi | gurjeet@myseneca.ca | Front-End Developer |
| Minhaz Abedin | minhazabedin53 | minhaz@myseneca.ca | Product Manager |
| Rohith Haridas | rharidas2 | rohith@myseneca.ca | Database Specialist |

---

## Overview

Gatekeeper modernizes building entry by issuing **encrypted virtual keys** instead of physical fobs. The system runs entirely within a building's internal network and only unlocks a door when the resident is both connected to the correct Wi-Fi and physically present near the building. It supports role-based access for residents, concierge staff, and management, and logs every access event for full traceability.

---

## Key Features

- Encrypted virtual key generation
- Proximity-based access validation (Wi-Fi + location presence)
- Role-based access control — Resident, Concierge, Management
- Concierge and management dashboard for adding residents and issuing keys
- Emergency override with full audit logging
- Centralized access logs for traceability
- Autonomous alerts for suspicious access attempts

---

## Tech Stack

**Back-End**
- Python, Flask
- Flask-SQLAlchemy, Flask-JWT-Extended, Flask-Login
- bcrypt (password hashing), APScheduler (scheduled tasks)
- RESTful API

**Front-End**
- HTML5 / Jinja2 templates
- CSS / Bootstrap 5, Bootstrap Icons
- JavaScript (ES6), Chart.js

**Database**
- SQLite (relational), with encrypted storage for sensitive data
- Tooling: DB Browser for SQLite, SQLite CLI

**Security & Authentication**
- JWT tokens and session cookies
- Role-based access control
- Account lockout on repeated failed attempts
- bcrypt password hashing

**Reporting**
- Pandas + openpyxl (Excel exports)

**Dev & Testing**
- pip, VS Code, Postman, pytest
- GitHub for version control, GitHub Projects for backlog management

**Deployment**
- Runs locally; deployable to the cloud with a WSGI server and a production-grade database.

---

## Role Permissions

| Route | Management | Concierge | Resident | Guest / Cleaner |
|-------|:---:|:---:|:---:|:---:|
| `/dashboard` (stats, chart, recent users) | ✅ | ✅ | Health only | Health only |
| `/api/dashboard/stats`, `/api/dashboard/recent-users` | ✅ | ✅ | ❌ | ❌ |
| `/concierge`, `/api/recent-logs` (live door activity) | ✅ | ✅ | ❌ | ❌ |
| `/door-controls`, `/doors/<id>/lock`, `/doors/<id>/unlock` (POST) | ✅ | ✅ | ❌ | ❌ |
| `/users` | All users | Residents and guests | ❌ | ❌ |
| `/create-user` | Concierge, Resident, Guest, Cleaner | Resident, Guest | ❌ | ❌ |
| `/users/toggle/<id>`, `/unlock-user/<id>` (POST) | ✅ | ❌ | ❌ | ❌ |
| `/users/<id>/zones`, `/zones/*`, `/doors/*` | ✅ | ❌ | ❌ | ❌ |
| `/incident-list`, `/incidents/<id>/acknowledge` (POST) | ✅ | ✅ | ❌ | ❌ |
| `/incidents`, `/incidents/<id>`, `/audit` | ✅ | ❌ | ❌ | ❌ |
| `/emergency-override`, `/logs/verify` | ✅ | ❌ | ❌ | ❌ |
| `/visitors/passes`, `/visitors/lobby`, `/visitors/parking` | Check and admit passes, approve parking | Check and admit passes, approve parking | Own passes, requests and permits; lobby door and elevator while a visitor is checked in | ❌ |
| `/visitors/watchlist` | View and edit | View | ❌ | ❌ |
| `/lobby` (lobby kiosk screen) | Public | Public | Public | Public |
| `/desk/packages` | ✅ | ✅ | Waiting packages on Home | ❌ |
| `/simulate` | ❌ | ❌ | ✅ | ✅ |
| `/profile`, `/profile/incidents`, `/reset-password` | ✅ | ✅ | ✅ | ✅ |

**Door rights:** main entrance for every role; common doors for management, concierge and cleaners; unit doors only for the resident of that unit. Zone rules apply on top. Guest access ends on the date set at creation. Every unlock must come from an address in `BUILDING_NETWORKS` and carry a proximity token from the door's beacon (`GET /api/access/beacon/<door_id>`, valid for 30 seconds).

Denied requests return `403` and are recorded in the audit log as `access_denied`.

---

## Getting Started

```bash
# clone the repository
git clone https://github.com/BSD-Capstone-Project-2026/Gatekeeper.git
cd Gatekeeper/secure-access-system

# create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate

# install dependencies
pip install -r requirements-dev.txt

# run the tests
pytest

# run the app
python app.py
```

Then open `http://localhost:5000` in your browser. The database is created and seeded in `instance/` on first run.

### Demo Data

Seed a realistic building for class demos (development only, safe to run more than once):

```bash
python scripts/seed_demo.py
```

It adds floors 2–6 with units A and B, one resident per unit, common doors (gym, amenities, rooftop) with zones, a week of access history, an open incident and a resident notification. Every demo account uses the password in `DEMO_SEED_PASSWORD` (default `Demo@2026`).

| Role | Email |
|------|-------|
| Management | `maya.chen@gatekeeper.demo`, `daniel.okafor@gatekeeper.demo` |
| Concierge | `priya.sharma@gatekeeper.demo`, `lucas.martin@gatekeeper.demo` |
| Resident | `aisha.khan@gatekeeper.demo` (unit 2A) … `jamal.brooks@gatekeeper.demo` (unit 6B) |
| Guest | `oliver.grant@gatekeeper.demo` (access for 7 days) |
| Cleaner | `rosa.diaz@gatekeeper.demo` |

### Backup and Restore

The app backs up the database daily to `secure-access-system/backups/` (newest 10 kept) and archives access logs older than 90 days.

```bash
python scripts/backup.py                                # manual backup
python scripts/restore.py                               # list available backups
python scripts/restore.py backups/secure_access_<timestamp>.db   # restore (stop the app first)
```

---

## My Role

As **Back-End Developer**, I worked on the server-side of Gatekeeper — the Flask application, the RESTful API, role-based authentication and session handling, the SQLite data layer, and the audit-logging system that records access events for traceability.

---

## Project Status

Functional prototype completed as a capstone project. Currently runs on a local network; designed to be deployable to the cloud with a production WSGI server and database.
