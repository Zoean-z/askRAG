const LONG_TERM_MEMORY_TYPES = new Set([
  "pinned_preference",
  "stable_profile_fact",
  "approved_long_term_fact",
]);
const PREFERENCE_MEMORY_TYPES = new Set(["pinned_preference"]);
const FACT_MEMORY_TYPES = new Set(["stable_profile_fact", "approved_long_term_fact"]);

const localeZhButton = document.querySelector("#localeZh");
const localeEnButton = document.querySelector("#localeEn");
const primaryNav = document.querySelector("#primaryNav");
const localeSwitch = document.querySelector("#localeSwitch");
const LOCALE_STORAGE_KEY = "askrag.locale";
const pageTitle = document.querySelector("#pageTitle");
const brandSubline = document.querySelector("#brandSubline");
const navChat = document.querySelector("#navChatLabel");
const navLibrary = document.querySelector("#navLibraryLabel");
const navMemory = document.querySelector("#navMemoryLabel");
const sidebarSettingsLabel = document.querySelector("#sidebarSettingsLabel");
const sidebarSupportLabel = document.querySelector("#sidebarSupportLabel");
const sidebarUserName = document.querySelector("#sidebarUserName");
const sidebarUserMeta = document.querySelector("#sidebarUserMeta");
const memoryStatusPill = document.querySelector("#memoryStatusPill");
const memoryScopePill = document.querySelector("#memoryScopePill");
const memorySearchLabel = document.querySelector("#memorySearchLabel");
const memorySearchInput = document.querySelector("#memorySearchInput");
const memoryNotificationsButton = document.querySelector("#memoryNotificationsButton");
const memoryHistoryButton = document.querySelector("#memoryHistoryButton");
const eyebrowText = document.querySelector("#eyebrowText");
const heroText = document.querySelector("#heroText");
const summaryLabel = document.querySelector("#summaryLabel");
const summaryValue = document.querySelector("#summaryValue");
const snapshotEyebrow = document.querySelector("#snapshotEyebrow");
const countsTitle = document.querySelector("#countsTitle");
const totalLabel = document.querySelector("#totalLabel");
const approvedLabel = document.querySelector("#approvedLabel");
const pendingLabel = document.querySelector("#pendingLabel");
const auditLabel = document.querySelector("#auditLabel");
const totalCount = document.querySelector("#totalCount");
const approvedCount = document.querySelector("#approvedCount");
const pendingCount = document.querySelector("#pendingCount");
const auditCount = document.querySelector("#auditCount");
const listEyebrow = document.querySelector("#listEyebrow");
const listTitle = document.querySelector("#listTitle");
const listText = document.querySelector("#listText");
const memoryActionEyebrow = document.querySelector("#memoryActionEyebrow");
const archiveMetaLabel = document.querySelector("#archiveMetaLabel");
const archiveMetaText = document.querySelector("#archiveMetaText");
const memoryLogicEyebrow = document.querySelector("#memoryLogicEyebrow");
const memoryLogicTitle = document.querySelector("#memoryLogicTitle");
const memoryLogicText = document.querySelector("#memoryLogicText");
const memoryStatus = document.querySelector("#memoryStatus");
const memoryArchiveEyebrow = document.querySelector("#memoryArchiveEyebrow");
const memoryArchiveTitle = document.querySelector("#memoryArchiveTitle");
const memoryArchiveMetaLabel = document.querySelector("#memoryArchiveMetaLabel");
const memoryArchiveMetaText = document.querySelector("#memoryArchiveMetaText");
const memoryPrivacyPill = document.querySelector("#memoryPrivacyPill");
const memoryRollbackPill = document.querySelector("#memoryRollbackPill");
const memoryCardTitle = document.querySelector("#memoryCardTitle");
const memoryCardText = document.querySelector("#memoryCardText");
const memoryPreviewEyebrow = document.querySelector("#memoryPreviewEyebrow");
const memoryPreviewTitle = document.querySelector("#memoryPreviewTitle");
const memoryPreviewText = document.querySelector("#memoryPreviewText");
const memoryFooterCopy = document.querySelector("#memoryFooterCopy");
const memoryExportButton = document.querySelector("#memoryExportButton");
const memoryPurgeButton = document.querySelector("#memoryPurgeButton");
const memoryList = document.querySelector("#memoryList");

