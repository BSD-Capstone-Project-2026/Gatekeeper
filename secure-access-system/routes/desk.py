from datetime import datetime

from flask import Blueprint, redirect, render_template, request, session, url_for

from models import db, Package, User
from routes.decorators import role_required
from routes.web import login_required
from routes.visitors import STAFF, resident_units
from utils.notifications import notify

desk_bp = Blueprint("desk", __name__, url_prefix="/desk")

CARRIERS = ("Amazon", "Canada Post", "UPS", "FedEx", "Purolator", "Other")


def clean(value, limit):
    return " ".join((value or "").split())[:limit]


@desk_bp.route("/packages")
@login_required
@role_required(*STAFF)
def packages(error=None, status=200):
    search = clean(request.args.get("unit"), 10).upper()
    waiting = Package.query.filter(Package.picked_up_at.is_(None)).order_by(Package.unit_number, Package.logged_at).all()
    history = Package.query.filter(Package.picked_up_at.isnot(None))
    if search:
        history = history.filter(Package.unit_number == search)
    groups = {}
    for package in waiting:
        groups.setdefault(package.unit_number, []).append(package)
    return render_template("desk/packages.html", groups=groups, history=history.order_by(Package.picked_up_at.desc()).limit(20).all(),
                           units=resident_units(), carriers=CARRIERS, search=search, form_error=error), status


@desk_bp.route("/packages", methods=["POST"])
@login_required
@role_required(*STAFF)
def log_package():
    unit = clean(request.form.get("unit"), 10).upper()
    carrier = request.form.get("carrier")
    description = clean(request.form.get("description"), 120)
    if unit not in resident_units() or carrier not in CARRIERS or not description:
        return packages(error="Choose a unit and carrier, and describe the package.", status=400)
    db.session.add(Package(unit_number=unit, carrier=carrier, description=description, logged_by=session['user_id']))
    db.session.commit()
    for resident in User.query.filter_by(role='resident', unit_number=unit, is_active=True):
        notify(resident, "Package waiting at the front desk", f"A {carrier} package ({description}) is waiting for you at the front desk.")
    return redirect(url_for("desk.packages"))


@desk_bp.route("/packages/<int:package_id>/pickup", methods=["POST"])
@login_required
@role_required(*STAFF)
def pickup_package(package_id):
    package = Package.query.get_or_404(package_id)
    if not package.picked_up_at:
        package.picked_up_at = datetime.utcnow()
        package.released_by = session['user_id']
        db.session.commit()
    return redirect(url_for("desk.packages"))
