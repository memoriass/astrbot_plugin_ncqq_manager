(function () {
  const els = {
    approvals: document.getElementById("approvals"),
    bindings: document.getElementById("bindings"),
    contextLine: document.getElementById("context-line"),
    kpis: document.getElementById("kpis"),
    managers: document.getElementById("managers"),
    refresh: document.getElementById("refresh"),
    toast: document.getElementById("toast"),
  };

  let bridge = null;
  let currentData = null;

  const mockData = {
    generated_at: Date.now() / 1000,
    default_manager: "local",
    managers: [
      {
        id: "local",
        name: "本地面板",
        url: "http://127.0.0.1:8080",
        is_default: true,
        health: {
          ok: true,
          status: "ok",
          docker: true,
          async_docker: true,
          state_engine: true,
          degraded_reasons: [],
        },
        bots: { ok: true, total: 3, online: 2 },
        instances: {
          ok: true,
          running: 2,
          total: 3,
          items: [
            { name: "alpha", status: "running", running: true, bot_online: true, uin: "10001" },
            { name: "beta", status: "running", running: true, bot_online: false, uin: "" },
            { name: "gamma", status: "exited", running: false, bot_online: false, uin: "" },
          ],
        },
        backends: {
          ok: true,
          total: 2,
          items: [
            { alias: "astrbot", url: "ws://127.0.0.1/ws", has_token: true },
            { alias: "cloud", url: "wss://example.com/ws", has_token: false },
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
      { qq: "123456", nickname: "Alice", instances: ["local/alpha", "cloud/demo"] },
      { qq: "654321", nickname: "", instances: ["local/beta"] },
    ],
    health_snapshot: [
      { ref: "local/alpha", online: true },
      { ref: "local/beta", online: false },
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
    return `${Math.floor(value / 3600)}h ${Math.floor((value % 3600) / 60)}m`;
  }

  function statusClass(ok, warn) {
    if (!ok) return "bad";
    return warn ? "warn" : "ok";
  }

  function statusLabel(ok, warn) {
    if (!ok) return "FAIL";
    return warn ? "WARN" : "OK";
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

  function render(data) {
    renderKpis(data);
    renderManagers(data.managers || []);
    renderApprovals(data.approvals || []);
    renderBindings(data.bindings || []);
    if (bridge) {
      els.contextLine.textContent = `更新 ${fmtTime(data.generated_at)}`;
    }
  }

  function renderKpis(data) {
    const managers = data.managers || [];
    const approvals = data.approvals || [];
    const managerCount = managers.length;
    const running = managers.reduce((sum, item) => sum + Number(item.instances?.running || 0), 0);
    const total = managers.reduce((sum, item) => sum + Number(item.instances?.total || 0), 0);
    const online = managers.reduce((sum, item) => sum + Number(item.bots?.online || 0), 0);
    const botTotal = managers.reduce((sum, item) => sum + Number(item.bots?.total || 0), 0);
    els.kpis.innerHTML = [
      kpi("Manager", managerCount),
      kpi("实例", `${running}/${total}`),
      kpi("Bot", `${online}/${botTotal}`),
      kpi("审批", approvals.length),
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
    els.managers.innerHTML = managers.map(renderManager).join("");
  }

  function renderManager(manager) {
    const health = manager.health || {};
    const inst = manager.instances || {};
    const backends = manager.backends || {};
    const warn = Boolean((health.degraded_reasons || []).length);
    return `
      <article class="manager-card">
        <div class="manager-head">
          <div>
            <h3>${escapeHtml(manager.name || manager.id)}</h3>
            <p>${escapeHtml(manager.id)}${manager.is_default ? " · default" : ""}</p>
          </div>
          <span class="pill ${statusClass(health.ok, warn)}">${statusLabel(health.ok, warn)}</span>
        </div>
        <div class="metric-row">
          <span>Docker ${health.docker ? "on" : "off"}</span>
          <span>Engine ${health.state_engine ? "on" : "off"}</span>
          <span>Bot ${escapeHtml(`${manager.bots?.online || 0}/${manager.bots?.total || 0}`)}</span>
          <span>后端 ${escapeHtml(backends.total || 0)}</span>
        </div>
        <div class="subhead">实例</div>
        <div class="rows">${renderInstances(inst)}</div>
        <div class="subhead">后端</div>
        <div class="rows">${renderBackends(backends)}</div>
      </article>
    `;
  }

  function renderInstances(instances) {
    if (!instances.ok) return `<div class="empty error">${escapeHtml(instances.error || "读取失败")}</div>`;
    const items = instances.items || [];
    if (!items.length) return empty("暂无实例");
    return items
      .map(
        (item) => `
        <div class="data-row">
          <span class="dot ${item.running ? "ok" : "bad"}"></span>
          <strong>${escapeHtml(item.name)}</strong>
          <span>${escapeHtml(item.status)}</span>
          <span>${item.bot_online ? "online" : "offline"}${item.uin ? ` · ${escapeHtml(item.uin)}` : ""}</span>
        </div>
      `,
      )
      .join("");
  }

  function renderBackends(backends) {
    if (!backends.ok) return `<div class="empty error">${escapeHtml(backends.error || "读取失败")}</div>`;
    const items = backends.items || [];
    if (!items.length) return empty("暂无后端");
    return items
      .map(
        (item) => `
        <div class="data-row">
          <span class="dot ${item.has_token ? "ok" : "warn"}"></span>
          <strong>${escapeHtml(item.alias)}</strong>
          <span>${escapeHtml(item.url)}</span>
        </div>
      `,
      )
      .join("");
  }

  function renderApprovals(approvals) {
    if (!approvals.length) {
      els.approvals.innerHTML = empty("暂无审批");
      return;
    }
    els.approvals.innerHTML = approvals
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
      .join("");
  }

  function renderBindings(bindings) {
    if (!bindings.length) {
      els.bindings.innerHTML = empty("暂无绑定");
      return;
    }
    els.bindings.innerHTML = bindings
      .map(
        (item) => `
        <div class="binding">
          <strong>${escapeHtml(item.nickname || item.qq)}</strong>
          <span>${escapeHtml(item.qq)}</span>
          <p>${escapeHtml((item.instances || []).join(" · ") || "-")}</p>
        </div>
      `,
      )
      .join("");
  }

  function empty(text) {
    return `<div class="empty">${escapeHtml(text)}</div>`;
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

  els.refresh.addEventListener("click", loadData);
  els.approvals.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    handleApproval(button.dataset.action, button.dataset.id);
  });

  initBridge().then(loadData).catch((error) => showToast(error.message || String(error), true));
})();
