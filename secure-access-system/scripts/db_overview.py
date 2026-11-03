import html
import os
import sys
import webbrowser
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db

HIDDEN = {"password_hash", "temporary_password", "door_code", "totp_secret", "reset_token"}
SAMPLE_ROWS = 5
AREAS = [
    ("Accounts and access", ["users", "zones", "user_zones", "doors", "access_logs", "access_logs_archive", "rate_limit_blocks"]),
    ("Alerts and audit", ["incidents", "notifications", "audit_logs"]),
    ("Visitors", ["visitor_passes", "entry_requests", "parking_permits", "watchlist_entries"]),
    ("Front desk", ["packages", "shift_log_entries", "building_keys", "key_loans", "lost_items"]),
    ("Resident services", ["announcements", "announcement_reads", "maintenance_requests", "amenities", "amenity_bookings", "move_requests"]),
    ("Safety", ["lockdowns", "roll_calls", "roll_call_entries", "emergency_contacts"]),
]


def describe():
    inspector = db.inspect(db.engine)
    tables = {}
    for name in sorted(inspector.get_table_names()):
        pk = set(inspector.get_pk_constraint(name)["constrained_columns"])
        fks = {fk["constrained_columns"][0]: f"{fk['referred_table']}.{fk['referred_columns'][0]}" for fk in inspector.get_foreign_keys(name)}
        columns = [(c["name"], str(c["type"]), c["name"] in pk, fks.get(c["name"]), c["nullable"]) for c in inspector.get_columns(name)]
        quoted = '"' + name.replace('"', '""') + '"'
        count = db.session.execute(db.text(f"SELECT COUNT(*) FROM {quoted}")).scalar()
        rows = db.session.execute(db.text(f"SELECT * FROM {quoted} LIMIT {SAMPLE_ROWS}")).mappings().all()
        tables[name] = {"columns": columns, "count": count, "rows": rows}
    return tables


def grouped(tables):
    known = {t for _, names in AREAS for t in names}
    groups = [(area, [t for t in names if t in tables]) for area, names in AREAS]
    others = [t for t in tables if t not in known]
    return [(area, names) for area, names in groups + [("Other", others)] if names]


def cell(column, value):
    if value is None:
        return '<span class="null">null</span>'
    if column in HIDDEN:
        return '<span class="hidden">hidden</span>'
    text = str(value)
    return html.escape(text if len(text) <= 60 else text[:57] + "...")


def render(path, tables):
    size = os.path.getsize(path) if path and os.path.exists(path) else 0
    groups = grouped(tables)
    links = sum(1 for t in tables.values() for c in t["columns"] if c[3])
    nav = "".join(f'<a href="#{t}">{t}</a>' for _, names in groups for t in names)
    sections = []
    for area, names in groups:
        cards = []
        for name in names:
            t = tables[name]
            cols = "".join(
                f"<tr><td><b>{html.escape(c)}</b></td><td>{html.escape(kind)}</td><td>{'PK' if pk else ''}</td>"
                f"<td>{html.escape(fk) if fk else ''}</td><td>{'' if null else 'required'}</td></tr>"
                for c, kind, pk, fk, null in t["columns"])
            head = "".join(f"<th>{html.escape(c[0])}</th>" for c in t["columns"])
            rows = "".join("<tr>" + "".join(f"<td>{cell(c[0], r[c[0]])}</td>" for c in t["columns"]) + "</tr>" for r in t["rows"])
            sample = (f'<div class="scroll"><table class="data"><tr>{head}</tr>{rows}</table></div>' if rows
                      else '<p class="muted">No rows yet.</p>')
            cards.append(f'<section class="card" id="{name}"><h3>{name}<span class="count">{t["count"]} rows</span></h3>'
                         f'<div class="scroll"><table><tr><th>Column</th><th>Type</th><th>Key</th><th>References</th><th></th></tr>{cols}</table></div>'
                         f'<details><summary>Sample rows (first {SAMPLE_ROWS})</summary>{sample}</details></section>')
        sections.append(f'<h2>{area}</h2><div class="grid">{"".join(cards)}</div>')
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gatekeeper Database</title><style>
body{{margin:0;background:#f5f5f7;color:#1d1d1f;font:14px/1.5 -apple-system,"Segoe UI",system-ui,sans-serif}}
main{{max-width:1200px;margin:0 auto;padding:32px 20px 60px}} h1{{margin:0 0 4px;font-size:28px}} h2{{margin:36px 0 12px;font-size:20px}}
.muted{{color:#6e6e73}} .facts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:20px 0}}
.fact{{background:#fff;border-radius:14px;padding:14px 16px;min-width:0}} .fact .muted{{display:block}} .fact b{{display:block;font-size:22px}} .fact code{{word-break:break-all}}
nav{{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}} nav a{{background:#fff;border-radius:999px;padding:3px 10px;color:#0066cc;text-decoration:none;font-size:12px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(420px,100%),1fr));gap:14px}} .card{{background:#fff;border-radius:16px;padding:16px;min-width:0}}
h3{{margin:0 0 10px;font-size:16px;display:flex;justify-content:space-between;gap:8px}} .count{{color:#0066cc;font-weight:500;font-size:13px}}
.scroll{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;font-size:12.5px}} th,td{{text-align:left;padding:5px 8px;border-bottom:1px solid #e5e5ea;white-space:nowrap}}
th{{color:#6e6e73;font-weight:600}} details{{margin-top:10px}} summary{{cursor:pointer;color:#0066cc}} .null{{color:#aeaeb2}} .hidden{{color:#c45500;font-style:italic}}
code{{font-family:"SF Mono",Consolas,monospace;font-size:12.5px}}
</style></head><body><main>
<h1>Gatekeeper Database</h1>
<p class="muted">Generated {datetime.now():%Y-%m-%d %H:%M} on this computer. Passwords, door codes and other secrets are hidden.</p>
<div class="facts">
<div class="fact"><span class="muted">Engine</span><b>SQLite</b>one file, created by the app on first run</div>
<div class="fact"><span class="muted">File on this computer</span><code>{html.escape(path or "in memory")}</code></div>
<div class="fact"><span class="muted">File size</span><b>{size / 1024:.0f} KB</b></div>
<div class="fact"><span class="muted">Tables</span><b>{len(tables)}</b>{links} foreign-key links</div>
<div class="fact"><span class="muted">Rows in total</span><b>{sum(t["count"] for t in tables.values())}</b></div>
</div>
<nav>{nav}</nav>
{"".join(sections)}
</main></body></html>"""


def build(app):
    with app.app_context():
        path = db.engine.url.database
        return path, render(path, describe())


def main():
    from app import create_app
    app = create_app()
    path, page = build(app)
    out = os.path.join(app.instance_path, "database_overview.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"Database file: {path}")
    print(f"Overview page: {out}")
    if "--no-open" not in sys.argv:
        webbrowser.open(f"file:///{out}")


if __name__ == "__main__":
    main()
