const page = document.body.dataset.page || "chat";
const localeZhButton = document.querySelector("#localeZh");
const localeEnButton = document.querySelector("#localeEn");
const navChat = document.querySelector("#navChat");
const navLibrary = document.querySelector("#navLibrary");
const brandSubline = document.querySelector("#brandSubline");
const MAX_HISTORY_MESSAGES = 8;

const translations = {
  zh: {
    localeLabel: "\u7b80\u4f53\u4e2d\u6587",
    localeLabelShort: "English",
    brandSubline: "\u672c\u5730\u77e5\u8bc6\u5de5\u4f5c\u53f0",
    nav: {
      chat: "\u5bf9\u8bdd",
      library: "\u77e5\u8bc6\u5e93",
    },
    pages: {
      chat: {
        title: "askRAG \u5bf9\u8bdd",
        heading: "askRAG Chat",
        eyebrow: "\u5bf9\u8bdd",
        hero: "\u56f4\u7ed5\u5f53\u524d\u77e5\u8bc6\u5e93\u63d0\u95ee\uff0c\u76f4\u63a5\u67e5\u770b\u56de\u7b54\u548c\u4e3b\u6765\u6e90\u3002",
        transcriptLabel: "\u5bf9\u8bdd\u8bb0\u5f55",
        intro: "\u8f93\u5165\u95ee\u9898\u540e\u5373\u53ef\u5f00\u59cb\u5bf9\u8bdd\uff0c\u4e5f\u53ef\u4ee5\u76f4\u63a5\u8ffd\u95ee\u4e0a\u4e00\u8f6e\u5185\u5bb9\u3002",
        promptTitle: "\u63d0\u95ee\u533a",
        promptText: "\u4e00\u6b21\u8f93\u5165\u4e00\u4e2a\u95ee\u9898\uff0c\u56de\u7b54\u4f1a\u663e\u793a\u5728\u5bf9\u8bdd\u533a\u3002",
        questionLabel: "\u95ee\u9898",
        placeholder: "Chroma \u662f\u7528\u6765\u505a\u4ec0\u4e48\u7684\uff1f",
        submit: "\u53d1\u9001",
        notesTitle: "\u63d0\u793a",
        noteOne: "\u53ef\u4ee5\u76f4\u63a5\u8ffd\u95ee\u4e0a\u4e00\u8f6e\u63d0\u5230\u7684\u5bf9\u8c61\u6216\u65b9\u6cd5\u3002",
        noteTwo: "\u5982\u679c\u9700\u8981\u8865\u5145\u8d44\u6599\uff0c\u53ef\u4ee5\u5230\u77e5\u8bc6\u5e93\u9875\u9762\u4e0a\u4f20\u6587\u4ef6\u3002",
        noteThree: "\u56de\u7b54\u4e0b\u65b9\u4f1a\u663e\u793a\u4e3b\u6765\u6e90\u3002",
      },
      library: {
        title: "askRAG \u77e5\u8bc6\u5e93",
        heading: "\u77e5\u8bc6\u5e93",
        eyebrow: "\u77e5\u8bc6\u5e93",
        hero: "\u5728\u8fd9\u91cc\u6dfb\u52a0\u6587\u4ef6\uff0c\u8865\u5145\u53ef\u4f9b\u95ee\u7b54\u4f7f\u7528\u7684\u5185\u5bb9\u3002",
        uploadTitle: "\u4e0a\u4f20\u6587\u6863",
        uploadText: "\u652f\u6301\u4e0a\u4f20 <span class=\"mono\">.txt</span> \u548c <span class=\"mono\">.md</span> \u6587\u4ef6\u3002",
        filePickerText: "\u9009\u62e9\u4e00\u4e2a\u6587\u672c\u6587\u4ef6",
        uploadSubmit: "\u4e0a\u4f20\u5165\u5e93",
        deleteAction: "\u5220\u9664",
        libraryTitle: "\u5df2\u6dfb\u52a0\u6587\u4ef6",
        libraryText: "\u8fd9\u91cc\u5c55\u793a\u5f53\u524d\u53ef\u7528\u7684\u77e5\u8bc6\u5e93\u6587\u4ef6\u3002",
        notesTitle: "\u63d0\u793a",
        noteOne: "\u4e0a\u4f20\u5b8c\u6210\u540e\uff0c\u6587\u4ef6\u4f1a\u51fa\u73b0\u5728\u53f3\u4fa7\u5217\u8868\u4e2d\u3002",
        noteTwo: "\u5df2\u6dfb\u52a0\u7684\u5185\u5bb9\u53ef\u4ee5\u5728\u5bf9\u8bdd\u9875\u76f4\u63a5\u4f7f\u7528\u3002",
        noteThree: "\u91cd\u590d\u6587\u4ef6\u4f1a\u81ea\u52a8\u8df3\u8fc7\u3002",
      },
    },
    roles: {
      user: "\u7528\u6237",
      assistant: "\u52a9\u624b",
    },
    sourcesLabel: "\u4e3b\u6765\u6e90",
    status: {
      ready: "\u51c6\u5907\u5c31\u7eea\u3002",
      asking: "\u6b63\u5728\u7ed3\u5408\u6700\u8fd1\u5bf9\u8bdd\u751f\u6210\u56de\u7b54...",
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
      loading: "\u6b63\u5728\u8bfb\u53d6\u6587\u4ef6\u5217\u8868...",
      failed: "\u8bfb\u53d6\u6587\u4ef6\u5217\u8868\u5931\u8d25\u3002",
      uploaded: "\u6dfb\u52a0\u65f6\u95f4",
      seed: "\u521d\u59cb\u6587\u4ef6",
      unknown: "\u672a\u77e5",
      confirmDelete: (name) => `\u786e\u8ba4\u5220\u9664 ${name} \u5417\uff1f\u8be5\u6587\u4ef6\u4f1a\u4ece\u77e5\u8bc6\u5e93\u548c\u5411\u91cf\u5e93\u4e2d\u79fb\u9664\u3002`,
    },
  },
  en: {
    localeLabel: "Chinese",
    localeLabelShort: "English",
    brandSubline: "Local Knowledge Workbench",
    nav: {
      chat: "Chat",
      library: "Library",
    },
    pages: {
      chat: {
        title: "askRAG Chat",
        heading: "askRAG Chat",
        eyebrow: "Chat",
        hero: "Ask about the current knowledge base and read the answer with the primary source in one place.",
        transcriptLabel: "Conversation transcript",
        intro: "Enter a question to start chatting, or ask a follow-up about the previous turn.",
        promptTitle: "Prompt",
        promptText: "Ask one question at a time. The answer appears in the transcript.",
        questionLabel: "Question",
        placeholder: "What is Chroma used for?",
        submit: "Send",
        notesTitle: "Tips",
        noteOne: "You can ask follow-up questions about the previous turn.",
        noteTwo: "Use the library page when you need to add new files.",
        noteThree: "The primary source appears below each answer.",
      },
      library: {
        title: "askRAG Library",
        heading: "Library",
        eyebrow: "Library",
        hero: "Add files here to expand what chat can answer.",
        uploadTitle: "Upload document",
        uploadText: "Upload <span class=\"mono\">.txt</span> or <span class=\"mono\">.md</span> files.",
        filePickerText: "Choose a text file",
        uploadSubmit: "Upload",
        deleteAction: "Delete",
        libraryTitle: "Added files",
        libraryText: "This panel shows the files currently available to chat.",
        notesTitle: "Tips",
        noteOne: "After upload, the file appears in the list on the right.",
        noteTwo: "New content becomes available in chat after processing.",
        noteThree: "Duplicate files are skipped automatically.",
      },
    },
    roles: {
      user: "user",
      assistant: "assistant",
    },
    sourcesLabel: "Primary source",
    status: {
      ready: "Ready.",
      asking: "Generating an answer with recent context...",
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
      loading: "Loading file list...",
      failed: "Failed to load file list.",
      uploaded: "Added",
      seed: "Seed file",
      unknown: "Unknown",
      confirmDelete: (name) => `Delete ${name}? This removes the file from the library and the vector store.`,
    },
  },
};

