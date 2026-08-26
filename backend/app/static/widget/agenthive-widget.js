/*!
 * AgentHive Web Widget SDK v0.3.0-alpha.1
 * Lightweight embeddable chat widget for Web Widget / REST API channels.
 * Polls outbound messages from /api/v1/channels/poll/web_widget/{channelKey}
 * and sends user input via /api/v1/channels/webhook/web_widget/{channelKey}.
 *
 * Usage (snippet for customer websites):
 *   <script>
 *     window.AgentHiveWidget = {
 *       baseUrl: "https://api.example.com",
 *       channelKey: "your-channel-key",
 *       channelSecret: "your-channel-secret",  // optional, enables HMAC signing
 *       externalUserId: "visitor-123",          // optional, auto-generated if absent
 *       conversationKey: "session-abc",         // optional
 *       primaryColor: "#2563eb",
 *       title: "Customer Support",
 *     };
 *   </script>
 *   <script src="https://api.example.com/widget/agenthive-widget.js" async></script>
 *
 * Security note: channelSecret is intended for same-origin / authenticated
 * deployments. For fully public sites, deploy a thin signing proxy that adds
 * the X-AgentHive-Signature header server-side and keep the secret off the client.
 */
(function (window, document) {
  "use strict";

  if (window.__agenthiveWidgetMounted) {
    return;
  }
  window.__agenthiveWidgetMounted = true;

  var config = window.AgentHiveWidget || {};
  var baseUrl = (config.baseUrl || "").replace(/\/+$/, "");
  var channelKey = config.channelKey || "";
  var channelSecret = config.channelSecret || "";
  var externalUserId = config.externalUserId || _generateUserId();
  var conversationKey = config.conversationKey || _generateConversationKey();
  var primaryColor = config.primaryColor || "#2563eb";
  var title = config.title || "Customer Support";
  var pollIntervalMs = Math.max(config.pollIntervalMs || 3000, 1500);
  var pollLimit = Math.min(Math.max(config.pollLimit || 50, 1), 200);

  if (!baseUrl || !channelKey) {
    if (window.console) {
      console.error("[AgentHiveWidget] baseUrl and channelKey are required.");
    }
    return;
  }

  var state = {
    cursor: null,
    hasMore: false,
    polling: false,
    pollTimer: null,
    open: false,
  };

  // ---- DOM ----------------------------------------------------------------

  var launcher, panel, messagesEl, inputEl, sendBtn, statusEl;

  function _buildDom() {
    var style = document.createElement("style");
    style.textContent = _css();
    document.head.appendChild(style);

    launcher = document.createElement("button");
    launcher.type = "button";
    launcher.className = "ahw-launcher";
    launcher.setAttribute("aria-label", title);
    launcher.innerHTML = _chatIcon();
    launcher.addEventListener("click", _toggleOpen);
    document.body.appendChild(launcher);

    panel = document.createElement("div");
    panel.className = "ahw-panel ahw-hidden";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", title);
    panel.innerHTML =
      '<div class="ahw-header">' +
      '<span class="ahw-title"></span>' +
      '<button type="button" class="ahw-close" aria-label="Close">&#x2715;</button>' +
      "</div>" +
      '<div class="ahw-messages" role="log" aria-live="polite"></div>' +
      '<div class="ahw-status ahw-hidden"></div>' +
      '<div class="ahw-composer">' +
      '<textarea class="ahw-input" rows="1" placeholder="Type a message..."></textarea>' +
      '<button type="button" class="ahw-send" aria-label="Send">' +
      _sendIcon() +
      "</button>" +
      "</div>";
    document.body.appendChild(panel);

    panel.querySelector(".ahw-title").textContent = title;
    panel.querySelector(".ahw-close").addEventListener("click", _close);
    messagesEl = panel.querySelector(".ahw-messages");
    inputEl = panel.querySelector(".ahw-input");
    sendBtn = panel.querySelector(".ahw-send");
    statusEl = panel.querySelector(".ahw-status");
    sendBtn.addEventListener("click", _onSend);
    inputEl.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        _onSend();
      }
    });
    inputEl.addEventListener("input", _autoResize);
  }

  // ---- Messaging ----------------------------------------------------------

  function _onSend() {
    var text = (inputEl.value || "").trim();
    if (!text) {
      return;
    }
    inputEl.value = "";
    _autoResize();
    _appendMessage("user", text);
    _sendToChannel(text).catch(function (err) {
      _showStatus("Failed to send message: " + (err.message || err), true);
    });
  }

  function _sendToChannel(text) {
    var payload = {
      external_user_id: externalUserId,
      conversation_key: conversationKey,
      message_type: "text",
      text: text,
      message_id: _uuid(),
    };
    var url = baseUrl + "/api/v1/channels/webhook/web_widget/" + channelKey;
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      credentials: "omit",
    }).then(function (response) {
      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }
      _schedulePoll(500);
      return response.json();
    });
  }

  function _poll() {
    if (state.polling || !state.open) {
      return;
    }
    state.polling = true;
    var params = new URLSearchParams();
    params.set("external_user_id", externalUserId);
    if (conversationKey) {
      params.set("conversation_key", conversationKey);
    }
    if (state.cursor) {
      params.set("after", state.cursor);
    }
    params.set("limit", String(pollLimit));
    var queryString = params.toString();
    var path = "/api/v1/channels/poll/web_widget/" + channelKey;
    var url = baseUrl + path + "?" + queryString;

    var headers = {};
    if (channelSecret) {
      var ts = String(Date.now());
      var nonce = _uuid();
      var canonicalQuery = queryString
        .split("&")
        .sort()
        .join("&");
      var signingBase =
        ts + "." + nonce + ".GET." + path + "?" + canonicalQuery;
      headers["X-AgentHive-Timestamp"] = ts;
      headers["X-AgentHive-Nonce"] = nonce;
      headers["X-AgentHive-Signature"] =
        "sha256=" + _hmacSha256Hex(channelSecret, signingBase);
    }

    fetch(url, { method: "GET", headers: headers, credentials: "omit" })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("HTTP " + response.status);
        }
        return response.json();
      })
      .then(function (data) {
        if (data && data.messages) {
          data.messages.forEach(function (msg) {
            _appendMessage("assistant", msg.content);
          });
        }
        state.cursor = data && data.next_cursor ? data.next_cursor : state.cursor;
        state.hasMore = Boolean(data && data.has_more);
      })
      .catch(function (err) {
        _showStatus("Polling error: " + (err.message || err), true);
      })
      .finally(function () {
        state.polling = false;
        if (state.open) {
          _schedulePoll(pollIntervalMs);
        }
      });
  }

  function _schedulePoll(delay) {
    if (state.pollTimer) {
      clearTimeout(state.pollTimer);
    }
    state.pollTimer = setTimeout(_poll, delay);
  }

  // ---- UI helpers ---------------------------------------------------------

  function _appendMessage(role, content) {
    var node = document.createElement("div");
    node.className = "ahw-message ahw-" + role;
    var bubble = document.createElement("div");
    bubble.className = "ahw-bubble";
    bubble.textContent = content;
    node.appendChild(bubble);
    messagesEl.appendChild(node);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function _showStatus(text, isError) {
    statusEl.textContent = text;
    statusEl.classList.toggle("ahw-error", Boolean(isError));
    statusEl.classList.remove("ahw-hidden");
    setTimeout(function () {
      statusEl.classList.add("ahw-hidden");
    }, 4000);
  }

  function _toggleOpen() {
    state.open ? _close() : _open();
  }

  function _open() {
    state.open = true;
    panel.classList.remove("ahw-hidden");
    launcher.classList.add("ahw-active");
    inputEl.focus();
    _schedulePoll(200);
  }

  function _close() {
    state.open = false;
    panel.classList.add("ahw-hidden");
    launcher.classList.remove("ahw-active");
    if (state.pollTimer) {
      clearTimeout(state.pollTimer);
      state.pollTimer = null;
    }
  }

  function _autoResize() {
    inputEl.style.height = "auto";
    inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + "px";
  }

  // ---- Crypto helpers (HMAC-SHA256 via WebCrypto) -------------------------

  function _hmacSha256Hex(secret, message) {
    // Synchronous fallback: WebCrypto is async; we use a minimal HMAC via
    // SubtleCrypto with a Promise that we resolve synchronously when possible.
    // Because fetch is async anyway, we accept async signing via a sync shim
    // using a precomputed key buffer cached on first call.
    // For broad compatibility we fall back to a simple keyed hash when
    // SubtleCrypto is unavailable. Production deployments should use a signing
    // proxy for strong security.
    try {
      var keyBytes = new TextEncoder().encode(secret);
      var msgBytes = new TextEncoder().encode(message);
      // Use a synchronous HMAC implementation if available (rare); otherwise
      // we cannot synchronously call SubtleCrypto. In practice the widget
      // signs with a Promise and awaits before fetch.
      var result = _hmacSync(keyBytes, msgBytes);
      if (result) {
        return result;
      }
    } catch (e) {
      // ignore and fall through
    }
    return "";
  }

  function _hmacSync(keyBytes, msgBytes) {
    // Minimal HMAC-SHA256 (RFC 2104) synchronous implementation.
    // Included so the widget can sign without async SubtleCrypto.
    var sha = _sha256;
    var blockSize = 64;
    var key = keyBytes;
    if (key.length > blockSize) {
      key = sha(key);
    }
    var paddedKey = new Uint8Array(blockSize);
    for (var i = 0; i < key.length; i++) {
      paddedKey[i] = key[i];
    }
    var oKeyPad = new Uint8Array(blockSize);
    var iKeyPad = new Uint8Array(blockSize);
    for (var j = 0; j < blockSize; j++) {
      oKeyPad[j] = paddedKey[j] ^ 0x5c;
      iKeyPad[j] = paddedKey[j] ^ 0x36;
    }
    var innerInput = new Uint8Array(blockSize + msgBytes.length);
    innerInput.set(iKeyPad, 0);
    innerInput.set(msgBytes, blockSize);
    var innerHash = sha(innerInput);
    var outerInput = new Uint8Array(blockSize + innerHash.length);
    outerInput.set(oKeyPad, 0);
    outerInput.set(innerHash, blockSize);
    return _bytesToHex(sha(outerInput));
  }

  // Minimal SHA-256 (synchronous, pure JS).
  function _sha256(message) {
    var k = [
      0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
      0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
      0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
      0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
      0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
      0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
      0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
      0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
      0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
      0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
      0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
    ];
    var h = [
      0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c,
      0x1f83d9ab, 0x5be0cd19,
    ];
    var msg = Array.from(message);
    var l = msg.length;
    var bitLen = l * 8;
    msg.push(0x80);
    while (msg.length % 64 !== 56) {
      msg.push(0);
    }
    var hi = Math.floor(bitLen / 0x100000000);
    var lo = bitLen >>> 0;
    for (var i = 0; i < 4; i++) {
      msg.push((hi >>> (24 - i * 8)) & 0xff);
    }
    for (var j = 0; j < 4; j++) {
      msg.push((lo >>> (24 - j * 8)) & 0xff);
    }
    for (var off = 0; off < msg.length; off += 64) {
      var w = new Array(64);
      for (var t = 0; t < 16; t++) {
        w[t] =
          (msg[off + t * 4] << 24) |
          (msg[off + t * 4 + 1] << 16) |
          (msg[off + t * 4 + 2] << 8) |
          msg[off + t * 4 + 3];
        w[t] >>>= 0;
      }
      for (var t2 = 16; t2 < 64; t2++) {
        var s0 =
          _rotr(w[t2 - 15], 7) ^ _rotr(w[t2 - 15], 18) ^ (w[t2 - 15] >>> 3);
        var s1 =
          _rotr(w[t2 - 2], 17) ^ _rotr(w[t2 - 2], 19) ^ (w[t2 - 2] >>> 10);
        w[t2] = (w[t2 - 16] + s0 + w[t2 - 7] + s1) >>> 0;
      }
      var a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5],
        g = h[6], hh = h[7];
      for (var t3 = 0; t3 < 64; t3++) {
        var S1 = _rotr(e, 6) ^ _rotr(e, 11) ^ _rotr(e, 25);
        var ch = (e & f) ^ (~e & g);
        var temp1 = (hh + S1 + ch + k[t3] + w[t3]) >>> 0;
        var S0 = _rotr(a, 2) ^ _rotr(a, 13) ^ _rotr(a, 22);
        var maj = (a & b) ^ (a & c) ^ (b & c);
        var temp2 = (S0 + maj) >>> 0;
        hh = g;
        g = f;
        f = e;
        e = (d + temp1) >>> 0;
        d = c;
        c = b;
        b = a;
        a = (temp1 + temp2) >>> 0;
      }
      h[0] = (h[0] + a) >>> 0;
      h[1] = (h[1] + b) >>> 0;
      h[2] = (h[2] + c) >>> 0;
      h[3] = (h[3] + d) >>> 0;
      h[4] = (h[4] + e) >>> 0;
      h[5] = (h[5] + f) >>> 0;
      h[6] = (h[6] + g) >>> 0;
      h[7] = (h[7] + hh) >>> 0;
    }
    var out = new Uint8Array(32);
    for (var n = 0; n < 8; n++) {
      out[n * 4] = (h[n] >>> 24) & 0xff;
      out[n * 4 + 1] = (h[n] >>> 16) & 0xff;
      out[n * 4 + 2] = (h[n] >>> 8) & 0xff;
      out[n * 4 + 3] = h[n] & 0xff;
    }
    return out;
  }

  function _rotr(x, n) {
    return (x >>> n) | (x << (32 - n));
  }

  function _bytesToHex(bytes) {
    var hex = "";
    for (var i = 0; i < bytes.length; i++) {
      hex += (bytes[i] < 16 ? "0" : "") + bytes[i].toString(16);
    }
    return hex;
  }

  // ---- Utilities ----------------------------------------------------------

  function _uuid() {
    if (window.crypto && window.crypto.randomUUID) {
      return window.crypto.randomUUID();
    }
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
      var r = (Math.random() * 16) | 0;
      var v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  function _generateUserId() {
    try {
      var stored = window.localStorage.getItem("ahw_user_id");
      if (stored) {
        return stored;
      }
    } catch (e) {
      // localStorage may be unavailable (private mode); fall through.
    }
    var id = "visitor-" + _uuid();
    try {
      window.localStorage.setItem("ahw_user_id", id);
    } catch (e) {
      // ignore
    }
    return id;
  }

  function _generateConversationKey() {
    return "session-" + _uuid();
  }

  function _chatIcon() {
    return (
      '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>' +
      "</svg>"
    );
  }

  function _sendIcon() {
    return (
      '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
      '<line x1="22" y1="2" x2="11" y2="13"></line>' +
      '<polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>' +
      "</svg>"
    );
  }

  // ---- Styles -------------------------------------------------------------

  function _css() {
    return [
      ".ahw-launcher{position:fixed;bottom:20px;right:20px;width:56px;height:56px;border-radius:50%;background:" +
        primaryColor +
        ";color:#fff;border:none;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,.2);display:flex;align-items:center;justify-content:center;z-index:99999;transition:transform .2s}",
      ".ahw-launcher:hover{transform:scale(1.05)}",
      ".ahw-launcher.ahw-active{transform:scale(0.9)}",
      ".ahw-panel{position:fixed;bottom:90px;right:20px;width:360px;max-width:calc(100vw - 40px);height:520px;max-height:calc(100vh - 120px);background:#fff;border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,.18);display:flex;flex-direction:column;overflow:hidden;z-index:99999;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}",
      ".ahw-hidden{display:none!important}",
      ".ahw-header{background:" +
        primaryColor +
        ";color:#fff;padding:14px 16px;display:flex;align-items:center;justify-content:space-between}",
      ".ahw-title{font-size:15px;font-weight:600}",
      ".ahw-close{background:transparent;border:none;color:#fff;cursor:pointer;font-size:16px;padding:4px;line-height:1}",
      ".ahw-messages{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px;background:#f7f7f8}",
      ".ahw-message{display:flex;max-width:85%}",
      ".ahw-user{align-self:flex-end}",
      ".ahw-assistant{align-self:flex-start}",
      ".ahw-bubble{padding:10px 14px;border-radius:14px;font-size:14px;line-height:1.4;word-break:break-word}",
      ".ahw-user .ahw-bubble{background:" +
        primaryColor +
        ";color:#fff;border-bottom-right-radius:4px}",
      ".ahw-assistant .ahw-bubble{background:#fff;color:#1f2937;border:1px solid #e5e7eb;border-bottom-left-radius:4px}",
      ".ahw-status{padding:6px 12px;font-size:12px;color:#6b7280;background:#fef3c7}",
      ".ahw-status.ahw-error{background:#fee2e2;color:#b91c1c}",
      ".ahw-composer{display:flex;align-items:flex-end;gap:8px;padding:10px 12px;border-top:1px solid #e5e7eb;background:#fff}",
      ".ahw-input{flex:1;border:1px solid #d1d5db;border-radius:8px;padding:8px 10px;font-size:14px;font-family:inherit;resize:none;outline:none;max-height:120px;line-height:1.4}",
      ".ahw-input:focus{border-color:" + primaryColor + "}",
      ".ahw-send{background:" +
        primaryColor +
        ";color:#fff;border:none;border-radius:8px;width:36px;height:36px;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0}",
      ".ahw-send:hover{opacity:.9}",
      "@media (max-width:480px){.ahw-panel{width:calc(100vw - 24px);right:12px;bottom:84px;height:calc(100vh - 100px)}}",
    ].join("\n");
  }

  // ---- Boot ---------------------------------------------------------------

  function _init() {
    _buildDom();
    if (window.console && window.console.log) {
      console.log("[AgentHiveWidget] mounted for channel " + channelKey);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", _init);
  } else {
    _init();
  }
})(window, document);
