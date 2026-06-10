(function () {
  const script =
    document.currentScript ||
    (function () {
      const s = document.getElementsByTagName("script");
      return s[s.length - 1];
    })();

  const CLIENT_ID   = script.getAttribute("data-client-id");
  const DATA_COLOR  = script.getAttribute("data-color");
  const DATA_AVATAR = script.getAttribute("data-avatar");
  const BASE_URL    = new URL(script.src).origin;
  const SESSION_ID  = Math.random().toString(36).substring(2);

  if (!CLIENT_ID) {
    console.error("[DentalWidget] data-client-id is required.");
    return;
  }

  let BRAND_COLOR  = DATA_COLOR || "#1a73e8";
  let PHONE        = "";
  let OFFICE_OPEN  = "09:00";
  let OFFICE_CLOSE = "17:00";
  let OFFICE_DAYS  = [1, 2, 3, 4, 5];

  function hexToRgb(hex) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `${r},${g},${b}`;
  }
  function getContrastColor(hex) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    return luminance > 0.55 ? "#111111" : "#ffffff";
  }
  function hhmm() {
    const d = new Date();
    return d.getHours().toString().padStart(2, "0") + ":" +
           d.getMinutes().toString().padStart(2, "0");
  }
  function isOfficeOpen() {
    const now  = new Date(), day = now.getDay();
    const mins = now.getHours() * 60 + now.getMinutes();
    const [oh, om] = OFFICE_OPEN.split(":").map(Number);
    const [ch, cm] = OFFICE_CLOSE.split(":").map(Number);
    return OFFICE_DAYS.includes(day) && mins >= oh * 60 + om && mins < ch * 60 + cm;
  }

  const styleEl = document.createElement("style");
  styleEl.id = "dw-styles";
  document.head.appendChild(styleEl);

  function applyStyles(color) {
    const rgb = hexToRgb(color);
    const textColor = getContrastColor(color);
    const closeAlpha = textColor === "#ffffff" ? "rgba(255,255,255,0.2)" : "rgba(0,0,0,0.1)";
    const closeHoverAlpha = textColor === "#ffffff" ? "rgba(255,255,255,0.35)" : "rgba(0,0,0,0.2)";
    styleEl.textContent = `
    #dw-bubble {
      position: fixed; bottom: 24px; right: 24px; z-index: 99999;
      width: 60px; height: 60px; border-radius: 50%;
      background: ${color};
      box-shadow: 0 4px 20px rgba(${rgb}, 0.5);
      cursor: pointer; display: flex; align-items: center; justify-content: center;
      transition: transform 0.2s, box-shadow 0.2s; border: none; outline: none;
    }
    #dw-bubble:hover { transform: scale(1.08); box-shadow: 0 6px 28px rgba(${rgb}, 0.65); }
    #dw-bubble svg { width: 28px; height: 28px; fill: #fff; }

    #dw-card {
      position: fixed; bottom: 96px; right: 24px; z-index: 99998;
      width: 380px; max-width: calc(100vw - 48px);
      background: #fff; border-radius: 18px;
      box-shadow: 0 8px 40px rgba(0,0,0,0.18);
      display: flex; flex-direction: column; overflow: hidden;
      transform: scale(0.92) translateY(20px); opacity: 0; pointer-events: none;
      transition: transform 0.25s cubic-bezier(.34,1.56,.64,1), opacity 0.2s ease;
      max-height: 600px;
    }
    #dw-card.dw-open { transform: scale(1) translateY(0); opacity: 1; pointer-events: all; }

    #dw-header {
      background: ${color}; color: ${textColor}; padding: 14px 16px;
      display: flex; align-items: center; gap: 10px; flex-shrink: 0;
    }
    #dw-avatar {
      width: 38px; height: 38px; border-radius: 50%;
      background: rgba(255,255,255,0.25);
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0; overflow: hidden;
    }
    #dw-avatar svg { width: 20px; height: 20px; fill: ${textColor}; }
    #dw-avatar img { width: 38px; height: 38px; object-fit: cover; border-radius: 50%; }
    #dw-header-text { flex: 1; min-width: 0; }
    #dw-header-title { font-weight: 700; font-size: 0.95rem; font-family: Arial, sans-serif; }
    #dw-header-sub {
      font-size: 0.72rem; opacity: 0.92; font-family: Arial, sans-serif;
      margin-top: 2px; display: flex; align-items: center; gap: 4px;
    }
    .dw-status-dot {
      width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; display: inline-block;
    }
    .dw-status-dot.online  { background: #4ade80; box-shadow: 0 0 0 2px rgba(74,222,128,0.3); }
    .dw-status-dot.offline { background: rgba(255,255,255,0.5); }
    #dw-call-hdr {
      display: none; align-items: center; gap: 5px;
      background: rgba(255,255,255,0.18); color: ${textColor};
      border: 1.5px solid rgba(255,255,255,0.45); border-radius: 18px;
      padding: 5px 12px; font-size: 0.78rem; font-weight: 700;
      font-family: Arial, sans-serif; text-decoration: none;
      white-space: nowrap; transition: background 0.15s; flex-shrink: 0;
    }
    #dw-call-hdr:hover { background: rgba(255,255,255,0.3); }
    #dw-call-hdr svg { width: 13px; height: 13px; fill: ${textColor}; flex-shrink: 0; }
    #dw-close {
      background: ${closeAlpha}; border: none; color: ${textColor};
      width: 30px; height: 30px; border-radius: 50%; cursor: pointer;
      font-size: 1.1rem; display: flex; align-items: center; justify-content: center;
      transition: background 0.15s; flex-shrink: 0;
    }
    #dw-close:hover { background: ${closeHoverAlpha}; }

    #dw-messages {
      flex: 1; overflow-y: auto; padding: 16px;
      display: flex; flex-direction: column; gap: 10px;
      background: #f7f9fc; min-height: 260px; max-height: 340px;
    }
    #dw-messages::-webkit-scrollbar { width: 4px; }
    #dw-messages::-webkit-scrollbar-thumb { background: #ddd; border-radius: 4px; }

    .dw-msg-row { display: flex; flex-direction: column; gap: 2px; }
    .dw-msg-row.dw-user { align-items: flex-end; }
    .dw-msg-row.dw-bot  { align-items: flex-start; }

    .dw-bubble-msg {
      max-width: 82%; padding: 9px 13px; border-radius: 16px;
      font-size: 0.875rem; line-height: 1.5; word-wrap: break-word;
      font-family: Arial, sans-serif;
    }
    .dw-user .dw-bubble-msg {
      background: ${color}; color: #fff; border-bottom-right-radius: 4px;
    }
    .dw-bot .dw-bubble-msg {
      background: #fff; color: #202124; border-bottom-left-radius: 4px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }
    .dw-bot .dw-bubble-msg strong { font-weight: 700; }
    .dw-bot .dw-bubble-msg a { color: ${color}; text-decoration: underline; }
    .dw-timestamp { font-size: 0.68rem; color: #aaa; padding: 0 4px; font-family: Arial, sans-serif; }

    .dw-typing {
      background: #fff; color: #aaa; font-style: italic;
      border-bottom-left-radius: 4px; box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }
    .dw-handoff {
      background: #fff8e1; border: 1px solid #ffd54f; color: #795548;
      border-radius: 10px; padding: 8px 12px; font-size: 0.8rem;
      text-align: center; font-family: Arial, sans-serif;
    }

    .dw-quick-replies {
      display: flex; flex-wrap: wrap; gap: 6px;
      padding: 2px 0 4px;
    }
    .dw-qr-btn {
      background: #fff; color: ${color};
      border: 1.5px solid ${color};
      border-radius: 16px; padding: 5px 11px;
      font-size: 0.76rem; cursor: pointer;
      font-family: Arial, sans-serif;
      transition: background 0.15s, color 0.15s;
      white-space: nowrap;
    }
    .dw-qr-btn:hover { background: ${color}; color: #fff; }

    #dw-call-bar {
      padding: 10px 14px; background: #f8faf8;
      border-top: 1px solid #eef0ee;
      display: flex; align-items: center; justify-content: center;
      gap: 10px; flex-shrink: 0; flex-direction: column;
    }
    #dw-call-btn {
      display: flex; align-items: center; justify-content: center; gap: 8px;
      background: #22c55e; color: #fff; border: none;
      border-radius: 22px; padding: 9px 28px; cursor: pointer;
      font-size: 0.85rem; font-family: Arial, sans-serif; font-weight: 600;
      text-decoration: none; transition: filter 0.15s; width: 100%; max-width: 220px;
    }
    #dw-call-btn:hover { filter: brightness(0.9); }
    #dw-call-btn svg { width: 15px; height: 15px; fill: #fff; flex-shrink: 0; }
    #dw-call-label { font-size: 0.72rem; color: #aaa; font-family: Arial, sans-serif; text-align: center; }

    #dw-footer {
      padding: 10px 12px; background: #fff;
      border-top: 1px solid #f0f0f0; display: flex; gap: 8px; align-items: center;
      flex-shrink: 0;
    }
    #dw-input {
      flex: 1; padding: 9px 14px; border: 1.5px solid #e0e0e0;
      border-radius: 22px; font-size: 0.875rem; outline: none;
      font-family: Arial, sans-serif; transition: border-color 0.15s; color: #202124;
    }
    #dw-input:focus { border-color: ${color}; }
    #dw-send {
      width: 38px; height: 38px; border-radius: 50%; background: ${color};
      border: none; cursor: pointer; display: flex; align-items: center;
      justify-content: center; flex-shrink: 0;
      transition: filter 0.15s, transform 0.1s;
    }
    #dw-send:hover { filter: brightness(0.9); }
    #dw-send:active { transform: scale(0.93); }
    #dw-send:disabled { background: #ccc; cursor: not-allowed; }
    #dw-send svg { width: 18px; height: 18px; fill: #fff; }
    #dw-branding {
      text-align: center; font-size: 0.65rem; color: #ccc;
      padding: 4px 0 6px; font-family: Arial, sans-serif; background: #fff; flex-shrink: 0;
    }

    /* ── Teaser positioning — offset from bubble only ── */

    /* ── Teaser bubbles (pop up after 10 s of inactivity) ── */
    #dw-teasers {
      position: fixed; bottom: 96px; right: 24px; z-index: 99997;
      display: flex; flex-direction: column; gap: 8px; align-items: flex-end;
    }
    .dw-teaser {
      background: #fff; border-radius: 18px 18px 4px 18px;
      box-shadow: 0 4px 22px rgba(0,0,0,0.15);
      padding: 10px 12px 10px 16px;
      font-size: 0.85rem; font-family: Arial, sans-serif; color: #222;
      display: flex; align-items: center; gap: 8px;
      cursor: pointer; max-width: 230px;
      animation: dw-pop-in 0.45s cubic-bezier(.34,1.56,.64,1) both;
    }
    .dw-teaser:nth-child(2) { animation-delay: 0.25s; }
    @keyframes dw-pop-in {
      from { opacity: 0; transform: translateX(18px) scale(0.88); }
      to   { opacity: 1; transform: translateX(0) scale(1); }
    }
    .dw-teaser-x {
      background: none; border: none; color: #bbb; cursor: pointer;
      font-size: 0.78rem; padding: 0; line-height: 1; flex-shrink: 0;
      transition: color 0.15s;
    }
    .dw-teaser-x:hover { color: #666; }
    `;
  }

  applyStyles(BRAND_COLOR);

  const chatIconSVG = `<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/></svg>`;
  const closeIconSVG = `&#10005;`;
  const sendIconSVG  = `<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>`;
  const botIconSVG   = `<svg viewBox="0 0 24 24"><path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z"/></svg>`;
  const phoneIconSVG = `<svg viewBox="0 0 24 24"><path d="M6.6 10.8c1.4 2.8 3.8 5.1 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1-9.4 0-17-7.6-17-17 0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.3.2 2.5.6 3.6.1.3 0 .7-.2 1L6.6 10.8z"/></svg>`;

  const bubble = document.createElement("button");
  bubble.id = "dw-bubble";
  bubble.innerHTML = chatIconSVG;
  bubble.setAttribute("aria-label", "Open chat");

  const card = document.createElement("div");
  card.id = "dw-card";
  card.setAttribute("role", "dialog");
  card.setAttribute("aria-label", "Chat window");
  card.innerHTML = `
    <div id="dw-header">
      <div id="dw-avatar">${botIconSVG}</div>
      <div id="dw-header-text">
        <div id="dw-header-title">Customer Support</div>
        <div id="dw-header-sub">
          <span class="dw-status-dot" id="dw-status-dot"></span>
          <span id="dw-status-label">Checking availability...</span>
        </div>
      </div>
      <a id="dw-call-hdr" href="#" aria-label="Call Us">${phoneIconSVG} Call Us</a>
      <button id="dw-close" aria-label="Close">${closeIconSVG}</button>
    </div>
    <div id="dw-messages"></div>
    <div id="dw-footer">
      <input id="dw-input" type="text" placeholder="Type your message..." autocomplete="off" />
      <button id="dw-send" aria-label="Send">${sendIconSVG}</button>
    </div>
    <div id="dw-branding">Powered by Dental AI</div>
  `;

  const teaserContainer = document.createElement("div");
  teaserContainer.id = "dw-teasers";

  document.body.appendChild(bubble);
  document.body.appendChild(card);
  document.body.appendChild(teaserContainer);

  const messagesEl  = card.querySelector("#dw-messages");
  const inputEl     = card.querySelector("#dw-input");
  const sendBtn     = card.querySelector("#dw-send");
  const closeBtn    = card.querySelector("#dw-close");
  const titleEl     = card.querySelector("#dw-header-title");
  const avatarEl    = card.querySelector("#dw-avatar");
  const statusDotEl = card.querySelector("#dw-status-dot");
  const statusLblEl = card.querySelector("#dw-status-label");
  const callHdrEl   = card.querySelector("#dw-call-hdr");

  function parseMd(text) {
    return text
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/g,     "<em>$1</em>")
      .replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>')
      .replace(/\n/g, "<br>");
  }

  function addMsg(text, type) {
    const row = document.createElement("div");
    row.className = `dw-msg-row ${type === "user" ? "dw-user" : "dw-bot"}`;

    const bub = document.createElement("div");
    bub.className = "dw-bubble-msg";
    if (type === "typing") {
      bub.classList.add("dw-typing");
      bub.textContent = "Typing...";
    } else if (type === "handoff") {
      bub.classList.add("dw-handoff");
      bub.textContent = "📞 Our team has been notified and will contact you shortly.";
    } else if (type === "user") {
      bub.textContent = text;
    } else {
      bub.innerHTML = parseMd(text);
    }

    const ts = document.createElement("div");
    ts.className = "dw-timestamp";
    ts.textContent = hhmm();

    row.appendChild(bub);
    row.appendChild(ts);
    messagesEl.appendChild(row);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return row;
  }

  function showQuickReplies(clinicName) {
    const wr = document.createElement("div");
    wr.className = "dw-quick-replies";
    wr.id = "dw-quick-replies";
    [
      "📅 Book Appointment",
      "⏰ Office Hours",
      "📞 Contact Info",
      "🦷 Our Services",
      "💰 Pricing"
    ].forEach(label => {
      const b = document.createElement("button");
      b.className = "dw-qr-btn";
      b.textContent = label;
      b.onclick = () => {
        const qr = document.getElementById("dw-quick-replies");
        if (qr) qr.remove();
        inputEl.value = label;
        send();
      };
      wr.appendChild(b);
    });
    messagesEl.appendChild(wr);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function updateStatus() {
    const online = isOfficeOpen();
    statusDotEl.className = "dw-status-dot " + (online ? "online" : "offline");
    statusLblEl.textContent = online
      ? "Available · typically replies instantly"
      : "Out of Office · we'll get back to you soon";
  }

  function setupCallBar(phone) {
    if (!phone) return;
    const callHdr = card.querySelector("#dw-call-hdr");
    if (callHdr) {
      callHdr.href = `tel:${phone}`;
      callHdr.style.display = "flex";
    }
  }

  const TEASER_MESSAGES = [
    "👋 Hi! Need any help today?",
    "We're here for all your dental questions 🦷"
  ];
  let teaserShown = false;

  function showTeasers() {
    if (teaserShown || card.classList.contains("dw-open")) return;
    teaserShown = true;
    teaserContainer.innerHTML = "";
    TEASER_MESSAGES.forEach(msg => {
      const el = document.createElement("div");
      el.className = "dw-teaser";
      el.innerHTML = `<span>${msg}</span><button class="dw-teaser-x" aria-label="Dismiss">✕</button>`;
      el.addEventListener("click", () => { hideTeasers(); openCard(); });
      el.querySelector(".dw-teaser-x").addEventListener("click", e => { e.stopPropagation(); hideTeasers(); });
      teaserContainer.appendChild(el);
    });
  }

  function hideTeasers() {
    teaserContainer.innerHTML = "";
  }

  setTimeout(showTeasers, 10000);

  async function send() {
    const text = inputEl.value.trim();
    if (!text) return;

    const qr = document.getElementById("dw-quick-replies");
    if (qr) qr.remove();

    addMsg(text, "user");
    inputEl.value = "";
    sendBtn.disabled = true;

    const typingRow = addMsg("", "typing");

    try {
      const url  = `${BASE_URL}/ask/${CLIENT_ID}?question=${encodeURIComponent(text)}&session_id=${SESSION_ID}`;
      const res  = await fetch(url);
      const data = await res.json();
      typingRow.remove();
      addMsg(data.answer || "No response received.", "bot");
      if (data.handoff) addMsg("", "handoff");
    } catch {
      typingRow.remove();
      addMsg("Connection error. Please try again.", "bot");
    }

    sendBtn.disabled = false;
    inputEl.focus();
  }

  function openCard() {
    hideTeasers();
    card.classList.add("dw-open");
    bubble.setAttribute("aria-expanded", "true");
    inputEl.focus();
  }
  function closeCard() {
    card.classList.remove("dw-open");
    bubble.setAttribute("aria-expanded", "false");
  }

  bubble.addEventListener("click", () => {
    card.classList.contains("dw-open") ? closeCard() : openCard();
  });
  closeBtn.addEventListener("click", closeCard);
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  });
  sendBtn.addEventListener("click", send);

  fetch(`${BASE_URL}/client/${CLIENT_ID}/info`)
    .then((r) => r.json())
    .then((d) => {
      const botName = d.bot_name || d.name || "Customer Support";
      titleEl.textContent = botName;

      if (!DATA_COLOR && d.color) {
        BRAND_COLOR = d.color;
        applyStyles(BRAND_COLOR);
      }

      const avatarUrl = DATA_AVATAR || d.bot_avatar || "";
      if (avatarUrl) {
        const img = document.createElement("img");
        img.src = avatarUrl;
        img.alt = botName;
        img.onerror = () => { avatarEl.innerHTML = botIconSVG; };
        avatarEl.innerHTML = "";
        avatarEl.appendChild(img);
      }

      if (d.office_open)  OFFICE_OPEN  = d.office_open;
      if (d.office_close) OFFICE_CLOSE = d.office_close;
      if (d.office_days)  OFFICE_DAYS  = d.office_days.split(",").map(Number);
      PHONE = d.phone || "";

      updateStatus();
      setupCallBar(PHONE);

      addMsg(`Hi there! 👋 Welcome to **${d.name}**. How can I help you today?`, "bot");
      showQuickReplies(d.name);
    })
    .catch(() => {
      titleEl.textContent = "Customer Support";
      updateStatus();
      addMsg("Hi there! 👋 How can I help you today?", "bot");
      showQuickReplies("");
    });
})();
