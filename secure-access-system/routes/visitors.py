import secrets
from datetime import datetime, timedelta

import qrcode
import qrcode.image.svg
from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for

from models import db, AccessLog, AuditLog, Door, EntryRequest, ParkingPermit, User, VisitorPass, WatchlistEntry
from routes.decorators import role_required
from routes.web import login_required

visitors_bp = Blueprint("visitors", __name__)

STAFF = ('concierge', 'management')
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
MAX_PASS_DAYS = 7
LOBBY_REQUEST_SECONDS = 120
PERMIT_HOURS = (2, 4, 24)
MAX_ACTIVE_PERMITS = 2
BLOCKED_MESSAGE = "This visitor cannot be admitted"


def current_user():
    return User.query.get(session['user_id'])


def new_pass_code():
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
        if not VisitorPass.query.filter_by(code=code).first():
            return code


def parse_local(value, offset_minutes):
    return datetime.strptime(value, "%Y-%m-%dT%H:%M") + timedelta(minutes=offset_minutes)


def name_key(name):
    return " ".join((name or "").casefold().split())


def block_if_watchlisted(name, unit, user_id):
    entry = WatchlistEntry.query.filter_by(name_key=name_key(name)).first()
    if entry:
        db.session.add(AuditLog(user_id=user_id, performed_by=user_id, action="watchlist_blocked",
                                details=f"{name} · unit {unit or '—'}", reason=entry.reason))
        db.session.commit()
    return entry is not None


def record_visitor_entry(resident, visitor_name, success, reason=""):
    door = Door.query.filter_by(door_type='main').first()
    db.session.add(AccessLog(user_id=resident.id, door_id=door.id if door else None, success=success,
                             failure_reason=reason, visitor_name=visitor_name,
                             ip_address=request.remote_addr, user_agent=request.headers.get('User-Agent')))
    db.session.commit()


def recent_visitor_entries(limit=8):
    return db.session.query(AccessLog, User).join(User, AccessLog.user_id == User.id).filter(
        AccessLog.visitor_name.isnot(None)).order_by(AccessLog.timestamp.desc()).limit(limit).all()


@visitors_bp.route("/visitors")
@login_required
@role_required('resident', *STAFF)
def index():
    return redirect(url_for("visitors.passes"))


@visitors_bp.route("/visitors/passes")
@login_required
@role_required('resident', *STAFF)
def passes():
    if session['user_role'] in STAFF:
        return render_template("visitors/pass_check.html", recent=recent_visitor_entries(), result=None)
    my_passes = VisitorPass.query.filter_by(resident_id=session['user_id']).order_by(VisitorPass.created_at.desc()).all()
    return render_template("visitors/passes.html", passes=my_passes, max_days=MAX_PASS_DAYS)


@visitors_bp.route("/visitors/passes", methods=["POST"])
@login_required
@role_required('resident')
def create_pass():
    name = " ".join((request.form.get("visitor_name") or "").split())[:80]
    offset = request.form.get("tz_offset", type=int) or 0
    try:
        valid_from = parse_local(request.form.get("valid_from", ""), offset)
        valid_until = parse_local(request.form.get("valid_until", ""), offset)
    except ValueError:
        return pass_error("Choose a start and end time for the pass.")
    if not name:
        return pass_error("Enter your visitor's name.")
    if valid_until <= valid_from or valid_until <= datetime.utcnow():
        return pass_error("The pass must end after it starts and in the future.")
    if valid_until - valid_from > timedelta(days=MAX_PASS_DAYS):
        return pass_error(f"A pass can be valid for at most {MAX_PASS_DAYS} days.")
    if block_if_watchlisted(name, current_user().unit_number, session['user_id']):
        return pass_error(BLOCKED_MESSAGE)
    visitor_pass = VisitorPass(code=new_pass_code(), resident_id=session['user_id'], visitor_name=name,
                               valid_from=valid_from, valid_until=valid_until)
    db.session.add(visitor_pass)
    db.session.commit()
    return redirect(url_for("visitors.passes", created=visitor_pass.id))


def pass_error(message):
    my_passes = VisitorPass.query.filter_by(resident_id=session['user_id']).order_by(VisitorPass.created_at.desc()).all()
    return render_template("visitors/passes.html", passes=my_passes, max_days=MAX_PASS_DAYS, sheet_error=message), 400


def own_pass(pass_id):
    visitor_pass = VisitorPass.query.get_or_404(pass_id)
    if visitor_pass.resident_id != session['user_id']:
        abort(404)
    return visitor_pass


@visitors_bp.route("/visitors/passes/<int:pass_id>/revoke", methods=["POST"])
@login_required
@role_required('resident')
def revoke_pass(pass_id):
    visitor_pass = own_pass(pass_id)
    visitor_pass.revoked_at = visitor_pass.revoked_at or datetime.utcnow()
    db.session.commit()
    return redirect(url_for("visitors.passes"))


