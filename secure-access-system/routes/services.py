from datetime import datetime, timedelta

from flask import Blueprint, abort, redirect, render_template, request, session, url_for

from models import db, Amenity, AmenityBooking, Announcement, AnnouncementRead, MaintenanceRequest, User
from routes.decorators import role_required
from routes.web import login_required
from routes.visitors import STAFF, current_user
from routes.desk import clean
from utils.notifications import notify

services_bp = Blueprint("services", __name__, url_prefix="/services")

MAINTENANCE_CATEGORIES = ("Plumbing", "Electrical", "Heating and cooling", "Appliance", "Other")
MAINTENANCE_STATUSES = ("Open", "In Progress", "Completed")
BOOKING_DAYS = 7


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


def bookable_amenities(user):
    amenities = Amenity.query.order_by(Amenity.name).all()
    if user.role != 'resident':
        return amenities
    zone_ids = {z.id for z in user.zones}
    return [a for a in amenities if not (a.door and a.door.zone_id) or a.door.zone_id in zone_ids]


def live_bookings(query):
    return query.filter(AmenityBooking.cancelled_at.is_(None))


@services_bp.route("/amenities")
@login_required
@role_required('resident', *STAFF)
def amenities(error=None, status=200):
    user = current_user()
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if user.role in STAFF:
        todays = live_bookings(AmenityBooking.query).filter(AmenityBooking.starts_at >= today, AmenityBooking.starts_at < today + timedelta(days=1))
        return render_template("services/amenities_staff.html", bookings=todays.order_by(AmenityBooking.starts_at).all(),
                               amenities=Amenity.query.order_by(Amenity.name).all())
    choices = bookable_amenities(user)
    amenity = next((a for a in choices if a.id == request.values.get("amenity", type=int)), choices[0] if choices else None)
    days = [today + timedelta(days=i) for i in range(BOOKING_DAYS)]
    try:
        day = datetime.strptime(request.values.get("day", ""), "%Y-%m-%d")
    except ValueError:
        day = today
    day = day if day in days else today
    slots = []
    if amenity:
        starts = [day + timedelta(hours=h) for h in range(amenity.opens_hour, amenity.closes_hour)]
        taken = live_bookings(AmenityBooking.query).filter(AmenityBooking.amenity_id == amenity.id, AmenityBooking.starts_at.in_(starts)).all()
        slots = [{"start": start, "booked": sum(b.starts_at == start for b in taken), "mine": any(b.starts_at == start and b.user_id == user.id for b in taken),
                  "past": start + timedelta(hours=1) <= now} for start in starts]
    mine = live_bookings(AmenityBooking.query).filter(AmenityBooking.user_id == user.id, AmenityBooking.starts_at > now - timedelta(hours=1))
    return render_template("services/amenities.html", choices=choices, amenity=amenity, days=days, day=day, slots=slots, now=now,
                           bookings=mine.order_by(AmenityBooking.starts_at).all(), error=error), status


@services_bp.route("/amenities/book", methods=["POST"])
@login_required
@role_required('resident')
def book_amenity():
    user = current_user()
    amenity = next((a for a in bookable_amenities(user) if a.id == request.form.get("amenity", type=int)), None)
    try:
        start = datetime.strptime(request.form.get("start", ""), "%Y-%m-%dT%H:%M")
    except ValueError:
        start = None
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if not amenity or not start or start.minute or not amenity.opens_hour <= start.hour < amenity.closes_hour             or start + timedelta(hours=1) <= now or start >= today + timedelta(days=BOOKING_DAYS):
        return amenities(error="Choose an open slot within the next week.", status=400)
    if live_bookings(AmenityBooking.query).filter_by(amenity_id=amenity.id, starts_at=start).count() >= amenity.capacity:
        return amenities(error=f"This {amenity.name.lower()} slot is full.", status=400)
    if live_bookings(AmenityBooking.query).filter_by(user_id=user.id, starts_at=start).first():
        return amenities(error="You already have a booking at this time.", status=400)
    db.session.add(AmenityBooking(amenity_id=amenity.id, user_id=user.id, starts_at=start))
    db.session.commit()
    return redirect(url_for("services.amenities", amenity=amenity.id, day=start.strftime("%Y-%m-%d")))


@services_bp.route("/amenities/bookings/<int:booking_id>/cancel", methods=["POST"])
@login_required
@role_required('resident')
def cancel_booking(booking_id):
    booking = AmenityBooking.query.get_or_404(booking_id)
    if booking.user_id != session['user_id']:
        abort(404)
    if not booking.cancelled_at and booking.starts_at > datetime.now():
        booking.cancelled_at = datetime.utcnow()
        db.session.commit()
    return redirect(url_for("services.amenities", amenity=booking.amenity_id))
