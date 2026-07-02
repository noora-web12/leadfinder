from flask import Flask, request, jsonify
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

app = Flask(__name__)

GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_PASS = os.environ.get("GMAIL_PASS")
PAYPAL_ME  = os.environ.get("PAYPAL_ME")
ABSENDER   = os.environ.get("ABSENDER")
BASE_URL   = os.environ.get("BASE_URL")

leads = {}

def mail_senden(an, betreff, html):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = betreff
    msg["From"] = GMAIL_USER
    msg["To"] = an
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL_USER, GMAIL_PASS)
        s.sendmail(GMAIL_USER, an, msg.as_string())

@app.route("/")
def index():
    return "Leadfinder laeuft!"

@app.route("/kontakt", methods=["POST"])
def kontakt():
    d = request.json
    lid = d["id"]
    leads[lid] = d
    ja = BASE_URL + "/antwort?id=" + lid + "&a=ja"
    nein = BASE_URL + "/antwort?id=" + lid + "&a=nein"
    html = "<p>Guten Tag,</p><p>mir ist aufgefallen dass <b>" + d["name"] + "</b> in " + d["adresse"] + " keine Website hat.</p><p>Darf ich gratis einen Entwurf zeigen?</p><p><a href='" + ja + "' style='background:#22c55e;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold;margin-right:8px'>Ja</a> <a href='" + nein + "' style='background:#e5e7eb;color:#374151;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold'>Nein</a></p><p>" + ABSENDER + "</p>"
    mail_senden(d["email"], "Kostenloser Website-Entwurf fuer " + d["name"], html)
    return jsonify({"ok": True})

@app.route("/antwort")
def antwort():
    lid = request.args.get("id")
    a = request.args.get("a")
    if a == "nein":
        return "<h2>Kein Problem, danke!</h2>"
    lead = leads.get(lid)
    if not lead:
        return "<h2>Link abgelaufen.</h2>"
    mail_senden(GMAIL_USER, "JA von " + lead["name"], "<p><b>" + lead["name"] + "</b> will eine Website!</p><p>Adresse: " + lead["adresse"] + "</p><p>Telefon: " + lead["telefon"] + "</p><p>Jetzt Claude oeffnen und Website generieren!</p>")
    return "<h2 style='color:green'>Super! Sie erhalten Ihren Entwurf bald.</h2>"

@app.route("/suche")
def suche():
    kat = request.args.get("kat", "hairdresser")
    key = request.args.get("key", "shop")
    max_n = int(request.args.get("max", 20))
    query = "[out:json][timeout:55];area[\"ISO3166-1\"=\"DE\"][admin_level=2]->.de;(node[\"" + key + "\"=\"" + kat + "\"][\"website\"!~\".*\"](area.de);way[\"" + key + "\"=\"" + kat + "\"][\"website\"!~\".*\"](area.de););out center tags " + str(max_n) + ";"
    r = requests.post("https://overpass-api.de/api/interpreter", data={"data": query}, timeout=60)
    ergebnis = []
    for el in r.json().get("elements", []):
        t = el.get("tags", {})
        if not t.get("name"):
            continue
        ergebnis.append({"id": "osm_" + str(el["id"]), "name": t.get("name", ""), "adresse": t.get("addr:street", "") + " " + t.get("addr:housenumber", "") + ", " + t.get("addr:postcode", "") + " " + t.get("addr:city", ""), "telefon": t.get("phone", t.get("contact:phone", "")), "email": t.get("email", t.get("contact:email", ""))})
    return jsonify(ergebnis)
@app.route("/auto")
def auto():
    kategorien = [
        ("shop", "hairdresser", "Friseur"),
        ("shop", "bakery", "Baeckerei"),
        ("amenity", "restaurant", "Restaurant"),
        ("craft", "electrician", "Elektriker"),
    ]
    gesamt = 0
    for key, val, name in kategorien:
        query = '[out:json][timeout:25];area["ISO3166-1"="DE"][admin_level=2]->.de;(node["' + key + '"="' + val + '"]["website"!~".*"](area.de););out 5;'
        try:
            r = requests.post("https://overpass-api.de/api/interpreter",
                             data={"data": query}, timeout=28)
            for el in r.json().get("elements", []):
                t = el.get("tags", {})
                if not t.get("name") or not t.get("email", t.get("contact:email", "")):
                    continue
                lid = "osm_" + str(el["id"])
                email = t.get("email", t.get("contact:email", ""))
                d = {"id": lid, "name": t.get("name",""), 
                     "adresse": t.get("addr:street","") + " " + t.get("addr:housenumber","") + ", " + t.get("addr:city",""),
                     "telefon": t.get("phone", ""), "email": email}
                leads[lid] = d
                ja = BASE_URL + "/antwort?id=" + lid + "&a=ja"
                nein = BASE_URL + "/antwort?id=" + lid + "&a=nein"
                html = "<p>Guten Tag,</p><p>mir ist aufgefallen dass <b>" + d["name"] + "</b> keine Website hat.</p><p><a href='" + ja + "' style='background:#22c55e;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold;margin-right:8px'>Ja, zeigen</a> <a href='" + nein + "' style='background:#e5e7eb;color:#374151;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold'>Nein danke</a></p><p>" + ABSENDER + "</p>"
                mail_senden(email, "Kostenloser Website-Entwurf fuer " + d["name"], html)
                gesamt += 1
        except:
            continue
    mail_senden(GMAIL_USER, "Leadfinder: " + str(gesamt) + " E-Mails gesendet", "<p>Heute wurden " + str(gesamt) + " Leads kontaktiert.</p>")
    return "OK: " + str(gesamt) + " gesendet"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
