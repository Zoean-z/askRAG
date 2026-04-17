const page = document.body.dataset.page || "chat";
const localeZhButton = document.querySelector("#localeZh");
const localeEnButton = document.querySelector("#localeEn");
const primaryNav = document.querySelector("#primaryNav");
const localeSwitch = document.querySelector("#localeSwitch");
const navChat = document.querySelector("#navChatLabel");
const navLibrary = document.querySelector("#navLibraryLabel");
const navMemory = document.querySelector("#navMemoryLabel");
const brandSubline = document.querySelector("#brandSubline");
const sidebarSettingsLabel = document.querySelector("#sidebarSettingsLabel");
const sidebarSupportLabel = document.querySelector("#sidebarSupportLabel");
const sidebarUserName = document.querySelector("#sidebarUserName");
const sidebarUserMeta = document.querySelector("#sidebarUserMeta");
const MAX_HISTORY_MESSAGES = 8;
const ACTIVE_CONVERSATION_STORAGE_KEY = "askrag.activeConversationId";
const LOCALE_STORAGE_KEY = "askrag.locale";
const WEB_SEARCH_STORAGE_KEY = "askrag.useWebSearch";
const LONG_TERM_MEMORY_TYPES = new Set([
  "pinned_preference",
  "stable_profile_fact",
  "approved_long_term_fact",
]);

