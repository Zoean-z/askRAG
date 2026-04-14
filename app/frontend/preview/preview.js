const page = document.body.dataset.page || "chat";

const state = {
  locale: "zh",
  activeConversationId: "conv-aphelios",
  conversations: [
    {
      id: "conv-aphelios",
      title: "搜索一下厄斐琉斯的剧情并且总结发出来",
      message_count: 6,
      updated_at: "2026-04-13T21:18:00+08:00",
      messages: [
        {
          role: "assistant",
          content: "欢迎使用预览模式。这个页面不会请求后端接口，但会完整展示聊天布局、滚动区域和来源标签。",
          sources: ["preview://layout-guide.md"],
        },
        {
          role: "user",
          content: "搜索一下厄斐琉斯的剧情并且总结发出来",
        },
        {
          role: "assistant",
          content: "厄斐琉斯是《英雄联盟》宇宙中皎月教派的武器圣徒。他几乎不说话，由远在神殿中的妹妹阿鲁恩通过灵魂联结协助作战。这个回答是本地 mock，用来帮助你检查消息区排版、来源标签和长段落宽度。",
          sources: ["web://leagueoflegends.com/champion/aphelios", "preview://lore-summary.md"],
        },
      ],
    },
    {
      id: "conv-openai",
      title: "请联网搜索 OpenAI 介绍",
      message_count: 4,
      updated_at: "2026-04-13T20:42:00+08:00",
      messages: [
        {
          role: "user",
          content: "请联网搜索 OpenAI 介绍",
        },
        {
          role: "assistant",
          content: "OpenAI 是一家专注于通用人工智能研究与产品化的公司。这段文字用于预览消息气泡、来源标签和主聊天区滚动行为。",
          sources: ["web://openai.com/about"],
        },
      ],
    },
    {
      id: "conv-kb",
      title: "总结一下当前知识库结构和文档来源",
      message_count: 5,
      updated_at: "2026-04-13T19:28:00+08:00",
      messages: [
        {
          role: "user",
          content: "总结一下当前知识库结构和文档来源",
        },
        {
          role: "assistant",
          content: "当前知识库分成上传文档层、切片索引层和回答引用层。这个预览会话主要用来展示左侧长标题的两行截断效果。",
          sources: ["preview://knowledge-base-map.md"],
        },
      ],
    },
  ],
  documents: [
    {
      file_name: "递归学习与第一性原理求职——AI时代的方法论.md",
      source: "local://docs/recursive-learning.md",
      uploaded_at: "2026-04-12T16:30:00+08:00",
      chunk_count: 42,
    },
    {
      file_name: "英雄联盟世界观与角色剧情整理.md",
      source: "local://docs/lol-lore.md",
      uploaded_at: "2026-04-11T09:05:00+08:00",
      chunk_count: 57,
    },
    {
      file_name: "OpenAI 产品与模型笔记.txt",
      source: "local://notes/openai-models.txt",
      uploaded_at: "2026-04-10T22:12:00+08:00",
      chunk_count: 18,
    },
  ],
  memories: [
    {
      id: "mem-1",
      title: "用户偏好简洁结论优先",
      summary: "在排查或评审类问题中，先给结论，再展开字段链路和细节。",
      memory_type: "pinned_preference",
      updated_at: "2026-04-13T18:10:00+08:00",
      tags: ["风格", "输出格式"],
    },
    {
      id: "mem-2",
      title: "项目以本地知识库问答为核心",
      summary: "askRAG 的主工作流围绕本地检索、联网补充和回答来源展示组织。",
      memory_type: "approved_long_term_fact",
      updated_at: "2026-04-13T17:30:00+08:00",
      tags: ["项目上下文", "知识库"],
    },
    {
      id: "mem-3",
      title: "用户强调不要轻易改成 web-first",
      summary: "在检索策略调整中，应区分 local-first 宽松和 web 注入严格，不混为一谈。",
      memory_type: "stable_profile_fact",
      updated_at: "2026-04-13T16:45:00+08:00",
      tags: ["检索策略", "约束"],
    },
  ],
};

