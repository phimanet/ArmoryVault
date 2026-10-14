#!/usr/bin/env python3
"""
FirearmsInventory Backend Microservice
Provides REST API endpoints for:
- Full CRUD for Firearms, Optics, Suppressors, Accessories, and Maintenance logs
- Multi-image uploads saved to uploads/photos/
- Automated data snapshots / rolling backups every 10 minutes
- Code modification watcher with instant auto-reload
- Origin-based RFC1918 & Tailscale CORS validation
- Insurance summary calculation & export
"""

import os
import sys
import json
import time
import uuid
import base64
import threading
import ssl
import smtplib
import zipfile
import io
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Configuration & Paths
PORT = int(os.environ.get("PORT", 5000))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Persistent directories (isolated from web root / git pulls)
if os.path.exists("/app/data"):
    DATA_DIR = "/app/data"
    UPLOADS_DIR = "/app/uploads/photos"
    DOCS_DIR = "/app/uploads/documents"
else:
    # Local fallback
    ROOT_DIR = os.path.dirname(BASE_DIR)
    DATA_DIR = os.path.join(ROOT_DIR, "data")
    UPLOADS_DIR = os.path.join(ROOT_DIR, "uploads", "photos")
    DOCS_DIR = os.path.join(ROOT_DIR, "uploads", "documents")

BACKUPS_DIR = os.path.join(DATA_DIR, "backups")
DB_FILE = os.path.join(DATA_DIR, "firearms.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)
os.makedirs(BACKUPS_DIR, exist_ok=True)

# Lock for thread-safe database file operations
db_lock = threading.Lock()

def get_seed_data():
    now_iso = datetime.now(timezone.utc).isoformat() + "Z"
    return {
        "firearms": [
            {
                "id": "fa-glock-19-gen5",
                "make": "Glock",
                "model": "19 Gen 5 MOS",
                "type": "Pistol",
                "caliber": "9x19mm Parabellum",
                "action": "Striker Fired",
                "barrelLength": "4.02 in",
                "serialNumber": "AFCD8923",
                "location": "Primary Safe - Shelf 1",
                "status": "Active",
                "purchaseDate": "2024-03-15",
                "purchasePrice": 620.00,
                "replacementValue": 850.00,
                "roundCount": 1450,
                "notes": "Everyday carry configuration. Runs reliably with standard 115gr, 124gr FMJ and Federal HST 124gr +P.",
                "images": [
                    "https://images.unsplash.com/photo-1595590424283-b8f17842773f?w=900&auto=format&fit=crop&q=80"
                ],
                "accessories": [
                    {"name": "Holosun 507C-X2 Red Dot", "type": "Optic", "serial": "HS507C-88192", "value": 310.00},
                    {"name": "Streamlight TLR-7A Weapon Light", "type": "Light", "serial": "", "value": 140.00}
                ],
                "sources": [
                    {"name": "Bass Pro Shops", "url": "https://www.basspro.com", "price": 620.00, "tags": ["New", "Local FFL"]}
                ],
                "maintenanceLogs": [
                    {"date": "2026-08-10", "type": "Cleaning", "roundsFired": 200, "notes": "Field stripped, cleaned barrel and slide rails, lubricated with Lucas Oil."},
                    {"date": "2026-04-02", "type": "Range Session", "roundsFired": 250, "notes": "Zeroed Holosun 507C at 25 yards."}
                ],
                "createdAt": now_iso,
                "updatedAt": now_iso
            },
            {
                "id": "fa-bcm-recce-16",
                "make": "BCM (Bravo Company)",
                "model": "Recce-16 MCMR",
                "type": "Rifle",
                "caliber": "5.56x45mm NATO / .223",
                "action": "Semi-Automatic (Direct Impingement)",
                "barrelLength": "16.0 in",
                "serialNumber": "BCM-99412A",
                "location": "Primary Safe - Rack Position 3",
                "status": "Active",
                "purchaseDate": "2023-11-20",
                "purchasePrice": 1490.00,
                "replacementValue": 2150.00,
                "roundCount": 2100,
                "notes": "Mid-length gas system, cold hammer forged barrel, BCM Mod 0 compensator.",
                "images": [
                    "https://images.unsplash.com/photo-1584281722572-886d38e21013?w=900&auto=format&fit=crop&q=80"
                ],
                "accessories": [
                    {"name": "Vortex Razor HD Gen II-E 1-6x24", "type": "Optic", "serial": "RZ6-44019", "value": 1399.00},
                    {"name": "Badger Ordnance Condition One 1.70 Mount", "type": "Mount", "serial": "", "value": 315.00},
                    {"name": "SureFire M640DF Scout Light Pro", "type": "Light", "serial": "", "value": 329.00}
                ],
                "sources": [
                    {"name": "Primary Arms", "url": "https://www.primaryarms.com", "price": 1490.00, "tags": ["New", "Online Sale"]}
                ],
                "maintenanceLogs": [
                    {"date": "2026-09-18", "type": "Inspection & Clean", "roundsFired": 300, "notes": "Checked gas rings, cleaned bolt carrier group and bore."}
                ],
                "createdAt": now_iso,
                "updatedAt": now_iso
            },
            {
                "id": "fa-beretta-a300-ultima",
                "make": "Beretta",
                "model": "A300 Ultima Patrol",
                "type": "Shotgun",
                "caliber": "12 Gauge (3 inch chamber)",
                "action": "Gas-Operated Semi-Automatic",
                "barrelLength": "19.1 in",
                "serialNumber": "BER-A300-5821",
                "location": "Primary Safe - Rack Position 1",
                "status": "Active",
                "purchaseDate": "2024-01-10",
                "purchasePrice": 999.00,
                "replacementValue": 1150.00,
                "roundCount": 350,
                "notes": "7+1 capacity, enlarged controls, ghost ring rear sight, M-LOK barrel clamp.",
                "images": [
                    "https://images.unsplash.com/photo-1589254065878-42c9da997008?w=900&auto=format&fit=crop&q=80"
                ],
                "accessories": [
                    {"name": "Esstac 7-Round Shotgun Card", "type": "Side Saddle", "serial": "", "value": 18.00},
                    {"name": "Magpul MS1 Padded Sling", "type": "Sling", "serial": "", "value": 45.00}
                ],
                "sources": [
                    {"name": "Sportsman's Warehouse", "url": "https://www.sportsmans.com", "price": 999.00, "tags": ["New", "In-Store Pick Up"]}
                ],
                "maintenanceLogs": [
                    {"date": "2026-07-04", "type": "Cleaning", "roundsFired": 100, "notes": "Cleaned gas piston assembly and magazine tube."}
                ],
                "createdAt": now_iso,
                "updatedAt": now_iso
            }
        ],
        "types": ["Pistol", "Rifle", "Shotgun", "NFA / Suppressor", "Receiver / Lower", "Other"],
        "locations": [
            "Primary Safe - Shelf 1",
            "Primary Safe - Shelf 2",
            "Primary Safe - Rack Position 1",
            "Primary Safe - Rack Position 2",
            "Primary Safe - Rack Position 3",
            "Range Bag",
            "Secure Lockbox"
        ],
        "ccw": {
            "permitNumber": "",
            "issuingAgency": "San Diego County Sheriff's Department",
            "expirationDate": "",
            "issueDate": "",
            "holderName": "Phimane",
            "status": "Active",
            "emailAlertsEnabled": True,
            "recipientEmail": "phimane@gmail.com",
            "liveScanCompleted": False,
            "liveScanDate": "",
            "liveScanNotes": "",
            "liveScanReminderFreq": "weekly",
            "trainingCompleted": False,
            "trainingDate": "",
            "trainingHours": 8,
            "trainingNotes": "",
            "trainingCompany": "",
            "trainingAddress": "",
            "trainingLeadTime": "1_week",
            "trainingReminderFreq": "weekly",
            "sdsoUploadCompleted": False,
            "sdsoUploadDate": "",
            "sdsoUploadNotes": "",
            "uploadReminderFreq": "weekly",
            "stopAlerts90Days": False,
            "checklistNotes": "",
            "importantLinks": [
                {"title": "SDSO CCW Pro Portal", "url": "https://sandiegoca.permitium.com/ccw/start", "category": "Sheriff Portal"},
                {"title": "San Diego County Sheriff CCW Guidelines", "url": "https://www.sdsheriff.gov/licensing/concealed-carry-weapon-license-ccw", "category": "Official Site"},
                {"title": "California DOJ LiveScan Form (BCIA 8016)", "url": "https://oag.ca.gov/fingerprints/forms", "category": "LiveScan"}
            ],
            "qualifyingGuns": [],
            "lastAlertSent": None,
            "alertHistory": []
        },
        "deletedIds": []
    }

def load_db():
    with db_lock:
        if not os.path.exists(DB_FILE):
            default_data = get_seed_data()
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(default_data, f, indent=2)
            return default_data

        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] Failed to load DB: {e}")
            return {"firearms": [], "types": [], "locations": [], "deletedIds": []}

