(function () {
  const els = {
    approvals: document.getElementById("approvals"),
    bindings: document.getElementById("bindings"),
    contextLine: document.getElementById("context-line"),
    kpis: document.getElementById("kpis"),
    managers: document.getElementById("managers"),
    refresh: document.getElementById("refresh"),
    toast: document.getElementById("toast"),
    tabs: document.getElementById("view-tabs"),
  };

  let bridge = null;
  let currentData = null;
  let activeView = "instances";
  const pageSize = { instances: 9, bindings: 8 };
  const pages = { instances: {}, bindings: 1 };

  const mockData = {
    generated_at: Date.now() / 1000,
    default_manager: "local",
    managers: [
      {
        id: "local",
        name: "本地面板",
        url: "http://127.0.0.1:8080",
        is_default: true,
        health: { ok: true, status: "ok", docker: true, state_engine: true, degraded_reasons: [] },
        bots: { ok: true, total: 10, online: 5 },
        instances: {
          ok: true,
          running: 7,
          online: 5,
          total: 10,
          items: [
            {
              name: "baka9",
              display_name: "baka9",
              status: "running",
              running: true,
              bot_online: true,
              uin: "315000754",
              avatar: "https://q1.qlogo.cn/g?b=qq&nk=315000754&s=100",
              login_stage: "logged_in",
              login_method: "sdk_ws",
              heartbeat_ts: Date.now() / 1000 - 60,
            },
            {
              name: "698076448",
              display_name: "698076448",
              status: "running",
              running: true,
              bot_online: true,
              uin: "171000139",
              avatar: "https://q1.qlogo.cn/g?b=qq&nk=171000139&s=100",
              login_stage: "logged_in",
            },
            {
              name: "788952021",
              display_name: "788952021",
              status: "exited",
              running: false,
              bot_online: false,
              uin: "",
              avatar: "",
              login_stage: "offline",
            },
            {
              name: "1154121306",
              display_name: "1154121306",
              status: "exited",
              running: false,
              bot_online: false,
              uin: "",
              avatar: "",
              login_stage: "offline",
            },
            {
              name: "miya",
              display_name: "miya",
              status: "running",
              running: true,
              bot_online: false,
              uin: "240000846",
              avatar: "https://q1.qlogo.cn/g?b=qq&nk=240000846&s=100",
              login_stage: "offline",
              heartbeat_ts: Date.now() / 1000 - 5400,
            },
            { name: "moka", display_name: "moka", status: "running", running: true, bot_online: true, uin: "100000001", avatar: "https://q1.qlogo.cn/g?b=qq&nk=100000001&s=100" },
            { name: "kira", display_name: "kira", status: "running", running: true, bot_online: false, uin: "100000002", avatar: "https://q1.qlogo.cn/g?b=qq&nk=100000002&s=100" },
            { name: "nana", display_name: "nana", status: "exited", running: false, bot_online: false, uin: "", avatar: "" },
            { name: "sora", display_name: "sora", status: "running", running: true, bot_online: true, uin: "100000003", avatar: "https://q1.qlogo.cn/g?b=qq&nk=100000003&s=100" },
            { name: "yuki", display_name: "yuki", status: "running", running: true, bot_online: true, uin: "100000004", avatar: "https://q1.qlogo.cn/g?b=qq&nk=100000004&s=100" },
          ],
        },
      },
      {
        id: "cloud",
        name: "云端面板",
        url: "https://ncqq.example.com",
        is_default: false,
        health: { ok: true, status: "degraded", docker: true, state_engine: true, degraded_reasons: ["heartbeat"] },
        bots: { ok: true, total: 3, online: 1 },
        instances: {
          ok: true,
          running: 2,
          online: 1,
          total: 3,
          items: [
            {
              name: "demo",
              display_name: "demo",
              status: "running",
              running: true,
              bot_online: true,
              uin: "112233445",
              avatar: "https://q1.qlogo.cn/g?b=qq&nk=112233445&s=100",
            },
            {
              name: "ops",
              display_name: "ops",
              status: "running",
              running: true,
              bot_online: false,
              uin: "223344556",
              avatar: "https://q1.qlogo.cn/g?b=qq&nk=223344556&s=100",
            },
            {
              name: "spare",
              display_name: "spare",
              status: "exited",
              running: false,
              bot_online: false,
              uin: "",
              avatar: "",
            },
          ],
        },
      },
    ],
    approvals: [
      {
        approval_id: "AB12CD",
        action: "delete",
        description: "销毁实例 cloud/demo",
        requester_qq: "123456",
        group_id: "987654",
        age_seconds: 420,
        manager_id: "cloud",
        instance_name: "demo",
      },
    ],
    bindings: [
      { qq: "123456", nickname: "Alice", instances: ["local/baka9", "cloud/demo"] },
      { qq: "654321", nickname: "", instances: ["local/miya"] },
      { qq: "100001", nickname: "B01", instances: ["local/moka"] },
      { qq: "100002", nickname: "B02", instances: ["local/kira"] },
      { qq: "100003", nickname: "B03", instances: ["local/nana"] },
      { qq: "100004", nickname: "B04", instances: ["cloud/ops"] },
      { qq: "100005", nickname: "B05", instances: ["cloud/spare"] },
      { qq: "100006", nickname: "B06", instances: ["local/698076448"] },
      { qq: "100007", nickname: "B07", instances: ["local/sora"] },
      { qq: "100008", nickname: "B08", instances: ["local/yuki"] },
      { qq: "100009", nickname: "B09", instances: ["cloud/demo"] },
    ],
  };

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function fmtTime(seconds) {
    if (!seconds) return "-";
    return new Date(seconds * 1000).toLocaleString("zh-CN", { hour12: false });
  }

  function fmtAge(seconds) {
    const value = Number(seconds || 0);
    if (value < 60) return `${value}s`;
    if (value < 3600) return `${Math.floor(value / 60)}m`;
    return `${Math.floor(value / 3600)}h`;
  }

  function maskQQ(value) {
    const text = String(value || "").trim();
    if (text.length < 7) return text || "-";
    return `${text.slice(0, 3)}****${text.slice(-3)}`;
  }

  function shortUrl(value) {
    const text = String(value || "").trim();
    if (!text || text === "-") return "-";
    try {
      return new URL(text).host;
    } catch {
      return text.replace(/^https?:\/\//, "").replace(/^wss?:\/\//, "");
    }
  }

  function instanceState(item) {
    if (item.bot_online) return { key: "online", text: "在线" };
    if (item.running) return { key: "warn", text: "心跳丢失" };
    return { key: "offline", text: "离线" };
  }

  function clampPage(value, total, size) {
    const max = Math.max(1, Math.ceil(total / size));
    const page = Number(value || 1);
    return Math.min(Math.max(1, page), max);
  }

  function pageSlice(items, page, size) {
    return items.slice((page - 1) * size, page * size);
  }

  function renderPager(scope, key, page, total, size) {
    const max = Math.ceil(total / size);
    if (max <= 1) return "";
    return `
      <div class="pager" aria-label="分页">
        <button type="button" data-page-scope="${escapeHtml(scope)}" data-page-key="${escapeHtml(key)}" data-page="${page - 1}" ${page <= 1 ? "disabled" : ""}>上一页</button>
        <span>${page}/${max}</span>
        <button type="button" data-page-scope="${escapeHtml(scope)}" data-page-key="${escapeHtml(key)}" data-page="${page + 1}" ${page >= max ? "disabled" : ""}>下一页</button>
      </div>
    `;
  }

  async function initBridge() {
    if (window.AstrBotPluginPage) {
      bridge = window.AstrBotPluginPage;
      const context = await bridge.ready();
      els.contextLine.textContent = `${context.displayName || "ncqq_manager"} · ${context.pageName || "dashboard"}`;
      return;
    }
    els.contextLine.textContent = "local preview";
  }

  async function loadData() {
    setLoading(true);
    try {
      currentData = bridge ? await bridge.apiGet("dashboard/summary") : mockData;
      render(currentData);
    } catch (error) {
      showToast(error.message || String(error), true);
    } finally {
      setLoading(false);
    }
  }

  function setLoading(loading) {
    els.refresh.disabled = loading;
    els.refresh.classList.toggle("spin", loading);
  }

  function setActiveView(view) {
    activeView = view || "instances";
    document.querySelectorAll("[data-view]").forEach((item) => {
      item.classList.toggle("active", item.dataset.view === activeView);
    });
    document.querySelectorAll("[data-view-panel]").forEach((item) => {
      item.classList.toggle("active", item.dataset.viewPanel === activeView);
    });
  }

  function render(data) {
    renderKpis(data);
    renderManagers(data.managers || []);
    renderApprovals(data.approvals || []);
    renderBindings(data.bindings || []);
    if (bridge) els.contextLine.textContent = `更新 ${fmtTime(data.generated_at)}`;
  }

  function renderKpis(data) {
    const managers = data.managers || [];
    const approvals = data.approvals || [];
    const running = managers.reduce((sum, item) => sum + Number(item.instances?.running || 0), 0);
    const total = managers.reduce((sum, item) => sum + Number(item.instances?.total || 0), 0);
    const online = managers.reduce((sum, item) => sum + Number(item.instances?.online || 0), 0);
    const healthyManagers = managers.reduce((sum, item) => sum + (item.health?.ok ? 1 : 0), 0);
    els.kpis.innerHTML = [
      kpi("ncqq 后端", `${healthyManagers}/${managers.length}`),
      kpi("实例在线", `${online}/${total}`),
      kpi("容器运行", `${running}/${total}`),
      kpi("待审批", approvals.length),
    ].join("");
  }

  function kpi(label, value) {
    return `<article class="kpi"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`;
  }

  function renderManagers(managers) {
    if (!managers.length) {
      els.managers.innerHTML = empty("暂无 Manager");
      return;
    }
    els.managers.innerHTML = managers.map(renderManagerSection).join("");
  }

  function renderManagerSection(manager) {
    const instances = manager.instances || {};
    const health = manager.health || {};
    const items = instances.items || [];
    const page = clampPage(pages.instances[manager.id], items.length, pageSize.instances);
    const pageItems = pageSlice(items, page, pageSize.instances);
    const warn = Boolean((health.degraded_reasons || []).length);
    const state = health.ok ? (warn ? "warn" : "online") : "offline";
    const url = shortUrl(manager.url);
    pages.instances[manager.id] = page;
    return `
      <section class="manager-section">
        <div class="manager-title">
          <div>
            <h2>${escapeHtml(manager.name || manager.id)}</h2>
            <p class="manager-url">${escapeHtml(manager.id)} · ${escapeHtml(url)}${manager.is_default ? " · default" : ""}</p>
          </div>
          <div class="manager-meta">
            <span class="status-chip ${state}">${escapeHtml(health.status || "-")}</span>
            <span>实例 ${escapeHtml(`${instances.online || 0}/${instances.total || 0}`)}</span>
            <span>容器 ${escapeHtml(`${instances.running || 0}/${instances.total || 0}`)}</span>
          </div>
        </div>
        ${instances.ok ? renderInstancePage(pageItems, manager.id, page, items.length) : empty(instances.error || "实例读取失败", true)}
      </section>
    `;
  }

  function renderInstancePage(items, managerId, page, total) {
    const body = items.length ? `<div class="instance-grid">${items.map(renderInstanceCard).join("")}</div>` : empty("暂无实例");
    return body + renderPager("instances", managerId, page, total, pageSize.instances);
  }

  function renderInstanceCard(item) {
    const state = instanceState(item);
    const avatar = String(item.avatar || "").trim();
    const name = item.display_name || item.name;
    const bgStyle = avatar ? ` style="--instance-bg:url('${escapeHtml(avatar)}')"` : "";
    return `
      <article class="instance-card ${state.key}"${bgStyle}>
        <div class="instance-card-body">
          <h3>${escapeHtml(name)}</h3>
          <div class="instance-avatar${avatar ? "" : " empty-avatar"}">
            ${avatar ? `<img src="${escapeHtml(avatar)}" alt="" loading="lazy" onerror="this.remove()" />` : "<span>OFF</span>"}
          </div>
          <p>QQ: ${escapeHtml(maskQQ(item.uin))}</p>
        </div>
        <div class="instance-foot">
          <span class="instance-state ${state.key}">${escapeHtml(state.text)}</span>
          <button class="instance-refresh" type="button" data-refresh title="刷新" aria-label="刷新实例数据">&#8635;</button>
        </div>
      </article>
    `;
  }

  function renderApprovals(approvals) {
    if (!approvals.length) {
      els.approvals.innerHTML = empty("暂无审批");
      return;
    }
    els.approvals.innerHTML = `<div class="approval-grid">${approvals
      .map(
        (item) => `
        <article class="approval">
          <div>
            <h3>${escapeHtml(item.description || item.action)}</h3>
            <p>${escapeHtml(item.approval_id)} · ${escapeHtml(item.manager_id || "-")}/${escapeHtml(item.instance_name || "-")} · ${fmtAge(item.age_seconds)}</p>
            <p>QQ ${escapeHtml(item.requester_qq || "-")}${item.group_id ? ` · 群 ${escapeHtml(item.group_id)}` : ""}</p>
          </div>
          <div class="approval-actions">
            <button class="approve" data-action="approve" data-id="${escapeHtml(item.approval_id)}">批准</button>
            <button class="reject" data-action="reject" data-id="${escapeHtml(item.approval_id)}">拒绝</button>
          </div>
        </article>
      `,
      )
      .join("")}</div>`;
  }

  function renderBindings(bindings) {
    if (!bindings.length) {
      els.bindings.innerHTML = empty("暂无绑定");
      return;
    }
    const page = clampPage(pages.bindings, bindings.length, pageSize.bindings);
    const items = pageSlice(bindings, page, pageSize.bindings);
    pages.bindings = page;
    els.bindings.innerHTML = `<div class="binding-grid">${items
      .map(
        (item) => `
        <div class="binding">
          <strong>${escapeHtml(item.nickname || item.qq)}</strong>
          <span>${escapeHtml(item.qq)}</span>
          <p>${escapeHtml((item.instances || []).join(" · ") || "-")}</p>
        </div>
      `,
      )
      .join("")}</div>${renderPager("bindings", "bindings", page, bindings.length, pageSize.bindings)}`;
  }

  function empty(text, error) {
    return `<div class="empty${error ? " error" : ""}">${escapeHtml(text)}</div>`;
  }

  async function handleApproval(action, approvalId) {
    if (!approvalId) return;
    if (action === "approve" && !window.confirm(`批准 ${approvalId}?`)) return;
    let body = {};
    if (action === "reject") {
      const reason = window.prompt(`拒绝 ${approvalId}`, "");
      if (reason === null) return;
      body = { reason };
    }
    try {
      if (bridge) {
        await bridge.apiPost(`approvals/${approvalId}/${action}`, body);
      } else {
        currentData.approvals = (currentData.approvals || []).filter((item) => item.approval_id !== approvalId);
      }
      showToast(action === "approve" ? "已批准" : "已拒绝", false);
      await loadData();
    } catch (error) {
      showToast(error.message || String(error), true);
    }
  }

  function showToast(message, error) {
    els.toast.textContent = message;
    els.toast.classList.toggle("error", Boolean(error));
    els.toast.classList.add("show");
    window.setTimeout(() => els.toast.classList.remove("show"), 2400);
  }

  function handlePageButton(event) {
    const button = event.target.closest("button[data-page-scope]");
    if (!button) return false;
    if (button.dataset.pageScope === "instances") pages.instances[button.dataset.pageKey] = Number(button.dataset.page);
    if (button.dataset.pageScope === "bindings") pages.bindings = Number(button.dataset.page);
    if (currentData) render(currentData);
    return true;
  }

  els.refresh.addEventListener("click", loadData);
  els.tabs.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-view]");
    if (!button) return;
    setActiveView(button.dataset.view);
  });
  els.managers.addEventListener("click", (event) => {
    if (handlePageButton(event)) return;
    const button = event.target.closest("button[data-refresh]");
    if (!button) return;
    loadData();
  });
  els.bindings.addEventListener("click", handlePageButton);
  els.approvals.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    handleApproval(button.dataset.action, button.dataset.id);
  });

  setActiveView(activeView);
  initBridge().then(loadData).catch((error) => showToast(error.message || String(error), true));
})();
