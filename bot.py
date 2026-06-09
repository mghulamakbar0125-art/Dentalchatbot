import os
import json
import sqlite3
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from openai import OpenAI
from langchain_community.document_loaders import WebBaseLoader
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY) if API_KEY else None

_website_cache = {}


# ── Website Scraping ──────────────────────────────────────────────────────────

def get_website_content(client_id, url):
    if client_id not in _website_cache:
        try:
            loader = WebBaseLoader(url)
            docs = loader.load()
            _website_cache[client_id] = " ".join([d.page_content for d in docs])[:8000]
        except Exception:
            _website_cache[client_id] = ""
    return _website_cache[client_id]


# ── SQLite ────────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect("database.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT,
            name TEXT,
            phone TEXT,
            email TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT,
            name TEXT,
            phone TEXT,
            date TEXT,
            treatment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_lead(client_id, name, phone, email, notes=""):
    conn = sqlite3.connect("database.db")
    conn.execute(
        "INSERT INTO leads (client_id, name, phone, email, notes) VALUES (?, ?, ?, ?, ?)",
        (client_id, name, phone, email, notes)
    )
    conn.commit()
    conn.close()

def save_booking(client_id, name, phone, date, treatment):
    conn = sqlite3.connect("database.db")
    conn.execute(
        "INSERT INTO bookings (client_id, name, phone, date, treatment) VALUES (?, ?, ?, ?, ?)",
        (client_id, name, phone, date, treatment)
    )
    conn.commit()
    conn.close()


# ── Google Sheets ─────────────────────────────────────────────────────────────

def append_lead_to_sheet(client_id, name, phone, email):
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    creds_json = os.getenv("GOOGLE_CREDENTIALS")
    if not sheet_id or not creds_json:
        return

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        creds_dict = json.loads(creds_json)
        scopes = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(sheet_id)
        worksheet = sh.sheet1
        worksheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            client_id, name, phone, email
        ])
    except Exception:
        pass


# ── Email Helpers ─────────────────────────────────────────────────────────────

def _send_email(to_email, subject, body):
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    if not all([to_email, sender_email, sender_password]):
        return False
    try:
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = to_email
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
        return True
    except Exception:
        return False

def send_handoff_email(clinic_email, patient_name, phone):
    subject = f"Urgent: Patient {patient_name} Needs Help"
    body = (
        f"URGENT: A patient requires immediate assistance.\n\n"
        f"Patient Name: {patient_name}\n"
        f"Phone Number: {phone}\n\n"
        f"Please contact them as soon as possible."
    )
    return _send_email(clinic_email, subject, body)

def send_booking_email(clinic_email, clinic_name, name, phone, date, treatment):
    subject = f"New Appointment Request — {name}"
    body = (
        f"A patient has requested an appointment at {clinic_name}.\n\n"
        f"Patient Name:  {name}\n"
        f"Phone Number:  {phone}\n"
        f"Preferred Date/Time: {date}\n"
        f"Treatment:     {treatment}\n\n"
        f"Please confirm the appointment with the patient."
    )
    return _send_email(clinic_email, subject, body)


# ── System Prompt ─────────────────────────────────────────────────────────────

def build_system_prompt(clinic_name, calendly, description):
    return f"""You are a professional, warm, and empathetic AI assistant for {clinic_name}.

About the clinic: {description}

Your goals in every conversation:
1. Answer patient questions accurately using your knowledge of the practice.
2. Naturally collect their **Full Name**, **Phone Number**, and **Email Address** during the conversation — do this warmly, not like a form.
3. If someone wants to book an appointment, collect their name, phone, preferred date/time, and the treatment needed. Share the booking link: {calendly}
   Once you have name + phone + date + treatment, include this tag at the END: [BOOKING:name=NAME,phone=PHONE,date=DATE,treatment=TREATMENT]
4. If a patient seems frustrated or asks for a real person, respond with empathy and include at the END: [HANDOFF]
5. Once you have captured name AND phone AND email, include at the END: [LEAD:name=NAME,phone=PHONE,email=EMAIL]
   (Replace with actual values. No spaces around = signs.)

Formatting:
- Use **bold** for treatment names, prices, contact details, and key facts.
- Keep responses friendly and concise.

Strict rules:
- NEVER mention websites, scraping, data sources, or external references.
- Speak as a knowledgeable team member of {clinic_name}.
- If you don't know something: "Let me have our team confirm that — could I take your contact details?"
"""


# ── Main Answer Function ──────────────────────────────────────────────────────

def _extract_tag(text, tag_name):
    """Extract and remove [TAG:key=val,...] from text. Returns (cleaned_text, dict or None)."""
    marker = f"[{tag_name}:"
    if marker not in text:
        return text, None
    try:
        start = text.index(marker)
        end = text.index("]", start) + 1
        raw = text[start:end]
        inner = raw[len(marker):-1]
        data = dict(p.split("=", 1) for p in inner.split(",") if "=" in p)
        text = text.replace(raw, "").strip()
        return text, data
    except Exception:
        return text, None


def get_dental_answer(messages, client_config, client_id):
    if not client:
        return "Bot is not configured. Please contact the clinic directly.", False, None, None

    try:
        content = get_website_content(client_id, client_config["website"])
        system = build_system_prompt(
            client_config["name"],
            client_config.get("calendly", ""),
            client_config.get("description", ""),
        ) + f"\n\nPractice Knowledge:\n{content}"

        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "system", "content": system}] + messages,
        )

        text = response.choices[0].message.content

        handoff = "[HANDOFF]" in text
        text = text.replace("[HANDOFF]", "").strip()

        text, lead_data = _extract_tag(text, "LEAD")
        text, booking_data = _extract_tag(text, "BOOKING")

        return text, handoff, lead_data, booking_data

    except Exception as e:
        err = str(e)
        if "429" in err or "rate" in err.lower() or "quota" in err.lower():
            return "Sorry, I'm temporarily unavailable. Please **call us directly**.", False, None, None
        if "401" in err or "authentication" in err.lower():
            return "Service configuration error. Please contact the clinic directly.", False, None, None
        if "credit" in err.lower() or "balance" in err.lower():
            return "Sorry, I'm temporarily unavailable. Please **call us directly**.", False, None, None
        return "Something went wrong. Please try again.", False, None, None
