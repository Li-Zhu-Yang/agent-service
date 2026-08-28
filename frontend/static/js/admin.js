/* 运营后台：登录 + 概览 / 工单 / 报表 / 知识库 / 会话 */
(function () {
  "use strict";

  const TOKEN_KEY = "ragent_admin_token";
  const USER_KEY = "ragent_admin_user";
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => document.querySelectorAll(s);

  let currentTab = "overview";

  /* ---------- 基础工具 ---------- */
  async function api(path, opts = {}) {
    const headers = Object.assign({}, opts.headers || {});
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) headers["Authorization"] = "Bearer " + token;
    if (opts.body && !(opts.body instanceof FormData)) headers["Content-Type"] = "application/json";
    const res = await fetch(path, Object.assign({}, opts, { headers }));
    if (res.status === 401) {
      logout();
      throw new Error("登录已过期，请重新登录");
    }
    const json = await res.json().catch(() => ({ data: null, message: "响应解析失败" }));
    if (!res.ok) throw new Error(json.message || "请求失败 " + res.status);
    return json.data;
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function toast(msg, ok = true) {
    const t = $("#toast");
    t.textContent = msg;
    t.style.background = ok ? "#0f172a" : "#dc2626";
    t.classList.add("show");
    clearTimeout(t._timer);
    t._timer = setTimeout(() => t.classList.remove("show"), 2200);
  }

  function modal(title, bodyHtml, onClose) {
    const mask = document.createElement("div");
    mask.className = "modal-mask";
    mask.innerHTML =
      '<div class="modal"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">' +
      "<h3 style='margin:0'>" + title + "</h3>" +
      '<button class="btn ghost sm" id="m-close">关闭</button></div><div id="m-body">' +
      bodyHtml + "</div></div>";
    mask.addEventListener("click", (e) => {
      if (e.target === mask) close();
    });
    mask.querySelector("#m-close").addEventListener("click", close);
    function close() {
      mask.remove();
      if (onClose) onClose();
    }
    document.body.appendChild(mask);
    return { mask, body: mask.querySelector("#m-body"), close };
  }

  function badge(cls, text) {
    return '<span class="badge ' + cls + '">' + esc(text) + "</span>";
  }

  /* ---------- 登录 ---------- */
  async function login() {
    const username = $("#login-user").value.trim();
    const password = $("#login-pass").value;
    if (!username || !password) return toast("请输入账号密码", false);
    try {
      const data = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      localStorage.setItem(TOKEN_KEY, data.access_token);
      localStorage.setItem(USER_KEY, JSON.stringify(data.user));
      showApp();
      toast("登录成功：" + (data.user.display_name || data.user.username));
    } catch (e) {
      toast(e.message, false);
    }
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    $("#login-wrap").classList.remove("hidden");
    $("#admin-wrap").classList.add("hidden");
  }

  function showApp() {
    $("#login-wrap").classList.add("hidden");
    $("#admin-wrap").classList.remove("hidden");
    const user = JSON.parse(localStorage.getItem(USER_KEY) || "{}");
    $("#admin-user").textContent = user.username || "";
    switchTab("overview");
  }

  /* ---------- Tab 导航 ---------- */
  function switchTab(name) {
    currentTab = name;
    $$(".nav-item").forEach((n) => n.classList.toggle("active", n.dataset.tab === name));
    $$(".tab-pane").forEach((p) => p.classList.toggle("hidden", p.id !== "pane-" + name));
    const titles = {
      overview: "运营概览", tickets: "问题工单", reports: "每日报表",
      knowledge: "知识库", conversations: "会话记录",
    };
    $("#page-title").textContent = titles[name] || "";
    const refresh = {
      overview: renderOverview, tickets: renderTickets, reports: renderReports,
      knowledge: renderKnowledge, conversations: renderConversations,
    }[name];
    if (refresh) refresh().catch((e) => toast(e.message, false));
  }

  /* ---------- 概览 ---------- */
  async function renderOverview() {
    const data = await api("/api/admin/overview");
    $("#overview-grid").innerHTML = [
      ["会话总数", data.total_conversations],
      ["今日咨询量", data.today_questions],
      ["未结工单", data.open_tickets],
      ["知识库文档", data.total_documents],
      ["向量分块", data.vector_chunks],
    ]
      .map(([label, value]) =>
        '<div class="stat-card"><div class="label">' + label + '</div><div class="value">' + value + "</div></div>"
      )
      .join("");
  }

  /* ---------- 工单 ---------- */
  async function renderTickets() {
    const data = await api("/api/admin/tickets");
    const tbody = $("#tickets-body");
    if (!data.length) {
      tbody.innerHTML = '<tr><td colspan="8" class="empty">暂无工单</td></tr>';
      return;
    }
    tbody.innerHTML = data
      .map(
        (t) =>
          "<tr class='row-click' data-id='" + t.id + "'>" +
          "<td>" + esc(t.ticket_no) + "</td>" +
          "<td>" + esc(t.issue_summary.slice(0, 30)) + "</td>" +
          "<td>" + esc(t.intent) + "</td>" +
          "<td>" + badge(t.priority, t.priority) + "</td>" +
          "<td>" + badge(t.status, t.status) + "</td>" +
          "<td>" + (t.assigned_to ? esc(t.assigned_to) : "—") + "</td>" +
          "<td>" + esc((t.created_at || "").slice(0, 16).replace("T", " ")) + "</td>" +
          "</tr>"
      )
      .join("");
    tbody.querySelectorAll("tr[data-id]").forEach((tr) =>
      tr.addEventListener("click", () => openTicket(Number(tr.dataset.id)))
    );
  }

  async function openTicket(id) {
    const t = await api("/api/admin/tickets/" + id);
    const transcript = (t.transcript || [])
      .map((m) => "<div><b>" + esc(m.role) + "：</b>" + esc(m.content) + "</div>")
      .join("");
    const { body, close } = modal("工单 " + t.ticket_no, "");
    body.innerHTML =
      "<p><b>问题：</b>" + esc(t.customer_text) + "</p>" +
      "<p><b>摘要：</b>" + esc(t.issue_summary) + "</p>" +
      "<p><b>意图：</b>" + esc(t.intent) + " ｜ 置信度：" + (t.confidence || 0).toFixed(2) + " ｜ 优先级：" + badge(t.priority, t.priority) + " ｜ 状态：" + badge(t.status, t.status) + "</p>" +
      "<div style='margin:10px 0'><b>对话记录：</b>" + (transcript || '<div class="empty">无</div>') + "</div>" +
      "<div class='form-row'>" +
      "<select id='t-status'><option value='open'>open</option><option value='accepted'>accepted</option><option value='closed'>closed</option></select>" +
      "<input id='t-assign' placeholder='指派给（客服名）' value='" + esc(t.assigned_to) + "'>" +
      "<button class='btn sm' id='t-save'>保存</button>" +
      "</div>";
    body.querySelector("#t-status").value = t.status;
    body.querySelector("#t-save").addEventListener("click", async () => {
      try {
        await api("/api/admin/tickets/" + id, {
          method: "PATCH",
          body: JSON.stringify({
            status: body.querySelector("#t-status").value,
            assigned_to: body.querySelector("#t-assign").value.trim(),
          }),
        });
        toast("工单已更新");
        close();
        renderTickets();
      } catch (e) {
        toast(e.message, false);
      }
    });
  }

  /* ---------- 报表 ---------- */
  async function renderReports() {
    const r = await api("/api/admin/reports/daily");
    $("#report-stats").innerHTML = [
      ["问题总量", r.total_questions],
      ["已解决", r.resolved_questions],
      ["未解决", r.unresolved_questions],
      ["转人工", r.transferred_count],
      ["平均响应(ms)", r.avg_latency_ms],
      ["缓存命中率", Math.round(r.cache_hit_rate * 100) + "%"],
    ]
      .map(([label, value]) =>
        '<div class="stat-card"><div class="label">' + label + '</div><div class="value">' + value + "</div></div>"
      )
      .join("");

    const freq = Object.entries(r.high_frequency || {});
    $("#report-freq").innerHTML = freq.length
      ? freq.map(([q, c], i) =>
          '<div class="bar-wrap"><span class="bar-label">#' + (i + 1) + "</span>" +
          '<div class="bar" style="flex:3"><i style="width:100%"></i></div>' +
          '<span class="bar-val">' + c + "</span><span style='flex:3'>" + esc(q) + "</span></div>"
        ).join("")
      : '<div class="empty">今日暂无咨询</div>';

    const dist = Object.entries(r.intent_distribution || {});
    const max = Math.max(1, ...dist.map(([, v]) => v));
    $("#report-dist").innerHTML = dist.length
      ? dist.map(([k, v]) =>
          '<div class="bar-wrap"><span class="bar-label">' + esc(k) + "</span>" +
          '<div class="bar"><i style="width:' + Math.round((v / max) * 100) + '%"></i></div>' +
          '<span class="bar-val">' + v + "</span></div>"
        ).join("")
      : '<div class="empty">暂无数据</div>';

    $("#report-actions").innerHTML =
      "<button class='btn sm' id='regen'>重新生成今日报表</button>";
    $("#regen").addEventListener("click", async () => {
      await api("/api/admin/reports/generate", { method: "POST" });
      toast("报表已生成");
      renderReports();
    });
  }

  /* ---------- 知识库 ---------- */
  async function renderKnowledge() {
    const docs = await api("/api/knowledge/documents");
    const tbody = $("#kb-body");
    tbody.innerHTML = docs.length
      ? docs
          .map(
            (d) =>
              "<tr>" +
              "<td>" + esc(d.title) + "</td>" +
              "<td>" + badge(d.status, d.status) + "</td>" +
              "<td>" + d.chunk_count + "</td>" +
              "<td>" + d.content_length + "</td>" +
              "<td>" + esc(d.category) + "</td>" +
              "<td><button class='btn danger sm' data-id='" + esc(d.doc_id) + "'>删除</button></td>" +
              "</tr>"
          )
          .join("")
      : '<tr><td colspan="6" class="empty">知识库为空，请先上传或录入文档</td></tr>';

    tbody.querySelectorAll("button[data-id]").forEach((btn) =>
      btn.addEventListener("click", async () => {
        if (!confirm("确定删除该文档及其全部向量分块？")) return;
        try {
          await api("/api/knowledge/documents/" + encodeURIComponent(btn.dataset.id), {
            method: "DELETE",
          });
          toast("已删除");
          renderKnowledge();
        } catch (e) {
          toast(e.message, false);
        }
      })
    );

    $("#kb-search-btn").onclick = async () => {
      const q = $("#kb-search").value.trim();
      if (!q) return toast("请输入检索词", false);
      const results = await api("/api/knowledge/search", {
        method: "POST",
        body: JSON.stringify({ query: q, top_k: 5 }),
      });
      $("#kb-results").innerHTML = results.length
        ? results
            .map(
              (r) =>
                "<div class='card' style='margin-bottom:10px'><h3>" + esc(r.title) + "（score " + (r.score || 0).toFixed(3) + "）</h3>" +
                "<p style='font-size:13px;white-space:pre-wrap'>" + esc(r.chunk) + "</p></div>"
            )
            .join("")
        : '<div class="empty">未检索到相关内容</div>';
    };
  }

  async function uploadKb() {
    const file = $("#kb-file").files[0];
    if (!file) return toast("请选择文件", false);
    const form = new FormData();
    form.append("file", file);
    const data = await api("/api/knowledge/upload", { method: "POST", body: form });
    toast("入库成功：" + data.title + "（" + data.chunk_count + " 块）");
    $("#kb-file").value = "";
    renderKnowledge();
  }

  async function ingestKbText() {
    const title = $("#kb-title").value.trim();
    const text = $("#kb-text").value.trim();
    if (!title || !text) return toast("请输入标题和内容", false);
    await api("/api/knowledge/text", {
      method: "POST",
      body: JSON.stringify({ title, text, category: "文本录入" }),
    });
    toast("入库成功");
    $("#kb-title").value = "";
    $("#kb-text").value = "";
    renderKnowledge();
  }

  /* ---------- 会话 ---------- */
  async function renderConversations() {
    const list = await api("/api/admin/conversations");
    const tbody = $("#conv-body");
    tbody.innerHTML = list.length
      ? list
          .map(
            (c) =>
              "<tr class='row-click' data-sid='" + esc(c.session_id) + "'>" +
              "<td>" + esc(c.title) + "</td>" +
              "<td>" + esc(c.intent_summary) + "</td>" +
              "<td>" + badge(c.status, c.status) + "</td>" +
              "<td>" + c.message_count + "</td>" +
              "<td>" + esc(c.last_message.slice(0, 40)) + "</td>" +
              "<td>" + esc((c.created_at || "").slice(0, 16).replace("T", " ")) + "</td>" +
              "</tr>"
          )
          .join("")
      : '<tr><td colspan="6" class="empty">暂无会话</td></tr>';
    tbody.querySelectorAll("tr[data-sid]").forEach((tr) =>
      tr.addEventListener("click", () => openConversation(tr.dataset.sid))
    );
  }

  async function openConversation(sid) {
    const data = await api("/api/admin/conversations/" + encodeURIComponent(sid) + "/messages");
    const html = data
      .map(
        (m) =>
          "<div style='margin:8px 0'><b style='color:" +
          (m.role === "user" ? "#2563eb" : "#475569") + "'>" + esc(m.role) + "：</b>" +
          esc(m.content) +
          (m.intent ? " <span class='badge normal'>" + esc(m.intent) + "</span>" : "") +
          (m.need_human ? " <span class='badge high'>转人工</span>" : "") +
          (m.from_cache ? " <span class='badge closed'>缓存</span>" : "") +
          "</div>"
      )
      .join("");
    modal("会话 " + sid, html || '<div class="empty">无消息</div>');
  }

  /* ---------- 初始化 ---------- */
  document.addEventListener("DOMContentLoaded", () => {
    $("#login-btn").addEventListener("click", login);
    $("#login-pass").addEventListener("keydown", (e) => e.key === "Enter" && login());
    $("#logout-btn").addEventListener("click", logout);
    $("#kb-upload-btn").addEventListener("click", uploadKb);
    $("#kb-ingest-btn").addEventListener("click", ingestKbText);
    $$(".nav-item").forEach((n) => n.addEventListener("click", () => switchTab(n.dataset.tab)));

    if (localStorage.getItem(TOKEN_KEY)) {
      showApp();
    } else {
      logout();
    }
  });
})();
