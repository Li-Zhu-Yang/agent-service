/* 客服聊天页：SSE 流式对话 */
(function () {
  "use strict";

  const SESSION_KEY = "ragent_session_id";
  let sessionId = localStorage.getItem(SESSION_KEY) || "";
  let streaming = false;

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);
  const messagesEl = $("#messages");

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  function addMessage(role, content) {
    const wrap = el("div", "msg " + role);
    const avatar = el("div", "avatar", role === "user" ? "我" : "智");
    const bubble = el("div", "bubble");
    bubble.textContent = content || "";
    const body = el("div");
    body.appendChild(bubble);
    wrap.appendChild(avatar);
    wrap.appendChild(body);
    messagesEl.appendChild(wrap);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return { wrap, body, bubble };
  }

  function addTag(body, text, cls) {
    const tag = el("span", "tag" + (cls ? " " + cls : ""), text);
    body.appendChild(tag);
  }

  function setTyping(body, on) {
    let dot = body.querySelector(".typing");
    if (on && !dot) {
      dot = el("div", "typing");
      dot.innerHTML = "<i></i><i></i><i></i>";
      body.appendChild(dot);
    }
    if (!on && dot) dot.remove();
  }

  async function readSSE(res, onEvent) {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const data = block
          .split("\n")
          .filter((l) => l.startsWith("data: "))
          .map((l) => l.slice(6))
          .join("\n");
        if (data) {
          try {
            onEvent(JSON.parse(data));
          } catch (_) {
            /* 忽略无法解析的事件 */
          }
        }
      }
    }
  }

  async function send(text) {
    text = (text || "").trim();
    if (!text || streaming) return;
    streaming = true;
    $("#send").disabled = true;
    $("#input").disabled = true;

    addMessage("user", text);
    const { body, bubble } = addMessage("bot", "");
    setTyping(body, true);

    try {
      const res = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: text }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.message || ("请求失败 " + res.status));
      }
      await readSSE(res, (evt) => {
        if (evt.session_id) {
          sessionId = evt.session_id;
          localStorage.setItem(SESSION_KEY, sessionId);
        } else if (typeof evt.delta === "string") {
          bubble.textContent += evt.delta;
          messagesEl.scrollTop = messagesEl.scrollHeight;
        } else if (evt.error) {
          bubble.textContent = "发生错误：" + evt.error.message;
        } else if (evt.intent !== undefined) {
          if (evt.need_human) {
            addTag(body, "已转人工" + (evt.ticket_no ? " · " + evt.ticket_no : ""), "human");
          } else if (evt.intent) {
            addTag(body, evt.intent);
          }
        }
      });
    } catch (err) {
      bubble.textContent = "发送失败：" + err.message;
    } finally {
      setTyping(body, false);
      streaming = false;
      $("#send").disabled = false;
      $("#input").disabled = false;
      $("#input").focus();
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }
  }

  async function restoreHistory() {
    if (!sessionId) return;
    try {
      const res = await fetch("/api/conversations/" + encodeURIComponent(sessionId));
      if (!res.ok) return;
      const { data } = await res.json();
      if (!data || !data.messages) return;
      for (const m of data.messages) {
        const { body } = addMessage(m.role, m.content);
        if (m.intent) addTag(body, m.intent, m.need_human ? "human" : "");
      }
    } catch (_) {
      /* 历史加载失败不影响使用 */
    }
  }

  function newConversation() {
    sessionId = "";
    localStorage.removeItem(SESSION_KEY);
    messagesEl.innerHTML = "";
    addWelcome();
  }

  function addWelcome() {
    const { body, bubble } = addMessage("bot", "您好！我是智享电器的智能客服，很高兴为您服务。\n\n您可以问我：订单/物流查询、退款/退货、报修/维修、发票/优惠券……也可以直接说「转人工」。");
    addTag(body, "智能客服");
  }

  document.addEventListener("DOMContentLoaded", () => {
    const input = $("#input");
    const sendBtn = $("#send");
    $("#new-chat").addEventListener("click", newConversation);
    $("#human-btn").addEventListener("click", () => {
      if (!streaming) send("转人工");
    });
    sendBtn.addEventListener("click", () => send(input.value));
    $$("[data-demo]").forEach((btn) =>
      btn.addEventListener("click", () => send(btn.dataset.demo))
    );
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        send(input.value);
        input.value = "";
      }
    });
    addWelcome();
    restoreHistory();
    input.focus();
  });
})();