const translations = {
  zh: {
    localeLabel: "\u7b80\u4f53\u4e2d\u6587",
    localeLabelShort: "English",
    brandSubline: "\u672c\u5730\u77e5\u8bc6\u5de5\u4f5c\u53f0",
    common: {
      primaryNavAria: "\u4e3b\u5bfc\u822a",
      localeSwitchAria: "\u8bed\u8a00\u5207\u6362",
      settings: "\u8bbe\u7f6e",
      support: "\u5e2e\u52a9",
      userName: "askRAG \u63a7\u5236\u53f0",
      userMeta: "\u672c\u5730\u77e5\u8bc6\u5de5\u4f5c\u533a",
      notifications: "\u901a\u77e5",
      history: "\u5386\u53f2",
    },
    nav: {
      chat: "\u5bf9\u8bdd",
      library: "\u77e5\u8bc6\u5e93",
      memory: "\u8bb0\u5fc6",
    },
    pages: {
      chat: {
        title: "askRAG \u5bf9\u8bdd",
        heading: "askRAG \u5bf9\u8bdd",
        eyebrow: "\u5bf9\u8bdd",
        hero: "\u5f53\u524d\u4f1a\u8bdd\u5de5\u4f5c\u533a",
        utilityStatus: "\u8bb0\u5fc6\u5df2\u542f\u7528",
        utilityScope: "\u5bf9\u8bdd\u5de5\u4f5c\u533a",
        conversationsEyebrow: "\u4f1a\u8bdd",
        conversationsTitle: "\u6700\u8fd1\u4f1a\u8bdd",
        newConversation: "\u65b0\u5bf9\u8bdd",
        conversationsLoading: "\u6b63\u5728\u8bfb\u53d6\u5386\u53f2\u5bf9\u8bdd...",
        conversationsEmpty: "\u8fd8\u6ca1\u6709\u5386\u53f2\u5bf9\u8bdd\u3002",
        conversationsReady: (count) => `\u5df2\u52a0\u8f7d ${count} \u4e2a\u5bf9\u8bdd\u3002`,
        conversationsFailed: "\u8bfb\u53d6\u5386\u53f2\u5bf9\u8bdd\u5931\u8d25\u3002",
        conversationCreating: "\u6b63\u5728\u521b\u5efa\u65b0\u5bf9\u8bdd...",
        conversationOpening: "\u6b63\u5728\u6253\u5f00\u5bf9\u8bdd...",
        conversationDeleting: "\u6b63\u5728\u5220\u9664\u5bf9\u8bdd...",
        conversationDeletedToast: (name) => `\u5df2\u5220\u9664\u201c${name}\u201d\u53ca\u76f8\u5173\u8bb0\u5fc6`,
        conversationFallbackTitle: "\u65b0\u5bf9\u8bdd",
        deleteConversation: "\u5220\u9664",
        confirmDeleteConversation: (name) => `\u786e\u8ba4\u5220\u9664 ${name} \u5417\uff1f\u8be5\u5bf9\u8bdd\u5c06\u4ece\u5386\u53f2\u5217\u8868\u4e2d\u79fb\u9664\u3002`,
        transcriptLabel: "\u5bf9\u8bdd\u8bb0\u5f55",
        intro: "\u8f93\u5165\u95ee\u9898\u540e\u5373\u53ef\u5f00\u59cb\u5bf9\u8bdd\uff0c\u4e5f\u53ef\u4ee5\u76f4\u63a5\u8ffd\u95ee\u4e0a\u4e00\u8f6e\u5185\u5bb9\u3002",
        stageEyebrow: "\u5bf9\u8bdd\u533a",
        stageTitle: "\u628a\u56de\u7b54\u3001\u4e3b\u6765\u6e90\u548c\u6d41\u5f0f\u8fdb\u5ea6\u653e\u5728\u540c\u4e00\u4e2a\u4e3b\u5de5\u4f5c\u533a\u3002",
        stageLead: "\u5de6\u4fa7\u4fdd\u6301\u4f1a\u8bdd\u5bfc\u822a\uff0c\u4e2d\u95f4\u4e13\u6ce8\u9605\u8bfb\u56de\u7b54\u548c\u7ee7\u7eed\u8ffd\u95ee\u3002",
        promptTitle: "\u8f93\u5165\u533a",
        promptText: "\u4e00\u6b21\u8f93\u5165\u4e00\u4e2a\u95ee\u9898\uff0c\u56de\u7b54\u4f1a\u6301\u7eed\u51fa\u73b0\u5728\u4e2d\u95f4\u7684\u6d88\u606f\u6d41\u91cc\u3002",
        questionLabel: "\u95ee\u9898",
        placeholder: "\u641c\u7d22\u5bf9\u8bdd\u3001\u77e5\u8bc6\u5e93\u548c\u8bb0\u5fc6...",
        submit: "\u53d1\u9001",
        webSearchLabel: "\u8054\u7f51\u641c\u7d22",
        webSearchOn: "\u5f00",
        webSearchOff: "\u5173",
        webSearchAriaOn: "\u5173\u95ed\u8054\u7f51\u641c\u7d22",
        webSearchAriaOff: "\u5f00\u542f\u8054\u7f51\u641c\u7d22",
        searchPanelEyebrow: "\u641c\u7d22",
        searchPanelTitle: "\u5339\u914d\u7ed3\u679c",
        searchPanelSummary: (count) => `\u627e\u5230 ${count} \u4e2a\u5339\u914d\u9879`,
        searchPanelEmpty: "\u8f93\u5165\u5173\u952e\u8bcd\uff0c\u5728\u5bf9\u8bdd\u3001\u77e5\u8bc6\u5e93\u548c\u8bb0\u5fc6\u4e2d\u5bfb\u627e\u76f8\u540c\u5185\u5bb9\u3002",
        searchLoading: "\u6b63\u5728\u52a0\u8f7d\u5bf9\u8bdd\u3001\u77e5\u8bc6\u5e93\u548c\u8bb0\u5fc6...",
        searchSectionCurrent: "\u5f53\u524d\u5bf9\u8bdd",
        searchSectionConversations: "\u5bf9\u8bdd\u5386\u53f2",
        searchSectionDocuments: "\u77e5\u8bc6\u5e93",
        searchSectionMemories: "\u8bb0\u5fc6",
        searchNoMatches: "\u672a\u627e\u5230\u5339\u914d\u5185\u5bb9\u3002",
        notesEyebrow: "\u63d0\u793a",
        notesTitle: "\u63d0\u793a",
        noteOne: "\u53ef\u4ee5\u76f4\u63a5\u8ffd\u95ee\u4e0a\u4e00\u8f6e\u63d0\u5230\u7684\u5bf9\u8c61\u6216\u65b9\u6cd5\u3002",
        noteTwo: "\u5982\u679c\u9700\u8981\u8865\u5145\u8d44\u6599\uff0c\u53ef\u4ee5\u5230\u77e5\u8bc6\u5e93\u9875\u9762\u4e0a\u4f20\u6587\u4ef6\u3002",
        noteThree: "\u56de\u7b54\u4e0b\u65b9\u4f1a\u663e\u793a\u4e3b\u6765\u6e90\u3002",
        memoryNoticeUpdated: "已更新记忆",
        memoryNoticeUsed: "\u5df2\u8bfb\u53d6\u8bb0\u5fc6",
        routingEyebrow: "\u6765\u6e90",
        routingTitle: "\u4e3b\u6765\u6e90",
        routingText: "\u95ee\u9898\u8d8a\u805a\u7126\uff0c\u6765\u6e90\u94fe\u8def\u5c31\u8d8a\u6e05\u6670\u3002",
        livePill: "\u5b9e\u65f6",
        streamingPill: "\u6d41\u5f0f\u8f93\u51fa",
        stateTitle: "\u54cd\u5e94\u72b6\u6001",
        stateText: "\u56de\u590d\u4f1a\u5728\u4e2d\u95f4\u5217\u9010\u6b65\u663e\u793a\uff0c\u6765\u6e90\u6807\u7b7e\u59cb\u7ec8\u8ddf\u5728\u56de\u7b54\u4e0b\u65b9\u3002",
        conversationMeta: (count, timeText) => {
          const parts = [];
          if (count > 0) {
            parts.push(`${count} \u6761\u6d88\u606f`);
          }
          if (timeText) {
            parts.push(timeText);
          }
          return parts.join(" \u00b7 ");
        },
      },
      library: {
        title: "askRAG \u77e5\u8bc6\u5e93",
        heading: "\u77e5\u8bc6\u5e93",
        eyebrow: "\u77e5\u8bc6\u5e93",
        hero: "\u5728\u8fd9\u91cc\u6dfb\u52a0\u6587\u4ef6\uff0c\u8865\u5145\u53ef\u4f9b\u95ee\u7b54\u4f7f\u7528\u7684\u5185\u5bb9\u3002",
        utilityStatus: "\u8bb0\u5fc6\u5df2\u542f\u7528",
        utilityScope: "\u6587\u6863\u5de5\u4f5c\u533a",
        searchPlaceholder: "\u641c\u7d22\u77e5\u8bc6\u5e93...",
        searchAria: "\u641c\u7d22\u77e5\u8bc6\u5e93",
        sidebarEyebrow: "\u6863\u6848",
        sidebarTitle: "\u5df2\u6dfb\u52a0\u6587\u4ef6",
        sidebarCopy: "\u8fd9\u91cc\u5c55\u793a\u5f53\u524d\u5bf9\u8bdd\u53ef\u4ee5\u5f15\u7528\u7684\u6587\u4ef6\u3002",
        sidebarAction: "\u77e5\u8bc6\u5e93\u6d41\u7a0b",
        heroMetaLabel: "\u6d41\u7a0b",
        heroMetaText: "\u5728\u8fd9\u91cc\u5f15\u5165\u8d44\u6599\u3001\u7ef4\u62a4\u6863\u6848\uff0c\u8ba9\u77e5\u8bc6\u5e93\u6210\u4e3a\u5bf9\u8bdd\u53ef\u5f15\u7528\u7684\u6587\u6863\u5de5\u4f5c\u533a\u3002",
        intakeEyebrow: "\u5f15\u5165",
        uploadTitle: "\u62d6\u5165\u6587\u4ef6\u8865\u5145\u77e5\u8bc6\u5e93",
        uploadText: "\u5f53\u524d\u652f\u6301 <span class=\"mono\">TXT</span> \u548c <span class=\"mono\">MD</span> \u6587\u672c\u6587\u4ef6",
        filePickerText: "\u6d4f\u89c8\u6587\u4ef6",
        uploadSubmit: "\u5f00\u59cb\u4e0a\u4f20",
        deleteAction: "\u5220\u9664",
        archiveEyebrow: "\u6863\u6848",
        libraryTitle: "\u5df2\u6dfb\u52a0\u6587\u4ef6",
        libraryText: "\u8fd9\u91cc\u5c55\u793a\u5f53\u524d\u53ef\u7528\u7684\u77e5\u8bc6\u5e93\u6587\u4ef6\u3002",
        archiveSummaryLabel: "\u7528\u9014",
        archiveSummaryText: "\u8fd9\u91cc\u7684\u6bcf\u4e00\u4efd\u6587\u6863\u90fd\u4f1a\u5728\u5904\u7406\u5b8c\u6210\u540e\u6210\u4e3a Chat \u53ef\u5f15\u7528\u7684\u8bc1\u636e\u6765\u6e90\u3002",
        notesEyebrow: "\u8bf4\u660e",
        notesTitle: "\u63d0\u793a",
        noteOne: "\u4e0a\u4f20\u5b8c\u6210\u540e\uff0c\u6587\u4ef6\u4f1a\u51fa\u73b0\u5728\u53f3\u4fa7\u5217\u8868\u4e2d\u3002",
        noteTwo: "\u5df2\u6dfb\u52a0\u7684\u5185\u5bb9\u53ef\u4ee5\u5728\u5bf9\u8bdd\u9875\u76f4\u63a5\u4f7f\u7528\u3002",
        noteThree: "\u91cd\u590d\u6587\u4ef6\u4f1a\u81ea\u52a8\u8df3\u8fc7\u3002",
        metricEyebrowOne: "\u8bc1\u636e",
        metricValueOne: "\u4e3b\u5c42",
        metricCopyOne: "\u4e0a\u4f20\u7684\u6587\u6863\u4f1a\u6210\u4e3a\u5bf9\u8bdd\u53ef\u5f15\u7528\u548c\u603b\u7ed3\u7684\u8bc1\u636e\u5c42\u3002",
        metricEyebrowTwo: "\u5904\u7406",
        metricValueTwo: "\u7a33\u5b9a",
        metricCopyTwo: "\u4e0a\u4f20\u533a\u57df\u4fdd\u6301\u5b89\u9759\uff0c\u8ba9\u6863\u6848\u5217\u8868\u66f4\u5bb9\u6613\u626b\u8bfb\u3002",
        metricEyebrowThree: "\u64cd\u4f5c",
        metricValueThree: "\u5c31\u7eea",
        metricCopyThree: "\u65b0\u6587\u4ef6\u5165\u5e93\u540e\uff0c\u540e\u7eed\u5bf9\u8bdd\u5c31\u80fd\u7ee7\u7eed\u5f15\u7528\u5b83\u3002",
      },
    },
    roles: {
      user: "\u7528\u6237",
      assistant: "\u52a9\u624b",
    },
    sourcesLabel: "\u4e3b\u6765\u6e90",
    status: {
      ready: "\u51c6\u5907\u5c31\u7eea\u3002",
      asking: "\u601d\u8003\u4e2d...",
      failed: "\u8bf7\u6c42\u5931\u8d25\u3002",
      unavailable: "\u670d\u52a1\u6682\u4e0d\u53ef\u7528\u3002",
      empty: "\u8bf7\u5148\u8f93\u5165\u95ee\u9898\u3002",
    },
    progress: {
      summary_start: "\u6b63\u5728\u8bfb\u53d6\u76ee\u6807\u6587\u6863...",
      summary_generating: "\u6b63\u5728\u751f\u6210\u603b\u7ed3...",
      summary_chunking: (total) => `\u6b63\u5728\u62c6\u5206\u957f\u6587\u6863\uff0c\u5171 ${total} \u6bb5...`,
      summary_chunk: (current, total) => `\u6b63\u5728\u63d0\u70bc\u7b2c ${current}/${total} \u6bb5...`,
      summary_reduce: "\u6b63\u5728\u6c47\u603b\u6700\u7ec8\u603b\u7ed3...",
      web_search_start: "\u6b63\u5728\u8054\u7f51\u641c\u7d22...",
      web_search_failed: "\u8054\u7f51\u641c\u7d22\u5931\u8d25\uff0c\u5df2\u8fd4\u56de\u63d0\u793a\u4fe1\u606f\u3002",
    },
    uploadStatus: {
      idle: "\u5c1a\u672a\u9009\u62e9\u6587\u4ef6\u3002",
      selected: (name) => `\u5df2\u9009\u62e9\uff1a${name}`,
      uploading: "\u6b63\u5728\u5904\u7406\u6587\u4ef6...",
      indexed: (name) => `\u5df2\u6dfb\u52a0\uff1a${name}`,
      duplicate: (name) => `\u6587\u4ef6\u5df2\u5b58\u5728\uff1a${name}`,
      deleting: (name) => `\u6b63\u5728\u5220\u9664\uff1a${name}`,
      deleted: (name) => `\u5df2\u5220\u9664\uff1a${name}`,
      failed: (detail) => `\u64cd\u4f5c\u5931\u8d25\uff1a${detail}`,
    },
    errors: {
      requestFailed: "\u8bf7\u6c42\u5931\u8d25\uff1a",
      unavailable: "\u8bf7\u6c42\u5931\u8d25\uff1a\u65e0\u6cd5\u8fde\u63a5\u672c\u5730 FastAPI \u670d\u52a1\u3002",
      uploadUnavailable: "\u4e0a\u4f20\u5931\u8d25\uff1a\u65e0\u6cd5\u8fde\u63a5\u672c\u5730 FastAPI \u670d\u52a1\u3002",
      deleteUnavailable: "\u5220\u9664\u5931\u8d25\uff1a\u65e0\u6cd5\u8fde\u63a5\u672c\u5730 FastAPI \u670d\u52a1\u3002",
      emptyStream: "\u6d41\u5f0f\u63a5\u53e3\u672a\u8fd4\u56de\u6709\u6548\u5185\u5bb9\u3002",
    },
    toolStatus: {
      pending: "\u5de5\u5177\u8c03\u7528\u4e2d",
      done: "\u5de5\u5177\u5df2\u5b8c\u6210",
      failed: "\u5de5\u5177\u8c03\u7528\u5931\u8d25",
    },
    library: {
      empty: "\u5f53\u524d\u8fd8\u6ca1\u6709\u53ef\u5c55\u793a\u7684\u6587\u6863\u3002",
      emptyFiltered: "\u6ca1\u6709\u6587\u6863\u5339\u914d\u5f53\u524d\u641c\u7d22\u3002",
      loading: "\u6b63\u5728\u8bfb\u53d6\u6587\u4ef6\u5217\u8868...",
      failed: "\u8bfb\u53d6\u6587\u4ef6\u5217\u8868\u5931\u8d25\u3002",
      uploaded: "\u6dfb\u52a0\u65f6\u95f4",
      chunks: "\u5207\u7247",
      source: "\u6765\u6e90",
      seed: "\u521d\u59cb\u6587\u4ef6",
      unknown: "\u672a\u77e5",
      confirmDelete: (name) => `\u786e\u8ba4\u5220\u9664 ${name} \u5417\uff1f\u8be5\u6587\u4ef6\u4f1a\u4ece\u77e5\u8bc6\u5e93\u548c\u5411\u91cf\u5e93\u4e2d\u79fb\u9664\u3002`,
    },
  },
  en: {
    localeLabel: "Chinese",
    localeLabelShort: "English",
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
    pages: {
      chat: {
        title: "askRAG Chat",
        heading: "askRAG Chat",
        eyebrow: "Chat",
        hero: "Current conversation workspace.",
        utilityStatus: "Memory active",
        utilityScope: "Chat workspace",
        conversationsEyebrow: "Threads",
        conversationsTitle: "Recent sessions",
        newConversation: "New chat",
        conversationsLoading: "Loading conversations...",
        conversationsEmpty: "No conversations yet.",
        conversationsReady: (count) => `${count} conversations loaded.`,
        conversationsFailed: "Failed to load conversations.",
        conversationCreating: "Creating a new chat...",
        conversationOpening: "Opening conversation...",
        conversationDeleting: "Deleting conversation...",
        conversationDeletedToast: (name) => `Deleted "${name}" and related memories`,
        conversationFallbackTitle: "New chat",
        deleteConversation: "Delete",
        confirmDeleteConversation: (name) => `Delete ${name}? This will remove the conversation from the history list.`,
        transcriptLabel: "Conversation transcript",
        intro: "Enter a question to start chatting, or ask a follow-up about the previous turn.",
        stageEyebrow: "Conversation",
        stageTitle: "Keep the answer, source trail, and stream status in one focused workspace.",
        stageLead: "The left rail keeps sessions close while the center column stays readable for replies and follow-ups.",
        promptTitle: "Composer",
        promptText: "Ask one question at a time. The answer streams into the center transcript.",
        questionLabel: "Question",
        placeholder: "Search conversations, files, and memories...",
        submit: "Send",
        webSearchLabel: "Web search",
        webSearchOn: "On",
        webSearchOff: "Off",
        webSearchAriaOn: "Disable web search",
        webSearchAriaOff: "Enable web search",
        searchPanelEyebrow: "Search",
        searchPanelTitle: "Matching results",
        searchPanelSummary: (count) => `Found ${count} matching items`,
        searchPanelEmpty: "Type a keyword to find matching content in conversations, the knowledge base, and memory.",
        searchLoading: "Loading conversations, documents, and memory...",
        searchSectionCurrent: "Current conversation",
        searchSectionConversations: "Conversation history",
        searchSectionDocuments: "Knowledge base",
        searchSectionMemories: "Memory",
        searchNoMatches: "No matching content found.",
        notesEyebrow: "Notes",
        notesTitle: "Tips",
        noteOne: "You can ask follow-up questions about the previous turn.",
        noteTwo: "Use the library page when you need to add new files.",
        noteThree: "The primary source appears below each answer.",
        memoryNoticeUpdated: "Memory updated",
        memoryNoticeUsed: "Memory used",
        routingEyebrow: "Source trail",
        routingTitle: "Primary source",
        routingText: "Keep the topic focused so the evidence path stays clear.",
        livePill: "Live",
        streamingPill: "Streaming",
        stateTitle: "Response state",
        stateText: "Replies stream into the center column while source chips stay attached to the answer bubble.",
        conversationMeta: (count, timeText) => {
          const parts = [];
          if (count > 0) {
            parts.push(`${count} messages`);
          }
          if (timeText) {
            parts.push(timeText);
          }
          return parts.join(" · ");
        },
      },
      library: {
        title: "askRAG Library",
        heading: "Knowledge Base",
        eyebrow: "Library",
        hero: "Add files here to expand what chat can answer.",
        utilityStatus: "Memory active",
        utilityScope: "Document workspace",
        searchPlaceholder: "Search knowledge base...",
        searchAria: "Search knowledge base",
        sidebarEyebrow: "Archive",
        sidebarTitle: "Added files",
        sidebarCopy: "This panel shows the files currently available to chat.",
        sidebarAction: "Library workflow",
        heroMetaLabel: "Workflow",
        heroMetaText: "Bring in source files, keep the archive tidy, and make the document workspace ready for citation-backed chat.",
        intakeEyebrow: "Intake",
        uploadTitle: "Drop files to expand the knowledge base",
        uploadText: "Currently supports <span class=\"mono\">TXT</span> and <span class=\"mono\">MD</span> text files",
        filePickerText: "Browse Files",
        uploadSubmit: "Start Upload",
        deleteAction: "Delete",
        archiveEyebrow: "Archive",
        libraryTitle: "Added files",
        libraryText: "This panel shows the files currently available to chat.",
        archiveSummaryLabel: "Use",
        archiveSummaryText: "Every document listed here becomes part of the evidence library that Chat can cite after processing.",
        notesEyebrow: "Guidance",
        notesTitle: "Tips",
        noteOne: "After upload, the file appears in the list on the right.",
        noteTwo: "New content becomes available in chat after processing.",
        noteThree: "Duplicate files are skipped automatically.",
        metricEyebrowOne: "Evidence",
        metricValueOne: "Primary",
        metricCopyOne: "Uploaded documents become the source layer that chat can cite and summarize.",
        metricEyebrowTwo: "Processing",
        metricValueTwo: "Steady",
        metricCopyTwo: "The upload surface stays quiet so the archive feels handled rather than crowded.",
        metricEyebrowThree: "Action",
        metricValueThree: "Ready",
        metricCopyThree: "Drop in a file to start a new citation trail for future answers.",
      },
    },
    roles: {
      user: "user",
      assistant: "assistant",
    },
    sourcesLabel: "Primary source",
    status: {
      ready: "Ready.",
      asking: "Thinking...",
      failed: "Request failed.",
      unavailable: "Service unavailable.",
      empty: "Enter a question before sending.",
    },
    progress: {
      summary_start: "Reading the target document...",
      summary_generating: "Generating the summary...",
      summary_chunking: (total) => `Splitting the long document into ${total} parts...`,
      summary_chunk: (current, total) => `Summarizing chunk ${current}/${total}...`,
      summary_reduce: "Merging the final summary...",
      web_search_start: "Searching the web...",
      web_search_failed: "Web search failed. Showing a fallback message.",
    },
    uploadStatus: {
      idle: "No file selected.",
      selected: (name) => `Selected: ${name}`,
      uploading: "Processing file...",
      indexed: (name) => `Added: ${name}`,
      duplicate: (name) => `Already exists: ${name}`,
      deleting: (name) => `Deleting: ${name}`,
      deleted: (name) => `Deleted: ${name}`,
      failed: (detail) => `Action failed: ${detail}`,
    },
    errors: {
      requestFailed: "Request failed:",
      unavailable: "Request failed: cannot reach the local FastAPI service.",
      uploadUnavailable: "Upload failed: cannot reach the local FastAPI service.",
      deleteUnavailable: "Delete failed: cannot reach the local FastAPI service.",
      emptyStream: "The stream returned no answer content.",
    },
    toolStatus: {
      pending: "Tool running",
      done: "Tool completed",
      failed: "Tool failed",
    },
    library: {
      empty: "No documents are available yet.",
      emptyFiltered: "No documents match the current search.",
      loading: "Loading file list...",
      failed: "Failed to load file list.",
      uploaded: "Added",
      chunks: "Chunks",
      source: "Source",
      seed: "Seed file",
      unknown: "Unknown",
      confirmDelete: (name) => `Delete ${name}? This removes the file from the library and the vector store.`,
    },
  },
};

