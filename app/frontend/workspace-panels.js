(function () {
  const overlay = document.querySelector("#workspaceOverlay");
  const closeButton = document.querySelector("#workspaceModalClose");
  const settingsButton = document.querySelector("#settingsButton");
  const supportButton = document.querySelector("#supportButton");
  const settingsPanel = document.querySelector("#settingsPanel");
  const supportPanel = document.querySelector("#supportPanel");
  const currentModelValue = document.querySelector("#currentModelValue");
  const currentModelHint = document.querySelector("#currentModelHint");
  const settingsEyebrow = document.querySelector("#settingsEyebrow");
  const workspaceModalTitle = document.querySelector("#workspaceModalTitle");
  const settingsCopy = document.querySelector("#settingsCopy");
  const settingsLanguageLabel = document.querySelector("#settingsLanguageLabel");
  const settingsThemeLabel = document.querySelector("#settingsThemeLabel");
  const settingsModelLabel = document.querySelector("#settingsModelLabel");
  const localeSwitch = document.querySelector("#localeSwitch");
  const themeSwitch = document.querySelector("#themeSwitch");
  const localeZhButton = document.querySelector("#localeZh");
  const localeEnButton = document.querySelector("#localeEn");
  const themeDarkButton = document.querySelector("#themeDark");
  const themeLightButton = document.querySelector("#themeLight");
  const supportEyebrow = document.querySelector("#supportEyebrow");
  const supportTitle = document.querySelector("#supportTitle");
  const supportCopy = document.querySelector("#supportCopy");
  const supportAuthorLabel = document.querySelector("#supportAuthorLabel");
  const supportAuthorValue = document.querySelector("#supportAuthorValue");
  const supportAuthorHint = document.querySelector("#supportAuthorHint");
  const supportStackLabel = document.querySelector("#supportStackLabel");
  const supportStackValue = document.querySelector("#supportStackValue");
  const supportStackHint = document.querySelector("#supportStackHint");

  const translations = {
    zh: {
      settingsEyebrow: "\u8bbe\u7f6e",
      workspaceModalTitle: "\u5de5\u4f5c\u533a\u8bbe\u7f6e",
      settingsCopy: "\u8c03\u6574\u754c\u9762\u8bed\u8a00\uff0c\u5e76\u67e5\u770b\u5f53\u524d\u8fd0\u884c\u6a21\u578b\u3002",
      settingsLanguageLabel: "\u8bed\u8a00",
      settingsThemeLabel: "\u4e3b\u9898",
      settingsModelLabel: "\u5f53\u524d\u6a21\u578b",
      themeDark: "\u6df1\u8272",
      themeLight: "\u6d45\u8272",
      themeSwitchAria: "\u4e3b\u9898\u5207\u6362",
      currentModelHint: (webModel) => `\u8054\u7f51\u641c\u7d22\u6a21\u578b\uff1a${webModel || "\u672a\u914d\u7f6e"}`,
      currentModelLoading: "\u8bfb\u53d6\u4e2d...",
      currentModelFallback: "\u672c\u5730\u8fd0\u884c\u65f6",
      supportEyebrow: "\u5e2e\u52a9",
      supportTitle: "\u5de5\u4f5c\u533a\u652f\u6301",
      supportCopy: "\u672c\u5730\u5de5\u4f5c\u533a\u4e0e\u5176\u6280\u672f\u6808\u8bf4\u660e\u3002",
      supportAuthorLabel: "\u4f5c\u8005",
      supportAuthorHint: "\u7531\u672c\u5730\u5de5\u4f5c\u533a\u6301\u7eed\u7ef4\u62a4\u3002",
      supportStackLabel: "\u6280\u672f\u6808",
      supportStackHint: "\u540e\u7aef\u670d\u52a1\u3001\u68c0\u7d22\u3001\u8bb0\u5fc6\u548c\u6d4f\u89c8\u5668\u754c\u9762\u3002",
    },
    en: {
      settingsEyebrow: "Settings",
      workspaceModalTitle: "Workspace settings",
      settingsCopy: "Adjust the interface language and inspect the active runtime model.",
      settingsLanguageLabel: "Language",
      settingsThemeLabel: "Theme",
      settingsModelLabel: "Current model",
      themeDark: "Dark",
      themeLight: "Light",
      themeSwitchAria: "Theme switcher",
      currentModelHint: (webModel) => `Web search model: ${webModel || "not configured"}`,
      currentModelLoading: "Loading...",
      currentModelFallback: "Local runtime",
      supportEyebrow: "Support",
      supportTitle: "Workspace support",
      supportCopy: "Reference information for the local workspace and the stack behind it.",
      supportAuthorLabel: "Author",
      supportAuthorHint: "Maintained as a local workspace.",
      supportStackLabel: "Tech stack",
      supportStackHint: "Backend services, retrieval, memory, and the browser shell.",
    },
  };

  const state = {
    locale: document.documentElement.lang.startsWith("zh") ? "zh" : "en",
    theme: readStoredTheme() || "dark",
    chatModel: "",
    webSearchModel: "",
    activePanel: "settings",
  };

  function readStoredTheme() {
    try {
      const value = window.localStorage.getItem("askrag.theme");
      return value === "light" || value === "dark" ? value : "";
    } catch (error) {
      return "";
    }
  }

  function writeStoredTheme(theme) {
    try {
      window.localStorage.setItem("askrag.theme", theme);
    } catch (error) {
      return;
    }
  }

  function text() {
    return translations[state.locale] || translations.en;
  }

  function setHidden(element, hidden) {
    if (!element) {
      return;
    }
    element.hidden = hidden;
    element.setAttribute("aria-hidden", hidden ? "true" : "false");
  }

  function updatePanelCopy() {
    const copy = text();
    if (settingsEyebrow) settingsEyebrow.textContent = copy.settingsEyebrow;
    if (workspaceModalTitle) workspaceModalTitle.textContent = copy.workspaceModalTitle;
    if (settingsCopy) settingsCopy.textContent = copy.settingsCopy;
    if (settingsLanguageLabel) settingsLanguageLabel.textContent = copy.settingsLanguageLabel;
    if (settingsThemeLabel) settingsThemeLabel.textContent = copy.settingsThemeLabel;
    if (settingsModelLabel) settingsModelLabel.textContent = copy.settingsModelLabel;
    if (supportEyebrow) supportEyebrow.textContent = copy.supportEyebrow;
    if (supportTitle) supportTitle.textContent = copy.supportTitle;
    if (supportCopy) supportCopy.textContent = copy.supportCopy;
    if (supportAuthorLabel) supportAuthorLabel.textContent = copy.supportAuthorLabel;
    if (supportAuthorHint) supportAuthorHint.textContent = copy.supportAuthorHint;
    if (supportStackLabel) supportStackLabel.textContent = copy.supportStackLabel;
    if (supportStackHint) supportStackHint.textContent = copy.supportStackHint;
    if (supportAuthorValue) supportAuthorValue.textContent = "Zoean/codex";
    if (supportStackValue) {
      supportStackValue.textContent =
        state.locale === "zh"
          ? "FastAPI\u3001Python\u3001Chroma\u3001OpenAI\u3001HTML/CSS/JS"
          : "FastAPI, Python, Chroma, OpenAI, HTML/CSS/JS";
    }
    if (themeSwitch) {
      themeSwitch.setAttribute("aria-label", copy.themeSwitchAria);
    }
    if (localeZhButton) {
      localeZhButton.classList.toggle("is-active", state.locale === "zh");
      localeZhButton.setAttribute("aria-pressed", state.locale === "zh" ? "true" : "false");
    }
    if (localeEnButton) {
      localeEnButton.classList.toggle("is-active", state.locale === "en");
      localeEnButton.setAttribute("aria-pressed", state.locale === "en" ? "true" : "false");
    }
    if (themeDarkButton) {
      themeDarkButton.textContent = copy.themeDark;
      themeDarkButton.classList.toggle("is-active", state.theme === "dark");
      themeDarkButton.setAttribute("aria-pressed", state.theme === "dark" ? "true" : "false");
    }
    if (themeLightButton) {
      themeLightButton.textContent = copy.themeLight;
      themeLightButton.classList.toggle("is-active", state.theme === "light");
      themeLightButton.setAttribute("aria-pressed", state.theme === "light" ? "true" : "false");
    }
    if (closeButton) {
      closeButton.setAttribute("aria-label", state.locale === "zh" ? "\u5173\u95ed" : "Close");
    }
  }

  function updateModelCopy() {
    const copy = text();
    if (currentModelValue) {
      currentModelValue.textContent = state.chatModel || copy.currentModelFallback;
    }
    if (currentModelHint) {
      currentModelHint.textContent = copy.currentModelHint(state.webSearchModel);
    }
  }

  function applyTheme() {
    const theme = state.theme === "light" ? "light" : "dark";
    state.theme = theme;
    document.body.dataset.theme = theme;
    document.documentElement.dataset.theme = theme;
  }

  function setTheme(theme) {
    state.theme = theme === "light" ? "light" : "dark";
    applyTheme();
    writeStoredTheme(state.theme);
    updatePanelCopy();
  }

  function applyPanelVisibility() {
    if (!overlay) {
      return;
    }
    if (state.activePanel === "support") {
      setHidden(settingsPanel, true);
      setHidden(supportPanel, false);
    } else {
      setHidden(settingsPanel, false);
      setHidden(supportPanel, true);
    }
  }

  function openPanel(panelName) {
    if (!overlay) {
      return;
    }
    state.activePanel = panelName === "support" ? "support" : "settings";
    document.body.classList.add("modal-open");
    setHidden(overlay, false);
    applyPanelVisibility();
    updatePanelCopy();
    updateModelCopy();
    if (state.activePanel === "settings") {
      void refreshModel();
    }
  }

  function closePanel() {
    if (!overlay) {
      return;
    }
    document.body.classList.remove("modal-open");
    setHidden(overlay, true);
  }

  async function refreshModel() {
    if (!currentModelValue && !currentModelHint) {
      return;
    }
    const copy = text();
    if (currentModelValue) {
      currentModelValue.textContent = copy.currentModelLoading;
    }
    if (currentModelHint) {
      currentModelHint.textContent = copy.currentModelHint("");
    }
    try {
      const response = await fetch("/ops/state", { headers: { Accept: "application/json" } });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.detail || "Failed to read workspace state.");
      }
      state.chatModel = String(payload.chat_model || "").trim();
      state.webSearchModel = String(payload.web_search_model || "").trim();
      updateModelCopy();
    } catch (error) {
      state.chatModel = "";
      state.webSearchModel = "";
      updateModelCopy();
    }
  }

  function setLocale(locale) {
    state.locale = locale === "en" ? "en" : "zh";
    updatePanelCopy();
    updateModelCopy();
  }

  settingsButton?.addEventListener("click", (event) => {
    event.preventDefault();
    openPanel("settings");
  });

  supportButton?.addEventListener("click", (event) => {
    event.preventDefault();
    openPanel("support");
  });

  closeButton?.addEventListener("click", closePanel);

  localeZhButton?.addEventListener("click", () => setLocale("zh"));
  localeEnButton?.addEventListener("click", () => setLocale("en"));
  themeDarkButton?.addEventListener("click", () => setTheme("dark"));
  themeLightButton?.addEventListener("click", () => setTheme("light"));

  overlay?.addEventListener("click", (event) => {
    if (event.target === overlay) {
      closePanel();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && overlay && !overlay.hidden) {
      closePanel();
    }
  });

  applyTheme();
  updatePanelCopy();
  updateModelCopy();
  setHidden(overlay, true);
  void refreshModel();

  window.WorkspacePanels = {
    setLocale,
    refreshModel,
    openSettings: () => openPanel("settings"),
    openSupport: () => openPanel("support"),
    close: closePanel,
    setTheme,
  };
})();