def save_db(data):
    with db_lock:
        data["updatedAt"] = datetime.now(timezone.utc).isoformat() + "Z"
        temp_file = DB_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(temp_file, DB_FILE)

def backup_worker():
    """Runs periodic rolling snapshot backups every 10 minutes (600s), keeping up to 30 rolling versions."""
    while True:
        try:
            time.sleep(600)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(BACKUPS_DIR, f"firearms_{timestamp}.json")
            with db_lock:
                if os.path.exists(DB_FILE):
                    with open(DB_FILE, "r", encoding="utf-8") as src, open(backup_path, "w", encoding="utf-8") as dst:
                        dst.write(src.read())

            backups = sorted([f for f in os.listdir(BACKUPS_DIR) if f.startswith("firearms_") and f.endswith(".json")])
            if len(backups) > 30:
                for old in backups[:-30]:
                    try:
                        os.remove(os.path.join(BACKUPS_DIR, old))
                    except Exception:
                        pass
        except Exception as e:
            print(f"[BACKUP] Error: {e}")

def code_reload_watcher():
    """Watches server.py for changes and restarts process automatically."""
    try:
        last_mtime = os.stat(__file__).st_mtime
    except Exception:
        return
    while True:
        time.sleep(2)
        try:
            current_mtime = os.stat(__file__).st_mtime
            if current_mtime != last_mtime:
                print(f"[RELOAD] File change detected on {__file__}. Restarting process...")
                os._exit(0)
        except Exception:
            pass