const pageConfig = {
  chat: {
      titleElement: document.querySelector("h1"),
      conversationsEyebrow: document.querySelector("#conversationsEyebrow"),
      conversationsTitle: document.querySelector("#conversationsTitle"),
      newConversationButton: document.querySelector("#newConversationButton"),
      newConversationButtonLabel: document.querySelector("#newConversationButtonLabel"),
      conversationRailStatus: document.querySelector("#conversationRailStatus"),
      conversationList: document.querySelector("#conversationList"),
      statusPill: document.querySelector("#chatStatusPill"),
      scopePill: document.querySelector("#chatScopePill"),
      eyebrowText: document.querySelector("#eyebrowText"),
      heroText: document.querySelector("#heroText"),
      stageEyebrow: document.querySelector("#stageEyebrow"),
      stageTitle: document.querySelector("#stageTitle"),
      stageLead: document.querySelector("#stageLead"),
      searchInput: document.querySelector("#chatSearchInput"),
      searchPanel: document.querySelector("#pageSearchPanel"),
      searchEyebrow: document.querySelector("#pageSearchEyebrow"),
      searchTitle: document.querySelector("#pageSearchTitle"),
      searchSummary: document.querySelector("#pageSearchSummary"),
      searchResults: document.querySelector("#pageSearchResults"),
      toastHost: document.querySelector("#toastHost"),
      transcriptPanel: document.querySelector("#transcriptPanel"),
      introMessage: document.querySelector("#introMessage"),
      scrollArea: document.querySelector(".stitch-scroll-area"),
      scrollToBottomButton: document.querySelector("#scrollToBottomButton"),
      promptTitle: document.querySelector("#promptTitle"),
    promptText: document.querySelector("#promptText"),
    questionLabel: document.querySelector("#questionLabel"),
    submitButtonLabel: document.querySelector("#submitButtonLabel"),
    webSearchToggleButton: document.querySelector("#webSearchToggleButton"),
    webSearchToggleLabel: document.querySelector("#webSearchToggleLabel"),
    webSearchToggleState: document.querySelector("#webSearchToggleState"),
    notesEyebrow: document.querySelector("#notesEyebrow"),
    notesTitle: document.querySelector("#notesTitle"),
    noteOne: document.querySelector("#noteOne"),
    noteTwo: document.querySelector("#noteTwo"),
    noteThree: document.querySelector("#noteThree"),
    routingEyebrow: document.querySelector("#routingEyebrow"),
    routingTitle: document.querySelector("#routingTitle"),
    routingText: document.querySelector("#routingText"),
    livePill: document.querySelector("#livePill"),
    streamingPill: document.querySelector("#streamingPill"),
    stateTitle: document.querySelector("#stateTitle"),
    stateText: document.querySelector("#stateText"),
    notificationsButton: document.querySelector("#chatNotificationsButton"),
    historyButton: document.querySelector("#chatHistoryButton"),
    form: document.querySelector("#chatForm"),
    input: document.querySelector("#questionInput"),
    messageList: document.querySelector("#messageList"),
    submitButton: document.querySelector("#submitButton"),
    statusText: document.querySelector("#statusText"),
    template: document.querySelector("#messageTemplate"),
  },
  library: {
    titleElement: document.querySelector("h1"),
    statusPill: document.querySelector("#libraryStatusPill"),
    scopePill: document.querySelector("#libraryScopePill"),
    eyebrowText: document.querySelector("#eyebrowText"),
    heroText: document.querySelector("#heroText"),
    sidebarEyebrow: document.querySelector("#librarySidebarEyebrow"),
    sidebarTitle: document.querySelector("#librarySidebarTitle"),
    sidebarCopy: document.querySelector("#librarySidebarCopy"),
    sidebarAction: document.querySelector("#librarySidebarAction"),
    heroMetaLabel: document.querySelector("#heroMetaLabel"),
    heroMetaText: document.querySelector("#heroMetaText"),
    intakeEyebrow: document.querySelector("#intakeEyebrow"),
    uploadTitle: document.querySelector("#uploadTitle"),
    uploadText: document.querySelector("#uploadText"),
    filePickerText: document.querySelector("#filePickerText"),
    searchLabel: document.querySelector("#librarySearchLabel"),
    searchInput: document.querySelector("#librarySearchInput"),
    archiveEyebrow: document.querySelector("#archiveEyebrow"),
    libraryTitle: document.querySelector("#libraryTitle"),
    libraryText: document.querySelector("#libraryText"),
    archiveSummaryLabel: document.querySelector("#archiveSummaryLabel"),
    archiveSummaryText: document.querySelector("#archiveSummaryText"),
    notesEyebrow: document.querySelector("#notesEyebrow"),
    notesTitle: document.querySelector("#notesTitle"),
    noteOne: document.querySelector("#noteOne"),
    noteTwo: document.querySelector("#noteTwo"),
    noteThree: document.querySelector("#noteThree"),
    metricEyebrowOne: document.querySelector("#metricEyebrowOne"),
    metricValueOne: document.querySelector("#metricValueOne"),
    metricCopyOne: document.querySelector("#metricCopyOne"),
    metricEyebrowTwo: document.querySelector("#metricEyebrowTwo"),
    metricValueTwo: document.querySelector("#metricValueTwo"),
    metricCopyTwo: document.querySelector("#metricCopyTwo"),
    metricEyebrowThree: document.querySelector("#metricEyebrowThree"),
    metricValueThree: document.querySelector("#metricValueThree"),
    metricCopyThree: document.querySelector("#metricCopyThree"),
    uploadButtonLabel: document.querySelector("#uploadButtonLabel"),
    notificationsButton: document.querySelector("#libraryNotificationsButton"),
    historyButton: document.querySelector("#libraryHistoryButton"),
    uploadForm: document.querySelector("#uploadForm"),
    fileInput: document.querySelector("#fileInput"),
    uploadButton: document.querySelector("#uploadButton"),
    uploadStatus: document.querySelector("#uploadStatus"),
    documentList: document.querySelector("#documentList"),
  },
  };

  let currentLocale = "zh";
  let currentStatusKey = "ready";
  let currentUploadStatus = { key: "idle", value: "" };
  let documentCache = [];
  let memoryCache = [];
  let conversationHistory = [];
  let conversationListCache = [];
  let activeConversationId = "";
  let chatBusy = false;
  let activeDeleteSource = "";
  let useWebSearch = readStoredWebSearch();
let searchIndexReady = false;
let searchIndexPromise = null;
let currentSearchQuery = "";
let toastTimer = null;

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

function readStoredWebSearch() {
  try {
    const value = window.localStorage.getItem(WEB_SEARCH_STORAGE_KEY);
    return value === "true";
  } catch (error) {
    return false;
  }
}

function writeStoredWebSearch(enabled) {
  try {
    window.localStorage.setItem(WEB_SEARCH_STORAGE_KEY, enabled ? "true" : "false");
  } catch (error) {
    // Ignore storage write failures.
  }
}

function getPageText() {
  return t().pages[page];
}

function readStoredConversationId() {
  try {
    return window.localStorage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY) || "";
  } catch (error) {
    return "";
  }
}

function writeStoredConversationId(conversationId) {
  try {
    if (conversationId) {
      window.localStorage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, conversationId);
    } else {
      window.localStorage.removeItem(ACTIVE_CONVERSATION_STORAGE_KEY);
    }
  } catch (error) {
    // Ignore storage write failures and keep the in-memory selection.
  }
}

function setActiveConversationId(conversationId) {
  activeConversationId = String(conversationId || "").trim();
  writeStoredConversationId(activeConversationId);
}

function setConversationRailStatus(message) {
  const railStatus = pageConfig.chat.conversationRailStatus;
  if (railStatus) {
    railStatus.textContent = message || "";
  }
}

