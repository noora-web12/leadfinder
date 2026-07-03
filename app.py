import os, uuid, csv, io, sqlite3, smtplib, time, threading, requests
from flask import Flask, request, jsonify, redirect, session, g, Response
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "leadfinder2024")

DB = "leads.db"
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_PASS = os.environ.get("GMAIL_PASS")
ABSENDER   = os.environ.get("ABSENDER", "Leadfinder")
BASE_URL   = os.environ.get("BASE_URL", "http://localhost:5000")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "admin123")

# ── Datenbank ──────────────────────────────────────────────────────────────

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db: db.close()

def init_db():
    with sqlite3.connect(DB) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY,
            name TEXT, adresse TEXT, telefon TEXT, email TEXT,
            kategorie TEXT, status TEXT DEFAULT 'neu',
            erstellt TEXT, kontaktiert TEXT, antwort TEXT
        )""")
        db.commit()

# ── E-Mail ─────────────────────────────────────────────────────────────────

def mail(an, betreff, html):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = betreff
        msg["From"]    = f"{ABSENDER} <{GMAIL_USER}>"
        msg["To"]      = an
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(GMAIL_USER, GMAIL_PASS)
            s.sendmail(GMAIL_USER, an, msg.as_string())
        return True
    except Exception as e:
        print(f"Mail-Fehler: {e}")
        return False

def outreach_html(name, adresse, ja_url, nein_url):
    return f"""
<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
<div style="background:#1a1a2e;color:white;padding:24px;border-radius:12px 12px 0 0;text-align:center">
  <h2 style="margin:0">Kostenloser Website-Entwurf</h2>
</div>
<div style="background:#f8f9fa;padding:24px;border-radius:0 0 12px 12px">
  <p>Guten Tag,</p>
  <p>mir ist aufgefallen, dass <strong>{name}</strong> in <em>{adresse}</em> 
  aktuell keine eigene Website hat.</p>
  <p>Ich erstelle Ihnen <strong>kostenlos und unverbindlich</strong> einen 
  ersten Entwurf — schauen Sie ihn an und entscheiden danach.</p>
  <div style="text-align:center;margin:32px 0">
    <a href="{ja_url}" style="background:#22c55e;color:white;padding:14px 32px;
       border-radius:8px;text-decoration:none;font-weight:bold;font-size:16px;
       margin-right:12px">✅ Ja, Entwurf zeigen</a>
    <a href="{nein_url}" style="background:#e5e7eb;color:#374151;padding:14px 32px;
       border-radius:8px;text-decoration:none;font-weight:bold;font-size:16px">
       ❌ Nein, danke</a>
  </div>
  <p style="color:#666;font-size:13px">Kein Risiko, keine Verpflichtung.</p>
  <p>Mit freundlichen Grüßen<br><strong>{ABSENDER}</strong></p>
</div>
</body></html>"""

# ── Admin-Auth ─────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated

# ── Routes: Auth ───────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASS:
            session["admin"] = True
            return redirect("/admin")
        error = "Falsches Passwort"
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Login</title></head>
<body style="font-family:Arial,sans-serif;display:flex;align-items:center;
justify-content:center;min-height:100vh;margin:0;background:#0f172a">
<div style="background:white;padding:32px;border-radius:12px;width:300px">
  <h2 style="margin:0 0 20px;text-align:center">🔒 Leadfinder</h2>
  <form method="POST">
    <input type="password" name="password" placeholder="Passwort"
           style="width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;
           box-sizing:border-box;font-size:16px">
    <button type="submit" style="width:100%;background:#3b82f6;color:white;
            padding:12px;border:none;border-radius:6px;font-size:16px;
            margin-top:12px;cursor:pointer">Einloggen</button>
  </form>
  <p style="color:red;text-align:center">{error}</p>
</div></body></html>"""

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ── Routes: Admin Dashboard ────────────────────────────────────────────────

