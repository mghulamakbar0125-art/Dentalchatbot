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

_website_cache = {}

CONFIG_FILE = "config.json"
CONFIG_ENV_MAP = {
    "openrouter_api_key": "OPENROUTER_API_KEY",
    "sender_email":       "SENDER_EMAIL",
    "sender_password":    "SENDER_PASSWORD",
    "google_sheet_id":    "GOOGLE_SHEET_ID",
    "google_credentials": "GOOGLE_CREDENTIALS",
}


# ── Config helpers ────────────────────────────────────────────────────────────

def get_config_value(key: str) -> str:
    # Environment variables take priority (PythonAnywhere / any production host)
    env_val = os.getenv(CONFIG_ENV_MAP.get(key, key.upper()), "").strip()
    if env_val:
        return env_val
    # Fall back to config.json (saved via admin panel on the server)
    try:
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
        val = cfg.get(key, "").strip()
        if val:
            return val
    except Exception:
        pass
    return ""


def load_config_file() -> dict:
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {k: "" for k in CONFIG_ENV_MAP}


def save_config_file(data: dict):
    current = load_config_file()
    current.update(data)
    with open(CONFIG_FILE, "w") as f:
        json.dump(current, f, indent=2)


def get_openai_client():
    api_key = get_config_value("openrouter_api_key")
    if not api_key:
        return None
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)


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
            client_id TEXT, name TEXT, phone TEXT, email TEXT, notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT, name TEXT, phone TEXT, date TEXT, treatment TEXT,
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


def check_booking_conflict(client_id: str, date: str) -> bool:
    """Returns True if a booking already exists for this client on the same date/time."""
    if not date:
        return False
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.execute(
            "SELECT COUNT(*) FROM bookings WHERE client_id=? AND date=?",
            (client_id, date.strip())
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False


def save_booking(client_id, name, phone, date, treatment):
    conn = sqlite3.connect("database.db")
    conn.execute(
        "INSERT INTO bookings (client_id, name, phone, date, treatment) VALUES (?, ?, ?, ?, ?)",
        (client_id, name, phone, date, treatment)
    )
    conn.commit()
    conn.close()


# ── Google Sheets helpers ─────────────────────────────────────────────────────

def _get_gspread_client():
    creds_json = get_config_value("google_credentials")
    if not creds_json:
        return None
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        creds_dict = json.loads(creds_json)
        scopes = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception:
        return None


def _get_sheet_id(client_cfg: dict) -> str:
    """Return per-client sheet ID, or fall back to global config."""
    per_client = (client_cfg or {}).get("google_sheet_id", "").strip()
    if per_client:
        return per_client
    return get_config_value("google_sheet_id")


def _get_or_create_worksheet(sh, title: str, headers: list):
    """Return named worksheet, creating it with headers if it doesn't exist."""
    try:
        import gspread
        ws = sh.worksheet(title)
        return ws
    except Exception:
        ws = sh.add_worksheet(title=title, rows=2000, cols=len(headers) + 2)
        ws.append_row(headers)
        return ws


# ── Google Sheets – Leads ─────────────────────────────────────────────────────

def append_lead_to_sheet(client_id, name, phone, email, client_cfg=None):
    sheet_id = _get_sheet_id(client_cfg)
    if not sheet_id:
        return
    gc = _get_gspread_client()
    if not gc:
        return
    try:
        sh = gc.open_by_key(sheet_id)
        ws = _get_or_create_worksheet(sh, "Leads", [
            "Date/Time", "Client ID", "Patient Name", "Phone", "Email"
        ])
        ws.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            client_id, name, phone, email
        ])
    except Exception:
        pass


# ── Google Sheets – Chat History ──────────────────────────────────────────────