function showToast(message, tone = "info", duration = 2800) {
  const host = pageConfig.chat.toastHost;
  const text = String(message || "").trim();
  if (!host || !text) {
    return;
  }
  host.innerHTML = "";
  const toast = document.createElement("div");
  toast.className = `toast is-${tone}`;
  toast.setAttribute("role", "status");
  toast.setAttribute("aria-live", "polite");
  toast.innerHTML = `
    <span class="material-symbols-outlined toast-icon" aria-hidden="true">notifications</span>
    <span class="toast-text"></span>
  `;
  const textEl = toast.querySelector(".toast-text");
  if (textEl) {
    textEl.textContent = text;
  }
  host.appendChild(toast);
  window.clearTimeout(toastTimer);
  requestAnimationFrame(() => {
    toast.classList.add("is-visible");
  });
  toastTimer = window.setTimeout(() => {
    toast.classList.remove("is-visible");
    window.setTimeout(() => {
      if (toast.isConnected) {
        toast.remove();
      }
    }, 180);
  }, duration);
}

function updateNavAndBrand() {
  const commonText = t().common;
  if (brandSubline) {
    brandSubline.textContent = t().brandSubline;
  }
  if (primaryNav) {
    primaryNav.setAttribute("aria-label", commonText.primaryNavAria);
  }
  if (localeSwitch) {
    localeSwitch.setAttribute("aria-label", commonText.localeSwitchAria);
  }
  if (navChat) {
    navChat.textContent = t().nav.chat;
  }
  if (navLibrary) {
    navLibrary.textContent = t().nav.library;
  }
  if (navMemory) {
    navMemory.textContent = t().nav.memory;
  }
  if (localeZhButton) {
    localeZhButton.textContent = t().localeLabel;
  }
  if (localeEnButton) {
    localeEnButton.textContent = t().localeLabelShort;
  }
  if (sidebarSettingsLabel) {
    sidebarSettingsLabel.textContent = commonText.settings;
  }
  if (sidebarSupportLabel) {
    sidebarSupportLabel.textContent = commonText.support;
  }
  if (sidebarUserName) {
    sidebarUserName.textContent = commonText.userName;
  }
  if (sidebarUserMeta) {
    sidebarUserMeta.textContent = commonText.userMeta;
  }
}

function updateWebSearchToggle() {
  const currentPage = pageConfig.chat;
  if (!currentPage.webSearchToggleButton) {
    return;
  }
  const text = t().pages.chat;
  const enabled = Boolean(useWebSearch);
  currentPage.webSearchToggleButton.classList.toggle("is-active", enabled);
  currentPage.webSearchToggleButton.setAttribute("aria-pressed", enabled ? "true" : "false");
  currentPage.webSearchToggleButton.setAttribute("aria-label", enabled ? text.webSearchAriaOn : text.webSearchAriaOff);
  currentPage.webSearchToggleButton.setAttribute("title", enabled ? text.webSearchAriaOn : text.webSearchAriaOff);
  if (currentPage.webSearchToggleLabel) {
    currentPage.webSearchToggleLabel.textContent = text.webSearchLabel;
  }
  if (currentPage.webSearchToggleState) {
    currentPage.webSearchToggleState.textContent = enabled ? text.webSearchOn : text.webSearchOff;
  }
}

function renderRoleLabels() {
  document.querySelectorAll(".message[data-role-key]").forEach((message) => {
    const roleKey = message.dataset.roleKey || "assistant";
    const roleLabel = message.querySelector(".message-role");
    if (roleLabel) {
      roleLabel.textContent = t().roles[roleKey] || roleKey;
    }
  });
}

function renderSourceLabels() {
  document.querySelectorAll(".sources-label").forEach((label) => {
    label.textContent = t().sourcesLabel;
  });
}

function getFilteredDocuments(items = []) {
  const query = normalizeSearchText(pageConfig.library.searchInput?.value || "");
  if (!query) {
    return items;
  }
  const tokens = buildSearchTokens(query);
  return items.filter((document) => {
    const haystack = [
      document.file_name,
      document.source,
      document.chunk_count,
      document.uploaded_at,
      document.md5,
    ]
      .map((value) => String(value || ""))
      .join(" ");
    return matchesSearchTokens(haystack, tokens);
  });
}

function setStatus(statusKey) {
  currentStatusKey = statusKey;
  const statusText = pageConfig.chat.statusText;
  if (statusText) {
    statusText.textContent = t().status[statusKey] || t().status.ready;
  }
}

function setStatusDetail(message) {
  const statusText = pageConfig.chat.statusText;
  if (statusText) {
    statusText.textContent = message || t().status.ready;
  }
}

function setUploadStatus(key, value = "") {
  currentUploadStatus = { key, value };
  const uploadStatus = pageConfig.library.uploadStatus;
  if (!uploadStatus) {
    return;
  }
  const statusMap = t().uploadStatus;
  const entry = statusMap[key];
  uploadStatus.textContent = typeof entry === "function" ? entry(value) : entry || statusMap.idle;
}

function formatProgressMessage(payload = {}) {
  const stage = payload.stage || "";
  const messages = t().progress || {};
  if (stage === "summary_chunk") {
    return messages.summary_chunk?.(payload.current || 0, payload.total || 0) || t().status.asking;
  }
  if (stage === "summary_chunking") {
    return messages.summary_chunking?.(payload.total || 0) || t().status.asking;
  }
  return messages[stage] || t().status.asking;
}

function isToolProgressStage(stage = "") {
  return stage.startsWith("summary_") || stage.startsWith("web_search");
}

function getMessageToolStatusElement(article) {
  let statusEl = article.querySelector(".message-tool-status");
  if (!statusEl) {
    statusEl = document.createElement("div");
    statusEl.className = "message-tool-status";
    const sourcesEl = article.querySelector(".message-sources");
    if (sourcesEl) {
      article.insertBefore(statusEl, sourcesEl);
    } else {
      article.appendChild(statusEl);
    }
  }
  return statusEl;
}

function setMessageToolStatus(article, message, tone = "pending") {
  const statusEl = getMessageToolStatusElement(article);
  if (!message) {
    statusEl.textContent = "";
    statusEl.hidden = true;
    statusEl.className = "message-tool-status";
    delete article.dataset.toolStatusTone;
    return;
  }
  statusEl.hidden = false;
  statusEl.className = `message-tool-status is-${tone}`;
  statusEl.textContent = message;
  article.dataset.toolStatusTone = tone;
}

function getMessageMemoryNoticeElement(article) {
  let noticeEl = article.querySelector(".message-memory-note");
  if (!noticeEl) {
    noticeEl = document.createElement("div");
    noticeEl.className = "message-memory-note";
    noticeEl.hidden = true;
    noticeEl.innerHTML = `
      <span class="material-symbols-outlined message-memory-note-icon" aria-hidden="true">edit_note</span>
      <span class="message-memory-note-text"></span>
    `;
    const bodyEl = article.querySelector(".message-body");
    if (bodyEl && bodyEl.parentNode === article) {
      article.insertBefore(noticeEl, bodyEl);
    } else {
      article.appendChild(noticeEl);
    }
  }
  return noticeEl;
}

function getMemoryNoticeText(notices = []) {
  const items = Array.isArray(notices) ? notices.filter((item) => item && typeof item === "object") : [];
  if (!items.length) {
    return "";
  }
  return items.some(
    (item) =>
      String(item.kind || "") === "remembered" &&
      LONG_TERM_MEMORY_TYPES.has(String(item.memory_type || "")) &&
      String(item.status || "") === "approved",
  )
    ? t().pages.chat.memoryNoticeUpdated
    : "";
}

function setMessageMemoryNotice(article, notices = []) {
  if (!article || String(article.dataset.roleKey || "assistant") !== "assistant") {
    return;
  }
  const noticeEl = getMessageMemoryNoticeElement(article);
  const noticeText = getMemoryNoticeText(notices);
  const textEl = noticeEl.querySelector(".message-memory-note-text");
  if (!noticeText) {
    noticeEl.hidden = true;
    if (textEl) {
      textEl.textContent = "";
    }
    delete article.dataset.memoryNotice;
    return;
  }
  noticeEl.hidden = false;
  if (textEl) {
    textEl.textContent = noticeText;
  }
  article.dataset.memoryNotice = noticeText;
}

