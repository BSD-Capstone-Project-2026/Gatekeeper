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

---

## My Role

As **Back-End Developer**, I worked on the server-side of Gatekeeper — the Flask application, the RESTful API, role-based authentication and session handling, the SQLite data layer, and the audit-logging system that records access events for traceability.

---

## Project Status

Functional prototype completed as a capstone project. Currently runs on a local network; designed to be deployable to the cloud with a production WSGI server and database.
