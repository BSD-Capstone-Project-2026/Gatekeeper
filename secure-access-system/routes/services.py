from datetime import datetime, timedelta

from flask import Blueprint, abort, redirect, render_template, request, session, url_for

from models import db, Announcement, AnnouncementRead, MaintenanceRequest, User
from routes.decorators import role_required
from routes.web import login_required
from routes.visitors import STAFF, current_user
from routes.desk import clean
from utils.notifications import notify

services_bp = Blueprint("services", __name__, url_prefix="/services")

MAINTENANCE_CATEGORIES = ("Plumbing", "Electrical", "Heating and cooling", "Appliance", "Other")
MAINTENANCE_STATUSES = ("Open", "In Progress", "Completed")


def resident_floors():
    return [f for (f,) in db.session.query(User.floor).filter(User.role == 'resident', User.is_active == True,
                                                              User.floor.isnot(None)).distinct().order_by(User.floor)]


def visible_announcements(user):
    current = [a for a in Announcement.query.order_by(Announcement.created_at.desc()) if a.is_current]
    return current if user.role in STAFF else [a for a in current if a.reaches(user)]


@services_bp.route("/announcements")
@login_required
@role_required('resident', *STAFF)
def announcements(error=None, status=200):
    user = current_user()
    items = Announcement.query.order_by(Announcement.created_at.desc()).all() if user.role == 'management' else visible_announcements(user)
    return render_template("services/announcements.html", items=items, floors=resident_floors(), user=user, sheet_error=error), status


@services_bp.route("/announcements", methods=["POST"])
@login_required
@role_required('management')
def publish_announcement():
    title = clean(request.form.get("title"), 100)
    body = (request.form.get("body") or "").strip()[:1000]
    chosen = request.form.getlist("floors")
    floors = [] if "all" in chosen else sorted({int(f) for f in chosen if f.isdigit() and int(f) in resident_floors()})
    try:
        expires = request.form.get("expires")
        expires_at = datetime.strptime(expires, "%Y-%m-%d") + timedelta(days=1, minutes=request.form.get("tz_offset", type=int) or 0) if expires else None
    except ValueError:
        expires_at = datetime.min
    if not title or not body or not chosen or (expires_at and expires_at <= datetime.utcnow()):
        return announcements(error="Add a title and message, choose the floors, and pick an expiry date from today onward.", status=400)
    db.session.add(Announcement(title=title, body=body, floors=",".join(map(str, floors)), expires_at=expires_at, created_by=session['user_id']))
    db.session.commit()
    return redirect(url_for("services.announcements"))


@services_bp.route("/announcements/<int:announcement_id>")
@login_required
@role_required('resident', *STAFF)
def open_announcement(announcement_id):
    item = Announcement.query.get_or_404(announcement_id)
    user = current_user()
    if user.role == 'resident':
        if not (item.is_current and item.reaches(user)):
            abort(404)
        if not item.read_by(user.id):
            db.session.add(AnnouncementRead(announcement_id=item.id, user_id=user.id))
            db.session.commit()
    return render_template("services/announcement.html", item=item)


@services_bp.route("/maintenance")
@login_required
@role_required('resident', *STAFF)
def maintenance(error=None, status=200):
    if session['user_role'] in STAFF:
        requests = MaintenanceRequest.query.order_by(MaintenanceRequest.created_at.desc()).all()
        board = {s: [r for r in requests if r.status == s] for s in MAINTENANCE_STATUSES}
        return render_template("services/maintenance_board.html", board=board, statuses=MAINTENANCE_STATUSES)
    mine = MaintenanceRequest.query.filter_by(resident_id=session['user_id']).order_by(MaintenanceRequest.created_at.desc()).all()
    return render_template("services/maintenance.html", requests=mine, categories=MAINTENANCE_CATEGORIES, sheet_error=error), status


@services_bp.route("/maintenance", methods=["POST"])
@login_required
@role_required('resident')
def submit_maintenance():
    category = request.form.get("category")
    description = (request.form.get("description") or "").strip()[:500]
    if category not in MAINTENANCE_CATEGORIES or not description:
        return maintenance(error="Choose a category and describe the problem.", status=400)
    resident = current_user()
    db.session.add(MaintenanceRequest(resident_id=resident.id, unit_number=resident.unit_number, category=category,
                                      description=description, entry_allowed=request.form.get("entry") == "on"))
    db.session.commit()
    return redirect(url_for("services.maintenance"))


@services_bp.route("/maintenance/<int:request_id>")
@login_required
@role_required('resident', *STAFF)
def maintenance_detail(request_id):
    item = MaintenanceRequest.query.get_or_404(request_id)
    if session['user_role'] == 'resident' and item.resident_id != session['user_id']:
        abort(403)
    return render_template("services/maintenance_detail.html", item=item, statuses=MAINTENANCE_STATUSES)


@services_bp.route("/maintenance/<int:request_id>/status", methods=["POST"])
@login_required
@role_required(*STAFF)
def update_maintenance(request_id):
    item = MaintenanceRequest.query.get_or_404(request_id)
    new_status = request.form.get("status")
    if new_status in MAINTENANCE_STATUSES and new_status != item.status:
        item.status = new_status
        item.updated_at = datetime.utcnow()
        item.updated_by = session['user_id']
        db.session.commit()
        notify(item.resident, f"Maintenance request {new_status.lower()}",
               f"Your {item.category.lower()} request \"{item.description[:60]}\" is now {new_status}.")
    return redirect(url_for("services.maintenance"))