@app.route("/")
@app.route("/admin")
@login_required
def admin():
    db = get_db()
    leads = db.execute("SELECT * FROM leads ORDER BY erstellt DESC").fetchall()
    stats = {
        "gesamt": len(leads),
        "neu": sum(1 for l in leads if l["status"] == "neu"),
        "kontaktiert": sum(1 for l in leads if l["status"] == "kontaktiert"),
        "ja": sum(1 for l in leads if l["status"] == "ja"),
        "bezahlt": sum(1 for l in leads if l["status"] == "bezahlt"),
    }
    rows = ""
    status_colors = {"neu":"#3b82f6","kontaktiert":"#f59e0b","ja":"#22c55e",
                     "bezahlt":"#10b981","abgelehnt":"#ef4444","nein":"#6b7280"}
    for l in leads:
        c = status_colors.get(l["status"], "#999")
        rows += f"""<tr>
          <td style="padding:10px 12px">{l["name"]}</td>
          <td style="padding:10px 12px;color:#666">{l["adresse"]}</td>
          <td style="padding:10px 12px">{l["email"] or "—"}</td>
          <td style="padding:10px 12px">{l["telefon"] or "—"}</td>
          <td style="padding:10px 12px">
            <span style="background:{c}22;color:{c};padding:3px 10px;
            border-radius:20px;font-size:12px;font-weight:600">{l["status"]}</span>
          </td>
          <td style="padding:10px 12px">
            <a href="/kontaktieren/{l['id']}" style="background:#3b82f6;color:white;
               padding:5px 10px;border-radius:5px;text-decoration:none;font-size:12px">
               📧 E-Mail</a>
          </td>
        </tr>"""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Leadfinder Admin</title></head>
<body style="font-family:Arial,sans-serif;margin:0;background:#0f172a;color:white">
<nav style="background:#1e293b;padding:16px 24px;display:flex;align-items:center;
     justify-content:space-between;border-bottom:1px solid #334155">
  <h1 style="margin:0;font-size:20px">⚡ Leadfinder</h1>
  <div style="display:flex;gap:10px">
    <a href="/suchen" style="background:#3b82f6;color:white;padding:8px 16px;
       border-radius:6px;text-decoration:none;font-size:14px">🔍 Leads suchen</a>
    <a href="/lead/neu" style="background:#22c55e;color:white;padding:8px 16px;
       border-radius:6px;text-decoration:none;font-size:14px">+ Lead hinzufügen</a>
    <a href="/export" style="background:#f59e0b;color:white;padding:8px 16px;
       border-radius:6px;text-decoration:none;font-size:14px">⬇ CSV</a>
    <a href="/logout" style="background:#ef4444;color:white;padding:8px 16px;
       border-radius:6px;text-decoration:none;font-size:14px">Logout</a>
  </div>
</nav>
<div style="padding:24px">
  <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:24px">
    {"".join(f'<div style="background:#1e293b;padding:16px;border-radius:10px;text-align:center"><div style="font-size:24px;font-weight:700">{stats[k]}</div><div style="color:#94a3b8;font-size:13px">{k.capitalize()}</div></div>' for k in stats)}
  </div>
  <div style="background:#1e293b;border-radius:10px;overflow:hidden">
    <table style="width:100%;border-collapse:collapse">
      <thead style="background:#334155">
        <tr>{''.join(f"<th style='padding:10px 12px;text-align:left;color:#94a3b8;font-size:13px'>{h}</th>" for h in ['Name','Adresse','E-Mail','Telefon','Status','Aktion'])}</tr>
      </thead>
      <tbody>{rows if rows else '<tr><td colspan="6" style="text-align:center;padding:40px;color:#64748b">Keine Leads. <a href="/lead/neu" style="color:#3b82f6">Lead hinzufügen</a> oder <a href="/suchen" style="color:#3b82f6">automatisch suchen</a></td></tr>'}</tbody>
    </table>
  </div>
</div></body></html>"""

# ── Routes: Lead hinzufügen ────────────────────────────────────────────────

@app.route("/lead/neu", methods=["GET", "POST"])
@login_required
def lead_neu():
    if request.method == "POST":
        lid = str(uuid.uuid4())[:8]
        get_db().execute(
            "INSERT INTO leads VALUES (?,?,?,?,?,?,?,?,?,?)",
            (lid, request.form["name"], request.form["adresse"],
             request.form["telefon"], request.form["email"],
             request.form["kategorie"], "neu",
             datetime.now().strftime("%Y-%m-%d %H:%M"), None, None)
        )
        get_db().commit()
        return redirect("/admin")
    return """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lead hinzufügen</title></head>
