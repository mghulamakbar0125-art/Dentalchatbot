import json
import os
import re
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bot import (
    get_dental_answer, init_db, save_lead, save_booking,
    send_handoff_email, send_booking_email, append_lead_to_sheet
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

conversations = {}
init_db()


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_clients():
    with open("clients.json", "r") as f:
        return json.load(f)

def save_clients(data):
    with open("clients.json", "w") as f:
        json.dump(data, f, indent=2)

def make_client_id(name: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", name.lower().strip())[:40]


# ── Public routes ─────────────────────────────────────────────────────────────

@app.get("/widget.js")
async def serve_widget():
    with open("widget.js", "r") as f:
        return Response(f.read(), media_type="application/javascript")

@app.get("/client/{client_id}/info")
async def client_info(client_id: str):
    clients = load_clients()
    if client_id not in clients:
        raise HTTPException(status_code=404, detail="Clinic not found.")
    return {"name": clients[client_id]["name"]}

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse("""
    <!DOCTYPE html><html><head><meta charset="UTF-8"><title>Dental AI</title>
    <style>body{font-family:Arial,sans-serif;display:flex;align-items:center;
    justify-content:center;min-height:100vh;background:#f0f4f8;margin:0;}
    .box{text-align:center;background:#fff;padding:40px;border-radius:14px;
    box-shadow:0 2px 12px rgba(0,0,0,.1);}h1{color:#1a73e8;margin-bottom:12px;}
    p{color:#555;}</style></head><body>
    <div class="box"><h1>Dental AI Platform</h1>
    <p>Please use your specific clinic link to access the chatbot.</p>
    <p style="margin-top:16px;font-size:.9rem;color:#aaa;">
    Admin: <a href="/admin" style="color:#1a73e8;">/admin</a></p>
    </div></body></html>
    """)

@app.get("/{client_id}/chat", response_class=HTMLResponse)
async def chat_page(client_id: str):
    clients = load_clients()
    if client_id not in clients:
        raise HTTPException(status_code=404, detail="Clinic not found.")
    clinic_name = clients[client_id]["name"]
    with open("chat.html", "r") as f:
        html = f.read()
    html = html.replace("{{CLIENT_ID}}", client_id).replace("{{CLIENT_NAME}}", clinic_name)
    return HTMLResponse(html)

@app.get("/ask/{client_id}")
async def ask_bot(client_id: str, question: str, session_id: str = "default"):
    clients = load_clients()
    if client_id not in clients:
        raise HTTPException(status_code=404, detail="Clinic not found.")

    cfg = clients[client_id]
    key = f"{client_id}:{session_id}"
    if key not in conversations:
        conversations[key] = []

    conversations[key].append({"role": "user", "content": question})
    answer, handoff, lead_data, booking_data = get_dental_answer(conversations[key], cfg, client_id)
    conversations[key].append({"role": "assistant", "content": answer})

    if lead_data:
        name  = lead_data.get("name", "")
        phone = lead_data.get("phone", "")
        email = lead_data.get("email", "")
        save_lead(client_id, name, phone, email)
        append_lead_to_sheet(client_id, name, phone, email)

    if booking_data:
        name      = booking_data.get("name", "")
        phone     = booking_data.get("phone", "")
        date      = booking_data.get("date", "")
        treatment = booking_data.get("treatment", "")
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
    if password != os.getenv("ADMIN_PASSWORD", ""):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return load_clients()

class ClientPayload(BaseModel):
    password: str
    client_id: str = ""
    name: str
    website: str
    email: str
    calendly: str = ""
    description: str = ""

@app.post("/admin/clients")
async def add_client(payload: ClientPayload):
    if payload.password != os.getenv("ADMIN_PASSWORD", ""):
        raise HTTPException(status_code=401, detail="Wrong password")
    if not payload.name or not payload.website or not payload.email:
        raise HTTPException(status_code=400, detail="Name, website, and email are required.")
    clients = load_clients()
    cid = payload.client_id.strip() or make_client_id(payload.name)
    clients[cid] = {
        "name": payload.name,
        "website": payload.website,
        "email": payload.email,
        "calendly": payload.calendly,
        "description": payload.description,
    }
    save_clients(clients)
    return {"success": True, "client_id": cid}

@app.delete("/admin/clients/{client_id}")
async def delete_client(client_id: str, password: str = ""):
    if password != os.getenv("ADMIN_PASSWORD", ""):
        raise HTTPException(status_code=401, detail="Unauthorized")
    clients = load_clients()
    if client_id not in clients:
        raise HTTPException(status_code=404, detail="Client not found")
    del clients[client_id]
    save_clients(clients)
    return {"success": True}