function formatUploadedAt(value) {
  if (!value) {
    return t().library.seed;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value || t().library.unknown;
  }
  return new Intl.DateTimeFormat(currentLocale === "zh" ? "zh-CN" : "en-US", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function getDocumentExtension(fileName = "") {
  const normalized = String(fileName || "").trim().toLowerCase();
  const dotIndex = normalized.lastIndexOf(".");
  return dotIndex >= 0 ? normalized.slice(dotIndex + 1) : "";
}

function getDocumentTypeLabel(fileName = "") {
  const extension = getDocumentExtension(fileName);
  const zh = currentLocale === "zh";
  if (extension === "pdf") {
    return zh ? "PDF 文档" : "PDF Document";
  }
  if (extension === "doc" || extension === "docx") {
    return zh ? "Word 文档" : "Word Document";
  }
  if (extension === "json") {
    return zh ? "JSON 数据" : "JSON Data";
  }
  if (extension === "md") {
    return zh ? "Markdown" : "Markdown";
  }
  if (extension === "txt") {
    return zh ? "文本文件" : "Text File";
  }
  return zh ? "文件资产" : "File Asset";
}

function getDocumentIconGlyph(fileName = "") {
  const extension = getDocumentExtension(fileName);
  if (extension === "pdf") {
    return "picture_as_pdf";
  }
  if (extension === "doc" || extension === "docx") {
    return "description";
  }
  if (extension === "json") {
    return "data_object";
  }
  if (extension === "md" || extension === "txt") {
    return "article";
  }
  return "draft";
}

function getDocumentIconTone(fileName = "") {
  const extension = getDocumentExtension(fileName);
  if (extension === "pdf") {
    return "is-pdf";
  }
  if (extension === "doc" || extension === "docx") {
    return "is-doc";
  }
  if (extension === "json") {
    return "is-json";
  }
  return "is-text";
}

function formatChunkCount(value) {
  if (value === null || value === undefined || value === "") {
    return t().library.unknown;
  }
  return currentLocale === "zh" ? `${value} 段` : `${value} chunks`;
}

function formatConversationTimestamp(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat(currentLocale === "zh" ? "zh-CN" : "en-US", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function getConversationMeta(conversation) {
  const count = Number(conversation.message_count || 0);
  const timeText = formatConversationTimestamp(conversation.updated_at || conversation.created_at);
  return t().pages.chat.conversationMeta(count, timeText);
}

function getChatScrollArea() {
  return pageConfig.chat.scrollArea || pageConfig.chat.messageList?.closest(".stitch-scroll-area") || null;
}

function isChatAtBottom(scrollArea = getChatScrollArea()) {
  if (!scrollArea) {
    return true;
  }
  return scrollArea.scrollHeight - scrollArea.scrollTop - scrollArea.clientHeight < 48;
}

function updateScrollToBottomButton() {
  const button = pageConfig.chat.scrollToBottomButton;
  if (!button) {
    return;
  }
  button.hidden = isChatAtBottom();
}

function scrollMessages({ behavior = "smooth" } = {}) {
  const scrollArea = getChatScrollArea();
  if (!scrollArea) {
    return;
  }
  scrollArea.scrollTo({
    top: scrollArea.scrollHeight,
    behavior,
  });
  updateScrollToBottomButton();
}

function renderDocuments() {
  const documentList = pageConfig.library.documentList;
  if (!documentList) {
    return;
  }

  const assetCount = document.querySelector("#libraryAssetCount");
  const libraryText = t().library;
  const libraryPageText = t().pages.library;
  const tableLabels =
    currentLocale === "zh"
      ? { name: "文件名称", type: "类型", modified: "更新时间", actions: "操作" }
      : { name: "Asset Name", type: "Type", modified: "Modified", actions: "Actions" };
  const query = normalizeSearchText(pageConfig.library.searchInput?.value || "");
  const visibleDocuments = getFilteredDocuments(documentCache);

  if (!documentCache.length) {
    documentList.innerHTML = `<div class="document-empty">${escapeHtml(libraryText.empty)}</div>`;
    if (assetCount) {
      assetCount.textContent = currentLocale === "zh" ? "显示 0 个资产" : "Showing 0 assets";
    }
    return;
  }

  if (!visibleDocuments.length) {
    documentList.innerHTML = `<div class="document-empty">${escapeHtml(query ? libraryText.emptyFiltered : libraryText.empty)}</div>`;
    if (assetCount) {
      assetCount.textContent = currentLocale === "zh" ? `显示 0 / ${documentCache.length} 个资产` : `Showing 0 / ${documentCache.length} assets`;
    }
    return;
  }

  const rows = visibleDocuments
    .map((document) => {
      const isDeleting = activeDeleteSource === document.source;
      const iconGlyph = getDocumentIconGlyph(document.file_name);
      const iconTone = getDocumentIconTone(document.file_name);
      const docType = getDocumentTypeLabel(document.file_name);
      return `
          <div class="document-table-row">
            <div class="document-cell document-cell-name">
              <span class="document-file-icon ${iconTone}">
                <span class="material-symbols-outlined">${iconGlyph}</span>
              </span>
              <div class="document-copy">
                <div class="document-name">${document.file_name}</div>
                <div class="document-source mono">${document.source || libraryText.unknown}</div>
              </div>
            </div>
            <div class="document-cell">${docType}</div>
            <div class="document-cell">${formatChunkCount(document.chunk_count)}</div>
            <div class="document-cell">${formatUploadedAt(document.uploaded_at)}</div>
            <div class="document-cell document-cell-actions">
              <button
                type="button"
                class="document-delete document-delete-icon"
                data-source="${document.source}"
                data-file-name="${document.file_name}"
                aria-label="${libraryPageText.deleteAction}"
                title="${libraryPageText.deleteAction}"
                ${isDeleting ? "disabled" : ""}
              ><span class="material-symbols-outlined">delete</span></button>
            </div>
          </div>
        `;
    })
    .join("");

  documentList.innerHTML = `
      <div class="document-table">
        <div class="document-table-head">
          <div class="document-table-row">
            <div class="document-cell">${tableLabels.name}</div>
            <div class="document-cell">${tableLabels.type}</div>
            <div class="document-cell">${libraryText.chunks}</div>
            <div class="document-cell">${tableLabels.modified}</div>
            <div class="document-cell">${tableLabels.actions}</div>
          </div>
        </div>
        <div class="document-table-body">${rows}</div>
      </div>
    `;

  if (assetCount) {
    assetCount.textContent =
      visibleDocuments.length === documentCache.length
        ? currentLocale === "zh"
          ? `显示 ${visibleDocuments.length} 个资产`
          : `Showing ${visibleDocuments.length} assets`
        : currentLocale === "zh"
          ? `显示 ${visibleDocuments.length} / ${documentCache.length} 个资产`
          : `Showing ${visibleDocuments.length} / ${documentCache.length} assets`;
  }
}
function applyLocale(locale) {
  currentLocale = locale;
  const text = getPageText();
  const currentPage = pageConfig[page];

  document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
  document.title = text.title;
  updateNavAndBrand();

  if (currentPage.titleElement) {
    currentPage.titleElement.textContent = text.heading;
  }
  if (currentPage.eyebrowText) {
    currentPage.eyebrowText.textContent = text.eyebrow;
  }
  if (currentPage.heroText) {
    currentPage.heroText.textContent = text.hero;
  }

  if (page === "chat") {
    if (currentPage.conversationsEyebrow) {
      currentPage.conversationsEyebrow.textContent = text.conversationsEyebrow;
    }
    if (currentPage.conversationsTitle) {
      currentPage.conversationsTitle.textContent = text.conversationsTitle;
    }
    if (currentPage.newConversationButtonLabel) {
      currentPage.newConversationButtonLabel.textContent = text.newConversation;
    }
    if (currentPage.statusPill) {
      currentPage.statusPill.textContent = text.utilityStatus;
    }
    if (currentPage.scopePill) {
      currentPage.scopePill.textContent = text.utilityScope;
    }
    if (currentPage.stageEyebrow) {
      currentPage.stageEyebrow.textContent = text.stageEyebrow;
    }
    if (currentPage.stageTitle) {
      currentPage.stageTitle.textContent = text.stageTitle;
    }
    if (currentPage.stageLead) {
      currentPage.stageLead.textContent = text.stageLead;
    }
    if (currentPage.transcriptPanel) {
      currentPage.transcriptPanel.setAttribute("aria-label", text.transcriptLabel);
    }
    const introArticle = currentPage.messageList.querySelector(".message-intro");
    if (introArticle) {
      introArticle.dataset.rawText = text.intro;
      renderMessageContent(introArticle);
    } else if (currentPage.introMessage) {
      currentPage.introMessage.innerHTML = `<p>${text.intro}</p>`;
    }
    if (currentPage.promptTitle) {
      currentPage.promptTitle.textContent = text.promptTitle;
    }
    if (currentPage.promptText) {
      currentPage.promptText.textContent = text.promptText;
    }
    if (currentPage.questionLabel) {
      currentPage.questionLabel.textContent = text.questionLabel;
    }
    if (currentPage.input) {
      currentPage.input.placeholder = text.placeholder;
    }
    if (currentPage.submitButtonLabel) {
      currentPage.submitButtonLabel.textContent = text.submit;
    }
    if (currentPage.webSearchToggleLabel) {
      currentPage.webSearchToggleLabel.textContent = text.webSearchLabel;
    }
      if (currentPage.webSearchToggleState) {
        currentPage.webSearchToggleState.textContent = useWebSearch ? text.webSearchOn : text.webSearchOff;
      }
      if (currentPage.searchInput) {
        currentPage.searchInput.placeholder = text.placeholder;
        currentPage.searchInput.setAttribute("aria-label", text.placeholder);
      }
      if (currentPage.searchEyebrow) {
        currentPage.searchEyebrow.textContent = text.searchPanelEyebrow;
      }
      if (currentPage.searchTitle) {
        currentPage.searchTitle.textContent = text.searchPanelTitle;
      }
      if (currentPage.searchSummary && currentSearchQuery) {
        currentPage.searchSummary.textContent = text.searchPanelSummary?.(0) || "";
      }
      if (currentPage.notesEyebrow) {
        currentPage.notesEyebrow.textContent = text.notesEyebrow;
      }
    if (currentPage.notesTitle) {
      currentPage.notesTitle.textContent = text.notesTitle;
    }
    if (currentPage.noteOne) {
      currentPage.noteOne.textContent = text.noteOne;
    }
    if (currentPage.noteTwo) {
      currentPage.noteTwo.textContent = text.noteTwo;
    }
    if (currentPage.noteThree) {
      currentPage.noteThree.textContent = text.noteThree;
    }
    if (currentPage.routingEyebrow) {
      currentPage.routingEyebrow.textContent = text.routingEyebrow;
    }
    if (currentPage.routingTitle) {
      currentPage.routingTitle.textContent = text.routingTitle;
    }
    if (currentPage.routingText) {
      currentPage.routingText.textContent = text.routingText;
    }
    if (currentPage.livePill) {
      currentPage.livePill.textContent = text.livePill;
    }
    if (currentPage.streamingPill) {
      currentPage.streamingPill.textContent = text.streamingPill;
    }
    if (currentPage.stateTitle) {
      currentPage.stateTitle.textContent = text.stateTitle;
    }
      if (currentPage.stateText) {
        currentPage.stateText.textContent = text.stateText;
      }
      currentPage.notificationsButton?.setAttribute("aria-label", t().common.notifications);
      currentPage.historyButton?.setAttribute("aria-label", t().common.history);
      renderSearchPanel(currentSearchQuery);
      renderRoleLabels();
      renderSourceLabels();
      document.querySelectorAll(".message").forEach((message) => renderMessageContent(message));
    renderConversationList();
    if (conversationListCache.length) {
      setConversationRailStatus(text.conversationsReady(conversationListCache.length));
    }
    setStatus(currentStatusKey);
  }

  if (page === "library") {
    currentPage.statusPill.textContent = text.utilityStatus;
    currentPage.scopePill.textContent = text.utilityScope;
    currentPage.sidebarEyebrow.textContent = text.sidebarEyebrow;
    currentPage.sidebarTitle.textContent = text.sidebarTitle;
    currentPage.sidebarCopy.textContent = text.sidebarCopy;
    currentPage.sidebarAction.textContent = text.sidebarAction;
    currentPage.heroMetaLabel.textContent = text.heroMetaLabel;
    currentPage.heroMetaText.textContent = text.heroMetaText;
    currentPage.intakeEyebrow.textContent = text.intakeEyebrow;
    currentPage.uploadTitle.textContent = text.uploadTitle;
    currentPage.uploadText.innerHTML = text.uploadText;
    currentPage.filePickerText.textContent = text.filePickerText;
    currentPage.uploadButtonLabel.textContent = text.uploadSubmit;
    currentPage.searchInput.placeholder = text.searchPlaceholder;
    currentPage.searchLabel.setAttribute("aria-label", text.searchAria);
    currentPage.archiveEyebrow.textContent = text.archiveEyebrow;
    currentPage.libraryTitle.textContent = text.libraryTitle;
    currentPage.libraryText.textContent = text.libraryText;
    currentPage.archiveSummaryLabel.textContent = text.archiveSummaryLabel;
    currentPage.archiveSummaryText.textContent = text.archiveSummaryText;
    currentPage.notesEyebrow.textContent = text.notesEyebrow;
    currentPage.notesTitle.textContent = text.notesTitle;
    currentPage.noteOne.textContent = text.noteOne;
    currentPage.noteTwo.textContent = text.noteTwo;
    currentPage.noteThree.textContent = text.noteThree;
    if (currentPage.metricEyebrowOne) {
      currentPage.metricEyebrowOne.textContent = text.metricEyebrowOne;
    }
    if (currentPage.metricValueOne) {
      currentPage.metricValueOne.textContent = text.metricValueOne;
    }
    if (currentPage.metricCopyOne) {
      currentPage.metricCopyOne.textContent = text.metricCopyOne;
    }
    if (currentPage.metricEyebrowTwo) {
      currentPage.metricEyebrowTwo.textContent = text.metricEyebrowTwo;
    }
    if (currentPage.metricValueTwo) {
      currentPage.metricValueTwo.textContent = text.metricValueTwo;
    }
    if (currentPage.metricCopyTwo) {
      currentPage.metricCopyTwo.textContent = text.metricCopyTwo;
    }
    if (currentPage.metricEyebrowThree) {
      currentPage.metricEyebrowThree.textContent = text.metricEyebrowThree;
    }
    if (currentPage.metricValueThree) {
      currentPage.metricValueThree.textContent = text.metricValueThree;
    }
    if (currentPage.metricCopyThree) {
      currentPage.metricCopyThree.textContent = text.metricCopyThree;
    }
    currentPage.notificationsButton?.setAttribute("aria-label", t().common.notifications);
    currentPage.historyButton?.setAttribute("aria-label", t().common.history);
    renderDocuments();
    setUploadStatus(currentUploadStatus.key, currentUploadStatus.value);
  }

  localeZhButton.classList.toggle("is-active", locale === "zh");
  localeEnButton.classList.toggle("is-active", locale === "en");
  updateWebSearchToggle();
  window.WorkspacePanels?.setLocale?.(locale);
  writeStoredLocale(locale);
}

function escapeHtml(text) {
  return (text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderInlineMarkdown(text) {
  let html = escapeHtml(text);
  html = html.replace(/`([^`\n]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/(^|[^*])\*([^*\n]+)\*(?=[^*]|$)/g, "$1<em>$2</em>");
  return html;
}

function renderMarkdownSafe(text) {
  const lines = (text || "").replace(/\r/g, "").split("\n");
  const htmlParts = [];
  let paragraphLines = [];
  let listType = null;
  let listItems = [];
  let inCodeBlock = false;
  let codeLines = [];

  const flushParagraph = () => {
    if (!paragraphLines.length) {
      return;
    }
    htmlParts.push(`<p>${paragraphLines.map((line) => renderInlineMarkdown(line)).join("<br>")}</p>`);
    paragraphLines = [];
  };

  const flushList = () => {
    if (!listItems.length || !listType) {
      listItems = [];
      listType = null;
      return;
    }
    const tag = listType === "ol" ? "ol" : "ul";
    htmlParts.push(`<${tag}>${listItems.map((item) => `<li>${renderInlineMarkdown(item)}</li>`).join("")}</${tag}>`);
    listItems = [];
    listType = null;
  };

  const flushCodeBlock = () => {
    if (!codeLines.length) {
      return;
    }
    htmlParts.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
    codeLines = [];
  };

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("```")) {
      if (inCodeBlock) {
        flushCodeBlock();
        inCodeBlock = false;
      } else {
        flushParagraph();
        flushList();
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(line);
      continue;
    }

    if (!trimmed) {
      flushParagraph();
      flushList();
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,3})\s+(.*)$/);
    if (headingMatch) {
      flushParagraph();
      flushList();
      const level = Math.min(headingMatch[1].length, 3);
      htmlParts.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`);
      continue;
    }

    const unorderedMatch = trimmed.match(/^[-*]\s+(.*)$/);
    if (unorderedMatch) {
      flushParagraph();
      if (listType && listType !== "ul") {
        flushList();
      }
      listType = "ul";
      listItems.push(unorderedMatch[1]);
      continue;
    }

    const orderedMatch = trimmed.match(/^\d+[.)]\s+(.*)$/);
    if (orderedMatch) {
      flushParagraph();
      if (listType && listType !== "ol") {
        flushList();
      }
      listType = "ol";
      listItems.push(orderedMatch[1]);
      continue;
    }

    flushList();
    paragraphLines.push(line);
  }

  if (inCodeBlock) {
    flushCodeBlock();
  }
  flushParagraph();
  flushList();

  return htmlParts.join("") || "<p></p>";
}

function renderMessageContent(article) {
  const bodyEl = article.querySelector(".message-body");
  if (!bodyEl) {
    return;
  }
  const rawText = article.dataset.rawText || "";
  const roleKey = article.dataset.roleKey || "assistant";
  if (roleKey === "assistant") {
    bodyEl.innerHTML = renderMarkdownSafe(rawText);
  } else {
    bodyEl.innerHTML = `<p>${escapeHtml(rawText).replace(/\n/g, "<br>")}</p>`;
  }
}

function setMessageThinking(article, isThinking) {
  if (!article) {
    return;
  }
  const thinking = Boolean(isThinking);
  article.classList.toggle("is-thinking", thinking);
  article.dataset.thinking = thinking ? "true" : "false";
  article.setAttribute("aria-busy", thinking ? "true" : "false");
}

function buildMessageArticle(roleKey) {
  const fragment = pageConfig.chat.template.content.cloneNode(true);
  const article = fragment.querySelector(".message");

  article.dataset.roleKey = roleKey;
  article.dataset.rawText = "";
  article.classList.add(roleKey === "user" ? "message-user" : "message-assistant");
  return article;
}

function populateMessageArticle(article, text = "", sources = [], { scroll = false } = {}) {
  setMessageText(article, text, scroll);
  setMessageSources(article, sources);
}

function createMessage(roleKey, text = "", sources = []) {
  const article = buildMessageArticle(roleKey);
  pageConfig.chat.messageList.appendChild(article);
  populateMessageArticle(article, text, sources, { scroll: false });
  setMessageThinking(article, roleKey === "assistant" && !String(text || "").trim());
  scrollMessages();
  return article;
}

function getMessageText(article) {
  return article?.dataset.rawText || "";
}

function getMessageSources(article) {
  return Array.from(article.querySelectorAll(".source-chip")).map((chip) => chip.textContent || "").filter(Boolean);
}

function setMessageText(article, text, shouldScroll = true) {
  article.dataset.rawText = text || "";
  renderMessageContent(article);
  if (String(text || "").trim()) {
    setMessageThinking(article, false);
  }
  if (shouldScroll) {
    scrollMessages();
  }
}

function appendMessageText(article, text) {
  article.dataset.rawText = `${article.dataset.rawText || ""}${text || ""}`;
  renderMessageContent(article);
  if (String(article.dataset.rawText || "").trim()) {
    setMessageThinking(article, false);
  }
  scrollMessages();
}

function setMessageSources(article, sources = []) {
  const sourcesEl = article.querySelector(".message-sources");
  if (!sourcesEl) {
    return;
  }
  sourcesEl.innerHTML = "";
  if (!sources.length) {
    return;
  }
  const label = document.createElement("span");
  label.className = "sources-label";
  label.textContent = t().sourcesLabel;
  sourcesEl.appendChild(label);
  for (const source of sources) {
    const chip = document.createElement("span");
    chip.className = "source-chip mono";
    chip.textContent = source;
    sourcesEl.appendChild(chip);
  }
}

function createIntroMessage() {
  const article = buildMessageArticle("assistant");
  article.classList.add("message-intro");
  pageConfig.chat.messageList.replaceChildren(article);
  populateMessageArticle(article, getPageText().intro, [], { scroll: false });
  return article;
}

function syncConversationHistory(messages = []) {
  conversationHistory = messages
    .filter((message) => message.role === "user" || message.role === "assistant")
    .map((message) => ({
      role: message.role,
      content: message.content || "",
      sources: Array.isArray(message.sources) ? message.sources : [],
    }));
}

function renderConversationTranscript(messages = []) {
  const messageList = pageConfig.chat.messageList;
  if (!messageList) {
    return;
  }
  messageList.innerHTML = "";
  if (!messages.length) {
    createIntroMessage();
    return;
  }
  for (const message of messages) {
    const article = buildMessageArticle(message.role || "assistant");
    messageList.appendChild(article);
    populateMessageArticle(article, message.content || "", Array.isArray(message.sources) ? message.sources : [], { scroll: false });
    setMessageMemoryNotice(article, Array.isArray(message.memory_notices) ? message.memory_notices : []);
  }
  requestAnimationFrame(() => scrollMessages({ behavior: "auto" }));
}

  function renderConversationList() {
    const { conversationList } = pageConfig.chat;
    if (!conversationList) {
      return;
    }
  const chatText = t().pages.chat;
  if (!conversationListCache.length) {
    conversationList.innerHTML = `<div class="conversation-empty">${chatText.conversationsEmpty}</div>`;
    return;
  }
  conversationList.innerHTML = conversationListCache
    .map((conversation) => {
      const isActive = conversation.id === activeConversationId;
      const rawTitle = String(conversation.title || "").trim();
      const title =
        !rawTitle || rawTitle === "New chat" || rawTitle === "\u65b0\u5bf9\u8bdd"
          ? chatText.conversationFallbackTitle
          : rawTitle;
      const meta = getConversationMeta(conversation) || chatText.promptText;
      return `
        <div class="conversation-item${isActive ? " is-active" : ""}">
          <button
            type="button"
            class="conversation-item-main"
            data-conversation-id="${escapeHtml(conversation.id || "")}"
            ${chatBusy ? "disabled" : ""}
            ${isActive ? 'aria-current="true"' : ""}
          >
            <span class="conversation-item-title">${escapeHtml(title)}</span>
            <span class="conversation-item-meta">${escapeHtml(meta)}</span>
          </button>
          <button
            type="button"
            class="conversation-item-delete button-danger"
            data-conversation-delete-id="${escapeHtml(conversation.id || "")}"
            data-conversation-delete-title="${escapeHtml(title)}"
            aria-label="${escapeHtml(chatText.deleteConversation)}"
            title="${escapeHtml(chatText.deleteConversation)}"
            ${chatBusy ? "disabled" : ""}
          ><span class="material-symbols-outlined">delete</span></button>
        </div>
      `;
    })
      .join("");
  }

  function normalizeSearchText(value) {
    return String(value || "").trim().toLowerCase();
  }

  function buildSearchTokens(query) {
    const normalized = normalizeSearchText(query);
    if (!normalized) {
      return [];
    }
    return normalized.split(/\s+/).filter(Boolean);
  }

  function matchesSearchTokens(haystack, tokens) {
    if (!tokens.length) {
      return true;
    }
    const normalizedHaystack = normalizeSearchText(haystack);
    return tokens.every((token) => normalizedHaystack.includes(token));
  }

  function highlightSearchText(text, tokens) {
    const escaped = escapeHtml(text);
    if (!tokens.length) {
      return escaped;
    }
    const sortedTokens = [...new Set(tokens)].filter(Boolean).sort((left, right) => right.length - left.length);
    let result = escaped;
    for (const token of sortedTokens) {
      const pattern = token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      if (!pattern) {
        continue;
      }
      result = result.replace(new RegExp(pattern, "gi"), (match) => `<mark>${match}</mark>`);
    }
    return result;
  }

  function excerptSearchText(text, tokens, limit = 180) {
    const normalized = String(text || "").trim();
    if (!normalized) {
      return "";
    }
    const compact = normalized.replace(/\s+/g, " ");
    if (!tokens.length) {
      return compact.slice(0, limit);
    }
    const haystack = compact.toLowerCase();
    const matchIndex = tokens.reduce((best, token) => {
      const index = haystack.indexOf(token);
      return index !== -1 && (best === -1 || index < best) ? index : best;
    }, -1);
    if (matchIndex === -1) {
      return compact.slice(0, limit);
    }
    const start = Math.max(0, matchIndex - Math.floor(limit / 3));
    const end = Math.min(compact.length, start + limit);
    const prefix = start > 0 ? "…" : "";
    const suffix = end < compact.length ? "…" : "";
    return `${prefix}${compact.slice(start, end)}${suffix}`;
  }

  function getConversationSearchMatches(queryTokens) {
    const results = [];
    const currentMessages = conversationHistory.filter((message) => matchesSearchTokens(`${message.role} ${message.content}`, queryTokens));
    if (currentMessages.length) {
      const snippet = currentMessages[0]?.content || "";
      results.push({
        kind: "current",
        title: t().pages.chat.searchSectionCurrent,
        meta: activeConversationId ? getConversationMeta(conversationListCache.find((item) => item.id === activeConversationId)) || "" : "",
        snippet,
        detail: `${currentMessages.length} ${currentLocale === "zh" ? "条命中" : "matches"}`,
      });
    }

    conversationListCache.forEach((conversation) => {
      const rawTitle = String(conversation.title || "").trim();
      const title =
        !rawTitle || rawTitle === "New chat" || rawTitle === "\u65b0\u5bf9\u8bdd"
          ? t().pages.chat.conversationFallbackTitle
          : rawTitle;
      const preview = String(conversation.last_message_preview || "").trim();
      const meta = getConversationMeta(conversation) || "";
      const haystack = [title, preview, meta, conversation.id || ""].join(" ");
      if (!matchesSearchTokens(haystack, queryTokens)) {
        return;
      }
      results.push({
        kind: "conversation",
        id: conversation.id || "",
        title,
        meta,
        snippet: preview,
      });
    });
    return results;
  }

  function getDocumentSearchMatches(queryTokens) {
    return documentCache
      .filter((document) => {
        const haystack = [document.file_name, document.source, document.chunk_count, document.uploaded_at, document.md5].join(" ");
        return matchesSearchTokens(haystack, queryTokens);
      })
      .map((document) => ({
        kind: "document",
        title: document.file_name || document.source || t().library.unknown,
        meta: [document.source, document.chunk_count != null ? `${document.chunk_count} chunks` : ""].filter(Boolean).join(" · "),
        snippet: document.source || "",
      }));
  }

  function getMemorySearchMatches(queryTokens) {
    return memoryCache
      .filter((entry) => {
        const tags = Array.isArray(entry.tags) ? entry.tags.join(" ") : "";
        const haystack = [entry.title, entry.summary, entry.memory_type, entry.status, tags, entry.scope, entry.layer].join(" ");
        return matchesSearchTokens(haystack, queryTokens);
      })
      .map((entry) => ({
        kind: "memory",
        title: entry.title || entry.memory_type || t().pages.chat.searchSectionMemories,
        meta: [entry.memory_type, entry.status, Array.isArray(entry.tags) && entry.tags.length ? entry.tags.join(", ") : ""]
          .filter(Boolean)
          .join(" · "),
        snippet: String(entry.summary || "").trim(),
      }));
  }

  function renderSearchPanel(query) {
    const panel = pageConfig.chat.searchPanel;
    const resultsHost = pageConfig.chat.searchResults;
    const summary = pageConfig.chat.searchSummary;
    const transcript = pageConfig.chat.transcriptPanel;
    if (!panel || !resultsHost || !summary) {
      return;
    }

    const tokens = buildSearchTokens(query);
    const hasQuery = tokens.length > 0;
    panel.hidden = !hasQuery;
    if (transcript) {
      transcript.hidden = hasQuery;
    }

    if (!hasQuery) {
      resultsHost.innerHTML = "";
      summary.textContent = "";
      return;
    }

    if (!searchIndexReady) {
      summary.textContent = t().pages.chat.searchLoading;
      resultsHost.innerHTML = `<div class="page-search-empty">${escapeHtml(t().pages.chat.searchLoading)}</div>`;
      return;
    }

    const conversationMatches = getConversationSearchMatches(tokens);
    const documentMatches = getDocumentSearchMatches(tokens);
    const memoryMatches = getMemorySearchMatches(tokens);
    const totalMatches = conversationMatches.length + documentMatches.length + memoryMatches.length;
    summary.textContent = totalMatches
      ? t().pages.chat.searchPanelSummary(totalMatches)
      : t().pages.chat.searchNoMatches;

    const sections = [];
    const renderItem = (item) => {
      const title = highlightSearchText(item.title || "", tokens);
      const meta = item.meta ? highlightSearchText(item.meta, tokens) : "";
      const snippetSource = item.snippet || item.detail || "";
      const snippet = snippetSource ? highlightSearchText(excerptSearchText(snippetSource, tokens), tokens) : "";
      return `
        <article class="page-search-item page-search-item-${item.kind}">
          <div class="page-search-item-head">
            <span class="page-search-item-kind">${escapeHtml(
              item.kind === "conversation"
                ? t().pages.chat.searchSectionConversations
                : item.kind === "document"
                  ? t().pages.chat.searchSectionDocuments
                  : item.kind === "memory"
                    ? t().pages.chat.searchSectionMemories
                    : item.kind,
            )}</span>
            <strong class="page-search-item-title">${title}</strong>
          </div>
          ${meta ? `<div class="page-search-item-meta">${meta}</div>` : ""}
          ${snippet ? `<p class="page-search-item-snippet">${snippet}</p>` : ""}
        </article>
      `;
    };

    if (conversationMatches.length) {
      sections.push(`
        <section class="page-search-group">
          <div class="page-search-group-head">
            <h3>${escapeHtml(t().pages.chat.searchSectionCurrent)}</h3>
            <span class="page-search-count">${conversationMatches.length}</span>
          </div>
          <div class="page-search-items">${conversationMatches.slice(0, 6).map(renderItem).join("")}</div>
        </section>
      `);
    }
    if (documentMatches.length) {
      sections.push(`
        <section class="page-search-group">
          <div class="page-search-group-head">
            <h3>${escapeHtml(t().pages.chat.searchSectionDocuments)}</h3>
            <span class="page-search-count">${documentMatches.length}</span>
          </div>
          <div class="page-search-items">${documentMatches.slice(0, 6).map(renderItem).join("")}</div>
        </section>
      `);
    }
    if (memoryMatches.length) {
      sections.push(`
        <section class="page-search-group">
          <div class="page-search-group-head">
            <h3>${escapeHtml(t().pages.chat.searchSectionMemories)}</h3>
            <span class="page-search-count">${memoryMatches.length}</span>
          </div>
          <div class="page-search-items">${memoryMatches.slice(0, 6).map(renderItem).join("")}</div>
        </section>
      `);
    }

    if (!sections.length) {
      resultsHost.innerHTML = `<div class="page-search-empty">${escapeHtml(t().pages.chat.searchNoMatches)}</div>`;
      return;
    }
    resultsHost.innerHTML = sections.join("");
  }

  async function fetchDocumentIndex() {
    const response = await fetch("/documents", { headers: { Accept: "application/json" } });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || t().library.failed);
    }
    documentCache = Array.isArray(payload.documents) ? payload.documents : [];
    return documentCache;
  }

  async function fetchMemoryIndex() {
    const response = await fetch("/memories", { headers: { Accept: "application/json" } });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || t().pages.memory?.loadFailed || "Failed to load memories.");
    }
    memoryCache = Array.isArray(payload.memories) ? payload.memories : [];
    return memoryCache;
  }

  async function primeSearchIndexes() {
    if (searchIndexPromise) {
      return searchIndexPromise;
    }
    searchIndexPromise = Promise.allSettled([fetchDocumentIndex(), fetchMemoryIndex()]).finally(() => {
      searchIndexPromise = null;
      searchIndexReady = true;
    });
    return searchIndexPromise;
  }

  function applyChatSearch(query) {
    currentSearchQuery = String(query || "");
    renderSearchPanel(currentSearchQuery);
  }

  function refreshActiveSearchResults() {
    if (currentSearchQuery) {
      renderSearchPanel(currentSearchQuery);
    }
  }

function getRecentHistory() {
  return conversationHistory.slice(-MAX_HISTORY_MESSAGES);
}

function setChatBusy(isBusy) {
  chatBusy = isBusy;
  if (pageConfig.chat.submitButton) {
    pageConfig.chat.submitButton.disabled = isBusy;
  }
  if (pageConfig.chat.input) {
    pageConfig.chat.input.disabled = isBusy;
  }
  if (pageConfig.chat.newConversationButton) {
    pageConfig.chat.newConversationButton.disabled = isBusy;
  }
  renderConversationList();
}

function setUploadBusy(isBusy) {
  if (pageConfig.library.uploadButton) {
    pageConfig.library.uploadButton.disabled = isBusy;
  }
  if (pageConfig.library.fileInput) {
    pageConfig.library.fileInput.disabled = isBusy;
  }
}

async function fetchConversationList() {
  const response = await fetch("/conversations", { headers: { Accept: "application/json" } });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || t().pages.chat.conversationsFailed);
    }
    conversationListCache = Array.isArray(payload.conversations) ? payload.conversations : [];
    renderConversationList();
    refreshActiveSearchResults();
    setConversationRailStatus(t().pages.chat.conversationsReady(conversationListCache.length));
    return conversationListCache;
  }

async function loadConversation(conversationId, { updateStatus = true } = {}) {
  const normalizedId = String(conversationId || "").trim();
  if (!normalizedId) {
    setActiveConversationId("");
    syncConversationHistory([]);
    createIntroMessage();
    renderConversationList();
    return;
  }
  if (updateStatus) {
    setConversationRailStatus(t().pages.chat.conversationOpening);
  }
  const response = await fetch(`/conversations/${encodeURIComponent(normalizedId)}`, {
    headers: { Accept: "application/json" },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || t().pages.chat.conversationsFailed);
  }
  const conversation = payload.conversation || {};
  const messages = Array.isArray(payload.messages) ? payload.messages : [];
  setActiveConversationId(conversation.id || normalizedId);
  syncConversationHistory(messages);
  renderConversationTranscript(messages);
  requestAnimationFrame(() => scrollMessages({ behavior: "auto" }));
  renderConversationList();
  refreshActiveSearchResults();
  setConversationRailStatus(t().pages.chat.conversationsReady(conversationListCache.length));
}

async function deleteConversation(conversationId, conversationTitle) {
  const normalizedId = String(conversationId || "").trim();
  if (!normalizedId) {
    return false;
  }
  const normalizedTitle = String(conversationTitle || "").trim() || t().pages.chat.conversationFallbackTitle;
  if (!window.confirm(t().pages.chat.confirmDeleteConversation(normalizedTitle))) {
    return false;
  }

  const deletingActiveConversation = normalizedId === activeConversationId;
  setChatBusy(true);
  setConversationRailStatus(t().pages.chat.conversationDeleting);
  try {
    const response = await fetch(`/conversations/${encodeURIComponent(normalizedId)}`, {
      method: "DELETE",
      headers: { Accept: "application/json" },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || t().pages.chat.conversationsFailed);
    }

    await fetchConversationList();
    if (deletingActiveConversation) {
      const nextConversationId = conversationListCache[0]?.id || "";
      if (nextConversationId) {
        await loadConversation(nextConversationId, { updateStatus: false });
      } else {
        setActiveConversationId("");
        syncConversationHistory([]);
        createIntroMessage();
        setConversationRailStatus(t().pages.chat.conversationsEmpty);
      }
    } else {
      setConversationRailStatus(t().pages.chat.conversationsReady(conversationListCache.length));
    }
    refreshActiveSearchResults();
    showToast(t().pages.chat.conversationDeletedToast(normalizedTitle), "success");
    return true;
  } catch (error) {
    setConversationRailStatus(error instanceof Error ? error.message : t().pages.chat.conversationsFailed);
    return false;
  } finally {
    setChatBusy(false);
  }
}

async function createNewConversation() {
  setConversationRailStatus(t().pages.chat.conversationCreating);
  const response = await fetch("/conversations", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({}),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || t().pages.chat.conversationsFailed);
  }
  const conversation = payload.conversation || {};
  setActiveConversationId(conversation.id || "");
  syncConversationHistory([]);
  createIntroMessage();
  requestAnimationFrame(() => scrollMessages({ behavior: "auto" }));
  await fetchConversationList();
  refreshActiveSearchResults();
}

async function initializeChatSessions() {
  try {
    await fetchConversationList();
    const storedId = readStoredConversationId();
    const candidateId =
      (storedId && conversationListCache.some((conversation) => conversation.id === storedId) && storedId) ||
      conversationListCache[0]?.id ||
      "";
    if (candidateId) {
      await loadConversation(candidateId, { updateStatus: false });
    } else {
      setActiveConversationId("");
      syncConversationHistory([]);
      createIntroMessage();
      requestAnimationFrame(() => scrollMessages({ behavior: "auto" }));
      setConversationRailStatus(t().pages.chat.conversationsEmpty);
      refreshActiveSearchResults();
    }
  } catch (error) {
    conversationListCache = [];
    setActiveConversationId("");
    syncConversationHistory([]);
    createIntroMessage();
    requestAnimationFrame(() => scrollMessages({ behavior: "auto" }));
    renderConversationList();
    refreshActiveSearchResults();
    setConversationRailStatus(error instanceof Error ? error.message : t().pages.chat.conversationsFailed);
  }
}

async function fetchDocuments() {
  const documentList = pageConfig.library.documentList;
  if (!documentList) {
    return;
  }

  documentList.innerHTML = `<div class="document-empty">${t().library.loading}</div>`;
  try {
    const response = await fetch("/documents", { headers: { Accept: "application/json" } });
    const payload = await response.json();
    if (!response.ok) {
      documentList.innerHTML = `<div class="document-empty">${t().library.failed}</div>`;
      return;
    }
    documentCache = payload.documents || [];
    renderDocuments();
  } catch (error) {
    documentList.innerHTML = `<div class="document-empty">${t().library.failed}</div>`;
  }
}

async function deleteDocument(source, fileName) {
  activeDeleteSource = source;
  renderDocuments();
  setUploadStatus("deleting", fileName);

  try {
    const response = await fetch(`/documents?source=${encodeURIComponent(source)}`, {
      method: "DELETE",
      headers: { Accept: "application/json" },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      setUploadStatus("failed", payload.detail || t().library.failed);
      return;
    }

    documentCache = documentCache.filter((document) => document.source !== source);
    renderDocuments();
    setUploadStatus("deleted", fileName);
  } catch (error) {
    setUploadStatus("failed", t().errors.deleteUnavailable);
  } finally {
    activeDeleteSource = "";
    renderDocuments();
  }
}

function parseSseEvent(rawEvent) {
  const lines = rawEvent.split(/\r?\n/);
  let eventName = "message";
  const dataLines = [];
  for (const line of lines) {
    if (line.startsWith("event:")) {
      eventName = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }
  let payload = {};
  if (dataLines.length > 0) {
    payload = JSON.parse(dataLines.join("\n"));
  }
  return { eventName, payload };
}

function handleStreamEvent(rawEvent, assistantMessage) {
  const { eventName, payload } = parseSseEvent(rawEvent);
  if (eventName === "conversation") {
    if (payload.conversation_id) {
      setActiveConversationId(payload.conversation_id);
      renderConversationList();
    }
    return false;
  }
  if (eventName === "sources") {
    setMessageSources(assistantMessage, payload.sources || []);
    if ((payload.sources || []).length && assistantMessage.dataset.activeTool === "web_search") {
      setMessageToolStatus(assistantMessage, t().toolStatus.done, "done");
    }
    return false;
  }
  if (eventName === "memory_notices") {
    setMessageMemoryNotice(assistantMessage, payload.items || []);
    return false;
  }
  if (eventName === "progress") {
    const detail = formatProgressMessage(payload);
    setStatusDetail(detail);
    if (isToolProgressStage(payload.stage || "")) {
      const tone = payload.stage === "web_search_failed" ? "failed" : "pending";
      if ((payload.stage || "").startsWith("web_search")) {
        assistantMessage.dataset.activeTool = "web_search";
      }
      setMessageToolStatus(assistantMessage, detail, tone);
    }
    return false;
  }
  if (eventName === "delta") {
    appendMessageText(assistantMessage, payload.text || "");
    return false;
  }
  if (eventName === "error") {
    setMessageThinking(assistantMessage, false);
    setMessageToolStatus(assistantMessage, t().toolStatus.failed, "failed");
    throw new Error(payload.detail || t().status.failed);
  }
  if (eventName === "done") {
    setMessageThinking(assistantMessage, false);
    const tone = assistantMessage.dataset.toolStatusTone || "";
    if (assistantMessage.dataset.activeTool !== "web_search" && tone && tone !== "failed") {
      setMessageToolStatus(assistantMessage, "", "pending");
    }
    return true;
  }
  return false;
}

async function streamAnswer(question, history, assistantMessage) {
  const response = await fetch("/ask/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({
      question,
      history,
      conversation_id: activeConversationId || null,
      use_web_search: useWebSearch,
    }),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || t().status.failed);
  }
  if (!response.body) {
    throw new Error(t().errors.emptyStream);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let doneReceived = false;

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

    let boundaryIndex = buffer.indexOf("\n\n");
    while (boundaryIndex !== -1) {
      const rawEvent = buffer.slice(0, boundaryIndex).trim();
      buffer = buffer.slice(boundaryIndex + 2);
      if (rawEvent) {
        doneReceived = handleStreamEvent(rawEvent, assistantMessage) || doneReceived;
      }
      boundaryIndex = buffer.indexOf("\n\n");
    }
    if (done) {
      break;
    }
  }

  if (buffer.trim()) {
    doneReceived = handleStreamEvent(buffer.trim(), assistantMessage) || doneReceived;
  }
  if (!doneReceived) {
    throw new Error(t().errors.emptyStream);
  }
}

function initChatPage() {
  const {
    form,
    input,
    searchInput,
    searchPanel,
    conversationList,
    newConversationButton,
    webSearchToggleButton,
    scrollArea,
    scrollToBottomButton,
  } = pageConfig.chat;
  if (!form || !input || !conversationList || !newConversationButton) {
    return;
  }

  if (scrollArea) {
    scrollArea.addEventListener(
      "scroll",
      () => {
        updateScrollToBottomButton();
      },
      { passive: true },
    );
    requestAnimationFrame(() => updateScrollToBottomButton());
  }

  if (scrollToBottomButton) {
    scrollToBottomButton.addEventListener("click", () => {
      scrollMessages({ behavior: "smooth" });
    });
  }

  if (searchInput) {
    searchInput.addEventListener("input", () => {
      const query = searchInput.value || "";
      applyChatSearch(query);
      if (normalizeSearchText(query) && !searchIndexReady) {
        void primeSearchIndexes().then(() => {
          refreshActiveSearchResults();
        });
      }
    });
    searchInput.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        searchInput.value = "";
        applyChatSearch("");
        input.focus();
      }
    });
  }

  if (webSearchToggleButton) {
    webSearchToggleButton.addEventListener("click", () => {
      useWebSearch = !useWebSearch;
      writeStoredWebSearch(useWebSearch);
      updateWebSearchToggle();
    });
  }

  newConversationButton.addEventListener("click", async () => {
    if (chatBusy) {
      return;
    }
    try {
      setChatBusy(true);
      await createNewConversation();
      setStatus("ready");
      input.focus();
    } catch (error) {
      setConversationRailStatus(error instanceof Error ? error.message : t().pages.chat.conversationsFailed);
    } finally {
      setChatBusy(false);
    }
  });

  conversationList.addEventListener("click", async (event) => {
    const deleteButton = event.target.closest("[data-conversation-delete-id]");
    if (deleteButton && conversationList.contains(deleteButton)) {
      if (chatBusy) {
        return;
      }
      const conversationId = deleteButton.getAttribute("data-conversation-delete-id") || "";
      const conversationTitle = deleteButton.getAttribute("data-conversation-delete-title") || "";
      await deleteConversation(conversationId, conversationTitle);
      return;
    }

    const item = event.target.closest("[data-conversation-id]");
    if (!item || chatBusy) {
      return;
    }
    const conversationId = item.getAttribute("data-conversation-id") || "";
    if (!conversationId || conversationId === activeConversationId) {
      return;
    }
    try {
      setChatBusy(true);
      await loadConversation(conversationId);
      requestAnimationFrame(() => scrollMessages({ behavior: "auto" }));
      setStatus("ready");
    } catch (error) {
      setConversationRailStatus(error instanceof Error ? error.message : t().pages.chat.conversationsFailed);
    } finally {
      setChatBusy(false);
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const question = input.value.trim();
    if (!question) {
      setStatus("empty");
      input.focus();
      return;
    }

    const history = getRecentHistory();
    createMessage("user", question);
    input.value = "";
    setChatBusy(true);
    setStatus("asking");

    const assistantMessage = createMessage("assistant", "");
    try {
      await streamAnswer(question, history, assistantMessage);
      const assistantText = getMessageText(assistantMessage).trim();
      if (!assistantText) {
        throw new Error(t().errors.emptyStream);
      }
      conversationHistory.push(
        { role: "user", content: question },
        { role: "assistant", content: assistantText, sources: getMessageSources(assistantMessage) },
      );
      await fetchConversationList();
      setStatus("ready");
      } catch (error) {
        const detail = error instanceof Error ? error.message : t().status.failed;
        setMessageToolStatus(assistantMessage, t().toolStatus.failed, "failed");
        if (getMessageText(assistantMessage)) {
          appendMessageText(assistantMessage, `\n\n${t().errors.requestFailed} ${detail}`);
      } else {
        setMessageText(assistantMessage, `${t().errors.requestFailed} ${detail}`);
      }
      setStatus("failed");
    } finally {
      setChatBusy(false);
      input.focus();
    }
  });

  void primeSearchIndexes();
  void initializeChatSessions();
}

function initLibraryPage() {
  const { uploadForm, fileInput, documentList, searchInput } = pageConfig.library;
  if (!uploadForm || !fileInput || !documentList) {
    return;
  }

  fileInput.addEventListener("change", () => {
    const file = fileInput.files?.[0];
    if (!file) {
      setUploadStatus("idle");
      return;
    }
    setUploadStatus("selected", file.name);
  });

  if (searchInput) {
    searchInput.addEventListener("input", () => {
      renderDocuments();
    });
  }

  uploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = fileInput.files?.[0];
    if (!file) {
      setUploadStatus("failed", t().uploadStatus.idle);
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    setUploadBusy(true);
    setUploadStatus("uploading");

    try {
      const response = await fetch("/documents/upload", {
        method: "POST",
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok) {
        const detail = payload.detail || t().library.failed;
        setUploadStatus("failed", detail);
        return;
      }

      const document = payload.document;
      if (payload.status === "duplicate") {
        setUploadStatus("duplicate", document.file_name);
      } else {
        setUploadStatus("indexed", document.file_name);
      }

      await fetchDocuments();
      fileInput.value = "";
    } catch (error) {
      setUploadStatus("failed", t().errors.uploadUnavailable);
    } finally {
      setUploadBusy(false);
    }
  });

  documentList.addEventListener("click", async (event) => {
    const button = event.target.closest(".document-delete");
    if (!button) {
      return;
    }

    const source = button.dataset.source || "";
    const fileName = button.dataset.fileName || "";
    if (!source || !fileName) {
      return;
    }

    const confirmed = window.confirm(t().library.confirmDelete(fileName));
    if (!confirmed) {
      return;
    }

    await deleteDocument(source, fileName);
  });

  fetchDocuments();
}

localeZhButton?.addEventListener("click", () => applyLocale("zh"));
localeEnButton?.addEventListener("click", () => applyLocale("en"));

applyLocale(readStoredLocale() || "zh");
if (page === "chat") {
  initChatPage();
} else if (page === "library") {
  initLibraryPage();
}
