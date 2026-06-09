(function () {
  const script =
    document.currentScript ||
    (function () {
      const s = document.getElementsByTagName("script");
      return s[s.length - 1];
    })();

  const CLIENT_ID   = script.getAttribute("data-client-id");
  const BRAND_COLOR = script.getAttribute("data-color") || "#1a73e8";
  const BASE_URL    = new URL(script.src).origin;
  const SESSION_ID  = Math.random().toString(36).substring(2);

  if (!CLIENT_ID) {
    console.error("[DentalWidget] data-client-id is required.");
    return;
  }

  // ── Helpers ──────────────────────────────────────────────────────────────
  function hhmm() {
    const d = new Date();
    return d.getHours().toString().padStart(2, "0") + ":" +
           d.getMinutes().toString().padStart(2, "0");
  }

  function hexToRgb(hex) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `${r},${g},${b}`;
  }

  // ── Styles ────────────────────────────────────────────────────────────────
  const css = `
    #dw-bubble {
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 99999;
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: ${BRAND_COLOR};
      box-shadow: 0 4px 20px rgba(${hexToRgb(BRAND_COLOR)}, 0.5);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.2s, box-shadow 0.2s;
      border: none;
      outline: none;
    }
    #dw-bubble:hover {
      transform: scale(1.08);
      box-shadow: 0 6px 28px rgba(${hexToRgb(BRAND_COLOR)}, 0.65);
    }
    #dw-bubble svg { width: 28px; height: 28px; fill: #fff; }

    #dw-card {
      position: fixed;
      bottom: 96px;
      right: 24px;
      z-index: 99998;
      width: 380px;
      max-width: calc(100vw - 48px);
      background: #fff;
      border-radius: 18px;
      box-shadow: 0 8px 40px rgba(0,0,0,0.18);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      transform: scale(0.92) translateY(20px);
      opacity: 0;
      pointer-events: none;
      transition: transform 0.25s cubic-bezier(.34,1.56,.64,1), opacity 0.2s ease;
      max-height: 560px;
    }
    #dw-card.dw-open {
      transform: scale(1) translateY(0);
      opacity: 1;
      pointer-events: all;
    }

    #dw-header {
      background: ${BRAND_COLOR};
      color: #fff;
      padding: 14px 16px;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    #dw-avatar {
      width: 38px;
      height: 38px;
      border-radius: 50%;
      background: rgba(255,255,255,0.25);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    #dw-avatar svg { width: 20px; height: 20px; fill: #fff; }
    #dw-header-text { flex: 1; }
    #dw-header-title { font-weight: 700; font-size: 0.95rem; font-family: Arial, sans-serif; }
    #dw-header-sub { font-size: 0.75rem; opacity: 0.85; font-family: Arial, sans-serif; margin-top: 1px; }
    #dw-close {
      background: rgba(255,255,255,0.2);
      border: none;
      color: #fff;
      width: 30px;
      height: 30px;
      border-radius: 50%;
      cursor: pointer;
      font-size: 1.1rem;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.15s;
      flex-shrink: 0;
    }
    #dw-close:hover { background: rgba(255,255,255,0.35); }

    #dw-messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      background: #f7f9fc;
      min-height: 300px;
      max-height: 360px;
    }
    #dw-messages::-webkit-scrollbar { width: 4px; }
    #dw-messages::-webkit-scrollbar-thumb { background: #ddd; border-radius: 4px; }

    .dw-msg-row {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .dw-msg-row.dw-user { align-items: flex-end; }
    .dw-msg-row.dw-bot  { align-items: flex-start; }

    .dw-bubble-msg {
      max-width: 82%;
      padding: 9px 13px;
      border-radius: 16px;
      font-size: 0.875rem;
      line-height: 1.5;
      word-wrap: break-word;
      font-family: Arial, sans-serif;
    }
    .dw-user .dw-bubble-msg {
      background: ${BRAND_COLOR};
      color: #fff;
      border-bottom-right-radius: 4px;
    }
    .dw-bot .dw-bubble-msg {
      background: #fff;
      color: #202124;
      border-bottom-left-radius: 4px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }
    .dw-bot .dw-bubble-msg strong { font-weight: 700; }
    .dw-bot .dw-bubble-msg a { color: ${BRAND_COLOR}; text-decoration: underline; }

    .dw-timestamp {
      font-size: 0.68rem;
      color: #aaa;
      padding: 0 4px;
      font-family: Arial, sans-serif;
    }

    .dw-typing {
      background: #fff;
      color: #aaa;
      font-style: italic;
      border-bottom-left-radius: 4px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }

    .dw-handoff {
      background: #fff8e1;
      border: 1px solid #ffd54f;
      color: #795548;
      border-radius: 10px;
      padding: 8px 12px;
      font-size: 0.8rem;
      text-align: center;
      font-family: Arial, sans-serif;
    }

    #dw-footer {
      padding: 10px 12px;
      background: #fff;
      border-top: 1px solid #f0f0f0;
      display: flex;
      gap: 8px;
      align-items: center;
    }
    #dw-input {
      flex: 1;
      padding: 9px 14px;
      border: 1.5px solid #e0e0e0;
      border-radius: 22px;
      font-size: 0.875rem;
      outline: none;
      font-family: Arial, sans-serif;
      transition: border-color 0.15s;
      color: #202124;
    }
    #dw-input:focus { border-color: ${BRAND_COLOR}; }
    #dw-send {
      width: 38px;
      height: 38px;
      border-radius: 50%;
      background: ${BRAND_COLOR};
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      transition: background 0.15s, transform 0.1s;
    }
    #dw-send:hover { filter: brightness(0.9); }
    #dw-send:active { transform: scale(0.93); }
    #dw-send:disabled { background: #ccc; cursor: not-allowed; }
    #dw-send svg { width: 18px; height: 18px; fill: #fff; }

    #dw-branding {
      text-align: center;
      font-size: 0.65rem;
      color: #ccc;
      padding: 4px 0 6px;
      font-family: Arial, sans-serif;
      background: #fff;
    }
  `;

  const styleEl = document.createElement("style");
  styleEl.textContent = css;
  document.head.appendChild(styleEl);

  // ── Icons (inline SVG) ────────────────────────────────────────────────────
  const chatIconSVG = `<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/></svg>`;
  const closeIconSVG = `&#10005;`;
  const sendIconSVG = `<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>`;
  const botIconSVG = `<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9V8h2v8zm4 0h-2V8h2v8z"/></svg>`;

  // ── DOM ───────────────────────────────────────────────────────────────────
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
        <div id="dw-header-title">Dental Assistant</div>
        <div id="dw-header-sub">&#x1F7E2; Online — typically replies instantly</div>
      </div>
      <button id="dw-close" aria-label="Close">${closeIconSVG}</button>
    </div>
    <div id="dw-messages"></div>
    <div id="dw-footer">
      <input id="dw-input" type="text" placeholder="Type your message..." autocomplete="off" />
      <button id="dw-send" aria-label="Send">${sendIconSVG}</button>
    </div>
    <div id="dw-branding">Powered by Dental AI</div>
  `;

  document.body.appendChild(bubble);
  document.body.appendChild(card);

  // ── Refs ──────────────────────────────────────────────────────────────────
  const messagesEl = card.querySelector("#dw-messages");
  const inputEl    = card.querySelector("#dw-input");
  const sendBtn    = card.querySelector("#dw-send");
  const closeBtn   = card.querySelector("#dw-close");
  const titleEl    = card.querySelector("#dw-header-title");

  // ── Parse markdown ────────────────────────────────────────────────────────
  function parseMd(text) {
    return text
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/g,     "<em>$1</em>")
      .replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>')
      .replace(/\n/g, "<br>");
  }

  // ── Add message ───────────────────────────────────────────────────────────
  function addMsg(text, type) {
    const row = document.createElement("div");
    row.className = `dw-msg-row ${type === "user" ? "dw-user" : "dw-bot"}`;

    const bub = document.createElement("div");
    bub.className = "dw-bubble-msg";
    if (type === "typing") {
      bub.classList.add("dw-typing");
      bub.textContent = "Typing…";
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

  // ── Send message ──────────────────────────────────────────────────────────
  async function send() {
    const text = inputEl.value.trim();
    if (!text) return;

    addMsg(text, "user");
    inputEl.value = "";
    sendBtn.disabled = true;

    const typingRow = addMsg("", "typing");

    try {
      const url = `${BASE_URL}/ask/${CLIENT_ID}?question=${encodeURIComponent(text)}&session_id=${SESSION_ID}`;
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

  // ── Toggle card ───────────────────────────────────────────────────────────
  function openCard() {
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

  // ── Load clinic name + greeting ───────────────────────────────────────────
  fetch(`${BASE_URL}/client/${CLIENT_ID}/info`)
    .then((r) => r.json())
    .then((d) => {
      titleEl.textContent = d.name || "Dental Assistant";
      addMsg(`Hello! I'm the AI assistant for **${d.name}**. How can I help you today?`, "bot");
    })
    .catch(() => {
      titleEl.textContent = "Dental Assistant";
      addMsg("Hello! How can I help you today?", "bot");
    });
})();