const pageConfig = {
  chat: {
    titleElement: document.querySelector("h1"),
    eyebrowText: document.querySelector("#eyebrowText"),
    heroText: document.querySelector("#heroText"),
    transcriptPanel: document.querySelector("#transcriptPanel"),
    introMessage: document.querySelector("#introMessage"),
    promptTitle: document.querySelector("#promptTitle"),
    promptText: document.querySelector("#promptText"),
    questionLabel: document.querySelector("#questionLabel"),
    notesTitle: document.querySelector("#notesTitle"),
    noteOne: document.querySelector("#noteOne"),
    noteTwo: document.querySelector("#noteTwo"),
    noteThree: document.querySelector("#noteThree"),
    form: document.querySelector("#chatForm"),
    input: document.querySelector("#questionInput"),
    messageList: document.querySelector("#messageList"),
    submitButton: document.querySelector("#submitButton"),
    statusText: document.querySelector("#statusText"),
    template: document.querySelector("#messageTemplate"),
  },
  library: {
    titleElement: document.querySelector("h1"),
    eyebrowText: document.querySelector("#eyebrowText"),
    heroText: document.querySelector("#heroText"),
    uploadTitle: document.querySelector("#uploadTitle"),
    uploadText: document.querySelector("#uploadText"),
    filePickerText: document.querySelector("#filePickerText"),
    libraryTitle: document.querySelector("#libraryTitle"),
    libraryText: document.querySelector("#libraryText"),
    notesTitle: document.querySelector("#notesTitle"),
    noteOne: document.querySelector("#noteOne"),
    noteTwo: document.querySelector("#noteTwo"),
    noteThree: document.querySelector("#noteThree"),
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
let conversationHistory = [];
let activeDeleteSource = "";

function t() {
  return translations[currentLocale];
}

function getPageText() {
  return t().pages[page];
}

function updateNavAndBrand() {
  if (brandSubline) {
    brandSubline.textContent = t().brandSubline;
  }
  if (navChat) {
    navChat.textContent = t().nav.chat;
  }
  if (navLibrary) {
    navLibrary.textContent = t().nav.library;
  }
  if (localeZhButton) {
    localeZhButton.textContent = t().localeLabel;
  }
  if (localeEnButton) {
    localeEnButton.textContent = t().localeLabelShort;
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

function scrollMessages() {
  if (pageConfig.chat.messageList) {
    pageConfig.chat.messageList.scrollTo({
      top: pageConfig.chat.messageList.scrollHeight,
      behavior: "smooth",
    });
  }
}

function renderDocuments() {
  const documentList = pageConfig.library.documentList;
  if (!documentList) {
    return;
  }

  const libraryText = t().library;
  const libraryPageText = t().pages.library;
  if (documentCache.length === 0) {
    documentList.innerHTML = `<div class="document-empty">${libraryText.empty}</div>`;
    return;
  }

  documentList.innerHTML = documentCache
    .map((document) => {
      const isDeleting = activeDeleteSource === document.source;
      return `
        <article class="document-item">
          <div class="document-row">
            <div class="document-name">${document.file_name}</div>
            <div class="document-actions">
              <button
                type="button"
                class="button-danger document-delete"
                data-source="${document.source}"
                data-file-name="${document.file_name}"
                ${isDeleting ? "disabled" : ""}
              >${libraryPageText.deleteAction}</button>
            </div>
          </div>
          <div class="document-meta">
            <div class="doc-meta"><span class="doc-meta-label">${libraryText.uploaded}</span><span class="doc-meta-value">${formatUploadedAt(document.uploaded_at)}</span></div>
          </div>
        </article>
      `;
    })
    .join("");
}

function applyLocale(locale) {
  currentLocale = locale;
  const text = getPageText();
  const currentPage = pageConfig[page];

  document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
  document.title = text.title;
  updateNavAndBrand();

  currentPage.titleElement.textContent = text.heading;
  currentPage.eyebrowText.textContent = text.eyebrow;
  currentPage.heroText.textContent = text.hero;

  if (page === "chat") {
    currentPage.transcriptPanel.setAttribute("aria-label", text.transcriptLabel);
    const introArticle = currentPage.introMessage.closest(".message");
    if (introArticle) {
      introArticle.dataset.rawText = text.intro;
      renderMessageContent(introArticle);
    } else {
      currentPage.introMessage.innerHTML = `<p>${text.intro}</p>`;
    }
    currentPage.promptTitle.textContent = text.promptTitle;
    currentPage.promptText.textContent = text.promptText;
    currentPage.questionLabel.textContent = text.questionLabel;
    currentPage.input.placeholder = text.placeholder;
    currentPage.submitButton.textContent = text.submit;
    currentPage.notesTitle.textContent = text.notesTitle;
    currentPage.noteOne.textContent = text.noteOne;
    currentPage.noteTwo.textContent = text.noteTwo;
    currentPage.noteThree.textContent = text.noteThree;
    renderRoleLabels();
    renderSourceLabels();
    document.querySelectorAll(".message").forEach((message) => renderMessageContent(message));
    setStatus(currentStatusKey);
  }

  if (page === "library") {
    currentPage.uploadTitle.textContent = text.uploadTitle;
    currentPage.uploadText.innerHTML = text.uploadText;
    currentPage.filePickerText.textContent = text.filePickerText;
    currentPage.uploadButton.textContent = text.uploadSubmit;
    currentPage.libraryTitle.textContent = text.libraryTitle;
    currentPage.libraryText.textContent = text.libraryText;
    currentPage.notesTitle.textContent = text.notesTitle;
    currentPage.noteOne.textContent = text.noteOne;
    currentPage.noteTwo.textContent = text.noteTwo;
    currentPage.noteThree.textContent = text.noteThree;
    renderDocuments();
    setUploadStatus(currentUploadStatus.key, currentUploadStatus.value);
  }

  localeZhButton.classList.toggle("is-active", locale === "zh");
  localeEnButton.classList.toggle("is-active", locale === "en");
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

function createMessage(roleKey, text = "", sources = []) {
  const fragment = pageConfig.chat.template.content.cloneNode(true);
  const article = fragment.querySelector(".message");
  const roleEl = fragment.querySelector(".message-role");

  article.dataset.roleKey = roleKey;
  article.dataset.rawText = "";
  article.classList.add(roleKey === "user" ? "message-user" : "message-assistant");
  roleEl.textContent = t().roles[roleKey] || roleKey;

  pageConfig.chat.messageList.appendChild(fragment);
  setMessageText(article, text);
  setMessageSources(article, sources);
  scrollMessages();
  return article;
}

function getMessageText(article) {
  return article?.dataset.rawText || "";
}

function getMessageSources(article) {
  return Array.from(article.querySelectorAll(".source-chip")).map((chip) => chip.textContent || "").filter(Boolean);
}

function setMessageText(article, text) {
  article.dataset.rawText = text || "";
  renderMessageContent(article);
  scrollMessages();
}

function appendMessageText(article, text) {
  article.dataset.rawText = `${article.dataset.rawText || ""}${text || ""}`;
  renderMessageContent(article);
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

function getRecentHistory() {
  return conversationHistory.slice(-MAX_HISTORY_MESSAGES);
}

function setChatBusy(isBusy) {
  if (pageConfig.chat.submitButton) {
    pageConfig.chat.submitButton.disabled = isBusy;
  }
  if (pageConfig.chat.input) {
    pageConfig.chat.input.disabled = isBusy;
  }
}

function setUploadBusy(isBusy) {
  if (pageConfig.library.uploadButton) {
    pageConfig.library.uploadButton.disabled = isBusy;
  }
  if (pageConfig.library.fileInput) {
    pageConfig.library.fileInput.disabled = isBusy;
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
  if (eventName === "sources") {
    setMessageSources(assistantMessage, payload.sources || []);
    if ((payload.sources || []).length && assistantMessage.dataset.activeTool === "web_search") {
      setMessageToolStatus(assistantMessage, t().toolStatus.done, "done");
    }
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
    setMessageToolStatus(assistantMessage, t().toolStatus.failed, "failed");
    throw new Error(payload.detail || t().status.failed);
  }
  if (eventName === "done") {
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
    body: JSON.stringify({ question, history }),
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
  const { form, input } = pageConfig.chat;
  if (!form || !input) {
    return;
  }

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
}

function initLibraryPage() {
  const { uploadForm, fileInput, documentList } = pageConfig.library;
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

applyLocale("zh");
if (page === "chat") {
  initChatPage();
} else if (page === "library") {
  initLibraryPage();
}
