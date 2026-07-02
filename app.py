from flask import Flask, request, jsonify
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import json

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
    msg["From"]    = GMAIL_USER
    msg["To"]      = an
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL_USER, GMAIL_PASS)
        s.sendmail(GMAIL_USER, an, msg.as_string())

@app.route("/")
def index():
    return "Leadfinder läuft!"

@app.route("/kontakt", methods=["POST"])
def kontakt():
    d = request.json
    lid = d["id"]
    leads[lid] = d
    ja   = f"{BASE_URL}/antwort?id={lid}&a=ja"
    nein = f"{BASE_URL}/antwort?id={lid}&a=nein"
    html = f"""