def load_env():
    env_vars = {}
    candidates = [
        os.path.join(os.path.dirname(__file__), '.env'),
        os.path.join(os.path.dirname(__file__), '..', '.env'),
        '/app/.env',
        '/docker/FirearmsInventory/.env',
        '/docker/FamilyCalender/.env'
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            k, v = line.split('=', 1)
                            env_vars[k.strip()] = v.strip().replace('"', '').replace("'", "")
                break
            except Exception:
                pass
    return env_vars

def send_smtp_email(to_emails, subject, html_content):
    env = load_env()
    gmail_user = env.get('GMAIL_USER') or os.environ.get('GMAIL_USER') or 'phimane@gmail.com'
    app_password = env.get('GMAIL_APP_PASSWORD') or os.environ.get('GMAIL_APP_PASSWORD') or ''
    app_password = app_password.replace(" ", "")

    if not app_password:
        return {"success": False, "error": "Missing GMAIL_APP_PASSWORD in .env file."}

    if isinstance(to_emails, str):
        to_emails = [e.strip() for e in to_emails.split(',') if e.strip()]

    if not to_emails:
        return {"success": False, "error": "No recipient email address provided."}

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Armory Vault • CCW Monitor <{gmail_user}>"
    msg["To"] = ", ".join(to_emails)

    msg.attach(MIMEText(html_content, "html"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=15) as server:
            server.login(gmail_user, app_password)
            server.sendmail(gmail_user, to_emails, msg.as_string())
        return {"success": True, "recipients": to_emails, "message": f"Email delivered to {', '.join(to_emails)}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def build_ccw_reminder_email(ccw, days_left, urgency_level="normal"):
    """Generates an executive, mobile-friendly HTML alert detailing renewal milestones."""
    raw_exp = ccw.get("expirationDate") or ""
    exp_date_str = "Not set"
    if raw_exp:
        try:
            parts = raw_exp.split("-")
            if len(parts) == 3 and len(parts[0]) == 4:
                exp_date_str = f"{parts[1]}-{parts[2]}-{parts[0]}"
            else:
                exp_date_str = raw_exp
        except Exception:
            exp_date_str = raw_exp
    permit_num = ccw.get("permitNumber") or "On File"
    holder = ccw.get("holderName") or "Phimane"
    agency = ccw.get("issuingAgency") or "San Diego County Sheriff's Department"

    # Status checkmarks
    livescan_icon = "✅ Completed" if ccw.get("liveScanCompleted") else "⚠️ Pending Action"
    training_icon = "✅ Completed" if ccw.get("trainingCompleted") else "⚠️ Pending Action"
    upload_icon = "✅ Uploaded" if ccw.get("sdsoUploadCompleted") else "⚠️ Pending Action (Deadline: 90 Days Prior)"

    training_company = ccw.get("trainingCompany") or ""
    training_address = ccw.get("trainingAddress") or ""
    class_location_html = ""
    if training_company or training_address:
        loc_parts = []
        if training_company:
            loc_parts.append(f"<strong>Company:</strong> {training_company}")
        if training_address:
            loc_parts.append(f"<strong>Location/Address:</strong> {training_address}")
        class_location_html = f"""<div style="margin-top:6px; font-size:12px; color:#93c5fd; background:rgba(59,130,246,0.1); padding:6px 10px; border-radius:4px; border:1px solid rgba(59,130,246,0.25);">{' &bull; '.join(loc_parts)}</div>"""

    header_color = "#f43f5e" if days_left <= 60 else ("#f59e0b" if days_left <= 90 else "#0284c7")
    badge_text = "URGENT ACTION REQUIRED" if days_left <= 60 else ("CRITICAL RENEWAL WINDOW" if days_left <= 90 else "CCW RENEWAL NOTICE")

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CCW Permit Renewal Alert</title>
</head>
<body style="margin:0; padding:0; background-color:#0b0f19; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color:#e2e8f0;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0b0f19; padding:24px 12px;">
    <tr>
      <td align="center">
        <table width="100%" max-width="600" cellpadding="0" cellspacing="0" style="max-width:600px; background-color:#111827; border:1px solid #1f2937; border-radius:12px; overflow:hidden; box-shadow:0 10px 25px rgba(0,0,0,0.5);">
          <!-- Header -->
          <tr>
            <td style="background-color:{header_color}; padding:20px 24px; text-align:left;">
              <span style="display:inline-block; font-size:11px; font-weight:800; letter-spacing:0.08em; text-transform:uppercase; background:rgba(0,0,0,0.25); color:#ffffff; padding:3px 8px; border-radius:4px; margin-bottom:8px;">{badge_text}</span>
              <h1 style="margin:0; font-size:22px; font-weight:800; color:#ffffff; letter-spacing:-0.02em;">CCW Permit Renewal Alert</h1>
              <p style="margin:4px 0 0 0; font-size:14px; color:rgba(255,255,255,0.9);">{days_left} Days Remaining Until Expiration ({exp_date_str})</p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:24px;">
              <p style="margin:0 0 16px 0; font-size:15px; line-height:1.5; color:#cbd5e1;">
                Hello <strong>{holder}</strong>, your California CCW permit with the <strong>{agency}</strong> will expire in <strong style="color:#f43f5e;">{days_left} days</strong>.
              </p>

              <!-- Overview Card -->
              <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#1e293b; border:1px solid #334155; border-radius:8px; margin-bottom:20px;">
                <tr>
                  <td style="padding:16px;">
                    <table width="100%" cellpadding="6" cellspacing="0" style="font-size:13px;">
                      <tr>
                        <td style="color:#94a3b8; width:40%;">Permit Number:</td>
                        <td style="color:#f8fafc; font-weight:600;">{permit_num}</td>
                      </tr>
                      <tr>
                        <td style="color:#94a3b8;">Expiration Date:</td>
                        <td style="color:#f43f5e; font-weight:700;">{exp_date_str}</td>
                      </tr>
                      <tr>
                        <td style="color:#94a3b8;">Issuing Agency:</td>
                        <td style="color:#f8fafc;">{agency}</td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <!-- Required Steps Checklist -->
              <h2 style="margin:0 0 12px 0; font-size:16px; font-weight:700; color:#38bdf8; text-transform:uppercase; letter-spacing:0.04em;">Critical Renewal Protocol:</h2>

              <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse; margin-bottom:20px;">
                <!-- Step 1 -->
                <tr>
                  <td style="padding:12px; background-color:#1e293b; border-bottom:1px solid #334155; border-radius:6px 6px 0 0;">
                    <div style="font-size:14px; font-weight:700; color:#ffffff;">1. CCW Renewal Class & Qualification</div>
                    <div style="font-size:12px; color:#94a3b8; margin-top:2px;">Complete approved 8-hour CCW retraining course and live-fire shooting qualification.</div>
                    {class_location_html}
                    <div style="margin-top:6px; font-size:12px; font-weight:600; color:{'#34d399' if ccw.get('trainingCompleted') else '#f59e0b'};">{training_icon}</div>
                  </td>
                </tr>
                <!-- Step 2 -->
                <tr>
                  <td style="padding:12px; background-color:#1e293b; border-bottom:1px solid #334155;">
                    <div style="font-size:14px; font-weight:700; color:#ffffff;">2. LiveScan Fingerprinting</div>
                    <div style="font-size:12px; color:#94a3b8; margin-top:2px;">Official DOJ fingerprint background check completed following CCW renewal class.</div>
                    <div style="margin-top:6px; font-size:12px; font-weight:600; color:{'#34d399' if ccw.get('liveScanCompleted') else '#f59e0b'};">{livescan_icon}</div>
                  </td>
                </tr>
                <!-- Step 3 -->
                <tr>
                  <td style="padding:12px; background-color:#1e293b; border-radius:0 0 6px 6px;">
                    <div style="font-size:14px; font-weight:700; color:#ffffff;">3. Upload Documents to San Diego Sheriff's Dept (90 Days Prior)</div>
                    <div style="font-size:12px; color:#94a3b8; margin-top:2px;">Submit certificates, training docs, and application directly through CCW Pro at least 90 days before expiration.</div>
                    <div style="margin-top:6px; font-size:12px; font-weight:600; color:{'#34d399' if ccw.get('sdsoUploadCompleted') else '#f59e0b'};">{upload_icon}</div>
                  </td>
                </tr>
              </table>

              <!-- Call to Action -->
              <div style="text-align:center; padding:12px 0 8px 0;">
                <a href="http://192.168.72.10:8186" style="display:inline-block; background-color:#10b981; color:#ffffff; text-decoration:none; font-weight:700; font-size:14px; padding:12px 24px; border-radius:6px; box-shadow:0 4px 12px rgba(16,185,129,0.3);">Open Armory Vault CCW Dashboard</a>
              </div>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color:#0f172a; border-top:1px solid #1e293b; padding:16px 24px; text-align:center; font-size:12px; color:#64748b;">
              Armory Vault Automated CCW Compliance System • Live on Port 8186<br>
              Daily alerts active 90 days prior to expiration until checked completed.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
    return html

def check_and_send_ccw_reminders(force=False, test_recipient=None):
    """
    Checks CCW expiration and milestone pending status to dispatch email reminders.
    Sends daily emails starting 90 days prior to CCW expiration until all pending milestones
    are check-marked as completed (or until stopAlerts90Days is checked / email alerts disabled).
    Also supports custom frequencies for LiveScan, Class, and Upload milestones.
    """
    db = load_db()
    ccw = db.get("ccw", {})
    if not ccw:
        return {"status": "no_ccw_data"}

    if not ccw.get("emailAlertsEnabled", True) and not force:
        return {"status": "alerts_disabled"}

    exp_str = ccw.get("expirationDate")
    if not exp_str:
        return {"status": "no_expiration_date"}

    try:
        exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
    except Exception:
        return {"status": "invalid_date_format"}

    today = datetime.now().date()
    days_left = (exp_date - today).days

    recipient = test_recipient or ccw.get("recipientEmail") or "phimane@gmail.com"

    # Status checkmarks
    livescan_done = Boolean(ccw.get("liveScanCompleted")) if 'Boolean' in globals() else bool(ccw.get("liveScanCompleted"))
    training_done = bool(ccw.get("trainingCompleted"))
    upload_done = bool(ccw.get("sdsoUploadCompleted"))
    all_done = livescan_done and training_done and upload_done
    stop_90_days = bool(ccw.get("stopAlerts90Days", False))

    should_send = force
    trigger_reason = "Manual Test / Trigger" if force else ""

    if not force:
        # Check if already sent today
        last_sent_iso = ccw.get("lastAlertSent")
        already_sent_today = False
        if last_sent_iso:
            try:
                last_sent_date = datetime.fromisoformat(last_sent_iso.replace("Z", "+00:00")).date()
                if last_sent_date == today:
                    already_sent_today = True
            except Exception:
                pass

        if not already_sent_today:
            # RULE 1: Daily reminders starting 90 days prior to CCW expiration until user check-marks to stop
            if days_left <= 90 and days_left > 0:
                if not stop_90_days and not all_done:
                    should_send = True
                    trigger_reason = f"Daily 90-Day Renewal Notice ({days_left} Days Remaining)"

            # RULE 2: Training Class Lead Time Reminder (Remind X days or weeks before scheduled class)
            training_date_str = ccw.get("trainingDate")
            if not should_send and not training_done and training_date_str:
                try:
                    tr_date = datetime.strptime(training_date_str, "%Y-%m-%d").date()
                    days_until_class = (tr_date - today).days
                    lead_time_choice = ccw.get("trainingLeadTime", "1_week")
                    lead_days_map = {
                        "1_day": 1,
                        "2_days": 2,
                        "3_days": 3,
                        "5_days": 5,
                        "1_week": 7,
                        "2_weeks": 14,
                        "3_weeks": 21,
                        "1_month": 30
                    }
                    target_lead_days = lead_days_map.get(lead_time_choice, 7)
                    if days_until_class == target_lead_days or days_until_class == 1 or days_until_class == 0:
                        should_send = True
                        if days_until_class == 0:
                            trigger_reason = f"CCW Class Reminder: TODAY ({training_date_str})"
                        elif days_until_class == 1:
                            trigger_reason = f"CCW Class Reminder: TOMORROW ({training_date_str})"
                        else:
                            trigger_reason = f"CCW Class Reminder: {days_until_class} Days Before Class ({training_date_str})"
                except Exception:
                    pass

            # RULE 3: Configurable recurring reminder frequencies for milestones (LiveScan, Class, Upload)
            if not should_send and days_left > 0:
                # Milestone reminder frequencies: 'daily', 'every_2_days', 'every_3_days', 'weekly', 'biweekly', 'monthly'
                freq_days_map = {
                    "daily": 1,
                    "every_2_days": 2,
                    "every_3_days": 3,
                    "weekly": 7,
                    "biweekly": 14,
                    "monthly": 30
                }

                # Helper to check if milestone frequency matches today
                def is_freq_due(freq_str, milestone_name):
                    days_interval = freq_days_map.get(freq_str, 7)
                    if days_interval == 1:
                        return True
                    # Check day interval based on days_left mod
                    return (days_left % days_interval) == 0

                ls_freq = ccw.get("liveScanReminderFreq", "weekly")
                tr_freq = ccw.get("trainingReminderFreq", "weekly")
                up_freq = ccw.get("uploadReminderFreq", "weekly")

                pending_reasons = []
                if not livescan_done and is_freq_due(ls_freq, "LiveScan"):
                    pending_reasons.append("LiveScan Pending")
                if not training_done and is_freq_due(tr_freq, "CCW Class"):
                    pending_reasons.append("CCW Class Pending")
                if not upload_done and is_freq_due(up_freq, "Doc Upload"):
                    pending_reasons.append("Doc Upload Pending")

                if pending_reasons and (days_left <= 120):
                    should_send = True
                    trigger_reason = f"Milestone Reminder: {', '.join(pending_reasons)} ({days_left} Days Left)"

    if should_send:
        us_exp_str = exp_str
        try:
            p = exp_str.split("-")
            if len(p) == 3 and len(p[0]) == 4:
                us_exp_str = f"{p[1]}-{p[2]}-{p[0]}"
        except Exception:
            pass
        subject = f"⚠️ CCW Renewal Alert: {days_left} Days Remaining Until Expiration ({us_exp_str})"
        html = build_ccw_reminder_email(ccw, days_left)
        result = send_smtp_email([recipient], subject, html)

        if result.get("success"):
            now_iso = datetime.now(timezone.utc).isoformat() + "Z"
            ccw["lastAlertSent"] = now_iso
            ccw.setdefault("alertHistory", []).append({
                "date": today.isoformat(),
                "timestamp": now_iso,
                "daysLeft": days_left,
                "recipient": recipient,
                "reason": trigger_reason
            })
            if len(ccw["alertHistory"]) > 30:
                ccw["alertHistory"] = ccw["alertHistory"][-30:]
            save_db(db)
            return {"status": "sent", "daysLeft": days_left, "recipient": recipient, "result": result}
        else:
            return {"status": "failed", "error": result.get("error")}

    return {"status": "skipped", "daysLeft": days_left}

def ccw_reminder_worker():
    """Daily background worker monitoring CCW expiration and sending renewal emails."""
    while True:
        try:
            # Check every 2 hours (7200 seconds) so daily alerts trigger reliably
            check_and_send_ccw_reminders(force=False)
            time.sleep(7200)
        except Exception as e:
            print(f"[CCW WORKER] Error: {e}")
            time.sleep(300)

class RequestHandler(BaseHTTPRequestHandler):
    def is_origin_allowed(self, origin):
        if not origin:
            return True
        origin_clean = origin.lower().split("://")[-1].split(":")[0]
        if origin_clean in ["localhost", "127.0.0.1", "dockermonster"]:
            return True
        if origin_clean.endswith(".local") or origin_clean.endswith(".lan"):
            return True
        # RFC1918 and Tailscale CGNAT
        if origin_clean.startswith("192.168.") or origin_clean.startswith("10."):
            return True
        if origin_clean.startswith("172."):
            try:
                second = int(origin_clean.split(".")[1])
                if 16 <= second <= 31:
                    return True
            except ValueError:
                pass
        if origin_clean.startswith("100."):  # Tailscale
            return True
        return False

    def send_cors_headers(self):
        origin = self.headers.get("Origin")
        if origin and self.is_origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.send_header("Access-Control-Max-Age", "86400")
        elif not origin:
            self.send_header("Access-Control-Allow-Origin", "*")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status, message):
        self.send_json(status, {"success": False, "error": message})

    def parse_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            return json.loads(raw)
        except Exception:
            return None

    def do_GET(self):
        url = urlparse(self.path)
        path = url.path.rstrip("/")
        query = parse_qs(url.query)

        if path in ["/api", "/api/health"]:
            self.send_json(200, {
                "status": "ok",
                "service": "FirearmsInventory API",
                "time": datetime.now(timezone.utc).isoformat() + "Z"
            })
            return

        if path == "/api/firearms":
            db = load_db()
            items = db.get("firearms", [])
            # Alphabetically sort by Manufacturer (make), then model
            items.sort(key=lambda it: (it.get("make", "").strip().lower(), it.get("model", "").strip().lower()))
            type_filter = query.get("type", [None])[0]
            search = query.get("q", [None])[0]

            filtered = items
            if type_filter and type_filter != "All":
                filtered = [it for it in filtered if it.get("type") == type_filter]
            if search:
                s_lower = search.lower()
                filtered = [
                    it for it in filtered
                    if s_lower in it.get("make", "").lower()
                    or s_lower in it.get("model", "").lower()
                    or s_lower in it.get("caliber", "").lower()
                    or s_lower in it.get("serialNumber", "").lower()
                    or s_lower in it.get("location", "").lower()
                    or s_lower in it.get("notes", "").lower()
                    or any(s_lower in acc.get("name", "").lower() for acc in it.get("accessories", []))
                ]

            self.send_json(200, {
                "success": True,
                "firearms": filtered,
                "types": db.get("types", []),
                "locations": db.get("locations", []),
                "summary": self._calc_summary(items)
            })
            return

        if path.startswith("/api/firearms/"):
            item_id = path.split("/api/firearms/")[1]
            db = load_db()
            target = next((it for it in db.get("firearms", []) if it.get("id") == item_id), None)
            if target:
                self.send_json(200, {"success": True, "firearm": target})
            else:
                self.send_error_json(404, "Firearm not found")
            return

        if path == "/api/ccw":
            db = load_db()
            ccw = db.get("ccw", {})
            # Enrich with active daysLeft and 90-days-prior deadline calculation
            days_left = None
            deadline_90_str = None
            exp_str = ccw.get("expirationDate")
            if exp_str:
                try:
                    exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
                    days_left = (exp_date - datetime.now().date()).days
                    deadline_90_date = exp_date - timedelta(days=90)
                    deadline_90_str = deadline_90_date.strftime("%Y-%m-%d")
                except Exception:
                    pass
            ccw["daysRemaining"] = days_left
            ccw["deadline90Days"] = deadline_90_str
            self.send_json(200, {"success": True, "ccw": ccw})
            return

        if path == "/api/insurance-report":
            db = load_db()
            items = db.get("firearms", [])
            self.send_json(200, {
                "success": True,
                "reportDate": datetime.now(timezone.utc).isoformat() + "Z",
                "summary": self._calc_summary(items),
                "items": items
            })
            return

        if path == "/api/backups":
            backups = sorted([f for f in os.listdir(BACKUPS_DIR) if f.startswith("firearms_") and f.endswith(".json")], reverse=True)
            self.send_json(200, {"success": True, "backups": backups})
            return

        if path == "/api/export-archive":
            try:
                zip_buffer = io.BytesIO()
                db = load_db()
                now_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
                filename = f"ArmoryVault_Full_Backup_{now_str}.zip"

                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    # 1. Main database
                    with db_lock:
                        if os.path.exists(DB_FILE):
                            zf.write(DB_FILE, arcname="database/firearms.json")
                        else:
                            zf.writestr("database/firearms.json", json.dumps(db, indent=2))

                    # 2. Photos
                    if os.path.exists(UPLOADS_DIR):
                        for root, _, files in os.walk(UPLOADS_DIR):
                            for f in files:
                                if f.startswith("."):
                                    continue
                                full_p = os.path.join(root, f)
                                arc_p = os.path.join("photos", f)
                                zf.write(full_p, arcname=arc_p)

                    # 3. Documents & DROS paperwork
                    if os.path.exists(DOCS_DIR):
                        for root, _, files in os.walk(DOCS_DIR):
                            for f in files:
                                if f.startswith("."):
                                    continue
                                full_p = os.path.join(root, f)
                                arc_p = os.path.join("documents", f)
                                zf.write(full_p, arcname=arc_p)

                    # 4. Manifest metadata
                    manifest = {
                        "project": "ArmoryVault",
                        "exportedAt": datetime.now(timezone.utc).isoformat() + "Z",
                        "firearmsCount": len(db.get("firearms", [])),
                        "ccwHolder": db.get("ccw", {}).get("holderName", ""),
                        "photosCount": len(os.listdir(UPLOADS_DIR)) if os.path.exists(UPLOADS_DIR) else 0,
                        "documentsCount": len(os.listdir(DOCS_DIR)) if os.path.exists(DOCS_DIR) else 0,
                        "version": "1.0"
                    }
                    zf.writestr("manifest.json", json.dumps(manifest, indent=2))

                zip_bytes = zip_buffer.getvalue()
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.send_header("Content-Length", str(len(zip_bytes)))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(zip_bytes)
                return
            except Exception as e:
                self.send_error_json(500, f"Error generating export archive: {str(e)}")
                return

        self.send_error_json(404, "Endpoint not found")

    def _calc_summary(self, items):
        total_items = len(items)
        total_purchase = sum(float(it.get("purchasePrice") or 0) for it in items)
        total_replacement = sum(float(it.get("replacementValue") or 0) for it in items)
        total_accessories_val = 0
        total_rounds = 0

        type_counts = {}
        for it in items:
            t = it.get("type", "Other")
            type_counts[t] = type_counts.get(t, 0) + 1
            total_rounds += int(it.get("roundCount") or 0)
            for acc in it.get("accessories", []):
                total_accessories_val += float(acc.get("value") or 0)

        return {
            "totalFirearms": total_items,
            "totalPurchaseCost": round(total_purchase, 2),
            "totalReplacementValue": round(total_replacement, 2),
            "totalAccessoriesValue": round(total_accessories_val, 2),
            "grandTotalInsuredValue": round(total_replacement + total_accessories_val, 2),
            "totalRoundsTracked": total_rounds,
            "typeCounts": type_counts
        }

    def do_POST(self):
        url = urlparse(self.path)
        path = url.path.rstrip("/")

        if path == "/api/firearms":
            body = self.parse_json_body()
            if not body or not body.get("make") or not body.get("model"):
                self.send_error_json(400, "Make and Model are required.")
                return

            db = load_db()
            item_id = body.get("id") or ("fa-" + str(uuid.uuid4())[:8])
            now_iso = datetime.now(timezone.utc).isoformat() + "Z"

            new_firearm = {
                "id": item_id,
                "make": body.get("make", "").strip(),
                "model": body.get("model", "").strip(),
                "type": body.get("type", "Pistol"),
                "caliber": body.get("caliber", "").strip(),
                "action": body.get("action", "").strip(),
                "barrelLength": body.get("barrelLength", "").strip(),
                "serialNumber": body.get("serialNumber", "").strip(),
                "location": body.get("location", "").strip(),
                "status": body.get("status", "Active"),
                "purchaseDate": body.get("purchaseDate", ""),
                "purchasePrice": float(body.get("purchasePrice") or 0),
                "replacementValue": float(body.get("replacementValue") or 0),
                "roundCount": int(body.get("roundCount") or 0),
                "notes": body.get("notes", "").strip(),
                "onCCW": bool(body.get("onCCW", False)),
                "images": body.get("images", []),
                "accessories": body.get("accessories", []),
                "sources": body.get("sources", []),
                "documents": body.get("documents", []),
                "maintenanceLogs": body.get("maintenanceLogs", []),
                "createdAt": now_iso,
                "updatedAt": now_iso
            }

            db.setdefault("firearms", []).insert(0, new_firearm)
            save_db(db)
            self.send_json(201, {"success": True, "firearm": new_firearm})
            return

        if path == "/api/upload-photo":
            body = self.parse_json_body()
            if not body or "image" not in body:
                self.send_error_json(400, "Missing image payload.")
                return

            try:
                data_str = body["image"]
                ext = "jpg"
                if "data:image/" in data_str and ";base64," in data_str:
                    header, base64_data = data_str.split(";base64,", 1)
                    if "png" in header:
                        ext = "png"
                    elif "webp" in header:
                        ext = "webp"
                    elif "heic" in header or "heif" in header:
                        ext = "heic"
                    elif "gif" in header:
                        ext = "gif"
                else:
                    base64_data = data_str

                # Clean any whitespace or newlines from base64 string
                base64_data = "".join(base64_data.split())
                img_bytes = base64.b64decode(base64_data)
                filename = f"fa_{int(time.time())}_{uuid.uuid4().hex[:6]}.{ext}"
                filepath = os.path.join(UPLOADS_DIR, filename)

                with open(filepath, "wb") as f:
                    f.write(img_bytes)

                public_url = f"/uploads/photos/{filename}"
                self.send_json(200, {"success": True, "url": public_url, "filename": filename})
            except Exception as e:
                self.send_error_json(500, f"Upload error: {str(e)}")
            return

        if path == "/api/upload-document":
            body = self.parse_json_body()
            if not body or "file" not in body:
                self.send_error_json(400, "Missing file payload.")
                return

            try:
                data_str = body["file"]
                orig_name = body.get("fileName", "document")
                title = body.get("title", "").strip() or orig_name
                category = body.get("category", "Receipt").strip()
                ext = "pdf"

                if "data:" in data_str and ";base64," in data_str:
                    header, base64_data = data_str.split(";base64,", 1)
                    if "pdf" in header:
                        ext = "pdf"
                    elif "png" in header:
                        ext = "png"
                    elif "webp" in header:
                        ext = "webp"
                    elif "jpeg" in header or "jpg" in header:
                        ext = "jpg"
                    elif "heic" in header or "heif" in header:
                        ext = "heic"
                else:
                    base64_data = data_str
                    if "." in orig_name:
                        cand_ext = orig_name.rsplit(".", 1)[1].lower()
                        if cand_ext in ["pdf", "jpg", "jpeg", "png", "webp", "heic"]:
                            ext = cand_ext

                base64_data = "".join(base64_data.split())
                doc_bytes = base64.b64decode(base64_data)
                doc_id = f"doc_{uuid.uuid4().hex[:8]}"
                filename = f"doc_{int(time.time())}_{uuid.uuid4().hex[:6]}.{ext}"
                filepath = os.path.join(DOCS_DIR, filename)

                with open(filepath, "wb") as f:
                    f.write(doc_bytes)

                public_url = f"/uploads/documents/{filename}"
                now_iso = datetime.now(timezone.utc).isoformat() + "Z"
                doc_info = {
                    "id": doc_id,
                    "title": title,
                    "category": category,
                    "fileName": orig_name,
                    "fileSize": len(doc_bytes),
                    "fileType": ext.upper(),
                    "url": public_url,
                    "uploadedAt": now_iso
                }
                self.send_json(200, {"success": True, "document": doc_info})
            except Exception as e:
                self.send_error_json(500, f"Document upload error: {str(e)}")
            return

        if path == "/api/snapshot":
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(BACKUPS_DIR, f"firearms_manual_{timestamp}.json")
            with db_lock:
                if os.path.exists(DB_FILE):
                    with open(DB_FILE, "r", encoding="utf-8") as src, open(backup_path, "w", encoding="utf-8") as dst:
                        dst.write(src.read())
            self.send_json(200, {"success": True, "snapshot": f"firearms_manual_{timestamp}.json"})
            return

        if path == "/api/ccw/test-email":
            body = self.parse_json_body() or {}
            recipient = body.get("recipient")
            res = check_and_send_ccw_reminders(force=True, test_recipient=recipient)
            self.send_json(200, {"success": res.get("status") == "sent", "details": res})
            return

        self.send_error_json(404, "Endpoint not found")

    def do_PUT(self):
        url = urlparse(self.path)
        path = url.path.rstrip("/")

        if path == "/api/ccw":
            body = self.parse_json_body()
            if not body:
                self.send_error_json(400, "Invalid JSON payload.")
                return

            db = load_db()
            ccw = db.get("ccw", {})
            ccw["permitNumber"] = body.get("permitNumber", ccw.get("permitNumber", "")).strip()
            ccw["issuingAgency"] = body.get("issuingAgency", ccw.get("issuingAgency", "San Diego County Sheriff's Department")).strip()
            ccw["expirationDate"] = body.get("expirationDate", ccw.get("expirationDate", ""))
            ccw["issueDate"] = body.get("issueDate", ccw.get("issueDate", ""))
            ccw["holderName"] = body.get("holderName", ccw.get("holderName", "Phimane")).strip()
            ccw["status"] = body.get("status", ccw.get("status", "Active"))
            ccw["emailAlertsEnabled"] = bool(body.get("emailAlertsEnabled", ccw.get("emailAlertsEnabled", True)))
            ccw["recipientEmail"] = body.get("recipientEmail", ccw.get("recipientEmail", "phimane@gmail.com")).strip()
            ccw["stopAlerts90Days"] = bool(body.get("stopAlerts90Days", ccw.get("stopAlerts90Days", False)))

            # Key Critical Renewal Checklist items
            ccw["liveScanCompleted"] = bool(body.get("liveScanCompleted", ccw.get("liveScanCompleted", False)))
            ccw["liveScanDate"] = body.get("liveScanDate", ccw.get("liveScanDate", ""))
            ccw["liveScanNotes"] = body.get("liveScanNotes", ccw.get("liveScanNotes", "")).strip()
            ccw["liveScanReminderFreq"] = body.get("liveScanReminderFreq", ccw.get("liveScanReminderFreq", "weekly"))

            ccw["trainingCompleted"] = bool(body.get("trainingCompleted", ccw.get("trainingCompleted", False)))
            ccw["trainingDate"] = body.get("trainingDate", ccw.get("trainingDate", ""))
            ccw["trainingHours"] = int(body.get("trainingHours") or ccw.get("trainingHours", 8))
            ccw["trainingNotes"] = body.get("trainingNotes", ccw.get("trainingNotes", "")).strip()
            ccw["trainingCompany"] = body.get("trainingCompany", ccw.get("trainingCompany", "")).strip()
            ccw["trainingAddress"] = body.get("trainingAddress", ccw.get("trainingAddress", "")).strip()
            ccw["trainingLeadTime"] = body.get("trainingLeadTime", ccw.get("trainingLeadTime", "1_week"))
            ccw["trainingReminderFreq"] = body.get("trainingReminderFreq", ccw.get("trainingReminderFreq", "weekly"))

            ccw["sdsoUploadCompleted"] = bool(body.get("sdsoUploadCompleted", ccw.get("sdsoUploadCompleted", False)))
            ccw["sdsoUploadDate"] = body.get("sdsoUploadDate", ccw.get("sdsoUploadDate", ""))
            ccw["sdsoUploadNotes"] = body.get("sdsoUploadNotes", ccw.get("sdsoUploadNotes", "")).strip()
            ccw["uploadReminderFreq"] = body.get("uploadReminderFreq", ccw.get("uploadReminderFreq", "daily"))

            ccw["checklistNotes"] = body.get("checklistNotes", ccw.get("checklistNotes", "")).strip()
            if "importantLinks" in body:
                ccw["importantLinks"] = body["importantLinks"]
            elif "importantLinks" not in ccw:
                ccw["importantLinks"] = []
            if "qualifyingGuns" in body:
                ccw["qualifyingGuns"] = body["qualifyingGuns"]

            db["ccw"] = ccw
            save_db(db)

            # Re-calculate days remaining and 90-days-prior deadline
            days_left = None
            deadline_90_str = None
            if ccw.get("expirationDate"):
                try:
                    exp_date = datetime.strptime(ccw["expirationDate"], "%Y-%m-%d").date()
                    days_left = (exp_date - datetime.now().date()).days
                    deadline_90_date = exp_date - timedelta(days=90)
                    deadline_90_str = deadline_90_date.strftime("%Y-%m-%d")
                except Exception:
                    pass
            ccw["daysRemaining"] = days_left
            ccw["deadline90Days"] = deadline_90_str
            self.send_json(200, {"success": True, "ccw": ccw})
            return

        if path.startswith("/api/firearms/"):
            item_id = path.split("/api/firearms/")[1]
            body = self.parse_json_body()
            if not body:
                self.send_error_json(400, "Invalid JSON payload.")
                return

            db = load_db()
            items = db.get("firearms", [])
            idx = next((i for i, it in enumerate(items) if it.get("id") == item_id), None)
            if idx is None:
                self.send_error_json(404, "Firearm not found.")
                return

            now_iso = datetime.now(timezone.utc).isoformat() + "Z"
            existing = items[idx]

            existing["make"] = body.get("make", existing.get("make", "")).strip()
            existing["model"] = body.get("model", existing.get("model", "")).strip()
            existing["type"] = body.get("type", existing.get("type", "Pistol"))
            existing["caliber"] = body.get("caliber", existing.get("caliber", "")).strip()
            existing["action"] = body.get("action", existing.get("action", "")).strip()
            existing["barrelLength"] = body.get("barrelLength", existing.get("barrelLength", "")).strip()
            existing["serialNumber"] = body.get("serialNumber", existing.get("serialNumber", "")).strip()
            existing["location"] = body.get("location", existing.get("location", "")).strip()
            existing["status"] = body.get("status", existing.get("status", "Active"))
            existing["purchaseDate"] = body.get("purchaseDate", existing.get("purchaseDate", ""))
            existing["purchasePrice"] = float(body.get("purchasePrice") if body.get("purchasePrice") is not None else existing.get("purchasePrice", 0))
            existing["replacementValue"] = float(body.get("replacementValue") if body.get("replacementValue") is not None else existing.get("replacementValue", 0))
            existing["roundCount"] = int(body.get("roundCount") if body.get("roundCount") is not None else existing.get("roundCount", 0))
            existing["notes"] = body.get("notes", existing.get("notes", "")).strip()
            existing["onCCW"] = bool(body.get("onCCW", existing.get("onCCW", False)))

            if "images" in body:
                existing["images"] = body["images"]
            if "accessories" in body:
                existing["accessories"] = body["accessories"]
            if "sources" in body:
                existing["sources"] = body["sources"]
            if "documents" in body:
                existing["documents"] = body["documents"]
            if "maintenanceLogs" in body:
                existing["maintenanceLogs"] = body["maintenanceLogs"]

            existing["updatedAt"] = now_iso
            items[idx] = existing
            save_db(db)

            self.send_json(200, {"success": True, "firearm": existing})
            return

        self.send_error_json(404, "Endpoint not found")

    def do_DELETE(self):
        url = urlparse(self.path)
        path = url.path.rstrip("/")

        if path.startswith("/api/firearms/"):
            item_id = path.split("/api/firearms/")[1]
            db = load_db()
            items = db.get("firearms", [])
            initial_count = len(items)
            db["firearms"] = [it for it in items if it.get("id") != item_id]

            if len(db["firearms"]) == initial_count:
                self.send_error_json(404, "Firearm not found.")
                return

            db.setdefault("deletedIds", []).append(item_id)
            save_db(db)
            self.send_json(200, {"success": True, "deleted": item_id})
            return

        self.send_error_json(404, "Endpoint not found")

def main():
    threading.Thread(target=backup_worker, daemon=True).start()
    threading.Thread(target=code_reload_watcher, daemon=True).start()
    threading.Thread(target=ccw_reminder_worker, daemon=True).start()
    server_address = ("0.0.0.0", PORT)
    httpd = HTTPServer(server_address, RequestHandler)
    print(f"[FIREARMS INVENTORY] Running on port {PORT}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

if __name__ == "__main__":
    main()