@visitors_bp.route("/visitors/passes/<int:pass_id>/qr.svg")
@login_required
@role_required('resident')
def pass_qr(pass_id):
    image = qrcode.make(own_pass(pass_id).code, image_factory=qrcode.image.svg.SvgPathImage, box_size=12, border=2)
    return Response(image.to_string(encoding="unicode"), mimetype="image/svg+xml")


@visitors_bp.route("/visitors/passes/check", methods=["POST"])
@login_required
@role_required(*STAFF)
def check_pass():
    code = (request.form.get("code") or "").strip().upper()
    visitor_pass = VisitorPass.query.filter_by(code=code).first()
    if not visitor_pass:
        result = {"ok": False, "title": "Pass not found", "detail": f"No pass matches code {code or '—'}."}
    else:
        reason = {"Expired": "Pass expired", "Revoked": "Pass revoked", "Scheduled": "Pass not yet valid"}.get(visitor_pass.status)
        if not reason and block_if_watchlisted(visitor_pass.visitor_name, visitor_pass.resident.unit_number, visitor_pass.resident_id):
            reason = BLOCKED_MESSAGE
        record_visitor_entry(visitor_pass.resident, visitor_pass.visitor_name, reason is None, reason or "")
        unit = visitor_pass.resident.unit_number or "—"
        result = {"ok": reason is None, "title": f"Admit {visitor_pass.visitor_name}" if reason is None else reason,
                  "detail": f"Visitor of {visitor_pass.resident.first_name} {visitor_pass.resident.last_name} · Unit {unit}",
                  "until": visitor_pass.valid_until}
    return render_template("visitors/pass_check.html", recent=recent_visitor_entries(), result=result), 200 if result["ok"] else 422


def resident_units():
    return [u for (u,) in db.session.query(User.unit_number).filter(User.role == 'resident', User.is_active == True,
                                                                     User.unit_number.isnot(None)).distinct().order_by(User.unit_number)]


def pending_for_unit(unit):
    return EntryRequest.query.filter(EntryRequest.unit_number == unit, EntryRequest.status == 'pending',
                                     EntryRequest.expires_at > datetime.utcnow()).order_by(EntryRequest.created_at).all()


@visitors_bp.app_context_processor
def inject_lobby_badge():
    if session.get('user_role') != 'resident':
        return {"lobby_badge": 0}
    user = User.query.get(session['user_id'])
    return {"lobby_badge": len(pending_for_unit(user.unit_number)) if user and user.unit_number else 0}


@visitors_bp.route("/lobby")
def lobby_screen():
    return render_template("visitors/lobby_screen.html", units=resident_units())


@visitors_bp.route("/lobby/requests", methods=["POST"])
def lobby_request():
    name = " ".join((request.form.get("visitor_name") or "").split())[:80]
    unit = request.form.get("unit")
    if not name or unit not in resident_units():
        return render_template("visitors/lobby_screen.html", units=resident_units(), error="Enter your name and choose a unit."), 400
    if block_if_watchlisted(name, unit, None):
        return render_template("visitors/lobby_screen.html", units=resident_units(), error=f"{BLOCKED_MESSAGE}. Please speak with the front desk."), 403
    entry = EntryRequest(token=secrets.token_urlsafe(16), visitor_name=name, unit_number=unit,
                         expires_at=datetime.utcnow() + timedelta(seconds=LOBBY_REQUEST_SECONDS))
    db.session.add(entry)
    db.session.commit()
    return redirect(url_for("visitors.lobby_wait", token=entry.token))


@visitors_bp.route("/lobby/requests/<token>")
def lobby_wait(token):
    return render_template("visitors/lobby_screen.html", entry=EntryRequest.query.filter_by(token=token).first_or_404())


@visitors_bp.route("/lobby/requests/<token>/status")
def lobby_status(token):
    entry = EntryRequest.query.filter_by(token=token).first_or_404()
    return jsonify({"status": entry.current_status, "seconds_left": entry.seconds_left})


@visitors_bp.route("/visitors/lobby")
@login_required
@role_required('resident', *STAFF)
def lobby():
    if session['user_role'] in STAFF:
        pending = EntryRequest.query.filter(EntryRequest.status == 'pending', EntryRequest.expires_at > datetime.utcnow()).order_by(EntryRequest.created_at).all()
        history = EntryRequest.query.order_by(EntryRequest.created_at.desc()).limit(10).all()
    else:
        unit = current_user().unit_number
        pending = pending_for_unit(unit)
        history = EntryRequest.query.filter_by(unit_number=unit).order_by(EntryRequest.created_at.desc()).limit(10).all()
    return render_template("visitors/lobby.html", pending=pending, history=history)