const translations = {
  zh: {
    common: {
      lang: "zh-CN",
      localeLabel: "简体中文",
      localeLabelShort: "English",
      brandSubline: "本地知识工作台",
      nav: { chat: "对话", library: "知识库", memory: "记忆" },
      navAria: "主导航",
      localeAria: "语言切换",
      settings: "设置",
      support: "帮助",
      userName: "askRAG 控制台",
      userMeta: "本地知识工作区",
      notifications: "通知",
      history: "历史",
      previewStatus: "预览模式",
    },
    roles: { assistant: "助手", user: "用户" },
    sourcesLabel: "主来源",
    chat: {
      title: "askRAG 对话预览",
      pageTitle: "askRAG 对话",
      scope: "对话工作区",
      eyebrow: "对话",
      hero: "直接查看当前前端聊天结构，不启动后端也能检查布局、滚动和中文化。",
      conversationsEyebrow: "会话",
      conversationsTitle: "最近会话",
      newConversation: "新对话",
      railStatus: (count) => `已加载 ${count} 个预览会话。`,
      stageEyebrow: "对话区",
      stageTitle: "把回答、主来源和状态放在同一个主工作区。",
      stageLead: "左侧栏稳定存在，中间消息流单独滚动，输入区固定在底部。",
      transcriptAria: "对话记录",
      promptTitle: "输入区",
      promptText: "这里是纯前端预览，不会发起真实请求，但你仍然可以模拟一轮问答。",
      questionLabel: "问题",
      placeholder: "搜索一下厄斐琉斯的剧情并且总结发出来",
      statusText: "预览模式，未连接后端。",
      submit: "发送",
      notesEyebrow: "提示",
      notesTitle: "预览说明",
      noteOne: "只有中间消息区滚动，外层 shell 不会一起滚。",
      noteTwo: "左侧会话项已经压缩成标题加简短元信息。",
      noteThree: "语言切换和来源标签都可以直接检查。",
      routingEyebrow: "来源链路",
      routingTitle: "主来源",
      routingText: "用 mock 数据检查来源标签、长文本排版和气泡宽度。",
      livePill: "静态预览",
      streamingPill: "本地 mock",
      stateTitle: "响应状态",
      stateText: "这个页面适合先看交互结构，再决定是否启动完整后端。",
      replyPrefix: "这是本地预览回复：",
      conversationFallbackTitle: "新对话",
      deleteConversation: "删除",
      deleteConversationAria: "删除会话",
      emptyConversation: "请输入问题以生成本地预览回复。",
      meta: (count, timeText) => [count > 0 ? `${count} 条消息` : "", timeText].filter(Boolean).join(" · "),
    },
    library: {
      title: "askRAG 知识库预览",
      pageTitle: "知识库",
      scope: "文档工作区",
      eyebrow: "知识库",
      hero: "不启动后端也能检查知识库页面的结构、留白、中文文案和卡片密度。",
      sidebarEyebrow: "档案",
      sidebarTitle: "已添加文件",
      sidebarCopy: "这里使用本地 mock 文档来展示列表密度和元信息排列。",
      sidebarAction: "知识库流程",
      searchAria: "搜索知识库",
      searchPlaceholder: "搜索知识库...",
      heroMetaLabel: "流程",
      heroMetaText: "上传控件在预览模式下只保留视觉层，用来检查布局与按钮层级。",
      intakeEyebrow: "引入",
      uploadTitle: "上传文档",
      uploadText: "当前是前端预览模式，上传不会发送到任何服务。",
      filePickerText: "选择一个文本文件",
      uploadStatus: "预览模式，文件不会真正上传。",
      uploadSubmit: "上传",
      notesEyebrow: "说明",
      notesTitle: "预览说明",
      noteOne: "搜索框只过滤本地 mock 文档。",
      noteTwo: "删除只影响当前页面的本地状态。",
      noteThree: "适合先检查中文和信息密度。",
      archiveEyebrow: "档案",
      libraryTitle: "已添加文件",
      libraryText: "这个列表只用于预览文档卡片、按钮位置和 metadata 展示。",
      archiveSummaryLabel: "用途",
      archiveSummaryText: "每一条记录都是本地预览数据，方便在无后端时检查布局结构。",
      uploaded: "添加时间",
      chunks: "切片",
      unknown: "未知",
      deleteAction: "删除",
      metricEyebrowOne: "证据",
      metricValueOne: "主层",
      metricCopyOne: "文档卡片现在更紧凑，适合直接评估中文标题和来源行长度。",
      metricEyebrowTwo: "处理",
      metricValueTwo: "稳定",
      metricCopyTwo: "引入面板和档案面板分层明确，但不会把页面挤成卡片墙。",
      metricEyebrowThree: "操作",
      metricValueThree: "就绪",
      metricCopyThree: "这个预览页可以脱离后端单独打开，适合先看结构效果。",
      empty: "没有匹配的预览文档。",
    },
    memory: {
      title: "askRAG 记忆预览",
      pageTitle: "长期记忆",
      scope: "记忆档案",
      eyebrow: "记忆",
      hero: "在不启动后端的情况下检查记忆页的中文术语、层级和滚动表现。",
      searchAria: "搜索记忆",
      searchPlaceholder: "搜索记忆...",
      statusPill: "预览模式",
      snapshotEyebrow: "快照",
      countsTitle: "一览",
      totalLabel: "总数",
      approvedLabel: "偏好",
      pendingLabel: "事实",
      auditLabel: "当前显示",
      listEyebrow: "档案",
      listTitle: "已保存的长期记忆",
      listText: "这里的条目全部来自本地 mock，用来预览密度、标题长度和删除操作。",
      summaryLabel: "概览",
      actionEyebrow: "操作",
      archiveMetaLabel: "处理",
      archiveMetaText: "删除只会作用在当前预览页，方便测试按钮和列表反馈。",
      logicEyebrow: "规则",
      logicTitle: "保留策略",
      logicText: "记忆页保持清晰的三栏结构，让真正的管理面板始终在中间。",
      archiveEyebrow: "档案",
      archiveTitle: "已保存的长期记忆",
      archiveVisibleLabel: "显示范围",
      archiveVisibleText: "搜索和删除都是本地预览行为，不会影响真实数据。",
      privacyPill: "预览",
      rollbackPill: "安全可改",
      cardTitle: "记忆逻辑",
      cardText: "这个右侧面板主要用来检查层级、行长和视觉节奏。",
      previewEyebrow: "认知核心",
      previewTitle: "渐进式智能",
      previewText: "右侧保持克制，让中间档案列表成为真正的操作中心。",
      footerCopy: "仅本地预览数据",
      exportButton: "导出数据",
      purgeButton: "清空全部记忆",
      statusLine: (visible, total) => `当前显示 ${visible} / ${total} 条预览记忆。`,
      summary: (total, preferences, facts) => `共 ${total} 条预览记忆，其中 ${preferences} 条偏好，${facts} 条事实。`,
      deleteAction: "删除",
      labels: { type: "类型", tags: "标签", updated: "更新时间" },
      values: { none: "无", unknown: "未知" },
      typeMap: {
        pinned_preference: "偏好",
        stable_profile_fact: "稳定事实",
        approved_long_term_fact: "长期事实",
      },
      empty: "没有匹配的预览记忆。",
    },
  },
  en: {
    common: {
      lang: "en",
      localeLabel: "Chinese",
      localeLabelShort: "English",
      brandSubline: "Local Knowledge Workbench",
      nav: { chat: "Chat", library: "Library", memory: "Memory" },
      navAria: "Primary navigation",
      localeAria: "Language switcher",
      settings: "Settings",
      support: "Support",
      userName: "askRAG Console",
      userMeta: "Local knowledge workspace",
      notifications: "Notifications",
      history: "History",
      previewStatus: "Preview mode",
    },
    roles: { assistant: "assistant", user: "user" },
    sourcesLabel: "Primary source",
    chat: {
      title: "askRAG Chat Preview",
      pageTitle: "askRAG Chat",
      scope: "Chat workspace",
      eyebrow: "Chat",
      hero: "Inspect the current front-end chat shell without starting the backend service.",
      conversationsEyebrow: "Threads",
      conversationsTitle: "Recent sessions",
      newConversation: "New chat",
      railStatus: (count) => `${count} preview conversations loaded.`,
      stageEyebrow: "Conversation",
      stageTitle: "Keep the answer, source trail, and state in one focused workspace.",
      stageLead: "The left rail stays stable while the center transcript owns the scroll and composer.",
      transcriptAria: "Conversation transcript",
      promptTitle: "Composer",
      promptText: "This is a front-end preview. You can still type to simulate a local reply.",
      questionLabel: "Question",
      placeholder: "Search Aphelios lore and summarize it",
      statusText: "Preview mode. No backend requests will be sent.",
      submit: "Send",
      notesEyebrow: "Notes",
      notesTitle: "Preview guidance",
      noteOne: "Only the transcript region scrolls.",
      noteTwo: "Sidebar items stay compact and dense.",
      noteThree: "Locale switching works without backend data.",
      routingEyebrow: "Source trail",
      routingTitle: "Primary source",
      routingText: "Use mock source chips to inspect density and bubble layout.",
      livePill: "Static preview",
      streamingPill: "Local mock",
      stateTitle: "Response state",
      stateText: "Use this screen to validate shell, spacing, and scroll behavior before starting the app.",
      replyPrefix: "This is a local preview reply:",
      conversationFallbackTitle: "New chat",
      deleteConversation: "Delete",
      deleteConversationAria: "Delete conversation",
      emptyConversation: "Enter a question to generate a local preview reply.",
      meta: (count, timeText) => [count > 0 ? `${count} messages` : "", timeText].filter(Boolean).join(" · "),
    },
    library: {
      title: "askRAG Library Preview",
      pageTitle: "Knowledge Base",
      scope: "Document workspace",
      eyebrow: "Library",
      hero: "Inspect library structure, spacing, and copy without starting the backend.",
      sidebarEyebrow: "Archive",
      sidebarTitle: "Added files",
      sidebarCopy: "This panel uses local mock documents so you can inspect density and metadata layout.",
      sidebarAction: "Library workflow",
      searchAria: "Search knowledge base",
      searchPlaceholder: "Search knowledge base...",
      heroMetaLabel: "Workflow",
      heroMetaText: "In preview mode the upload controls are visual only, useful for layout review.",
      intakeEyebrow: "Intake",
      uploadTitle: "Upload document",
      uploadText: "This is preview mode. Upload does not send anything to a service.",
      filePickerText: "Choose a text file",
      uploadStatus: "Preview mode. Files are not uploaded.",
      uploadSubmit: "Upload",
      notesEyebrow: "Guidance",
      notesTitle: "Preview guidance",
      noteOne: "Search filters local mock documents only.",
      noteTwo: "Delete affects only local preview state.",
      noteThree: "Use this page to validate Chinese and spacing before backend wiring.",
      archiveEyebrow: "Archive",
      libraryTitle: "Added files",
      libraryText: "This list previews document cards, action placement, and metadata density.",
      archiveSummaryLabel: "Use",
      archiveSummaryText: "Every record here is local preview data so you can inspect the shell offline.",
      uploaded: "Added",
      chunks: "Chunks",
      unknown: "Unknown",
      deleteAction: "Delete",
      metricEyebrowOne: "Evidence",
      metricValueOne: "Primary",
      metricCopyOne: "Cards stay compact enough to review long Chinese titles and source lines.",
      metricEyebrowTwo: "Processing",
      metricValueTwo: "Steady",
      metricCopyTwo: "Intake and archive panels stay distinct without becoming a card grid.",
      metricEyebrowThree: "Action",
      metricValueThree: "Ready",
      metricCopyThree: "This page opens offline and is suitable for shell review before the app is running.",
      empty: "No preview documents match the current search.",
    },
    memory: {
      title: "askRAG Memory Preview",
      pageTitle: "Long-term Memory",
      scope: "Memory archive",
      eyebrow: "Memory",
      hero: "Review the memory page shell, terminology, and density without calling backend APIs.",
      searchAria: "Search memories",
      searchPlaceholder: "Search memories...",
      statusPill: "Preview mode",
      snapshotEyebrow: "Snapshot",
      countsTitle: "At a glance",
      totalLabel: "Total",
      approvedLabel: "Preferences",
      pendingLabel: "Facts",
      auditLabel: "Visible",
      listEyebrow: "Archive",
      listTitle: "Saved long-term memories",
      listText: "All items here are local mock records so you can validate density, titles, and delete actions.",
      summaryLabel: "Summary",
      actionEyebrow: "Action",
      archiveMetaLabel: "Action",
      archiveMetaText: "Delete only changes the current preview state.",
      logicEyebrow: "Logic",
      logicTitle: "Retention policy",
      logicText: "The three-column shell keeps the true management surface centered and readable.",
      archiveEyebrow: "Archive",
      archiveTitle: "Saved long-term memories",
      archiveVisibleLabel: "Visible",
      archiveVisibleText: "Search and delete are local-only preview actions.",
      privacyPill: "Preview",
      rollbackPill: "Safe to edit",
      cardTitle: "Memory logic",
      cardText: "Use this panel to inspect hierarchy, line length, and copy tone in isolation.",
      previewEyebrow: "Cognitive core",
      previewTitle: "Evolving Intelligence",
      previewText: "The right side stays calm so the archive remains the main operational surface.",
      footerCopy: "Preview data only",
      exportButton: "Export Data",
      purgeButton: "Purge All Memory",
      statusLine: (visible, total) => `Showing ${visible} / ${total} preview memories.`,
      summary: (total, preferences, facts) => `${total} preview memories loaded, including ${preferences} preferences and ${facts} facts.`,
      deleteAction: "Delete",
      labels: { type: "Type", tags: "Tags", updated: "Updated" },
      values: { none: "None", unknown: "Unknown" },
      typeMap: {
        pinned_preference: "Preference",
        stable_profile_fact: "Stable fact",
        approved_long_term_fact: "Long-term fact",
      },
      empty: "No preview memories match the current search.",
    },
  },
};

