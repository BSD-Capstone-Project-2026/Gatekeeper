import secrets
from datetime import datetime, timedelta

import qrcode
import qrcode.image.svg
from flask import Blueprint, Response, abort, redirect, render_template, request, session, url_for

from models import db, AccessLog, Door, User, VisitorPass
from routes.decorators import role_required
from routes.web import login_required

visitors_bp = Blueprint("visitors", __name__)

STAFF = ('concierge', 'management')
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
MAX_PASS_DAYS = 7


def current_user():
    return User.query.get(session['user_id'])


def new_pass_code():
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
        if not VisitorPass.query.filter_by(code=code).first():
            return code


def parse_local(value, offset_minutes):
    return datetime.strptime(value, "%Y-%m-%dT%H:%M") + timedelta(minutes=offset_minutes)


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
    visitor_pass = VisitorPass(code=new_pass_code(), resident_id=session['user_id'], visitor_name=name,
                               valid_from=valid_from, valid_until=valid_until)
    db.session.add(visitor_pass)
    db.session.commit()
    return redirect(url_for("visitors.passes", created=visitor_pass.id))


def pass_error(message):
    my_passes = VisitorPass.query.filter_by(resident_id=session['user_id']).order_by(VisitorPass.created_at.desc()).all()
    return render_template("visitors/passes.html", passes=my_passes, max_days=MAX_PASS_DAYS, error=message), 400


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
        record_visitor_entry(visitor_pass.resident, visitor_pass.visitor_name, reason is None, reason or "")
        unit = visitor_pass.resident.unit_number or "—"
        result = {"ok": reason is None, "title": f"Admit {visitor_pass.visitor_name}" if reason is None else reason,
                  "detail": f"Visitor of {visitor_pass.resident.first_name} {visitor_pass.resident.last_name} · Unit {unit}",
                  "until": visitor_pass.valid_until}
    return render_template("visitors/pass_check.html", recent=recent_visitor_entries(), result=result), 200 if result["ok"] else 422