const translations = {
  zh: {
    localeLabel: "简体中文",
    localeLabelShort: "English",
    title: "askRAG 记忆",
    brandSubline: "本地知识工作台",
    common: {
      primaryNavAria: "主导航",
      localeSwitchAria: "语言切换",
      settings: "设置",
      support: "帮助",
      userName: "askRAG 控制台",
      userMeta: "本地知识工作区",
      notifications: "通知",
      history: "历史",
    },
    nav: {
      chat: "对话",
      library: "知识库",
      memory: "记忆",
    },
    page: {
      eyebrow: "记忆",
      heading: "长期记忆",
      hero: "在独立页面里查看和移除会持续影响后续回答的长期记忆，不打断主对话工作区。",
      statusPill: "记忆已启用",
      scopePill: "记忆档案",
      searchPlaceholder: "搜索记忆...",
      searchAria: "搜索记忆",
      summaryLabel: "概览",
      snapshotEyebrow: "快照",
      countsTitle: "一览",
      totalLabel: "总数",
      approvedLabel: "偏好",
      pendingLabel: "事实",
      auditLabel: "当前显示",
      listEyebrow: "档案",
      listTitle: "已保存的长期记忆",
      listText: "查看仍会参与未来回答的长期偏好与稳定事实。",
      actionEyebrow: "操作",
      archiveMetaLabel: "处理",
      archiveMetaText: "如果某条记忆不该再影响后续回答，可以在这里删除。",
      logicEyebrow: "规则",
      logicTitle: "保留策略",
      logicText: "长期记忆会持续保留，直到用户在记忆档案中明确移除。",
      archiveEyebrow: "档案",
      archiveTitle: "已保存的长期记忆",
      archiveVisibleLabel: "显示范围",
      archiveVisibleText: "在这里删除条目后，它就不会再继续影响后续回答。",
      privacyPill: "隐私",
      rollbackPill: "可回滚",
      cardTitle: "记忆逻辑",
      cardText: "稳定偏好和事实可以单独移除，不会影响其他工作区内容。",
      previewEyebrow: "认知核心",
      previewTitle: "渐进式智能",
      previewText: "长期记忆应当像安静的档案，而不是吵闹的仪表盘。",
      footerCopy: "当前记忆占用：0.4%",
      exportButton: "导出数据",
      purgeButton: "清空全部记忆",
      loading: "正在读取长期记忆...",
      loadFailed: "读取长期记忆失败。",
      emptyStore: "当前还没有可管理的长期记忆。",
      emptyFiltered: "没有长期记忆匹配当前搜索。",
      summary: (total, preferences, facts) => `共 ${total} 条长期记忆，其中 ${preferences} 条偏好，${facts} 条事实。`,
      statusLine: (visible, total) => `当前显示 ${visible} / ${total} 条长期记忆。`,
      deleteAction: "删除",
      deletingAction: "删除中...",
      deleteConfirm: (title) => `确认删除“${title}”吗？删除后它将不再参与未来回答。`,
      deleteSuccess: (title) => `已删除长期记忆：${title}。`,
      deleteFailed: "删除长期记忆失败。",
      labels: {
        type: "类型",
        tags: "标签",
        updated: "更新时间",
      },
      values: {
        none: "无",
        unknown: "未知",
      },
      typeMap: {
        pinned_preference: "偏好",
        stable_profile_fact: "稳定事实",
        approved_long_term_fact: "长期事实",
      },
    },
  },
  en: {
    localeLabel: "Chinese",
    localeLabelShort: "English",
    title: "askRAG Memory",
    brandSubline: "Local Knowledge Workbench",
    common: {
      primaryNavAria: "Primary navigation",
      localeSwitchAria: "Language switcher",
      settings: "Settings",
      support: "Support",
      userName: "askRAG Console",
      userMeta: "Local knowledge workspace",
      notifications: "Notifications",
      history: "History",
    },
    nav: {
      chat: "Chat",
      library: "Library",
      memory: "Memory",
    },
    page: {
      eyebrow: "Memory",
      heading: "Long-term Memory",
      hero: "Review and remove durable assistant memory on a dedicated page without interrupting the main chat workspace.",
      statusPill: "Memory active",
      scopePill: "Memory archive",
      searchPlaceholder: "Search memories...",
      searchAria: "Search memories",
      summaryLabel: "Summary",
      snapshotEyebrow: "Snapshot",
      countsTitle: "At a glance",
      totalLabel: "Total",
      approvedLabel: "Preferences",
      pendingLabel: "Facts",
      auditLabel: "Visible",
      listEyebrow: "Archive",
      listTitle: "Saved long-term memories",
      listText: "Review durable preferences and stable facts that remain active for future answers.",
      actionEyebrow: "Action",
      archiveMetaLabel: "Action",
      archiveMetaText: "Delete an entry here when it should stop shaping future responses.",
      logicEyebrow: "Logic",
      logicTitle: "Retention policy",
      logicText: "Long-term entries stay visible until the user removes them from the memory archive.",
      archiveEyebrow: "Archive",
      archiveTitle: "Saved long-term memories",
      archiveVisibleLabel: "Visible",
      archiveVisibleText: "Delete entries here when they should stop shaping future responses.",
      privacyPill: "Privacy",
      rollbackPill: "Rollback safe",
      cardTitle: "Memory logic",
      cardText: "Stable preferences and facts can be removed without changing the rest of the workspace.",
      previewEyebrow: "Cognitive core",
      previewTitle: "Evolving Intelligence",
      previewText: "Durable memory is treated as a quiet archive, not as a loud dashboard.",
      footerCopy: "Total memory usage: 0.4%",
      exportButton: "Export Data",
      purgeButton: "Purge All Memory",
      loading: "Loading long-term memories...",
      loadFailed: "Failed to load long-term memories.",
      emptyStore: "There are no long-term memories to manage yet.",
      emptyFiltered: "No long-term memories match the current search.",
      summary: (total, preferences, facts) => `${total} long-term memories loaded, including ${preferences} preferences and ${facts} facts.`,
      statusLine: (visible, total) => `Showing ${visible} of ${total} long-term memories.`,
      deleteAction: "Delete",
      deletingAction: "Deleting...",
      deleteConfirm: (title) => `Delete "${title}"? It will stop shaping future answers.`,
      deleteSuccess: (title) => `Deleted long-term memory: ${title}.`,
      deleteFailed: "Failed to delete the long-term memory.",
      labels: {
        type: "Type",
        tags: "Tags",
        updated: "Updated",
      },
      values: {
        none: "None",
        unknown: "Unknown",
      },
      typeMap: {
        pinned_preference: "Preference",
        stable_profile_fact: "Stable fact",
        approved_long_term_fact: "Long-term fact",
      },
    },
  },
};