<body style="font-family:Arial,sans-serif;background:#0f172a;color:white;
     display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0">
<div style="background:#1e293b;padding:32px;border-radius:12px;width:400px">
  <h2 style="margin:0 0 20px">+ Lead hinzufügen</h2>
  <form method="POST">
    <input name="name" placeholder="Firmenname" required
           style="width:100%;padding:10px;margin:6px 0;border-radius:6px;
           border:1px solid #334155;background:#0f172a;color:white;box-sizing:border-box">
    <input name="adresse" placeholder="Adresse"
           style="width:100%;padding:10px;margin:6px 0;border-radius:6px;
           border:1px solid #334155;background:#0f172a;color:white;box-sizing:border-box">
    <input name="telefon" placeholder="Telefon"
           style="width:100%;padding:10px;margin:6px 0;border-radius:6px;
           border:1px solid #334155;background:#0f172a;color:white;box-sizing:border-box">
    <input name="email" placeholder="E-Mail" type="email"
           style="width:100%;padding:10px;margin:6px 0;border-radius:6px;
           border:1px solid #334155;background:#0f172a;color:white;box-sizing:border-box">
    <select name="kategorie" style="width:100%;padding:10px;margin:6px 0;
            border-radius:6px;border:1px solid #334155;background:#0f172a;
            color:white;box-sizing:border-box">
      <option>Friseur</option><option>Baeckerei</option>
      <option>Restaurant</option><option>Cafe</option>
      <option>Elektriker</option><option>Zahnarzt</option>
      <option>KFZ Werkstatt</option><option>Sonstige</option>
    </select>
    <button type="submit" style="width:100%;background:#22c55e;color:white;
            padding:12px;border:none;border-radius:6px;font-size:16px;
            margin-top:12px;cursor:pointer">Speichern</button>
    <a href="/admin" style="display:block;text-align:center;margin-top:10px;
       color:#94a3b8;text-decoration:none">Abbrechen</a>
  </form>
</div></body></html>"""

# ── Routes: Kontaktieren ───────────────────────────────────────────────────

@app.route("/kontaktieren/<lid>")
@login_required
def kontaktieren(lid):
    db = get_db()
    lead = db.execute("SELECT * FROM leads WHERE id=?", (lid,)).fetchone()
    if not lead or not lead["email"]:
        return redirect("/admin")
    ja   = f"{BASE_URL}/ja/{lid}"
    nein = f"{BASE_URL}/nein/{lid}"
    html = outreach_html(lead["name"], lead["adresse"], ja, nein)
    if mail(lead["email"], f"Kostenloser Website-Entwurf für {lead['name']}", html):
        db.execute("UPDATE leads SET status='kontaktiert', kontaktiert=? WHERE id=?",
                   (datetime.now().strftime("%Y-%m-%d %H:%M"), lid))
        db.commit()
    return redirect("/admin")

# ── Routes: Automatische Suche ─────────────────────────────────────────────

@app.route("/suchen")
@login_required
def suchen():
    return """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Leads suchen</title></head>
<body style="font-family:Arial,sans-serif;background:#0f172a;color:white;
     display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0">
<div style="background:#1e293b;padding:32px;border-radius:12px;width:400px">
  <h2 style="margin:0 0 20px">🔍 Leads automatisch suchen</h2>
  <form method="POST" action="/suchen/start">
    <select name="kategorie" style="width:100%;padding:10px;margin:6px 0;
            border-radius:6px;border:1px solid #334155;background:#0f172a;
            color:white;box-sizing:border-box">
      <option value="hairdresser|shop">Friseur</option>
      <option value="bakery|shop">Bäckerei</option>
      <option value="restaurant|amenity">Restaurant</option>
      <option value="cafe|amenity">Café</option>
      <option value="electrician|craft">Elektriker</option>
      <option value="dentist|amenity">Zahnarzt</option>
      <option value="car_repair|shop">KFZ Werkstatt</option>
    </select>
    <input name="max" type="number" value="10" min="1" max="50"
           placeholder="Max. Anzahl"
           style="width:100%;padding:10px;margin:6px 0;border-radius:6px;
           border:1px solid #334155;background:#0f172a;color:white;box-sizing:border-box">
    <button type="submit" style="width:100%;background:#3b82f6;color:white;
            padding:12px;border:none;border-radius:6px;font-size:16px;
            margin-top:12px;cursor:pointer">Suchen &amp; importieren</button>
    <a href="/admin" style="display:block;text-align:center;margin-top:10px;
       color:#94a3b8;text-decoration:none">Zurück</a>
  </form>