const commonEls = {
  brandSubline: document.querySelector("#brandSubline"),
  primaryNav: document.querySelector("#primaryNav"),
  localeSwitch: document.querySelector("#localeSwitch"),
  localeZh: document.querySelector("#localeZh"),
  localeEn: document.querySelector("#localeEn"),
  navChat: document.querySelector("#navChat"),
  navLibrary: document.querySelector("#navLibrary"),
  navMemory: document.querySelector("#navMemory"),
  sidebarSettingsLabel: document.querySelector("#sidebarSettingsLabel"),
  sidebarSupportLabel: document.querySelector("#sidebarSupportLabel"),
  sidebarUserName: document.querySelector("#sidebarUserName"),
  sidebarUserMeta: document.querySelector("#sidebarUserMeta"),
};

function t() {
  return translations[state.locale];
}

function pageText() {
  return t()[page];
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
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat(state.locale === "zh" ? "zh-CN" : "en-US", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function setCommonCopy() {
  const text = t().common;
  document.documentElement.lang = text.lang;
  document.title = pageText().title;
  commonEls.primaryNav?.setAttribute("aria-label", text.navAria);
  commonEls.localeSwitch?.setAttribute("aria-label", text.localeAria);
  commonEls.brandSubline.textContent = text.brandSubline;
  commonEls.localeZh.textContent = text.localeLabel;
  commonEls.localeEn.textContent = text.localeLabelShort;
  commonEls.localeZh.classList.toggle("is-active", state.locale === "zh");
  commonEls.localeEn.classList.toggle("is-active", state.locale === "en");
  commonEls.navChat.textContent = text.nav.chat;
  commonEls.navLibrary.textContent = text.nav.library;
  commonEls.navMemory.textContent = text.nav.memory;
  commonEls.sidebarSettingsLabel.textContent = text.settings;
  commonEls.sidebarSupportLabel.textContent = text.support;
  commonEls.sidebarUserName.textContent = text.userName;
  commonEls.sidebarUserMeta.textContent = text.userMeta;
}

function renderSources(sources = []) {
  if (!sources.length) {
    return "";
  }
  return `
    <div class="message-sources">
      <span class="sources-label">${escapeHtml(t().sourcesLabel)}</span>
      ${sources.map((source) => `<span class="source-chip mono">${escapeHtml(source)}</span>`).join("")}
    </div>
  `;
}

function renderChat() {
  const text = pageText();
  document.querySelector("#chatStatusPill").textContent = t().common.previewStatus;
  document.querySelector("#chatScopePill").textContent = text.scope;
  document.querySelector("#eyebrowText").textContent = text.eyebrow;
  document.querySelector("#pageTitle").textContent = text.pageTitle;
  document.querySelector("#heroText").textContent = text.hero;
  document.querySelector("#conversationsEyebrow").textContent = text.conversationsEyebrow;
  document.querySelector("#conversationsTitle").textContent = text.conversationsTitle;
  document.querySelector("#newConversationButtonLabel").textContent = text.newConversation;
  document.querySelector("#conversationRailStatus").textContent = text.railStatus(state.conversations.length);
  document.querySelector("#stageEyebrow").textContent = text.stageEyebrow;
  document.querySelector("#stageTitle").textContent = text.stageTitle;
  document.querySelector("#stageLead").textContent = text.stageLead;
  document.querySelector("#transcriptPanel").setAttribute("aria-label", text.transcriptAria);
  document.querySelector("#promptTitle").textContent = text.promptTitle;
  document.querySelector("#promptText").textContent = text.promptText;
  document.querySelector("#questionLabel").textContent = text.questionLabel;
  document.querySelector("#questionInput").placeholder = text.placeholder;
  document.querySelector("#statusText").textContent = text.statusText;
  document.querySelector("#submitButtonLabel").textContent = text.submit;
  document.querySelector("#notesEyebrow").textContent = text.notesEyebrow;
  document.querySelector("#notesTitle").textContent = text.notesTitle;
  document.querySelector("#noteOne").textContent = text.noteOne;
  document.querySelector("#noteTwo").textContent = text.noteTwo;
  document.querySelector("#noteThree").textContent = text.noteThree;
  document.querySelector("#routingEyebrow").textContent = text.routingEyebrow;
  document.querySelector("#routingTitle").textContent = text.routingTitle;
  document.querySelector("#routingText").textContent = text.routingText;
  document.querySelector("#livePill").textContent = text.livePill;
  document.querySelector("#streamingPill").textContent = text.streamingPill;
  document.querySelector("#stateTitle").textContent = text.stateTitle;
  document.querySelector("#stateText").textContent = text.stateText;
  document.querySelector("#chatNotificationsButton").setAttribute("aria-label", t().common.notifications);
  document.querySelector("#chatHistoryButton").setAttribute("aria-label", t().common.history);

  const active = state.conversations.find((item) => item.id === state.activeConversationId) || state.conversations[0];
  state.activeConversationId = active.id;

  document.querySelector("#conversationList").innerHTML = state.conversations
    .map((conversation) => {
      const isActive = conversation.id === state.activeConversationId;
      return `
        <div class="conversation-item${isActive ? " is-active" : ""}">
          <button type="button" class="conversation-item-main" data-conversation-id="${escapeHtml(conversation.id)}" ${isActive ? 'aria-current="true"' : ""}>
            <span class="conversation-item-title">${escapeHtml(conversation.title || text.conversationFallbackTitle)}</span>
            <span class="conversation-item-meta">${escapeHtml(text.meta(conversation.message_count, formatDate(conversation.updated_at)))}</span>
          </button>
          <button type="button" class="conversation-item-delete button-danger" data-conversation-delete-id="${escapeHtml(conversation.id)}" aria-label="${escapeHtml(text.deleteConversationAria)}" title="${escapeHtml(text.deleteConversation)}">
            <span class="material-symbols-outlined">delete</span>
          </button>
        </div>
      `;
    })
    .join("");

  const messageList = document.querySelector("#messageList");
  messageList.innerHTML = active.messages
    .map((message) => `
      <article class="message ${message.role === "user" ? "message-user" : "message-assistant"}" data-role-key="${escapeHtml(message.role)}">
        <div class="message-role">${escapeHtml(t().roles[message.role])}</div>
        <div class="message-body"><p>${escapeHtml(message.content).replace(/\n/g, "<br>")}</p></div>
        ${renderSources(message.sources || [])}
      </article>
    `)
    .join("");
  messageList.scrollTop = messageList.scrollHeight;

  document.querySelector("#conversationList").onclick = (event) => {
    const deleteButton = event.target.closest("[data-conversation-delete-id]");
    if (deleteButton) {
      const id = deleteButton.getAttribute("data-conversation-delete-id");
      state.conversations = state.conversations.filter((item) => item.id !== id);
      if (!state.conversations.length) {
        state.conversations = [{
          id: "conv-empty",
          title: text.conversationFallbackTitle,
          message_count: 1,
          updated_at: new Date().toISOString(),
          messages: [{ role: "assistant", content: text.emptyConversation, sources: [] }],
        }];
      }
      state.activeConversationId = state.conversations[0].id;
      renderChat();
      return;
    }
    const item = event.target.closest("[data-conversation-id]");
    if (item) {
      state.activeConversationId = item.getAttribute("data-conversation-id");
      renderChat();
    }
  };

  document.querySelector("#newConversationButton").onclick = () => {
    const id = `conv-${Date.now()}`;
    state.conversations.unshift({
      id,
      title: text.conversationFallbackTitle,
      message_count: 1,
      updated_at: new Date().toISOString(),
      messages: [{ role: "assistant", content: text.emptyConversation, sources: [] }],
    });
    state.activeConversationId = id;
    renderChat();
  };

  document.querySelector("#chatForm").onsubmit = (event) => {
    event.preventDefault();
    const input = document.querySelector("#questionInput");
    const question = input.value.trim();
    if (!question) {
      return;
    }
    active.messages.push({ role: "user", content: question, sources: [] });
    active.messages.push({
      role: "assistant",
      content: `${text.replyPrefix} ${question}\n\n这个回答来自前端 mock，用来帮助你检查消息流、输入区固定和来源标签的位置。`,
      sources: ["preview://local-simulation.md"],
    });
    active.message_count = active.messages.length;
    active.updated_at = new Date().toISOString();
    input.value = "";
    renderChat();
  };
}

function renderLibrary() {
  const text = pageText();
  document.querySelector("#libraryStatusPill").textContent = t().common.previewStatus;
  document.querySelector("#libraryScopePill").textContent = text.scope;
  document.querySelector("#eyebrowText").textContent = text.eyebrow;
  document.querySelector("#pageTitle").textContent = text.pageTitle;
  document.querySelector("#heroText").textContent = text.hero;
  document.querySelector("#librarySidebarEyebrow").textContent = text.sidebarEyebrow;
  document.querySelector("#librarySidebarTitle").textContent = text.sidebarTitle;
  document.querySelector("#librarySidebarCopy").textContent = text.sidebarCopy;
  document.querySelector("#librarySidebarAction").textContent = text.sidebarAction;
  document.querySelector("#librarySearchLabel").setAttribute("aria-label", text.searchAria);
  document.querySelector("#librarySearchInput").placeholder = text.searchPlaceholder;
  document.querySelector("#libraryNotificationsButton").setAttribute("aria-label", t().common.notifications);
  document.querySelector("#libraryHistoryButton").setAttribute("aria-label", t().common.history);
  document.querySelector("#heroMetaLabel").textContent = text.heroMetaLabel;
  document.querySelector("#heroMetaText").textContent = text.heroMetaText;
  document.querySelector("#intakeEyebrow").textContent = text.intakeEyebrow;
  document.querySelector("#uploadTitle").textContent = text.uploadTitle;
  document.querySelector("#uploadText").textContent = text.uploadText;
  document.querySelector("#filePickerText").textContent = text.filePickerText;
  document.querySelector("#uploadStatus").textContent = text.uploadStatus;
  document.querySelector("#uploadButtonLabel").textContent = text.uploadSubmit;
  document.querySelector("#notesEyebrow").textContent = text.notesEyebrow;
  document.querySelector("#notesTitle").textContent = text.notesTitle;
  document.querySelector("#noteOne").textContent = text.noteOne;
  document.querySelector("#noteTwo").textContent = text.noteTwo;
  document.querySelector("#noteThree").textContent = text.noteThree;
  document.querySelector("#archiveEyebrow").textContent = text.archiveEyebrow;
  document.querySelector("#libraryTitle").textContent = text.libraryTitle;
  document.querySelector("#libraryText").textContent = text.libraryText;
  document.querySelector("#archiveSummaryLabel").textContent = text.archiveSummaryLabel;
  document.querySelector("#archiveSummaryText").textContent = text.archiveSummaryText;
  document.querySelector("#metricEyebrowOne").textContent = text.metricEyebrowOne;
  document.querySelector("#metricValueOne").textContent = text.metricValueOne;
  document.querySelector("#metricCopyOne").textContent = text.metricCopyOne;
  document.querySelector("#metricEyebrowTwo").textContent = text.metricEyebrowTwo;
  document.querySelector("#metricValueTwo").textContent = text.metricValueTwo;
  document.querySelector("#metricCopyTwo").textContent = text.metricCopyTwo;
  document.querySelector("#metricEyebrowThree").textContent = text.metricEyebrowThree;
  document.querySelector("#metricValueThree").textContent = text.metricValueThree;
  document.querySelector("#metricCopyThree").textContent = text.metricCopyThree;

  const query = document.querySelector("#librarySearchInput").value.trim().toLowerCase();
  const visible = state.documents.filter((item) => !query || `${item.file_name} ${item.source}`.toLowerCase().includes(query));
  document.querySelector("#documentList").innerHTML = visible.length
    ? visible.map((item) => `
        <article class="document-item">
          <div class="document-row">
            <div class="document-copy">
              <div class="document-name">${escapeHtml(item.file_name)}</div>
              <div class="document-source mono">${escapeHtml(item.source)}</div>
            </div>
            <div class="document-actions">
              <button type="button" class="button-danger document-delete" data-doc-id="${escapeHtml(item.source)}">${escapeHtml(text.deleteAction)}</button>
            </div>
          </div>
          <div class="document-meta">
            <div class="doc-meta"><span class="doc-meta-label">${escapeHtml(text.uploaded)}</span><span class="doc-meta-value">${escapeHtml(formatDate(item.uploaded_at))}</span></div>
            <div class="doc-meta"><span class="doc-meta-label">${escapeHtml(text.chunks)}</span><span class="doc-meta-value">${escapeHtml(String(item.chunk_count ?? text.unknown))}</span></div>
          </div>
        </article>
      `).join("")
    : `<div class="document-empty">${escapeHtml(text.empty)}</div>`;

  document.querySelector("#librarySearchInput").oninput = () => renderLibrary();
  document.querySelector("#uploadForm").onsubmit = (event) => {
    event.preventDefault();
    document.querySelector("#uploadStatus").textContent = text.uploadStatus;
  };
  document.querySelector("#documentList").onclick = (event) => {
    const button = event.target.closest("[data-doc-id]");
    if (!button) {
      return;
    }
    const id = button.getAttribute("data-doc-id");
    state.documents = state.documents.filter((item) => item.source !== id);
    renderLibrary();
  };
}

function renderMemory() {
  const text = pageText();
  document.querySelector("#memoryStatusPill").textContent = text.statusPill;
  document.querySelector("#memoryScopePill").textContent = text.scope;
  document.querySelector("#eyebrowText").textContent = text.eyebrow;
  document.querySelector("#pageTitle").textContent = text.pageTitle;
  document.querySelector("#heroText").textContent = text.hero;
  document.querySelector("#memorySearchLabel").setAttribute("aria-label", text.searchAria);
  document.querySelector("#memorySearchInput").placeholder = text.searchPlaceholder;
  document.querySelector("#memoryNotificationsButton").setAttribute("aria-label", t().common.notifications);
  document.querySelector("#memoryHistoryButton").setAttribute("aria-label", t().common.history);
  document.querySelector("#snapshotEyebrow").textContent = text.snapshotEyebrow;
  document.querySelector("#countsTitle").textContent = text.countsTitle;
  document.querySelector("#totalLabel").textContent = text.totalLabel;
  document.querySelector("#approvedLabel").textContent = text.approvedLabel;
  document.querySelector("#pendingLabel").textContent = text.pendingLabel;
  document.querySelector("#auditLabel").textContent = text.auditLabel;
  document.querySelector("#listEyebrow").textContent = text.listEyebrow;
  document.querySelector("#listTitle").textContent = text.listTitle;
  document.querySelector("#listText").textContent = text.listText;
  document.querySelector("#summaryLabel").textContent = text.summaryLabel;
  document.querySelector("#memoryActionEyebrow").textContent = text.actionEyebrow;
  document.querySelector("#archiveMetaLabel").textContent = text.archiveMetaLabel;
  document.querySelector("#archiveMetaText").textContent = text.archiveMetaText;
  document.querySelector("#memoryLogicEyebrow").textContent = text.logicEyebrow;
  document.querySelector("#memoryLogicTitle").textContent = text.logicTitle;
  document.querySelector("#memoryLogicText").textContent = text.logicText;
  document.querySelector("#memoryArchiveEyebrow").textContent = text.archiveEyebrow;
  document.querySelector("#memoryArchiveTitle").textContent = text.archiveTitle;
  document.querySelector("#memoryArchiveMetaLabel").textContent = text.archiveVisibleLabel;
  document.querySelector("#memoryArchiveMetaText").textContent = text.archiveVisibleText;
  document.querySelector("#memoryPrivacyPill").textContent = text.privacyPill;
  document.querySelector("#memoryRollbackPill").textContent = text.rollbackPill;
  document.querySelector("#memoryCardTitle").textContent = text.cardTitle;
  document.querySelector("#memoryCardText").textContent = text.cardText;
  document.querySelector("#memoryPreviewEyebrow").textContent = text.previewEyebrow;
  document.querySelector("#memoryPreviewTitle").textContent = text.previewTitle;
  document.querySelector("#memoryPreviewText").textContent = text.previewText;
  document.querySelector("#memoryFooterCopy").textContent = text.footerCopy;
  document.querySelector("#memoryExportButton").textContent = text.exportButton;
  document.querySelector("#memoryPurgeButton").textContent = text.purgeButton;

  const query = document.querySelector("#memorySearchInput").value.trim().toLowerCase();
  const visible = state.memories.filter((item) => !query || `${item.title} ${item.summary} ${(item.tags || []).join(" ")}`.toLowerCase().includes(query));
  const prefCount = state.memories.filter((item) => item.memory_type === "pinned_preference").length;
  const factCount = state.memories.length - prefCount;
  document.querySelector("#totalCount").textContent = String(state.memories.length);
  document.querySelector("#approvedCount").textContent = String(prefCount);
  document.querySelector("#pendingCount").textContent = String(factCount);
  document.querySelector("#auditCount").textContent = String(visible.length);
  document.querySelector("#summaryValue").textContent = text.summary(state.memories.length, prefCount, factCount);
  document.querySelector("#memoryStatus").textContent = text.statusLine(visible.length, state.memories.length);

  document.querySelector("#memoryList").innerHTML = visible.length
    ? visible.map((item) => {
        const typeText = text.typeMap[item.memory_type] || text.values.unknown;
        const tags = (item.tags || []).length
          ? item.tags.map((tag) => `<span class="memory-badge">${escapeHtml(tag)}</span>`).join("")
          : `<span class="memory-meta-value">${escapeHtml(text.values.none)}</span>`;
        return `
          <article class="memory-item">
            <div class="memory-item-header">
              <div class="memory-item-heading">
                <p class="eyebrow">${escapeHtml(typeText)}</p>
                <h3>${escapeHtml(item.title)}</h3>
              </div>
              <div class="memory-item-actions">
                <span class="memory-badge">${escapeHtml(typeText)}</span>
                <button type="button" class="memory-delete-button" data-memory-id="${escapeHtml(item.id)}">${escapeHtml(text.deleteAction)}</button>
              </div>
            </div>
            <p class="memory-summary">${escapeHtml(item.summary)}</p>
            <dl class="memory-meta-grid">
              <div class="memory-meta-row">
                <dt>${escapeHtml(text.labels.type)}</dt>
                <dd>${escapeHtml(typeText)}</dd>
              </div>
              <div class="memory-meta-row">
                <dt>${escapeHtml(text.labels.updated)}</dt>
                <dd>${escapeHtml(formatDate(item.updated_at))}</dd>
              </div>
              <div class="memory-meta-row memory-meta-row-block">
                <dt>${escapeHtml(text.labels.tags)}</dt>
                <dd class="memory-tag-list">${tags}</dd>
              </div>
            </dl>
          </article>
        `;
      }).join("")
    : `<div class="document-empty">${escapeHtml(text.empty)}</div>`;

  document.querySelector("#memorySearchInput").oninput = () => renderMemory();
  document.querySelector("#memoryList").onclick = (event) => {
    const button = event.target.closest("[data-memory-id]");
    if (!button) {
      return;
    }
    const id = button.getAttribute("data-memory-id");
    state.memories = state.memories.filter((item) => item.id !== id);
    renderMemory();
  };
}

function renderPage() {
  setCommonCopy();
  if (page === "chat") {
    renderChat();
  } else if (page === "library") {
    renderLibrary();
  } else if (page === "memory") {
    renderMemory();
  }
}

commonEls.localeZh?.addEventListener("click", () => {
  state.locale = "zh";
  renderPage();
});

commonEls.localeEn?.addEventListener("click", () => {
  state.locale = "en";
  renderPage();
});

renderPage();
