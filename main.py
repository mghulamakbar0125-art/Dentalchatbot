import json
import os
import re
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from bot import (
    get_dental_answer, init_db, save_lead, save_booking,
    send_handoff_email, send_booking_email,
    append_lead_to_sheet, append_chat_to_sheet,
    load_config_file, save_config_file, check_booking_conflict
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

conversations = {}
init_db()

CLIENT_DEFAULTS = {
    "color":                "#1a73e8",
    "bot_name":             "Support Team",
    "bot_avatar":           "",
    "bg_color":             "#f0f4f8",
    "bg_image":             "",
    "extra_info":           "",
    "special_instructions": "",
    "google_sheet_id":      "",
    "phone":                "",
    "office_open":          "09:00",
    "office_close":         "17:00",
    "office_days":          "1,2,3,4,5",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_clients():
    with open("clients.json", "r") as f:
        return json.load(f)

def save_clients(data):
    with open("clients.json", "w") as f:
        json.dump(data, f, indent=2)

def make_client_id(name: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", name.lower().strip())[:40]

def client_with_defaults(cfg: dict) -> dict:
    result = dict(cfg)
    for k, v in CLIENT_DEFAULTS.items():
        if k not in result or result[k] is None:
            result[k] = v
    return result

def check_password(password: str):
    if password != os.getenv("ADMIN_PASSWORD", ""):
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── Public routes ─────────────────────────────────────────────────────────────

@app.get("/widget.js")
async def serve_widget():
    with open("widget.js", "r") as f:
        return Response(
            f.read(),
            media_type="application/javascript",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET",
                "Cache-Control": "public, max-age=60",
            }
        )

@app.get("/client/{client_id}/info")
async def client_info(client_id: str):
    clients = load_clients()
    if client_id not in clients:
        raise HTTPException(status_code=404, detail="Clinic not found.")
    cfg = client_with_defaults(clients[client_id])
    return {
        "name":         cfg["name"],
        "color":        cfg["color"],
        "bot_name":     cfg["bot_name"],
        "bot_avatar":   cfg["bot_avatar"],
        "phone":        cfg.get("phone", ""),
        "office_open":  cfg.get("office_open", "09:00"),
        "office_close": cfg.get("office_close", "17:00"),
        "office_days":  cfg.get("office_days", "1,2,3,4,5"),
    }

@app.get("/", response_class=HTMLResponse)
async def home():
    with open("index.html", "r") as f:
        return HTMLResponse(f.read())

@app.get("/{client_id}/chat", response_class=HTMLResponse)
async def chat_page(client_id: str):
    clients = load_clients()
    if client_id not in clients:
        raise HTTPException(status_code=404, detail="Clinic not found.")
    cfg = client_with_defaults(clients[client_id])
    with open("chat.html", "r") as f:
        html = f.read()

    avatar_url = cfg["bot_avatar"]
    if avatar_url:
        avatar_html = f'<img src="{avatar_url}" alt="Bot" class="bot-avatar-img" onerror="this.style.display=\'none\'">'
    else:
        avatar_html = '<div class="bot-avatar-placeholder"><svg viewBox="0 0 24 24"><path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z"/></svg></div>'

    bg_image_css = f"background-image: url('{cfg['bg_image']}'); background-size: cover; background-position: center;" if cfg["bg_image"] else ""

    phone = cfg.get("phone", "").strip()
    call_btn_html = (
        f'<a id="call-btn" href="tel:{phone}">'
        f'<svg viewBox="0 0 24 24"><path d="M6.6 10.8c1.4 2.8 3.8 5.1 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1-9.4 0-17-7.6-17-17 0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.3.2 2.5.6 3.6.1.3 0 .7-.2 1L6.6 10.8z"/></svg>'
        f' Call Us</a>'
    ) if phone else ""
    office_days_js = cfg.get("office_days", "1,2,3,4,5")

    html = (html
        .replace("{{CLIENT_ID}}",      client_id)
        .replace("{{CLIENT_NAME}}",    cfg["name"])
        .replace("{{PRIMARY_COLOR}}",  cfg["color"])
        .replace("{{BOT_NAME}}",       cfg["bot_name"])
        .replace("{{BOT_AVATAR}}",     avatar_url)
        .replace("{{BOT_AVATAR_HTML}}", avatar_html)
        .replace("{{BG_COLOR}}",       cfg["bg_color"])
        .replace("{{BG_IMAGE_CSS}}",   bg_image_css)
        .replace("{{PHONE}}",          phone)
        .replace("{{OFFICE_OPEN}}",    cfg.get("office_open", "09:00"))
        .replace("{{OFFICE_CLOSE}}",   cfg.get("office_close", "17:00"))
        .replace("{{OFFICE_DAYS_JS}}", office_days_js)
        .replace("{{CALL_BTN_HTML}}",  call_btn_html)
    )
    return HTMLResponse(html)

@app.get("/ask/{client_id}")
async def ask_bot(client_id: str, question: str, session_id: str = "default"):
    clients = load_clients()
    if client_id not in clients:
        raise HTTPException(status_code=404, detail="Clinic not found.")

    cfg = client_with_defaults(clients[client_id])
    key = f"{client_id}:{session_id}"
    if key not in conversations:
        conversations[key] = []

    conversations[key].append({"role": "user", "content": question})
    answer, handoff, lead_data, booking_data = get_dental_answer(conversations[key], cfg, client_id)
    conversations[key].append({"role": "assistant", "content": answer})

    # Log chat to Google Sheets in background (non-blocking)
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, append_chat_to_sheet, client_id, session_id, question, answer, cfg)

    if lead_data:
        name  = lead_data.get("name", "")
        phone = lead_data.get("phone", "")
        email = lead_data.get("email", "")
        save_lead(client_id, name, phone, email)
        loop.run_in_executor(None, append_lead_to_sheet, client_id, name, phone, email, cfg)

    if booking_data:
        name      = booking_data.get("name", "")
        phone     = booking_data.get("phone", "")
        date      = booking_data.get("date", "")
        treatment = booking_data.get("treatment", "")
        if check_booking_conflict(client_id, date):
            answer = (f"I'm sorry, that time slot ({date}) is already booked. "
                      f"Could you please choose a different date or time? "
                      f"I want to make sure we can fit you in!")
            conversations[key][-1]["content"] = answer
            return {"answer": answer, "handoff": False}
        save_booking(client_id, name, phone, date, treatment)
        send_booking_email(cfg["email"], cfg["name"], name, phone, date, treatment)

    if handoff:
        n = lead_data.get("name", "Unknown") if lead_data else "Unknown"
        p = lead_data.get("phone", "Not provided") if lead_data else "Not provided"
        send_handoff_email(cfg["email"], n, p)

    return {"answer": answer, "handoff": handoff}


# ── Admin routes ──────────────────────────────────────────────────────────────

@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    with open("admin.html", "r") as f:
        return f.read()

@app.get("/admin/clients")
async def admin_list_clients(password: str = ""):
    check_password(password)
    clients = load_clients()
    return {cid: client_with_defaults(cfg) for cid, cfg in clients.items()}


class ClientPayload(BaseModel):
    password: str
    client_id: str = ""
    name: str
    website: str
    email: str
    calendly: str = ""
    description: str = ""
    extra_info: str = ""
    special_instructions: str = ""
    color: str = "#1a73e8"
    bot_name: str = "Support Team"
    bot_avatar: str = ""
    bg_color: str = "#f0f4f8"
    bg_image: str = ""
    google_sheet_id: str = ""
    phone: str = ""
    office_open: str = "09:00"
    office_close: str = "17:00"
    office_days: str = "1,2,3,4,5"

def _client_dict_from_payload(p: ClientPayload) -> dict:
    return {
        "name":                 p.name,
        "website":              p.website,
        "email":                p.email,
        "calendly":             p.calendly,
        "description":          p.description,
        "extra_info":           p.extra_info,
        "special_instructions": p.special_instructions,
        "color":                p.color or "#1a73e8",
        "bot_name":             p.bot_name or "Support Team",
        "bot_avatar":           p.bot_avatar,
        "bg_color":             p.bg_color or "#f0f4f8",
        "bg_image":             p.bg_image,
        "google_sheet_id":      p.google_sheet_id,
        "phone":                p.phone,
        "office_open":          p.office_open or "09:00",
        "office_close":         p.office_close or "17:00",
        "office_days":          p.office_days or "1,2,3,4,5",
    }

@app.post("/admin/clients")
async def add_client(payload: ClientPayload):
    check_password(payload.password)
    if not payload.name or not payload.website or not payload.email:
        raise HTTPException(status_code=400, detail="Name, website, and email are required.")
    clients = load_clients()
    cid = payload.client_id.strip() or make_client_id(payload.name)
    clients[cid] = _client_dict_from_payload(payload)
    save_clients(clients)
    return {"success": True, "client_id": cid}

@app.put("/admin/clients/{client_id}")
async def update_client(client_id: str, payload: ClientPayload):
    check_password(payload.password)
    clients = load_clients()
    if client_id not in clients:
        raise HTTPException(status_code=404, detail="Client not found")
    clients[client_id] = _client_dict_from_payload(payload)
    save_clients(clients)
    return {"success": True}

@app.delete("/admin/clients/{client_id}")
async def delete_client(client_id: str, password: str = ""):
    check_password(password)
    clients = load_clients()
    if client_id not in clients:
        raise HTTPException(status_code=404, detail="Client not found")
    del clients[client_id]
    save_clients(clients)
    return {"success": True}


# ── Plans routes ──────────────────────────────────────────────────────────────

PLANS_FILE = "plans.json"

def load_plans():
    if not os.path.exists(PLANS_FILE):
        return []
    with open(PLANS_FILE, "r") as f:
        return json.load(f)

def save_plans(data):
    with open(PLANS_FILE, "w") as f:
        json.dump(data, f, indent=2)

@app.get("/plans")
async def get_plans_public():
    return load_plans()

@app.get("/admin/plans")
async def get_plans(password: str = ""):
    check_password(password)
    return load_plans()

class PlansPayload(BaseModel):
    password: str
    plans: list

@app.post("/admin/plans")
async def save_plans_route(payload: PlansPayload):
    check_password(payload.password)
    save_plans(payload.plans)
    return {"success": True}


# ── Settings routes ───────────────────────────────────────────────────────────

@app.get("/admin/settings")
async def get_settings(password: str = ""):
    check_password(password)
    cfg = load_config_file()
    return {
        "openrouter_api_key": cfg.get("openrouter_api_key", ""),
        "sender_email":       cfg.get("sender_email", ""),
        "sender_password":    cfg.get("sender_password", ""),
        "google_sheet_id":    cfg.get("google_sheet_id", ""),
        "google_credentials": cfg.get("google_credentials", ""),
    }

class SettingsPayload(BaseModel):
    password: str
    openrouter_api_key: Optional[str] = ""
    sender_email:       Optional[str] = ""
    sender_password:    Optional[str] = ""
    google_sheet_id:    Optional[str] = ""
    google_credentials: Optional[str] = ""

@app.post("/admin/settings")
async def save_settings(payload: SettingsPayload):
    check_password(payload.password)
    save_config_file({
        "openrouter_api_key": payload.openrouter_api_key or "",
        "sender_email":       payload.sender_email or "",
        "sender_password":    payload.sender_password or "",
        "google_sheet_id":    payload.google_sheet_id or "",
        "google_credentials": payload.google_credentials or "",
    })
    return {"success": True}