def append_chat_to_sheet(client_id, session_id, user_msg, bot_reply, client_cfg=None):
    sheet_id = _get_sheet_id(client_cfg)
    if not sheet_id:
        return
    gc = _get_gspread_client()
    if not gc:
        return
    try:
        sh = gc.open_by_key(sheet_id)
        ws = _get_or_create_worksheet(sh, "Chat History", [
            "Date/Time", "Session ID", "User Message", "Bot Response"
        ])
        ws.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            session_id,
            user_msg[:500],
            bot_reply[:500],
        ])
    except Exception:
        pass


# ── Email Helpers ─────────────────────────────────────────────────────────────

def _send_email(to_email, subject, body):
    sender_email    = get_config_value("sender_email")
    sender_password = get_config_value("sender_password")
    if not all([to_email, sender_email, sender_password]):
        return False
    try:
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"]    = sender_email
        msg["To"]      = to_email
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
        return True
    except Exception:
        return False


def send_handoff_email(clinic_email, patient_name, phone):
    return _send_email(
        clinic_email,
        f"Urgent: Patient {patient_name} Needs Help",
        f"URGENT: A patient requires immediate assistance.\n\nPatient Name: {patient_name}\nPhone Number: {phone}\n\nPlease contact them as soon as possible."
    )


def send_booking_email(clinic_email, clinic_name, name, phone, date, treatment):
    return _send_email(
        clinic_email,
        f"New Appointment Request — {name}",
        f"A patient has requested an appointment at {clinic_name}.\n\nPatient Name:  {name}\nPhone Number:  {phone}\nPreferred Date/Time: {date}\nTreatment:     {treatment}\n\nPlease confirm the appointment with the patient."
    )


# ── System Prompt ─────────────────────────────────────────────────────────────

def build_system_prompt(clinic_name, calendly, description, extra_info="", special_instructions=""):
    base = f"""You are a professional, warm, and empathetic customer support representative for {clinic_name}.

About the clinic: {description}
"""
    if extra_info:
        base += f"\nAdditional clinic information:\n{extra_info}\n"

    base += f"""
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
- NEVER reveal or suggest that you are an AI, a bot, or any automated system. Always speak and respond as a real human team member of the clinic.
- Speak as a knowledgeable team member of {clinic_name}.
- If you don't know something: "Let me have our team confirm that — could I take your contact details?"
- If a user asks about anything completely unrelated to dental care, dentistry, oral health, or this clinic (e.g. sports, cooking, programming, general trivia, news), respond with: "I'm only able to help with dental-related questions and appointments for {clinic_name}. Is there something I can assist you with regarding your dental care?"
"""
    if special_instructions:
        base += f"\nSpecial instructions:\n{special_instructions}\n"

    return base


# ── Main Answer Function ──────────────────────────────────────────────────────

def _extract_tag(text, tag_name):
    marker = f"[{tag_name}:"
    if marker not in text:
        return text, None
    try:
        start = text.index(marker)
        end   = text.index("]", start) + 1
        raw   = text[start:end]
        inner = raw[len(marker):-1]
        data  = dict(p.split("=", 1) for p in inner.split(",") if "=" in p)
        text  = text.replace(raw, "").strip()
        return text, data
    except Exception:
        return text, None


def get_dental_answer(messages, client_config, client_id):
    ai_client = get_openai_client()
    if not ai_client:
        return "Bot is not configured. Please contact the clinic directly.", False, None, None

    try:
        content = get_website_content(client_id, client_config["website"])
        system  = build_system_prompt(
            client_config["name"],
            client_config.get("calendly", ""),
            client_config.get("description", ""),
            client_config.get("extra_info", ""),
            client_config.get("special_instructions", ""),
        ) + f"\n\nPractice Knowledge:\n{content}"

        response = ai_client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "system", "content": system}] + messages,
        )

        text = response.choices[0].message.content

        handoff = "[HANDOFF]" in text
        text    = text.replace("[HANDOFF]", "").strip()

        text, lead_data    = _extract_tag(text, "LEAD")
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