let currentLocale = "zh";
let memoryCache = [];
const deletingIds = new Set();

function t() {
  return translations[currentLocale];
}

function readStoredLocale() {
  try {
    const value = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    return value === "zh" || value === "en" ? value : "";
  } catch (error) {
    return "";
  }
}

function writeStoredLocale(locale) {
  try {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  } catch (error) {
    // Ignore storage write failures.
  }
}

function escapeHtml(text) {
  return String(text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatDate(value) {
  if (!value) {
    return t().page.values.none;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(currentLocale === "zh" ? "zh-CN" : "en-US", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function normalizeText(value) {
  return String(value || "").trim().toLowerCase();
}

function badge(text, tone = "") {
  const toneClass = tone ? ` memory-badge-${tone}` : "";
  return `<span class="memory-badge${toneClass}">${escapeHtml(text)}</span>`;
}

function formatMemoryTag(tag) {
  const raw = String(tag || "").trim();
  if (!raw) {
    return "";
  }
  if (currentLocale !== "zh") {
    return raw;
  }
  const map = {
    PREFERENCE: "偏好",
    STYLE: "风格",
    EXPLICIT: "显式",
    FACT: "事实",
    SOURCE: "来源",
  };
  return map[raw.toUpperCase()] || raw;
}

function getLongTermMemories() {
  return memoryCache.filter(
    (entry) => LONG_TERM_MEMORY_TYPES.has(entry.memory_type) && entry.status === "approved",
  );
}

function getFilteredMemories(items) {
  const query = normalizeText(memorySearchInput?.value);
  if (!query) {
    return items;
  }
  return items.filter((entry) => {
    const tags = Array.isArray(entry.tags) ? entry.tags.join(" ") : "";
    const haystack = [
      entry.title,
      entry.summary,
      entry.memory_type,
      entry.status,
      tags,
    ]
      .map(normalizeText)
      .join(" ");
    return haystack.includes(query);
  });
}

function renderSummary(allItems, visibleItems, summaryOverride = "") {
  const preferences = allItems.filter((entry) => PREFERENCE_MEMORY_TYPES.has(entry.memory_type)).length;
  const facts = allItems.filter((entry) => FACT_MEMORY_TYPES.has(entry.memory_type)).length;
  totalCount.textContent = String(allItems.length);
  approvedCount.textContent = String(preferences);
  pendingCount.textContent = String(facts);
  auditCount.textContent = String(visibleItems.length);
  summaryValue.textContent = summaryOverride || t().page.summary(allItems.length, preferences, facts);
}

function renderMemories(statusOverride = "") {
  const allItems = getLongTermMemories();
  const visibleItems = getFilteredMemories(allItems);
  renderSummary(allItems, visibleItems);
  memoryStatus.textContent = statusOverride || t().page.statusLine(visibleItems.length, allItems.length);

  if (!visibleItems.length) {
    const emptyText = allItems.length ? t().page.emptyFiltered : t().page.emptyStore;
    memoryList.innerHTML = `<div class="document-empty">${escapeHtml(emptyText)}</div>`;
    return;
  }

  memoryList.innerHTML = visibleItems
    .map((entry) => {
      const labels = t().page.labels;
      const values = t().page.values;
      const typeText = t().page.typeMap[entry.memory_type] || entry.memory_type || values.unknown;
      const tags = (entry.tags || []).length
        ? entry.tags.map((tag) => badge(formatMemoryTag(tag))).join("")
        : `<span class="memory-meta-value">${escapeHtml(values.none)}</span>`;
      const isDeleting = deletingIds.has(entry.id);
      const actionLabel = isDeleting ? t().page.deletingAction : t().page.deleteAction;
      const updatedText = formatDate(entry.updated_at || entry.approved_at || entry.created_at);

      return `
        <article class="memory-item memory-item-compact">
          <div class="memory-item-header">
            <div class="memory-item-heading">
              <p class="eyebrow">${escapeHtml(typeText)}</p>
              <h3>${escapeHtml(entry.title || values.unknown)}</h3>
              <p class="memory-item-summary">${escapeHtml(entry.summary || values.none)}</p>
            </div>
            <div class="memory-item-actions">
              <button
                type="button"
                class="memory-delete-button memory-delete-button-icon"
                data-memory-action="delete"
                data-memory-id="${escapeHtml(entry.id)}"
                aria-label="${escapeHtml(actionLabel)}"
                title="${escapeHtml(actionLabel)}"
                ${isDeleting ? "disabled" : ""}
              >
                <span class="material-symbols-outlined">delete</span>
              </button>
            </div>
          </div>
          <dl class="memory-meta-grid">
            <div class="memory-meta-row">
              <dt>${escapeHtml(labels.type)}</dt>
              <dd>${escapeHtml(typeText)}</dd>
            </div>
            <div class="memory-meta-row">
              <dt>${escapeHtml(labels.updated)}</dt>
              <dd>${escapeHtml(updatedText)}</dd>
            </div>
            <div class="memory-meta-row memory-meta-row-block">
              <dt>${escapeHtml(labels.tags)}</dt>
              <dd class="memory-tag-list">${tags}</dd>
            </div>
          </dl>
        </article>
      `;
    })
    .join("");
}

function applyLocale(locale) {
  currentLocale = locale;
  const text = t();
  document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
  document.title = text.title;

  localeZhButton.textContent = text.localeLabel;
  localeEnButton.textContent = text.localeLabelShort;
  primaryNav?.setAttribute("aria-label", text.common.primaryNavAria);
  localeSwitch?.setAttribute("aria-label", text.common.localeSwitchAria);
  brandSubline.textContent = text.brandSubline;
  navChat.textContent = text.nav.chat;
  navLibrary.textContent = text.nav.library;
  navMemory.textContent = text.nav.memory;
  sidebarSettingsLabel.textContent = text.common.settings;
  sidebarSupportLabel.textContent = text.common.support;
  sidebarUserName.textContent = text.common.userName;
  sidebarUserMeta.textContent = text.common.userMeta;
  memoryStatusPill.textContent = text.page.statusPill;
  memoryScopePill.textContent = text.page.scopePill;
  memorySearchLabel?.setAttribute("aria-label", text.page.searchAria);
  memorySearchInput.placeholder = text.page.searchPlaceholder;
  memoryNotificationsButton?.setAttribute("aria-label", text.common.notifications);
  memoryHistoryButton?.setAttribute("aria-label", text.common.history);
  eyebrowText.textContent = text.page.eyebrow;
  pageTitle.textContent = text.page.heading;
  heroText.textContent = text.page.hero;
  summaryLabel.textContent = text.page.summaryLabel;
  snapshotEyebrow.textContent = text.page.snapshotEyebrow;
  countsTitle.textContent = text.page.countsTitle;
  totalLabel.textContent = text.page.totalLabel;
  approvedLabel.textContent = text.page.approvedLabel;
  pendingLabel.textContent = text.page.pendingLabel;
  auditLabel.textContent = text.page.auditLabel;
  listEyebrow.textContent = text.page.listEyebrow;
  listTitle.textContent = text.page.listTitle;
  listText.textContent = text.page.listText;
  memoryActionEyebrow.textContent = text.page.actionEyebrow;
  archiveMetaLabel.textContent = text.page.archiveMetaLabel;
  archiveMetaText.textContent = text.page.archiveMetaText;
  memoryLogicEyebrow.textContent = text.page.logicEyebrow;
  memoryLogicTitle.textContent = text.page.logicTitle;
  memoryLogicText.textContent = text.page.logicText;
  memoryArchiveEyebrow.textContent = text.page.archiveEyebrow;
  memoryArchiveTitle.textContent = text.page.archiveTitle;
  memoryArchiveMetaLabel.textContent = text.page.archiveVisibleLabel;
  memoryArchiveMetaText.textContent = text.page.archiveVisibleText;
  memoryPrivacyPill.textContent = text.page.privacyPill;
  memoryRollbackPill.textContent = text.page.rollbackPill;
  memoryCardTitle.textContent = text.page.cardTitle;
  memoryCardText.textContent = text.page.cardText;
  memoryPreviewEyebrow.textContent = text.page.previewEyebrow;
  memoryPreviewTitle.textContent = text.page.previewTitle;
  memoryPreviewText.textContent = text.page.previewText;
  memoryFooterCopy.textContent = text.page.footerCopy;
  memoryExportButton.textContent = text.page.exportButton;
  memoryPurgeButton.textContent = text.page.purgeButton;
  localeZhButton.classList.toggle("is-active", locale === "zh");
  localeEnButton.classList.toggle("is-active", locale === "en");
  window.WorkspacePanels?.setLocale?.(locale);
  writeStoredLocale(locale);
  renderMemories();
}

async function loadMemories() {
  memoryStatus.textContent = t().page.loading;
  summaryValue.textContent = t().page.loading;
  try {
    const response = await fetch("/memories", {
      headers: { Accept: "application/json" },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || t().page.loadFailed);
    }
    memoryCache = Array.isArray(payload.memories) ? payload.memories : [];
    renderMemories();
  } catch (error) {
    memoryCache = [];
    memoryStatus.textContent = error instanceof Error ? error.message : t().page.loadFailed;
    memoryList.innerHTML = `<div class="document-empty">${escapeHtml(t().page.loadFailed)}</div>`;
    renderSummary([], [], t().page.loadFailed);
  }
}

async function deleteMemory(memoryId) {
  const entry = memoryCache.find((item) => item.id === memoryId);
  if (!entry || deletingIds.has(memoryId)) {
    return;
  }
  const title = entry.title || t().page.values.unknown;
  if (!window.confirm(t().page.deleteConfirm(title))) {
    return;
  }

  deletingIds.add(memoryId);
  renderMemories();

  try {
    const response = await fetch(`/memories/${encodeURIComponent(memoryId)}`, {
      method: "DELETE",
      headers: { Accept: "application/json" },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || t().page.deleteFailed);
    }
    memoryCache = memoryCache.map((item) =>
      item.id === memoryId ? { ...item, status: "rolled_back" } : item,
    );
    deletingIds.delete(memoryId);
    renderMemories(t().page.deleteSuccess(title));
  } catch (error) {
    deletingIds.delete(memoryId);
    renderMemories(error instanceof Error ? error.message : t().page.deleteFailed);
  }
}

function initMemoryActions() {
  memoryList?.addEventListener("click", (event) => {
    const actionButton = event.target.closest("[data-memory-action='delete']");
    if (!actionButton) {
      return;
    }
    const memoryId = actionButton.getAttribute("data-memory-id");
    if (memoryId) {
      void deleteMemory(memoryId);
    }
  });

  memorySearchInput?.addEventListener("input", () => {
    renderMemories();
  });
}

localeZhButton?.addEventListener("click", () => applyLocale("zh"));
localeEnButton?.addEventListener("click", () => applyLocale("en"));

applyLocale(readStoredLocale() || "zh");
initMemoryActions();
void loadMemories();