@visitors_bp.route("/visitors/lobby/feed")
@login_required
@role_required('resident', *STAFF)
def lobby_feed():
    query = EntryRequest.query.filter(EntryRequest.status == 'pending', EntryRequest.expires_at > datetime.utcnow())
    if session['user_role'] == 'resident':
        query = query.filter_by(unit_number=current_user().unit_number)
    return jsonify({"pending": [r.id for r in query.all()]})


@visitors_bp.route("/visitors/lobby/<int:request_id>/<any(approve, deny):decision>", methods=["POST"])
@login_required
@role_required('resident')
def decide_lobby(request_id, decision):
    resident = current_user()
    entry = EntryRequest.query.get_or_404(request_id)
    if entry.unit_number != resident.unit_number:
        abort(404)
    if entry.current_status == 'pending':
        entry.status = 'approved' if decision == 'approve' else 'denied'
        entry.decided_at = datetime.utcnow()
        entry.decided_by = resident.id
        db.session.commit()
        if decision == 'approve':
            record_visitor_entry(resident, entry.visitor_name, True)
    return redirect(url_for("visitors.lobby"))


def plate_key(plate):
    return "".join(ch for ch in (plate or "").upper() if ch.isalnum())


def active_permits(query):
    return query.filter(ParkingPermit.ends_at > datetime.utcnow())


@visitors_bp.route("/visitors/parking")
@login_required
@role_required('resident', *STAFF)
def parking(error=None, status=200):
    if session['user_role'] in STAFF:
        search = request.args.get("plate", "")
        matches = ParkingPermit.query.filter_by(plate_key=plate_key(search)).order_by(ParkingPermit.ends_at.desc()).all() if search else []
        current = active_permits(ParkingPermit.query).order_by(ParkingPermit.ends_at).all()
        return render_template("visitors/parking_search.html", search=search, matches=matches, current=current)
    permits = ParkingPermit.query.filter_by(resident_id=session['user_id']).order_by(ParkingPermit.ends_at.desc()).limit(10).all()
    return render_template("visitors/parking.html", permits=permits, hours=PERMIT_HOURS, limit=MAX_ACTIVE_PERMITS, error=error), status


@visitors_bp.route("/visitors/parking", methods=["POST"])
@login_required
@role_required('resident')
def create_permit():
    plate = " ".join((request.form.get("plate") or "").upper().split())[:12]
    hours = request.form.get("hours", type=int)
    if not plate_key(plate) or hours not in PERMIT_HOURS:
        return parking(error="Enter a licence plate and choose how long the visitor will stay.", status=400)
    if active_permits(ParkingPermit.query.filter_by(resident_id=session['user_id'])).count() >= MAX_ACTIVE_PERMITS:
        return parking(error=f"Limit of {MAX_ACTIVE_PERMITS} active permits reached", status=400)
    now = datetime.utcnow()
    db.session.add(ParkingPermit(resident_id=session['user_id'], plate=plate, plate_key=plate_key(plate),
                                 starts_at=now, ends_at=now + timedelta(hours=hours)))
    db.session.commit()
    return redirect(url_for("visitors.parking"))


@visitors_bp.route("/visitors/watchlist")
@login_required
@role_required(*STAFF)
def watchlist(error=None, status=200):
    search = request.args.get("q", "")
    query = WatchlistEntry.query
    if search:
        query = query.filter(WatchlistEntry.name_key.contains(name_key(search)))
    return render_template("visitors/watchlist.html", entries=query.order_by(WatchlistEntry.created_at.desc()).all(),
                           search=search, sheet_error=error), status


@visitors_bp.route("/visitors/watchlist", methods=["POST"])
@login_required
@role_required('management')
def add_to_watchlist():
    name = " ".join((request.form.get("name") or "").split())[:80]
    reason = " ".join((request.form.get("reason") or "").split())[:200]
    if not name or not reason:
        return watchlist(error="Enter the person's name and the reason.", status=400)
    if WatchlistEntry.query.filter_by(name_key=name_key(name)).first():
        return watchlist(error=f"{name} is already on the watchlist.", status=400)
    db.session.add(WatchlistEntry(name=name, name_key=name_key(name), reason=reason, added_by=session['user_id']))
    db.session.add(AuditLog(user_id=session['user_id'], performed_by=session['user_id'], action="watchlist_added",
                            details=name, reason=reason))
    db.session.commit()
    return redirect(url_for("visitors.watchlist"))


@visitors_bp.route("/visitors/watchlist/<int:entry_id>/remove", methods=["POST"])
@login_required
@role_required('management')
def remove_from_watchlist(entry_id):
    entry = WatchlistEntry.query.get_or_404(entry_id)
    db.session.add(AuditLog(user_id=session['user_id'], performed_by=session['user_id'], action="watchlist_removed",
                            details=entry.name, reason=entry.reason))
    db.session.delete(entry)
    db.session.commit()
    return redirect(url_for("visitors.watchlist"))
