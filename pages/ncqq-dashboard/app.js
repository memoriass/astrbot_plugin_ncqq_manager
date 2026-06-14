(function () {
  const els = {
    approvals: document.getElementById("approvals"),
    bindings: document.getElementById("bindings"),
    kpis: document.getElementById("kpis"),
    managers: document.getElementById("managers"),
    refresh: document.getElementById("refresh"),
    toast: document.getElementById("toast"),
    tabs: document.getElementById("view-tabs"),
  };

  let bridge = null;
  let currentData = null;
  let activeView = "instances";
  let activeManagerId = "";
  let instanceFilter = "all";
  const pageSize = { instances: 9, bindings: 8 };
  const pages = { instances: {}, bindings: 1 };
  const mockData = window.NcqqDashboardMockData || { managers: [], approvals: [], bindings: [] };
  const instanceFilters = [
    ["all", "全部"],
    ["abnormal", "异常"],
    ["warn", "心跳"],
    ["offline", "离线"],
  ];

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
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

  function managerState(health) {
    const warn = Boolean((health.degraded_reasons || []).length);
    return health.ok ? (warn ? "warn" : "online") : "offline";
  }

  function ensureActiveManager(managers) {
    if (managers.some((item) => item.id === activeManagerId)) return;
    const preferred = managers.find((item) => item.id === currentData?.default_manager);
    activeManagerId = (preferred || managers[0] || {}).id || "";
  }

  function filterInstances(items) {
    if (instanceFilter === "all") return items;
    return items.filter((item) => {
      const key = instanceState(item).key;
      if (instanceFilter === "abnormal") return key !== "online";
      return key === instanceFilter;
    });
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
      await bridge.ready();
      return;
    }
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
    ensureActiveManager(managers);
    const manager = managers.find((item) => item.id === activeManagerId) || managers[0];
    els.managers.innerHTML = renderManagerSelector(managers) + renderManagerSection(manager);
  }

  function renderManagerSelector(managers) {
    return `<div class="manager-selector" aria-label="后端选择">${managers.map(renderManagerCard).join("")}</div>`;
  }

  function renderManagerCard(manager) {
    const instances = manager.instances || {};
    const state = managerState(manager.health || {});
    const url = shortUrl(manager.url);
    return `
      <button class="manager-card ${manager.id === activeManagerId ? "active" : ""}" type="button" data-manager-id="${escapeHtml(manager.id)}" aria-pressed="${manager.id === activeManagerId}">
        <span class="manager-card-head">
          <strong>${escapeHtml(manager.name || manager.id)}</strong>
          <span class="status-chip ${state}">${escapeHtml(manager.health?.status || "-")}</span>
        </span>
        <span class="manager-card-url">${escapeHtml(manager.id)} · ${escapeHtml(url)}${manager.is_default ? " · default" : ""}</span>
        <span class="manager-card-stats">
          <span>实例 ${escapeHtml(`${instances.online || 0}/${instances.total || 0}`)}</span>
          <span>容器 ${escapeHtml(`${instances.running || 0}/${instances.total || 0}`)}</span>
        </span>
      </button>
    `;
  }

  function renderManagerSection(manager) {
    const instances = manager.instances || {};
    const health = manager.health || {};
    const items = instances.items || [];
    const filtered = filterInstances(items);
    const page = clampPage(pages.instances[manager.id], filtered.length, pageSize.instances);
    const pageItems = pageSlice(filtered, page, pageSize.instances);
    const state = managerState(health);
    const url = shortUrl(manager.url);
    pages.instances[manager.id] = page;
    return `
      <section class="manager-section">
        <div class="manager-title">
          <div>
            <h2>${escapeHtml(manager.name || manager.id)}</h2>
            <p class="manager-url">${escapeHtml(manager.id)} · ${escapeHtml(url)}${manager.is_default ? " · default" : ""}</p>
          </div>
          <div class="manager-actions">
            ${renderInstanceFilters(items)}
            <div class="manager-meta">
              <span class="status-chip ${state}">${escapeHtml(health.status || "-")}</span>
              <span>实例 ${escapeHtml(`${instances.online || 0}/${instances.total || 0}`)}</span>
              <span>容器 ${escapeHtml(`${instances.running || 0}/${instances.total || 0}`)}</span>
              ${instanceFilter === "all" ? "" : `<span>显示 ${escapeHtml(`${filtered.length}/${items.length}`)}</span>`}
            </div>
          </div>
        </div>
        ${instances.ok ? renderInstancePage(pageItems, manager.id, page, filtered.length) : empty(instances.error || "实例读取失败", true)}
      </section>
    `;
  }

  function renderInstanceFilters(items) {
    const counts = { all: items.length, abnormal: 0, warn: 0, offline: 0 };
    items.forEach((item) => {
      const key = instanceState(item).key;
      if (key !== "online") counts.abnormal += 1;
      if (counts[key] !== undefined) counts[key] += 1;
    });
    return `<div class="instance-filter" aria-label="实例筛选">${instanceFilters
      .map(
        ([key, label]) =>
          `<button class="${key === instanceFilter ? "active" : ""}" type="button" data-instance-filter="${key}">${label}<span>${counts[key]}</span></button>`,
      )
      .join("")}</div>`;
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
    const lookup = buildInstanceLookup(currentData?.managers || []);
    const page = clampPage(pages.bindings, bindings.length, pageSize.bindings);
    const items = pageSlice(bindings, page, pageSize.bindings);
    pages.bindings = page;
    els.bindings.innerHTML = `<div class="binding-grid">${items
      .map((item) => renderBindingCard(item, lookup))
      .join("")}</div>${renderPager("bindings", "bindings", page, bindings.length, pageSize.bindings)}`;
  }

  function buildInstanceLookup(managers) {
    const lookup = {};
    managers.forEach((manager) => {
      (manager.instances?.items || []).forEach((item) => {
        [item.name, item.display_name].filter(Boolean).forEach((name) => {
          lookup[`${manager.id}/${name}`] = item;
          if (manager.is_default) lookup[name] = item;
        });
      });
    });
    return lookup;
  }

  function renderBindingCard(item, lookup) {
    const refs = item.instances || [];
    const primary = refs.map((ref) => lookup[ref]).find(Boolean) || {};
    const avatar = String(primary.avatar || "").trim();
    const label = primary.display_name || primary.name || refs[0] || "-";
    const initial = String(label).slice(0, 1).toUpperCase();
    return `
      <article class="binding binding-card">
        <div class="binding-avatar${avatar ? "" : " no-avatar"}">
          ${avatar ? `<img src="${escapeHtml(avatar)}" alt="" loading="lazy" onerror="this.remove()" />` : `<span>${escapeHtml(initial)}</span>`}
        </div>
        <strong>${escapeHtml(item.qq || "-")}</strong>
        <p>${escapeHtml(label)}</p>
        <div class="binding-refs">
          ${refs.map((ref) => `<span>${escapeHtml(ref)}</span>`).join("") || "<span>-</span>"}
        </div>
      </article>
    `;
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
    const managerButton = event.target.closest("button[data-manager-id]");
    if (managerButton) {
      activeManagerId = managerButton.dataset.managerId || "";
      if (currentData) renderManagers(currentData.managers || []);
      return;
    }
    const filterButton = event.target.closest("button[data-instance-filter]");
    if (filterButton) {
      instanceFilter = filterButton.dataset.instanceFilter || "all";
      if (activeManagerId) pages.instances[activeManagerId] = 1;
      if (currentData) renderManagers(currentData.managers || []);
      return;
    }
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