</div></body></html>"""

@app.route("/suchen/start", methods=["POST"])
@login_required
def suchen_start():
    kat_raw = request.form.get("kategorie", "hairdresser|shop")
    max_n   = int(request.form.get("max", 10))
    val, key = kat_raw.split("|")
    query = f'[out:json][timeout:25];area["ISO3166-1"="DE"][admin_level=2]->.de;(node["{key}"="{val}"]["website"!~".*"](area.de););out {max_n};'
    try:
        r = requests.post("https://overpass-api.de/api/interpreter",
                         data={"data": query}, timeout=28)
        db = get_db()
        neu = 0
        for el in r.json().get("elements", []):
            t   = el.get("tags", {})
            name = t.get("name", "")
            if not name: continue
            lid  = "osm_" + str(el["id"])
            exists = db.execute("SELECT id FROM leads WHERE id=?", (lid,)).fetchone()
            if exists: continue
            db.execute("INSERT INTO leads VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (lid, name,
                        f"{t.get('addr:street','')} {t.get('addr:housenumber','')}, {t.get('addr:city','')}".strip(", "),
                        t.get("phone", t.get("contact:phone", "")),
                        t.get("email", t.get("contact:email", "")),
                        val, "neu",
                        datetime.now().strftime("%Y-%m-%d %H:%M"), None, None))
            neu += 1
        db.commit()
        return redirect(f"/admin?msg={neu}+Leads+importiert")
    except Exception as e:
        return redirect(f"/admin?msg=Fehler:+{str(e)[:50]}")

# ── Routes: Ja/Nein ───────────────────────────────────────────────────────

@app.route("/ja/<lid>")
def ja(lid):
    db = get_db()
    lead = db.execute("SELECT * FROM leads WHERE id=?", (lid,)).fetchone()
    if not lead:
        return "<h2>Link abgelaufen.</h2>"
    db.execute("UPDATE leads SET status='ja', antwort=? WHERE id=?",
               (datetime.now().strftime("%Y-%m-%d %H:%M"), lid))
    db.commit()
    mail(GMAIL_USER, f"✅ JA von {lead['name']}",
         f"<p><b>{lead['name']}</b> will eine Website!</p>"
         f"<p>Adresse: {lead['adresse']}</p>"
         f"<p>Telefon: {lead['telefon']}</p>"
         f"<p>E-Mail: {lead['email']}</p>"
         f"<p>Jetzt Claude öffnen und Website generieren!</p>")
    return """<html><body style="font-family:Arial,sans-serif;text-align:center;
    padding:60px;background:#f0fdf4"><h2 style="color:#16a34a">
    Super! Sie erhalten Ihren Entwurf bald per E-Mail.</h2>
    <p>Wir melden uns in Kürze bei Ihnen.</p></body></html>"""

@app.route("/nein/<lid>")
def nein(lid):
    get_db().execute("UPDATE leads SET status='nein' WHERE id=?", (lid,))
    get_db().commit()
    return """<html><body style="font-family:Arial,sans-serif;text-align:center;
    padding:60px"><h2>Kein Problem, danke für Ihre Rückmeldung!</h2></body></html>"""

# ── Routes: CSV Export ────────────────────────────────────────────────────

@app.route("/export")
@login_required
def export():
    leads = get_db().execute("SELECT * FROM leads").fetchall()
    out   = io.StringIO()
    w     = csv.writer(out)
    w.writerow(["ID","Name","Adresse","Telefon","E-Mail","Kategorie","Status","Erstellt"])
    for l in leads:
        w.writerow([l["id"],l["name"],l["adresse"],l["telefon"],
                    l["email"],l["kategorie"],l["status"],l["erstellt"]])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=leads.csv"})

# ── Start ─────────────────────────────────────────────────────────────────

init_db()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
