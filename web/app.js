const state = {
  config: null,
  methods: [],
  activeMethodPhase: "discover",
  methodPools: {
    discover: new Set(),
    solve: new Set(),
    validate: new Set(),
  },
  methodAssignments: {
    discover: new Set(),
    solve: new Set(),
    validate: new Set(),
  },
  frameworkSvg: "",
  outline: null,
  markdown: "",
  citations: [],
  projects: [],
  currentProjectId: "default",
  currentDirection: { id: "", name: "" },
  drafts: {},
  autosaveTimer: null,
  draftAutosaveTimers: {},
  writingAll: false,
  chatMessages: [],
  chatLoading: false,
  sectionCitations: {},
  license: null,
};

// Per-subsection citation management state
const citationPageState = {
  activeDraftKey: null,
  cardCache: {},
};

const DEFAULT_PROJECT_CONTEXT = `论文题目、研究方向、项目背景和论文思路请在「论文信息」页面自行填写。填写后生成的大纲和内容将更贴合你的实际研究。`;

let _methodCatalogCache = null;

async function getMethodCatalog() {
  if (_methodCatalogCache) return _methodCatalogCache;
  try {
    const data = await api("/api/method-catalog");
    _methodCatalogCache = (data.catalog || []).map((item) => ({
      name: item.name,
      phases: item.phases || [],
      type: item.category || "method",
      aliases: [item.name, ...(item.aliases || [])],
    }));
    return _methodCatalogCache;
  } catch (e) {
    return [];
  }
}

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

const CHAT_BUBBLE_TIPS = {
  setup: "需要帮助配置AI模型？点我聊聊",
  paper_info: "论文题目或方向定不下来？问我",
  methods: "不确定选哪些方法论？让我帮你分析",
  framework: "研究框架不知道怎么搭？聊聊思路",
  outline: "大纲结构不满意？告诉我哪里想调",
  citations: "引文格式拿不准？我来帮你把关",
  writing: "写作卡住了？把这一段发给我看看",
  blind_review: "担心盲审被挂？我帮你预审一遍",
};

function activeStep(id) {
  if (id === "methods") {
    syncPromptMethodsToOptions();
    if (state.methods.length) renderMethods();
  }
  if (id === "framework") renderSvgPreview();
  $$(".page").forEach((page) => page.classList.toggle("active", page.id === id));
  $$(".step").forEach((step) => step.classList.toggle("active", step.dataset.step === id));
  const bubble = $("#chatBubble");
  if (bubble) {
    bubble.title = CHAT_BUBBLE_TIPS[id] || "打开论文助手，随时问我";
    bubble.setAttribute("aria-label", bubble.title);
  }
  const chatTitle = $("#chatFloatTitle");
  if (chatTitle) {
    const labels = { setup:"配置引导", paper_info:"论文信息引导", methods:"方法论引导", framework:"框架引导", outline:"大纲引导", citations:"引文引导", writing:"写作引导", blind_review:"盲审引导", proposal:"开题报告引导", ppt_proposal:"开题PPT制作", ppt_midterm:"中期PPT制作", ppt_defense:"答辩PPT制作", table_generator:"表格生成器", aigc_check:"AIGC率评估", aigc_reduce:"AIGC降重" };
    chatTitle.textContent = labels[id] || "论文助手";
  }
  if (id === "license") updateLicenseUI();
}

function selectedDirection() {
  return state.currentDirection;
}

function refreshDirectionDisplay() {
  const el = $("#currentTopic");
  const dirEl = $("#currentDirection");
  if (el) el.textContent = $("#topicInput").value.trim() || "未设置";
  if (dirEl) dirEl.textContent = state.currentDirection.name || "未设置";
}

function populateModalDirection() {
  const select = $("#newProjectDirection");
  if (!select || !state.config?.directions) return;
  select.innerHTML = state.config.directions
    .map((item) => `<option value="${item.id}">${item.name}</option>`)
    .join("");
  if (state.currentDirection.id) {
    select.value = state.currentDirection.id;
  }
}

function methodNameById(id) {
  return state.methods.find((item) => item.id === id)?.name || id;
}

function methodIdFromName(name) {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^\u4e00-\u9fffa-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function ensureMethodOption(name, phases, type = "method", source = "从项目背景识别") {
  const id = `prompt_${methodIdFromName(name)}`;
  const existing = state.methods.find((item) => item.id === id || item.name === name);
  if (existing) {
    existing.phases = Array.from(new Set([...(existing.phases || []), ...phases]));
    existing.sources = Array.from(new Set([...(existing.sources || []), source])).slice(0, 8);
    return existing.id;
  }
  state.methods.push({
    id,
    name,
    type,
    source_count: 0,
    sources: [source],
    phases,
    detected_by: "project_context",
    llm_reason: "用户项目背景中明确提到，已自动加入候选项。",
  });
  return id;
}

async function syncPromptMethodsToOptions() {
  const text = projectContextPayload();
  if (!text) return;
  const catalog = await getMethodCatalog();
  if (!catalog.length) return;
  let changed = false;
  catalog.forEach((item) => {
    if (item.aliases.some((alias) => text.toLowerCase().includes(alias.toLowerCase()))) {
      ensureMethodOption(item.name, item.phases, item.type);
      changed = true;
    }
  });
  if (changed) renderMethods();
}

function phaseLabel(phase) {
  return { discover: "发现问题", solve: "解决问题", validate: "验证问题" }[phase] || phase;
}

function cleanHeadingTitle(title, number = "") {
  let value = String(title || "").trim();
  value = value.replace(/^#{1,6}\s*/, "");
  value = value.replace(/^第[一二三四五六七八九十\d]+章\s*/, "");
  if (number) {
    const escaped = number.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    value = value.replace(new RegExp(`^${escaped}\\s+`), "");
  }
  value = value.replace(/^\d+(?:\.\d+){0,3}\s+/, "");
  return value.trim();
}

function chapterPrefix(number) {
  const numerals = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"];
  const n = Number(number) || 0;
  if (n <= 10) return `第${numerals[n]}章`;
  if (n < 20) return `第十${numerals[n - 10]}章`;
  return `第${n}章`;
}

function chapterDisplayTitle(chapter) {
  return `${chapterPrefix(chapter.number)} ${cleanHeadingTitle(chapter.title) || "未命名章节"}`;
}

function stripMarkdownText(text) {
  return String(text || "")
    .replace(/^#{1,6}\s*/gm, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/__([^_]+)__/g, "$1")
    .replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, "$1$2")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^\s*[-*+]\s+/gm, "")
    .trim();
}

function normalizeDraftContent(text, target = null) {
  let value = stripMarkdownText(text);
  const number = target?.number ? String(target.number) : "";
  const title = cleanHeadingTitle(target?.title || "", number);
  const lines = value.split(/\r?\n/).map((line) => line.trim());
  const cleaned = [];
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const bare = cleanHeadingTitle(line, number);
    const looksLikeHeading =
      /^第[一二三四五六七八九十\d]+章/.test(line) ||
      /^\d+(?:\.\d+){1,3}\s+\S{2,80}$/.test(line) ||
      (number && line.startsWith(number)) ||
      (title && bare === title);
    if (index < 5 && looksLikeHeading) {
      continue;
    }
    if (line && cleaned[cleaned.length - 1] === line) continue;
    cleaned.push(line);
  }
  return cleaned.join("\n").trim();
}

function draftKeyFor(chapter, section, subsection = null) {
  return subsection?.number || section?.number || `${chapter.number}`;
}

function renumberOutline() {
  (state.outline?.chapters || []).forEach((chapter, chapterIndex) => {
    chapter.number = chapterIndex + 1;
    chapter.title = cleanHeadingTitle(chapter.title);
    ensureChapterSummarySection(chapter);
    (chapter.sections || []).forEach((section, sectionIndex) => {
      section.level = 2;
      section.number = `${chapterIndex + 1}.${sectionIndex + 1}`;
      section.title = cleanHeadingTitle(section.title, section.number);
      (section.subsections || []).forEach((subsection, subsectionIndex) => {
        subsection.level = 3;
        subsection.number = `${chapterIndex + 1}.${sectionIndex + 1}.${subsectionIndex + 1}`;
        subsection.title = cleanHeadingTitle(subsection.title, subsection.number);
      });
    });
  });
}

function ensureChapterSummarySection(chapter) {
  chapter.sections = chapter.sections || [];
  if (!chapter.sections.length) return;
  const summaryIndex = chapter.sections.findIndex((section) => cleanHeadingTitle(section.title, section.number) === "本章小结");
  let summary = null;
  if (summaryIndex >= 0) {
    summary = chapter.sections.splice(summaryIndex, 1)[0];
  }
  if (!summary) {
    summary = {
      level: 2,
      number: "",
      title: "本章小结",
      estimated_words: 500,
      subsections: [],
    };
  }
  summary.title = "本章小结";
  summary.subsections = summary.subsections || [];
  chapter.sections.push(summary);
}

function scheduleOutlineAutosave() {
  clearTimeout(state.autosaveTimer);
  $("#outlineStatus").textContent = "有未保存修改，稍后自动保存...";
  state.autosaveTimer = setTimeout(() => saveOutlineState("自动保存完成"), 1200);
}

function countTextWords(text) {
  const value = stripMarkdownText(text || "");
  const chinese = (value.match(/[\u4e00-\u9fff]/g) || []).length;
  const words = (value.replace(/[\u4e00-\u9fff]/g, " ").match(/[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*/g) || []).length;
  return chinese + words;
}

function syncWordSelect(total) {
  const select = $("#wordCount");
  if (!select || !total) return;
  const value = String(total);
  if (!Array.from(select.options).some((option) => option.value === value)) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = `${total} 字`;
    select.appendChild(option);
  }
  select.value = value;
}

function rollupOutlineWords(kind = "estimated_words") {
  if (!state.outline) return 0;
  let total = 0;
  (state.outline.chapters || []).forEach((chapter) => {
    let chapterTotal = 0;
    (chapter.sections || []).forEach((section) => {
      const subsections = section.subsections || [];
      if (subsections.length) {
        section[kind] = subsections.reduce(
          (sum, subsection) => sum + (Number(subsection[kind]) || 0),
          0
        );
      }
      chapterTotal += Number(section[kind]) || 0;
    });
    chapter[kind] = chapterTotal;
    total += chapterTotal;
  });
  state.outline.metadata = state.outline.metadata || {};
  state.outline.metadata[kind] = total;
  if (kind === "estimated_words") syncWordSelect(total);
  updateWordSummary();
  return total;
}

function updateWordSummary() {
  const estimated = state.outline?.metadata?.estimated_words || 0;
  const actual = state.outline?.metadata?.actual_words || 0;
  const node = $("#wordSummary");
  if (node) node.textContent = `预计 ${estimated} 字 · 实际 ${actual} 字`;
}

function updateOutlineWordsFromDraft(draftKey, content) {
  if (!state.outline) return;
  const words = countTextWords(content);
  (state.outline.chapters || []).forEach((chapter) => {
    (chapter.sections || []).forEach((section) => {
      if (section.number === draftKey && !(section.subsections || []).length) {
        section.actual_words = words;
      }
      (section.subsections || []).forEach((subsection) => {
        if (subsection.number === draftKey) {
          subsection.actual_words = words;
        }
      });
    });
  });
  const total = rollupOutlineWords("actual_words");
  renderOutline();
  renderWritingList();
  saveOutlineState(`已按正文统计实际字数，总计 ${total} 字`);
}

function nowTime() {
  return new Date().toLocaleTimeString("zh-CN", { hour12: false });
}

function setWritingStatus(message) {
  $("#writingStatus").textContent = message;
}

function setSerialProgress(done, total, message = "") {
  const box = $("#serialProgress");
  if (!box) return;
  const percent = total ? Math.min(100, Math.max(0, Math.round((done / total) * 100))) : 0;
  box.hidden = false;
  $("#snailRunner").style.left = `calc(${percent}% - 18px)`;
  $("#serialProgressText").textContent = message || `正在串行扩写 ${done}/${total}`;
}

function setSubsectionProgress(done, total, message = "") {
  const box = $("#subsectionProgress");
  if (!box) return;
  const percent = total ? Math.min(100, Math.max(0, Math.round((done / total) * 100))) : 0;
  box.hidden = false;
  $("#subsectionSnailRunner").style.left = `calc(${percent}% - 18px)`;
  $("#subsectionProgressText").textContent = message || `正在生成三级目录 ${done}/${total}`;
}

function hideSubsectionProgress() {
  const box = $("#subsectionProgress");
  if (box) box.hidden = true;
}

function hideSerialProgress() {
  const box = $("#serialProgress");
  if (box) box.hidden = true;
}

function renderConsistencyFeedback(consistency, citationCheck, staleChapters) {
  const container = $("#consistencyFeedback");
  if (!container) return;
  let html = "";

  if (consistency) {
    const total = consistency.total_commitments || 0;
    const resolved = consistency.resolved || 0;
    const hard = consistency.hard_unresolved || 0;
    const soft = consistency.soft_unresolved || 0;
    if (total > 0) {
      html += `<div class="cf-item ${hard > 0 ? 'cf-warn' : 'cf-ok'}">`;
      html += `一致性：前文 ${total} 项承诺，已闭合 ${resolved}，`;
      if (hard > 0) html += `<strong>${hard} 项未闭合</strong>`;
      else if (soft > 0) html += `${soft} 项可选未覆盖`;
      else html += "全部闭合";
      html += "</div>";
      if (consistency.definition_drifts && consistency.definition_drifts.length > 0) {
        html += '<div class="cf-item cf-warn">术语定义漂移：';
        for (const d of consistency.definition_drifts) {
          html += `<span class="cf-tag">${escHtml(d.term)}</span>`;
        }
        html += "</div>";
      }
    }
  }

  if (citationCheck) {
    const missing = citationCheck.missing || [];
    const unknown = citationCheck.unknown || [];
    const fabricated = citationCheck.fabricated_indices || [];
    const anyFound = citationCheck.any_found;
    if (citationCheck.total_expected > 0) {
      if (missing.length > 0) {
        html += `<div class="cf-item cf-warn">引用缺失：要求引用 [${missing.map(i => i+1).join(', ')}] 但未找到</div>`;
      } else if (unknown.length > 0) {
        html += `<div class="cf-item cf-warn">意外引用：[${unknown.map(i => i+1).join(', ')}] 不在要求列表中</div>`;
      } else {
        html += `<div class="cf-item cf-ok">引用：全部 ${citationCheck.total_expected} 篇已正确引用</div>`;
      }
      if (fabricated.length > 0) {
        html += `<div class="cf-item cf-warn">疑似虚构引用号：[${fabricated.map(i => i+1).join(', ')}] 超出引用库范围</div>`;
      }
    } else if (anyFound) {
      html += '<div class="cf-item cf-warn">当前小节不要求引用，但生成了引用标记</div>';
    }
  }

  if (staleChapters && staleChapters.length > 0) {
    html += `<div class="cf-item cf-stale">下游章节可能过时：第 ${staleChapters.map(s => s.chapter).join('、')} 章需要重新生成</div>`;
  }

  container.innerHTML = html;
  if (html) {
    container.style.display = "block";
    setTimeout(() => { container.style.display = "none"; }, 12000);
  }
}

function renderStaleChapterWarnings(staleChapters) {
  if (!staleChapters || !staleChapters.length) return;
  for (const stale of staleChapters) {
    const badge = $(`[data-stale-chapter="${CSS.escape(stale.chapter)}"]`);
    if (badge) {
      badge.hidden = false;
      badge.title = stale.reason || "上游内容已变更";
    }
  }
}

function setCitationProgress(done, total, message = "") {
  const box = $("#citationProgress");
  if (!box) return;
  if (!box) return;
  const percent = total ? Math.min(100, Math.max(0, Math.round((done / total) * 100))) : 0;
  box.hidden = false;
  $("#citationSnailRunner").style.left = `calc(${percent}% - 18px)`;
  $("#citationProgressText").textContent = message || `正在生成引用 ${done}/${total}`;
}

function hideCitationProgress() {
  const box = $("#citationProgress");
  if (box) box.hidden = true;
}

function selectedMethodNames() {
  const ids = new Set([
    ...state.methodAssignments.discover,
    ...state.methodAssignments.solve,
    ...state.methodAssignments.validate,
  ]);
  return Array.from(ids).map(methodNameById);
}

function phaseMethodsPayload() {
  return {
    discover: Array.from(state.methodAssignments.discover).map(methodNameById),
    solve: Array.from(state.methodAssignments.solve).map(methodNameById),
    validate: Array.from(state.methodAssignments.validate).map(methodNameById),
  };
}

function projectContextPayload() {
  let bg = ($("#projectBgInput")?.value || "").trim();
  let approach = ($("#projectApproachInput")?.value || "").trim();
  // 剥离用户可能粘贴进来的旧标题，避免双包
  bg = bg.replace(/^##\s*项目背景\s*\n?/gm, "").trim();
  approach = approach.replace(/^##\s*论文思路\s*\n?/gm, "").trim();
  if (!bg && !approach) return "";
  let result = "";
  if (bg) result += `## 项目背景\n${bg}`;
  if (approach) result += `\n\n## 论文思路\n${approach}`;
  return result.trim();
}

async function saveProjectContext() {
  const payload = projectContextPayload();
  if (!payload) return;
  await api("/api/project-context", {
    method: "POST",
    body: JSON.stringify({
      project_context: payload,
      topic: $("#topicInput")?.value?.trim() || state.currentProjectId,
      direction: (state.currentDirection || {}).name || "",
    }),
  });
}

async function saveMethodAssignments() {
  const phaseMethods = {
    discover: Array.from(state.methodAssignments.discover),
    solve: Array.from(state.methodAssignments.solve),
    validate: Array.from(state.methodAssignments.validate),
  };
  await api("/api/method-assignments/save", {
    method: "POST",
    body: JSON.stringify({ phase_methods: phaseMethods }),
  }).catch(() => {});
}

async function saveMethodPool(phase) {
  const p = phase || state.activeMethodPhase;
  await api("/api/method-pool/save", {
    method: "POST",
    body: JSON.stringify({ method_pool: Array.from(state.methodPools[p] || []), phase: p }),
  }).catch(() => {});
}

async function saveAllMethodSelections() {
  await saveMethodAssignments();
  for (const phase of ["discover", "solve", "validate"]) {
    await saveMethodPool(phase);
  }
  const el = $("#saveMethodSelections");
  if (el) {
    const orig = el.textContent;
    el.textContent = "✅ 已保存";
    el.classList.add("saved-flash");
    setTimeout(() => {
      el.textContent = orig;
      el.classList.remove("saved-flash");
    }, 1500);
  }
}

function loadProjectContext() {
  const topicInput = $("#topicInput");
  if (topicInput) {
    topicInput.addEventListener("input", () => refreshDirectionDisplay());
  }
  const example = $("#projectContextExample");
  if (example) example.value = DEFAULT_PROJECT_CONTEXT;
  const toggle = $("#toggleExample");
  if (toggle) {
    toggle.addEventListener("click", () => {
      const textarea = $("#projectContextExample");
      if (!textarea) return;
      const hidden = textarea.hidden;
      textarea.hidden = !hidden;
      toggle.textContent = hidden ? "收起示例" : "展开示例";
    });
  }
  const bgInput = $("#projectBgInput");
  const approachInput = $("#projectApproachInput");
  if (bgInput) bgInput.addEventListener("input", () => {
    $("#saveTip").textContent = "项目背景将在生成或保存时写入长期记忆";
  });
  if (approachInput) approachInput.addEventListener("input", () => {
    $("#saveTip").textContent = "论文思路将在生成或保存时写入长期记忆";
  });
  if (approachInput) approachInput.addEventListener("blur", syncPromptMethodsToOptions);
}

function resetWorkspaceView() {
  state.frameworkSvg = "";
  state.outline = null;
  state.markdown = "";
  state.citations = [];
  state.drafts = {};
  state.methodAssignments = { discover: new Set(), solve: new Set(), validate: new Set() };
  state.sectionCitations = {};
  state.paperCitations = [];
  citationPageState.activeDraftKey = null;
  citationPageState.cardCache = {};
  $("#svgPreview").innerHTML = "";
  $("#outlinePreview").innerHTML = "";
  $("#outlineLog").innerHTML = "";
  $("#writingList").innerHTML = "";
  $("#downloadOutline").disabled = true;
  $("#outlineStatus").textContent = "";
  $("#writingStatus").textContent = "";
  $("#citationStatus").textContent = "";
  renderCitations();
}

function renderProjects() {
  const select = $("#projectSelect");
  if (!select) return;
  select.innerHTML = state.projects
    .map((project) => {
      const date = project.updated_at
        ? new Date(project.updated_at * 1000).toLocaleDateString("zh-CN")
        : "";
      return `<option value="${project.id}">${project.topic || "未命名论文项目"}${date ? ` · ${date}` : ""}</option>`;
    })
    .join("");
  select.value = state.currentProjectId;
  const current = state.projects.find((project) => project.id === state.currentProjectId);
  if (current?.topic && $("#topicInput")) {
    $("#topicInput").value = current.topic;
  }
  refreshDirectionDisplay();
}

async function loadProjects() {
  const data = await api("/api/projects");
  state.projects = data.projects || [];
  state.currentProjectId = data.current_project_id || "default";
  renderProjects();
}

async function createNewProject() {
  const topic = $("#newProjectTopic").value.trim() || $("#topicInput").value.trim();
  const dirSelect = $("#newProjectDirection");
  if (dirSelect?.value) {
    state.currentDirection = { id: dirSelect.value, name: dirSelect.options[dirSelect.selectedIndex]?.textContent || "" };
  }
  const data = await api("/api/projects/create", {
    method: "POST",
    body: JSON.stringify({ topic: topic || "未命名论文项目" }),
  });
  state.projects = data.projects || [];
  state.currentProjectId = data.project.id;
  // 持久化方向到新项目 scope
  if (state.currentDirection.id) {
    api("/api/workspace/save", {
      method: "POST",
      body: JSON.stringify({ key: "current_direction", value: state.currentDirection }),
    }).catch(() => {});
  }
  refreshDirectionDisplay();
  renderProjects();
  resetWorkspaceView();
  await loadWorkspace();
  $("#topicInput").value = topic || "";
  if ($("#continueLast")) $("#continueLast").disabled = true;
  $("#saveTip").textContent = "已新建论文项目，工作区已清空";
  closeNewProjectModal();
}

function openNewProjectModal() {
  $("#newProjectTopic").value = $("#topicInput").value.trim();
  populateModalDirection();
  if (state.currentDirection.id) {
    $("#newProjectDirection").value = state.currentDirection.id;
  }
  $("#newProjectModal").hidden = false;
  $("#newProjectTopic").focus();
}

function closeNewProjectModal() {
  $("#newProjectModal").hidden = true;
}

async function switchProject(projectId) {
  await api("/api/projects/switch", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId }),
  });
  resetWorkspaceView();
  await loadProjects();
  await loadWorkspace();
  $("#saveTip").textContent = "已切换历史论文项目";
}

async function loadConfig() {
  state.config = await api("/api/config");
  $("#modelBadge").textContent = state.config.model;
  $("#providerInput").value = state.config.provider;
  $("#modelInput").value = state.config.model;
  $("#baseUrlInput").value = state.config.base_url || "";
  $("#maxTokensInput").value = state.config.max_tokens || 4000;
  $("#apiKeyInput").placeholder = state.config.api_key_configured
    ? `已保存 ${state.config.api_key_preview}，留空不修改`
    : "请输入 API Key";
  if (state.config.directions?.length && !state.currentDirection.id) {
    state.currentDirection = { id: state.config.directions[0].id, name: state.config.directions[0].name };
  }
  refreshDirectionDisplay();
  populateModalDirection();
}

const PROVIDER_PRESETS = {
  deepseek:     { base_url: "https://api.deepseek.com/anthropic",            model: "deepseek-v4-pro" },
  minimax:      { base_url: "https://api.minimax.chat/anthropic",            model: "minimax-m1" },
  moonshot:     { base_url: "https://api.moonshot.cn/anthropic",             model: "moonshot-v1-128k" },
  zhipu:        { base_url: "https://open.bigmodel.cn/api/paas/v4/anthropic",model: "glm-4-plus" },
  qwen:         { base_url: "https://dashscope.aliyuncs.com/compatible-mode/anthropic", model: "qwen-max" },
  bytedance:    { base_url: "https://ark.cn-beijing.volces.com/api/v3/anthropic", model: "doubao-pro-256k" },
  anthropic:    { base_url: "https://api.anthropic.com",                      model: "claude-opus-4-7" },
  openai:       { base_url: "", model: "gpt-4o" },
  openai_compatible: { base_url: "", model: "" },
};

function onProviderChange() {
  const provider = $("#providerInput").value;
  const preset = PROVIDER_PRESETS[provider];
  if (!preset) return;
  if (preset.base_url) $("#baseUrlInput").value = preset.base_url;
  if (preset.model) {
    $("#modelInput").value = preset.model;
    $("#modelBadge").textContent = preset.model;
  }
}

async function loadLicense() {
  try {
    state.license = await api("/api/license/status");
  } catch (e) {
    state.license = { status: "no_license", tier: "free", tier_label: "免费版(未激活)", days_left: 0, features: [] };
  }
  updateLicenseUI();
}

function updateLicenseUI() {
  const lic = state.license || { status: "no_license", tier: "free", days_left: 0, features: [] };

  // Badge
  const badge = $("#licenseBadge");
  const dot = $("#licenseDot");
  const label = $("#licenseLabel");
  const days = $("#licenseDays");

  if (badge) {
    badge.onclick = () => activeStep("license");
  }
  if (dot) {
    dot.className = "license-dot";
    if (lic.status === "active") dot.classList.add("active");
    else if (lic.status === "trial") dot.classList.add("trial");
    else if (lic.status === "expired") dot.classList.add("expired");
    else dot.classList.add("none");
  }
  if (label) label.textContent = lic.tier_label || "许可证";
  if (days) {
    if (lic.status === "trial") {
      days.textContent = `试用剩余 ${lic.days_left} 天`;
      days.style.color = lic.days_left <= 1 ? "#ef4444" : "#f59e0b";
    } else if (lic.status === "active") {
      days.textContent = `剩余 ${lic.days_left} 天`;
      days.style.color = lic.days_left <= 30 ? "#f59e0b" : "#10b981";
    } else if (lic.status === "expired") {
      days.textContent = "已到期";
      days.style.color = "#ef4444";
    } else {
      days.textContent = "未激活";
      days.style.color = "#94a3b8";
    }
  }

  // Gate menu items
  const features = lic.features || [];
  const hasAll = features.includes("all");
  const hasWorkflow = hasAll || features.includes("workflow");
  const hasAdvanced = hasAll || features.includes("advanced");
  state.hasAdvanced = hasAdvanced;
  state.hasWorkflow = hasWorkflow;

  const advancedMenus = ["proposal", "ppt_proposal", "ppt_midterm", "ppt_defense"];
  const vipMenus = ["blind_review", "aigc_check", "aigc_reduce"];

  // Basic workflow steps are always visible but gated when no license
  const basicSteps = $$(".steps > .step[data-step]");
  basicSteps.forEach(btn => {
    const step = btn.dataset.step;
    if (!step) return;
    if (step === "setup") return; // setup always accessible
    if (advancedMenus.includes(step) || vipMenus.includes(step)) return; // handled below

    if (!hasWorkflow) {
      btn.classList.add("gated");
      btn.title = "请先激活许可证或开始试用";
    } else {
      btn.classList.remove("gated");
      btn.title = "";
    }
  });

  // 增值服务 — 畅享版及以上才显示
  const servicesToggle = $("#servicesToggle");
  const servicesSub = $("#servicesSub");
  if (servicesToggle) servicesToggle.hidden = !hasAdvanced;
  if (servicesSub) servicesSub.hidden = !hasAdvanced;

  // VIP — VIP版才显示
  const vipToggle = $("#vipToggle");
  const vipSub = $("#vipSub");
  if (vipToggle) vipToggle.hidden = !hasAll;
  if (vipSub) vipSub.hidden = !hasAll;

  // Update license page
  const tierIcon = $("#licenseTierIcon");
  const tierName = $("#licenseTierName");
  const tierDesc = $("#licenseTierDesc");
  const tierMeta = $("#licenseMeta");
  const activateSection = $("#licenseActivateSection");
  const trialSection = $("#licenseTrialSection");

  if (tierIcon) {
    const icons = { active: "🎓", trial: "🎓", expired: "⏰", no_license: "🎓" };
    tierIcon.textContent = icons[lic.status] || "🎓";
  }
  if (tierName) tierName.textContent = lic.tier_label || "免费版";
  if (tierDesc) {
    const descs = {
      active: lic.days_left > 0 ? `有效期至 ${lic.expires_at || ""}，剩余 ${lic.days_left} 天` : "",
      trial: `免费试用中，剩余 ${lic.days_left} 天 · 可体验全部功能`,
      expired: "试用已到期，请激活许可证继续使用",
      no_license: "请先开始免费试用或激活许可证",
    };
    tierDesc.textContent = descs[lic.status] || "";
  }
  if (tierMeta) {
    if (lic.status === "active" && lic.user_email) {
      tierMeta.innerHTML = `授权用户：${escHtml(lic.user_email)}<br>激活日期：${lic.issued_at ? lic.issued_at.slice(0, 10) : ""}`;
    } else if (lic.status === "trial") {
      tierMeta.innerHTML = `<span class="days-warning">试用将于${lic.trial_days_left}天后到期，届时所有功能将被锁定</span>`;
    } else if (lic.status === "expired") {
      tierMeta.innerHTML = `<span class="days-critical">试用已到期，请激活许可证以恢复使用</span>`;
    } else {
      tierMeta.textContent = "";
    }
  }

  // License activation must stay available for trial/expired/active users so
  // they can upgrade or renew without needing an admin account.
  if (activateSection) {
    activateSection.hidden = false;
  }
  if (trialSection) {
    trialSection.hidden = lic.status !== "no_license";
  }

  // License management is accessible to all users for activation/trial
  const licBtn = document.querySelector('.step[data-step="license"]');
  if (licBtn) {
    licBtn.classList.remove("gated");
    licBtn.title = "管理许可证";
  }

  // Inline license section on setup page
  const inlineDot = $("#licenseInlineDot");
  const inlineLabel = $("#licenseInlineLabel");
  const inlineDays = $("#licenseInlineDays");
  const inlineActivate = $("#licenseInlineActivate");
  const inlineTrial = $("#licenseInlineTrial");

  if (inlineDot) {
    inlineDot.className = "license-inline-dot";
    if (lic.status === "active") inlineDot.classList.add("active");
    else if (lic.status === "trial") inlineDot.classList.add("trial");
    else if (lic.status === "expired") inlineDot.classList.add("expired");
  }
  if (inlineLabel) inlineLabel.textContent = lic.tier_label || "许可证";
  if (inlineDays) {
    if (lic.status === "trial") inlineDays.textContent = `试用剩余 ${lic.days_left} 天`;
    else if (lic.status === "active") inlineDays.textContent = `剩余 ${lic.days_left} 天`;
    else if (lic.status === "expired") inlineDays.textContent = "已到期";
    else inlineDays.textContent = "未激活";
  }
  if (inlineActivate) inlineActivate.hidden = false;
  if (inlineTrial) inlineTrial.hidden = lic.status !== "no_license";
}

async function saveConfig() {
  $("#saveTip").textContent = "保存中...";
  const data = await api("/api/config", {
    method: "POST",
    body: JSON.stringify({
      provider: $("#providerInput").value,
      model: $("#modelInput").value.trim(),
      base_url: $("#baseUrlInput").value.trim(),
      api_key: $("#apiKeyInput").value.trim(),
      max_tokens: parseInt($("#maxTokensInput").value) || 4000,
    }),
  });
  $("#apiKeyInput").value = "";
  $("#saveTip").textContent = data.api_key_configured ? "已保存，本地配置已更新" : "已保存，API Key 仍未配置";
  await loadConfig();
  setTimeout(() => {
    $("#saveTip").textContent = "";
  }, 2800);
}


function htmlEscape(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

async function loadMethods(force = false) {
  $("#methodCount").textContent = "正在扫描知识库，并调用大模型判断适用阶段...";
  try {
    const data = await api(force ? "/api/methodologies?refresh=1" : "/api/methodologies");
    state.methods = data.items;
    const validIds = new Set(state.methods.map((m) => m.id));
    if (!force) {
      state.methodAssignments = { discover: new Set(), solve: new Set(), validate: new Set() };
    } else {
      // Clean up stale assignments that reference deleted cards
      for (const phase of ["discover", "solve", "validate"]) {
        state.methodAssignments[phase] = new Set(
          [...state.methodAssignments[phase]].filter((id) => validIds.has(id))
        );
      }
      for (const phase of ["discover", "solve", "validate"]) {
        state.methodPools[phase] = new Set([...state.methodPools[phase]].filter((id) => validIds.has(id)));
        saveMethodPool(phase);
      }
      saveMethodAssignments();
    }
    syncPromptMethodsToOptions();
    renderMethods();
  } catch (e) {
    console.error("loadMethods failed", e);
  }
}

function renderMethods() {
  const keyword = $("#methodSearch").value.trim().toLowerCase();
  const phase = state.activeMethodPhase;
  const dirId = selectedDirection()?.id || "";
  const dirName = selectedDirection()?.name || "";

  const filtered = state.methods.filter((item) => {
    const matchesPhase = (item.phases || []).includes(phase);
    const matchesKeyword = item.name.toLowerCase().includes(keyword);
    return matchesPhase && matchesKeyword;
  });

  // 按研究方向匹配度分区：推荐区（domain 匹配）→ 跨学科创新方法区 → 通用区
  // 已在方法候选池中的方法不在下方区域重复显示
  const selectedCount = state.methodAssignments[phase].size;
  const poolIds = state.methodPools[phase];
  const poolItemsAll = state.methods.filter((m) => poolIds.has(m.id));
  const poolItems = poolItemsAll.filter((item) => (item.phases || []).includes(phase));
  const isCrossDiscipline = (item) => (item.source_type || "") === "cross_discipline";
  const notInPool = (item) => !poolIds.has(item.id);
  const recommended = filtered.filter((item) => notInPool(item) && !isCrossDiscipline(item) && (item.domains || []).includes(dirId));
  const crossDiscipline = filtered.filter((item) => notInPool(item) && isCrossDiscipline(item));
  const general = filtered.filter((item) => notInPool(item) && !isCrossDiscipline(item) && !(item.domains || []).includes(dirId));

  // 收集当前 tab 已选方法的互补/冲突关系
  const selectedIds = Array.from(state.methodAssignments[phase]);
  const pairIds = new Set();
  const conflictIds = new Set();
  const selectedRiskTags = new Set();
  const guessMethodTags = (name) => {
    const runs = name.match(/[a-zA-Z0-9]+/g) || [];
    return runs.map((r) => "method_" + r.toLowerCase());
  };
  selectedIds.forEach((sid) => {
    const sel = state.methods.find((m) => m.id === sid);
    if (!sel) return;
    (sel.pairs_with || []).forEach((p) => pairIds.add(p));
    (sel.conflicts_with || []).forEach((c) => conflictIds.add(c));
    // 将被选方法自身的推测 tag 加入 pairIds，确保双向匹配（如 PEST↔SWOT）
    guessMethodTags(sel.name).forEach((t) => pairIds.add(t));
  });
  $("#methodCount").textContent = `${filtered.length} 个方法 · 已选 ${selectedCount} · 推荐 ${recommended.length} · 跨学科 ${crossDiscipline.length}`;

  const diffLabel = { beginner: "入门", intermediate: "进阶", advanced: "高级" };

  function renderCard(item) {
    const checked = state.methodAssignments[phase].has(item.id) ? "checked" : "";
    const diff = diffLabel[item.difficulty] || "";
    const diffBadge = diff ? `<span class="method-diff method-diff-${item.difficulty}\">${diff}</span>` : "";
    const dataHints = (item.data_type || []).slice(0, 2).map((d) => {
      const map = { expert_scoring: "专家评分", judgment_matrix: "判断矩阵", survey_data: "问卷",
        process_documentation: "流程文档", interview_data: "访谈", case_documents: "案例",
        observation_data: "观察", industry_reports: "行业报告", policy_documents: "政策",
        economic_data: "经济数据", technology_reports: "技术报告", defect_records: "缺陷记录",
        brainstorming_records: "头脑风暴", internal_documents: "内部文档", audit_records: "审计",
        capability_metrics: "能力指标", competitor_data: "竞品数据", best_practice_data: "最佳实践",
        scale_data: "量表", expert_opinion: "专家意见", fault_logs: "故障日志",
        inspection_data: "检查数据", process_data: "流程数据", industry_data: "行业数据" };
      return map[d] || d;
    }).filter(Boolean);
    const dataStr = dataHints.length ? dataHints.join(" ｜ ") : "";

    let pairBadge = "";
    let conflictBadge = "";
    let extraClass = "";
    const cardPairTags = item.pairs_with || [];
    const cardConflictTags = item.conflicts_with || [];
    if (selectedIds.length && !checked) {
      const isPaired = cardPairTags.some((p) => pairIds.has(p));
      const isConflict = cardConflictTags.some((c) => conflictIds.has(c));
      if (isPaired) { pairBadge = '<span class="method-tag method-tag-pair">推荐搭配</span>'; extraClass += " method-card-paired"; }
      if (isConflict) { conflictBadge = '<span class="method-tag method-tag-conflict">⚠ 冲突</span>'; extraClass += " method-card-conflict"; }
    }

    const checkId = `chk_${item.id}_${phase}`;

    const summary = (item.summary || "").trim();
    const tooltipContent = summary || "暂无方法介绍，可在右下角论文助手中搜索了解此方法";
    return `<label class="method-card selectable${extraClass}" draggable="true" data-method-id="${item.id}">
      <input class="method-check" type="checkbox" value="${item.id}" id="${checkId}" ${checked} />
      <div class="method-card-inner">
        <div class="method-card-top">
          <span class="method-card-name">${item.name}</span>
          ${diffBadge}
          ${pairBadge}
          ${conflictBadge}
        </div>
        ${dataStr ? `<div class="method-card-detail"><span class="method-icon">📋</span>${dataStr}</div>` : ""}
        ${checked && cardPairTags.length ? `<div class="method-card-detail method-card-hint">💡 可搭配：${cardPairTags.slice(0,3).map(p => p.replace("method_","")).join("、")}</div>` : ""}
        ${summary
          ? `<div class="method-card-tooltip">${escapeHtml(summary)}</div>`
          : `<div class="method-card-tooltip empty-tip">暂无方法介绍。<br><button class="supplement-btn" data-method-name="${escapeHtml(item.name)}" data-method-id="${item.id}">🔍 补充权威材料</button></div>`}
      </div>
    </label>`;
  }

  let html = "";

  const phaseLabelMap = { discover: "发现问题", solve: "解决问题", validate: "验证问题" };
  // ── 方法候选池：用户主动选中的方法（仅显示当前阶段适用的） ──
  html += `<div class="method-zone method-zone-pool">
    <div class="method-zone-header">
      <span class="zone-icon">📋</span>
      <span>方法候选池 · ${phaseLabelMap[phase] || phase}</span>
      <span class="zone-count">${poolItems.length}</span>
      <span class="pool-hint">— 点击方法卡片加入池中，自动勾选并保存</span>
    </div>`;
  if (poolItems.length) {
    html += `<div class="method-zone-cards">${poolItems.map((item) => {
      const poolCard = renderCard(item);
      return poolCard.replace('</label>',
        '<button class="pool-remove-btn" data-pool-remove="' + item.id + '" title="从方法候选池移除">✕ 移除</button></label>');
    }).join("")}</div>`;
  } else {
    html += `<p class="hint" style="margin:8px 0;color:var(--muted);font-size:0.82rem;">当前阶段方法候选池为空 — 点击下方方法卡片即可加入，自动按阶段归类</p>`;
  }
  html += `</div>`;

  if (recommended.length) {
    html += `<div class="method-zone method-zone-recommended">
      <div class="method-zone-header">
        <span class="zone-icon">✦</span>
        <span>推荐方法 — 适合「${dirName || "当前研究方向"}」</span>
        <span class="zone-count">${recommended.length}</span>
      </div>
      <div class="method-zone-cards">${recommended.map(renderCard).join("")}</div>
    </div>`;
  }
  if (crossDiscipline.length) {
    html += `<div class="method-zone method-zone-cross">
      <div class="method-zone-header">
        <span class="zone-icon">◇</span>
        <span>非工程领域创新方法 — 跨学科可迁移研究方法</span>
        <span class="zone-count">${crossDiscipline.length}</span>
      </div>
      <div class="method-zone-cards">${crossDiscipline.map(renderCard).join("")}</div>
    </div>`;
  }
  if (general.length) {
    html += `<div class="method-zone method-zone-general">
      <div class="method-zone-header">
        <span class="zone-icon">—</span>
        <span>通用方法</span>
        <span class="zone-count">${general.length}</span>
      </div>
      <div class="method-zone-cards">${general.map(renderCard).join("")}</div>
    </div>`;
  }
  if (!filtered.length) {
    html = '<p class="hint">当前阶段没有匹配的方法。尝试切换阶段或调整搜索关键词。</p>';
  }

  $("#methodList").innerHTML = html;

  $$("#methodList .method-check").forEach((input) => {
    input.addEventListener("change", () => {
      if (input.checked) {
        state.methodAssignments[phase].add(input.value);
        state.methodPools[phase].add(input.value);
        saveMethodPool(phase);
      } else {
        state.methodAssignments[phase].delete(input.value);
      }
      renderMethods();
      saveMethodAssignments();
    });
  });

  $$("#methodList .method-card").forEach((card) => {
    card.addEventListener("dragstart", (event) => {
      event.dataTransfer.setData("text/plain", card.dataset.methodId);
      event.dataTransfer.effectAllowed = "copyMove";
    });
    // 点击方法卡片 → 加入方法候选池并自动勾选当前阶段（排除 checkbox 和按钮点击）
    card.addEventListener("click", (event) => {
      if (event.target.tagName === "INPUT" || event.target.tagName === "BUTTON" || event.target.closest("button")) return;
      const methodId = card.dataset.methodId;
      if (methodId) {
        state.methodPools[phase].add(methodId);
        state.methodAssignments[phase].add(methodId);
        saveMethodPool(phase);
        saveMethodAssignments();
        renderMethods();
      }
    });
  });

  // 方法候选池移除按钮
  $$("#methodList .pool-remove-btn").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const methodId = btn.dataset.poolRemove;
      if (methodId) {
        state.methodPools[phase].delete(methodId);
        saveMethodPool(phase);
        renderMethods();
      }
    });
  });

  $$("#methodList .supplement-btn").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      supplementMethod(btn.dataset.methodName, btn.dataset.methodId);
    });
  });
}

async function supplementMethod(methodName, methodId) {
  const btn = document.querySelector(`.supplement-btn[data-method-id="${methodId}"]`);
  if (btn) {
    btn.disabled = true;
    btn.textContent = "⏳ 正在检索权威资料...";
  }
  try {
    const data = await api("/api/method-supplement", {
      method: "POST",
      body: JSON.stringify({
        name: methodName,
        direction: (state.currentDirection || {}).name || "",
        phase: state.activeMethodPhase,
      }),
    });
    if (data.status === "ok") {
      // Replace the custom method with the supplemented card in state.methods
      const idx = state.methods.findIndex((m) => m.id === methodId);
      if (idx >= 0) {
        state.methods[idx] = {
          ...state.methods[idx],
          ...data,
          custom: false,
          supplemented: true,
        };
      }
      if (btn) {
        btn.textContent = "✅ 资料已补充";
        btn.classList.add("supplemented");
      }
      renderMethods();
    } else {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "❌ 补充失败，重试";
      }
    }
  } catch (error) {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "❌ 网络错误，重试";
    }
  }
}

async function addCustomMethod() {
  const input = $("#customMethodInput");
  const name = input.value.trim();
  if (!name) {
    input.focus();
    return;
  }
  const phase = state.activeMethodPhase;
  const direction = (state.currentDirection || {}).id || "";

  input.disabled = true;
  const btn = $("#addCustomMethod");
  const origText = btn.textContent;
  btn.disabled = true;
  btn.textContent = "正在创建方法卡...";

  try {
    const data = await api("/api/methods/create-card", {
      method: "POST",
      body: JSON.stringify({ name, phase, direction }),
    });
    if (data.status === "ok") {
      await loadMethods(true);
      state.methodAssignments[phase].add(data.id);
      state.methodPools[phase].add(data.id);
      saveMethodPool(phase);
      saveMethodAssignments();
      renderMethods();
      input.value = "";
      btn.textContent = "✓ 已添加";
      btn.classList.add("saved-flash");
      setTimeout(() => {
        btn.textContent = origText;
        btn.classList.remove("saved-flash");
      }, 1500);
    } else {
      alert("创建失败: " + (data.message || "未知错误"));
    }
  } catch (err) {
    alert("创建方法卡失败: " + (err.message || err));
  } finally {
    input.disabled = false;
    btn.disabled = false;
    btn.textContent = origText;
  }
}

async function generateFramework() {
  if (!$("#topicInput").value.trim()) {
    $("#topicInput").focus();
    return;
  }
  const direction = selectedDirection();
  const data = await api("/api/framework", {
    method: "POST",
    body: JSON.stringify({
      topic: $("#topicInput").value.trim(),
      project_context: projectContextPayload(),
      direction: direction.id,
      direction_name: direction.name,
      methods: selectedMethodNames(),
      phase_methods: phaseMethodsPayload(),
    }),
  });
  state.frameworkSvg = data.svg;
  renderSvgPreview();
  activeStep("framework");
}

function renderSvgPreview() {
  $("#svgPreview").innerHTML = state.frameworkSvg || "";
}

function downloadTextFile(filename, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}


function downloadFrameworkPng() {
  if (!state.frameworkSvg) return;
  const image = new Image();
  const svgBlob = new Blob([state.frameworkSvg], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(svgBlob);
  image.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = image.naturalWidth || 1440;
    canvas.height = image.naturalHeight || 960;
    const context = canvas.getContext("2d");
    context.fillStyle = "#edf7ff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0);
    URL.revokeObjectURL(url);
    canvas.toBlob((blob) => {
      if (!blob) return;
      const pngUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = pngUrl;
      link.download = "research_framework.png";
      link.click();
      URL.revokeObjectURL(pngUrl);
    }, "image/png");
  };
  image.src = url;
}

// ── Framework Save ──────────────────────────────────────────

async function saveFrameworkToWorkspace() {
  const dir = selectedDirection();
  if (!dir) { alert("请先选择研究方向"); return; }
  const btn = $("#saveFrameworkBtn");
  const orig = btn ? btn.textContent : "保存框架";
  if (btn) { btn.textContent = "正在保存..."; btn.disabled = true; }
  try {
    const data = await api("/api/framework/save", {
      method: "POST",
      body: JSON.stringify({
        svg: state.frameworkSvg,
        topic: $("#topicInput").value.trim(),
        direction: dir.name,
        phase_methods: phaseMethodsPayload(),
      }),
    });
    state.frameworkSaved = true;
    if (data.stale_chapters && data.stale_chapters.length > 0) {
      renderStaleChapterWarnings(data.stale_chapters);
    }
    if (btn) { btn.textContent = "✓ 已保存"; btn.classList.add("saved-flash"); }
    setTimeout(() => {
      if (btn) { btn.textContent = orig; btn.disabled = false; btn.classList.remove("saved-flash"); }
    }, 2000);
  } catch (err) {
    alert("保存失败: " + (err.message || err));
    if (btn) { btn.textContent = orig; btn.disabled = false; }
  }
}

// ── Table Generator ──

function showTableResult(markdown) {
  const container = $("#tableResultContent");
  if (!container) return;
  let html = markdown
    .replace(/### (.+)/g, '<h4>$1</h4>')
    .replace(/\|(.+)\|/g, (match) => {
      if (match.indexOf("---") >= 0) return "</thead><tbody>";
      const cells = match.split("|").filter((c, i, a) => i > 0 && i < a.length - 1 || (i === 0 && c.trim()) || (i === a.length - 1 && c.trim()));
      const tag = container.innerHTML.indexOf("<thead>") >= 0 && container.innerHTML.indexOf("</thead>") >= 0 && container.innerHTML.indexOf("<tbody>") < 0 ? "td" : "th";
      return "<tr>" + cells.map(c => `<${tag}>${c.trim()}</${tag}>`).join("") + "</tr>";
    });
  html = html.replace(/^([^<].+)$/gm, '<p>$1</p>');
  html = "<table><thead>" + html + "</tbody></table>";
  container.innerHTML = html;
  $("#tableResult").hidden = false;
}

function copyTableToClipboard() {
  const md = state._lastGeneratedTable || "";
  if (!md) return;
  navigator.clipboard.writeText(md).then(() => {
    const btn = $("#copyTableBtn");
    if (btn) { btn.textContent = "已复制"; setTimeout(() => { btn.textContent = "复制表格"; }, 2000); }
  }).catch(() => alert("复制失败"));
}

async function generateTableFromExcel() {
  const fileInput = $("#tableFileInput");
  const desc = $("#tableDescription");
  const status = $("#tableGenStatus");
  const file = fileInput?.files?.[0];

  if (!desc.value.trim()) { desc.focus(); return; }

  const formData = new FormData();
  if (file) formData.append("file", file);
  formData.append("description", desc.value.trim());

  const btn = $("#generateTableBtn");
  if (btn) { btn.disabled = true; btn.textContent = "生成中..."; }
  if (status) status.textContent = "正在调用 AI 生成表格...";

  try {
    const res = await fetch("/api/table/generate", { method: "POST", body: formData });
    const data = await res.json();
    if (data.status === "ok" && data.table) {
      state._lastGeneratedTable = data.table;
      showTableResult(data.table);
      if (status) status.textContent = "表格生成成功";
    } else {
      if (status) status.textContent = "错误: " + (data.message || "未知错误");
    }
  } catch (err) {
    if (status) status.textContent = "请求失败: " + err.message;
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "生成表格"; }
  }
}

// ── Table Modal (Writing Page) ──────────────────────────────

let _tableModalTarget = null; // {chapterIndex, sectionIndex, subsectionIndex}

function openTableModal(button) {
  const ci = parseInt(button.dataset.chapter);
  const si = parseInt(button.dataset.section);
  const ssi = button.dataset.subsection ? parseInt(button.dataset.subsection) : null;
  _tableModalTarget = { chapterIndex: ci, sectionIndex: si, subsectionIndex: ssi };

  // Find the target textarea
  const chapter = state.outline?.chapters?.[ci];
  const section = ssi != null ? chapter?.sections?.[si]?.subsections?.[ssi] : chapter?.sections?.[si];
  const dk = draftKeyFor(chapter, section);
  const existing = state.drafts[dk] || "";

  $("#tableModalText").value = existing;
  $("#tableModalDescription").value = "";
  $("#tableModalResult").hidden = true;
  $("#insertModalTableBtn").hidden = true;
  $("#tableModal").hidden = false;
}

async function generateModalTable() {
  const text = $("#tableModalText").value.trim();
  const desc = $("#tableModalDescription").value.trim();
  if (!desc) { $("#tableModalDescription").focus(); return; }

  const btn = $("#generateModalTableBtn");
  btn.disabled = true;
  btn.textContent = "生成中...";

  try {
    const data = await api("/api/table/generate-from-text", {
      method: "POST",
      body: JSON.stringify({
        text,
        description: desc,
        topic: $("#topicInput").value.trim(),
      }),
    });
    if (data.status === "ok" && data.table) {
      state._lastGeneratedTable = data.table;
      const container = $("#tableModalResultContent");
      if (container) {
        let html = data.table.replace(/### (.+)/g, "<h4>$1</h4>");
        html = html.replace(/\|(.+)\|/g, (match) => {
          if (match.indexOf("---") >= 0) return "</thead><tbody>";
          const cells = match.split("|").filter(c => c.trim());
          const tag = container.innerHTML.indexOf("<tbody>") < 0 ? "th" : "td";
          return "<tr>" + cells.map(c => `<${tag}>${c.trim()}</${tag}>`).join("") + "</tr>";
        });
        container.innerHTML = "<table><thead>" + html + "</tbody></table>";
      }
      $("#tableModalResult").hidden = false;
      $("#insertModalTableBtn").hidden = false;
    } else {
      alert("生成失败: " + (data.message || "未知错误"));
    }
  } catch (err) {
    alert("请求失败: " + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "生成表格";
  }
}

function insertModalTable() {
  if (!_tableModalTarget || !state._lastGeneratedTable) return;
  const { chapterIndex, sectionIndex, subsectionIndex } = _tableModalTarget;
  const chapter = state.outline?.chapters?.[chapterIndex];
  const section = subsectionIndex != null
    ? chapter?.sections?.[sectionIndex]?.subsections?.[subsectionIndex]
    : chapter?.sections?.[sectionIndex];
  const dk = draftKeyFor(chapter, section);
  const existing = state.drafts[dk] || "";
  state.drafts[dk] = existing ? existing + "\n\n" + state._lastGeneratedTable : state._lastGeneratedTable;
  saveDraft(dk, state.drafts[dk]);
  renderWritingList();
  $("#tableModal").hidden = true;
  _tableModalTarget = null;
}

async function generateOutline() {
  const direction = selectedDirection();
  $("#outlineStatus").textContent = "正在创建生成任务...";
  $("#outlineLog").innerHTML = "";
  $("#generateOutline").disabled = true;
  const data = await api("/api/outline", {
    method: "POST",
    body: JSON.stringify({
      topic: $("#topicInput").value.trim(),
      project_context: projectContextPayload(),
      direction: direction.id,
      direction_name: direction.name,
      methods: selectedMethodNames(),
      phase_methods: phaseMethodsPayload(),
      svg: state.frameworkSvg,
      total_words: Number($("#wordCount").value),
    }),
  });
  pollOutlineTask(data.task_id, 0);
}

async function pollOutlineTask(taskId, count) {
  const data = await api(`/api/tasks/${taskId}`);
  $("#outlineStatus").textContent = `${data.message || data.status} · ${Math.max(count, 1)} 次检查`;
  renderTaskLog(data.logs || []);

  if (data.status === "done") {
    state.outline = data.result.outline;
    state.markdown = data.result.markdown;
    $("#downloadOutline").disabled = false;
    renderOutline();
    renderWritingList();
    $("#generateOutline").disabled = false;
    $("#outlineStatus").textContent =
      data.result.generation_mode === "llm_rag"
        ? "已由大模型结合知识库生成"
        : `已生成：${data.result.generation_mode}`;
    return;
  }

  if (data.status === "error") {
    $("#generateOutline").disabled = false;
    $("#outlineStatus").textContent = `生成失败：${data.message}`;
    return;
  }

  setTimeout(() => pollOutlineTask(taskId, count + 1), 2500);
}

function renderTaskLog(logs, selector = "#outlineLog") {
  const logBox = $(selector);
  if (!logBox) return;
  if (!logs.length) {
    logBox.innerHTML = "";
    return;
  }
  logBox.innerHTML = logs
    .map((item) => `<div><time>${item.time}</time><span>${item.message}</span></div>`)
    .join("");
  logBox.scrollTop = logBox.scrollHeight;
}

async function saveOutlineState(message = "大纲和字数已保存") {
  const data = await api("/api/outline/save", {
    method: "POST",
    body: JSON.stringify({
      topic: $("#topicInput").value.trim(),
      project_context: projectContextPayload(),
      outline: state.outline,
    }),
  });
  state.markdown = data.markdown;
  if (data.stale_chapters && data.stale_chapters.length > 0) {
    renderStaleChapterWarnings(data.stale_chapters);
  }
  $("#outlineStatus").textContent = message;
}

async function generateCitations() {
  const direction = selectedDirection();
  const btn = $("#generateCitationsBtn");
  if (btn) { btn.disabled = true; btn.textContent = "生成中..."; }
  $("#citationStatus").textContent = "正在创建引用生成任务...";
  const logEl = $("#citationLog");
  if (logEl) logEl.innerHTML = "";
  try {
    const expectedCount = Math.max(10, Math.min(150, Number(($("#citationCount") && $("#citationCount").value) || 100)));
    const data = await api("/api/citations/generate", {
      method: "POST",
      body: JSON.stringify({
        topic: $("#topicInput").value.trim(),
        project_context: projectContextPayload(),
        direction: direction.id,
        direction_name: direction.name,
        methods: selectedMethodNames(),
        phase_methods: phaseMethodsPayload(),
        expected_count: expectedCount,
      }),
    });
    if (!data.task_id) {
      throw new Error("未能创建引用生成任务");
    }
    pollCitationTask(data.task_id, 0);
  } catch (error) {
    $("#citationStatus").textContent = `引用生成失败：${error.message}`;
    if (btn) { btn.disabled = false; btn.textContent = "生成引用"; }
  }
}

async function pollCitationTask(taskId, count) {
  const data = await api(`/api/tasks/${taskId}`);
  $("#citationStatus").textContent = `${data.message || data.status} · ${Math.max(count, 1)} 次检查`;
  renderTaskLog(data.logs || [], "#citationLog");

  // 更新进度条
  const progress = data.progress || 0;
  setCitationProgress(progress, 100, data.message || "正在生成引用...");

  if (data.status === "done") {
    const result = data.result || {};
    state.citations = result.citations || [];
    state.localCitations = result.local_citations || [];
    state.llmCitations = result.llm_citations || [];
    renderCitations();
    const alloc = result.allocation || {};
    $("#citationStatus").textContent = `${result.message || "引用已生成"} · 方向 ${result.direction_count || 0} 条 + 方法 ${result.local_count - (result.direction_count || 0)} 条 + LLM ${result.llm_count || 0} 条`;
    setCitationProgress(100, 100, "引用生成完成");
    setTimeout(hideCitationProgress, 4000);
    const genBtn = $("#generateCitationsBtn");
    if (genBtn) { genBtn.disabled = false; genBtn.textContent = "重新生成"; }
    return;
  }

  if (data.status === "error") {
    $("#citationStatus").textContent = `引用生成失败：${data.message || "未知错误"}`;
    hideCitationProgress();
    const failBtn = $("#generateCitationsBtn");
    if (failBtn) { failBtn.disabled = false; failBtn.textContent = "重试"; }
    return;
  }

  setTimeout(() => pollCitationTask(taskId, count + 1), 1500);
}


async function pollClassifyTask(taskId, count, btn) {
  const data = await api(`/api/tasks/${taskId}`);
  setCitationProgress(data.progress || 0, 100, data.message || "正在LLM分类...");

  if (data.status === "done") {
    const r = data.result || {};
    $("#citationStatus").textContent = `LLM分类完成：${r.updated || 0} 条已标注，${r.remaining || 0} 条无明确方法`;
    setCitationProgress(100, 100, "LLM分类完成");
    setTimeout(hideCitationProgress, 5000);
    if (btn) { btn.disabled = false; btn.textContent = "LLM分类"; }
    loadLibrary();
    return;
  }
  if (data.status === "error") {
    $("#citationStatus").textContent = `LLM分类失败：${data.message || "未知错误"}`;
    hideCitationProgress();
    if (btn) { btn.disabled = false; btn.textContent = "LLM分类"; }
    return;
  }
  setTimeout(() => pollClassifyTask(taskId, count + 1, btn), 2000);
}

function renderCitations() {
  const localItems = state.localCitations || [];
  const llmItems = state.llmCitations || [];
  const items = state.citations || [];

  if (!items.length && !localItems.length && !llmItems.length) {
    $("#citationList").innerHTML = `<div class="empty-state">尚未生成引用。确认大纲后，点击"生成引用"再进入章节写作。</div>`;
    return;
  }

  // 按 source 分组本地引用：方向 vs 方法
  const dirItems = localItems.filter(c => c.source === "local_direction");
  const methodItems = localItems.filter(c => c.source === "local_method");

  // 方法引用按方法名分组
  const methodGroups = {};
  methodItems.forEach(c => {
    const methodNames = (c.methods || []).filter(m => m !== state.currentDirection?.name);
    const key = methodNames.length ? methodNames.join(" + ") : "其他方法";
    if (!methodGroups[key]) methodGroups[key] = [];
    methodGroups[key].push(c);
  });

  const renderGroup = (title, groupItems, startIndex, colorClass, icon) => {
    if (!groupItems.length) return "";
    const text = groupItems
      .map((item, i) => `[${startIndex + i}] ${item.formatted || item.title || ""}`)
      .join("\n\n");
    return `<details class="citation-group" open>
      <summary class="citation-group-header ${colorClass}">
        <span>${icon || "📄"} ${title}</span>
        <span class="citation-group-count">${groupItems.length} 条</span>
      </summary>
      <textarea class="citation-group-text" readonly>${text}</textarea>
    </details>`;
  };

  // 方向引用
  const directionName = state.currentDirection?.name || "研究方向";
  const dirHtml = renderGroup(`${directionName}相关引用（配额 ~20%）`, dirItems, 1, "citation-local", "📚");

  // 每个方法分组
  const methodGroupEntries = Object.entries(methodGroups);
  let runningIndex = dirItems.length + 1;
  const methodGroupHtmls = methodGroupEntries.map(([methodName, refs]) => {
    const html = renderGroup(`${methodName}`, refs, runningIndex, "citation-method", "🔬");
    runningIndex += refs.length;
    return html;
  });

  // LLM 补充
  const llmHtml = renderGroup("大模型补充检索", llmItems, runningIndex, "citation-llm", "🤖");

  // 合并清单
  const mergedHtml = items.length ? renderGroup("合并引用清单（中英文平衡 · 最终输出）", items, 1, "citation-merged", "📋") : "";

  $("#citationList").innerHTML = `
    ${dirHtml || ""}
    ${methodGroupHtmls.join("") || ""}
    ${llmHtml ? `<div class="citation-llm-section">${llmHtml}</div>` : ""}
    ${mergedHtml ? `<div class="citation-merged-section">${mergedHtml}</div>` : ""}
  `;
}

async function saveCitations() {
  const data = await api("/api/citations/save", {
    method: "POST",
    body: JSON.stringify({ citations: state.citations || [] }),
  });
  state.citations = data.citations || [];
  renderCitations();
  $("#citationStatus").textContent = `已于 ${nowTime()} 保存引用`;
}

function renderOutline() {
  renumberOutline();
  rollupOutlineWords("estimated_words");
  rollupOutlineWords("actual_words");
  const chapters = state.outline?.chapters || [];
  $("#outlinePreview").innerHTML = chapters.map(renderChapter).join("");
  $$("#outlinePreview input[data-kind='chapter']").forEach((input) => {
    input.addEventListener("input", () => {
      const chapter = state.outline.chapters[Number(input.dataset.chapter)];
      chapter.title = cleanHeadingTitle(input.value);
      renderWritingList();
      scheduleOutlineAutosave();
    });
  });
  $$("#outlinePreview input[data-kind='section']").forEach((input) => {
    input.addEventListener("input", () => {
      const chapter = state.outline.chapters[Number(input.dataset.chapter)];
      const section = chapter.sections[Number(input.dataset.section)];
      section.title = cleanHeadingTitle(input.value, section.number);
      renderWritingList();
      scheduleOutlineAutosave();
    });
  });
  $$("#outlinePreview input[data-kind='subsection']").forEach((input) => {
    input.addEventListener("input", () => {
      const chapter = state.outline.chapters[Number(input.dataset.chapter)];
      const section = chapter.sections[Number(input.dataset.section)];
      const subsection = section.subsections[Number(input.dataset.subsection)];
      subsection.title = cleanHeadingTitle(input.value, subsection.number);
      renderWritingList();
      scheduleOutlineAutosave();
    });
  });
  $$("#outlinePreview input[data-kind='words']").forEach((input) => {
    input.addEventListener("blur", () => {
      const chapter = state.outline.chapters[Number(input.dataset.chapter)];
      if (input.dataset.section === undefined) {
        chapter.estimated_words = Number(input.value) || 0;
      } else {
        const section = chapter.sections[Number(input.dataset.section)];
        if (input.dataset.subsection === undefined) {
          section.estimated_words = Number(input.value) || 0;
        } else {
          const subsection = section.subsections[Number(input.dataset.subsection)];
          subsection.estimated_words = Number(input.value) || 0;
        }
      }
      const total = rollupOutlineWords("estimated_words");
      rollupOutlineWords("actual_words");
      $("#outlineStatus").textContent = `已汇总预计字数，总计 ${total} 字`;
      renderOutline();
      renderWritingList();
      saveOutlineState();
    });
  });
  $$("#outlinePreview button[data-action='subsections']").forEach((button) => {
    button.addEventListener("click", () => generateChapterSubsections(button));
  });
  $$("#outlinePreview button[data-action='add-chapter']").forEach((button) => {
    button.addEventListener("click", () => addChapter(Number(button.dataset.chapter)));
  });
  $$("#outlinePreview button[data-action='delete-chapter']").forEach((button) => {
    button.addEventListener("click", () => deleteChapter(Number(button.dataset.chapter)));
  });
  $$("#outlinePreview button[data-action='add-section']").forEach((button) => {
    button.addEventListener("click", () => addSection(Number(button.dataset.chapter), Number(button.dataset.section)));
  });
  $$("#outlinePreview button[data-action='delete-section']").forEach((button) => {
    button.addEventListener("click", () => deleteSection(Number(button.dataset.chapter), Number(button.dataset.section)));
  });
  $$("#outlinePreview button[data-action='add-subsection']").forEach((button) => {
    button.addEventListener("click", () => addSubsection(Number(button.dataset.chapter), Number(button.dataset.section), Number(button.dataset.subsection)));
  });
  $$("#outlinePreview button[data-action='delete-subsection']").forEach((button) => {
    button.addEventListener("click", () => deleteSubsection(Number(button.dataset.chapter), Number(button.dataset.section), Number(button.dataset.subsection)));
  });
}

function renderChapter(chapter, chapterIndex) {
  const sections = chapter.sections
    .map((section, sectionIndex) => {
      const subsections = (section.subsections || [])
        .map((subsection, subsectionIndex) => {
          const title = cleanHeadingTitle(subsection.title, subsection.number);
          subsection.title = title;
          return `
            <div class="subsection-line">
              <span>${subsection.number}</span>
              <input data-kind="subsection" data-chapter="${chapterIndex}" data-section="${sectionIndex}" data-subsection="${subsectionIndex}" value="${title}" />
              <input class="word-input small" data-kind="words" data-chapter="${chapterIndex}" data-section="${sectionIndex}" data-subsection="${subsectionIndex}" type="number" min="0" value="${subsection.estimated_words || 0}" />
              <span class="actual-chip">实 ${subsection.actual_words || 0}</span>
              <div class="outline-mini-tools">
                <button data-action="add-subsection" data-chapter="${chapterIndex}" data-section="${sectionIndex}" data-subsection="${subsectionIndex}">+</button>
                <button data-action="delete-subsection" data-chapter="${chapterIndex}" data-section="${sectionIndex}" data-subsection="${subsectionIndex}">-</button>
              </div>
            </div>
          `;
        })
        .join("");
      return `
        <div class="section-row outline-row">
          <div class="section-title stacked">
            <div>
              <span>${section.number}</span>
              <input data-kind="section" data-chapter="${chapterIndex}" data-section="${sectionIndex}" value="${section.title}" />
            </div>
            ${subsections}
          </div>
          <input class="word-input" data-kind="words" data-chapter="${chapterIndex}" data-section="${sectionIndex}" type="number" min="0" value="${section.estimated_words || 0}" />
          <span class="actual-chip">实际 ${section.actual_words || 0}</span>
          <div class="outline-mini-tools">
            <button data-action="add-section" data-chapter="${chapterIndex}" data-section="${sectionIndex}">+ 二级</button>
            <button data-action="add-subsection" data-chapter="${chapterIndex}" data-section="${sectionIndex}" data-subsection="-1">+ 三级</button>
            <button data-action="delete-section" data-chapter="${chapterIndex}" data-section="${sectionIndex}">-</button>
          </div>
        </div>
      `;
    })
    .join("");
  return `
    <article class="chapter-card">
      <div class="chapter-head">
        <div class="chapter-title-input">
          <span>${chapterPrefix(chapter.number)}</span>
          <input data-kind="chapter" data-chapter="${chapterIndex}" value="${cleanHeadingTitle(chapter.title)}" />
        </div>
        <div class="chapter-tools">
          <input class="word-input" data-kind="words" data-chapter="${chapterIndex}" type="number" min="0" value="${chapter.estimated_words || 0}" />
          <span class="actual-chip">实际 ${chapter.actual_words || 0}</span>
          <button data-action="subsections" data-chapter="${chapterIndex}">生成三级目录</button>
          <button data-action="add-chapter" data-chapter="${chapterIndex}">+ 一级</button>
          <button data-action="delete-chapter" data-chapter="${chapterIndex}">删除</button>
        </div>
      </div>
      ${sections}
    </article>
  `;
}

function addChapter(afterIndex) {
  state.outline.chapters.splice(afterIndex + 1, 0, {
    level: 1,
    number: afterIndex + 2,
    title: "新增章节",
    estimated_words: 3000,
    sections: [
      { level: 2, number: "", title: "新增小节", estimated_words: 1000, subsections: [] },
    ],
  });
  renumberOutline();
  renderOutline();
  renderWritingList();
  scheduleOutlineAutosave();
}

function deleteChapter(chapterIndex) {
  if ((state.outline.chapters || []).length <= 1) return;
  state.outline.chapters.splice(chapterIndex, 1);
  renumberOutline();
  renderOutline();
  renderWritingList();
  scheduleOutlineAutosave();
}

function addSection(chapterIndex, afterIndex) {
  const chapter = state.outline.chapters[chapterIndex];
  chapter.sections = chapter.sections || [];
  chapter.sections.splice(afterIndex + 1, 0, {
    level: 2,
    number: "",
    title: "",
    estimated_words: 0,
    subsections: [],
  });
  renumberOutline();
  renderOutline();
  renderWritingList();
  scheduleOutlineAutosave();
}

function deleteSection(chapterIndex, sectionIndex) {
  const chapter = state.outline.chapters[chapterIndex];
  if ((chapter.sections || []).length <= 1) return;
  chapter.sections.splice(sectionIndex, 1);
  renumberOutline();
  renderOutline();
  renderWritingList();
  scheduleOutlineAutosave();
}

function addSubsection(chapterIndex, sectionIndex, afterIndex) {
  const section = state.outline.chapters[chapterIndex].sections[sectionIndex];
  section.subsections = section.subsections || [];
  section.subsections.splice(afterIndex + 1, 0, {
    level: 3,
    number: "",
    title: "",
    estimated_words: 0,
  });
  renumberOutline();
  renderOutline();
  renderWritingList();
  scheduleOutlineAutosave();
}

function deleteSubsection(chapterIndex, sectionIndex, subsectionIndex) {
  const section = state.outline.chapters[chapterIndex].sections[sectionIndex];
  section.subsections.splice(subsectionIndex, 1);
  renumberOutline();
  renderOutline();
  renderWritingList();
  scheduleOutlineAutosave();
}

async function generateChapterSubsections(button) {
  const chapterIndex = Number(button.dataset.chapter);
  const chapter = state.outline.chapters[chapterIndex];
  button.disabled = true;
  button.textContent = "生成中";
  const data = await api("/api/subsections", {
    method: "POST",
    body: JSON.stringify({
      topic: $("#topicInput").value.trim(),
      project_context: projectContextPayload(),
      chapter,
      methods: selectedMethodNames(),
    }),
  });
  state.outline.chapters[chapterIndex] = data.chapter;
  await saveOutlineState();
  renderOutline();
  renderWritingList();
  if (data.fallback) {
    const chTitle = chapterDisplayTitle(data.chapter);
    alert(`⚠️ 第${data.chapter.number}章「${chTitle}」三级目录 LLM 生成失败，已使用本地模板兜底。\n\n建议手动编辑三级标题后重新生成该章。`);
  }
}

async function generateAllSubsectionsSerial() {
  if (!state.outline?.chapters?.length) return;
  const button = $("#generateAllSubsections");
  button.disabled = true;
  setSubsectionProgress(0, state.outline.chapters.length, `准备生成三级目录 0/${state.outline.chapters.length}`);
  for (let index = 0; index < state.outline.chapters.length; index += 1) {
    const chapter = state.outline.chapters[index];
    $("#outlineStatus").textContent = `正在串行生成三级目录 ${index + 1}/${state.outline.chapters.length}`;
    setSubsectionProgress(index, state.outline.chapters.length, `正在生成 ${chapterDisplayTitle(chapter)} · ${index + 1}/${state.outline.chapters.length}`);
    const data = await api("/api/subsections", {
      method: "POST",
      body: JSON.stringify({
        topic: $("#topicInput").value.trim(),
        project_context: projectContextPayload(),
        chapter,
        methods: selectedMethodNames(),
      }),
    });
    state.outline.chapters[index] = data.chapter;
    renumberOutline();
    rollupOutlineWords("estimated_words");
    rollupOutlineWords("actual_words");
    renderOutline();
    renderWritingList();
    await saveOutlineState(`已生成 ${index + 1}/${state.outline.chapters.length} 章三级目录`);
    if (data.fallback) {
      $("#outlineStatus").textContent = `⚠️ 第${data.chapter.number}章 LLM 生成失败，已使用模板兜底——请手动重新生成该章`;
    }
    setSubsectionProgress(index + 1, state.outline.chapters.length, `已完成 ${index + 1}/${state.outline.chapters.length}`);
  }
  button.disabled = false;
  $("#outlineStatus").textContent = "三级目录已全部串行生成";
  setSubsectionProgress(state.outline.chapters.length, state.outline.chapters.length, "三级目录已全部串行生成");
  setTimeout(hideSubsectionProgress, 4000);
}

function renderWritingList() {
  const chapters = state.outline?.chapters || [];
  const content = chapters
    .map((chapter, chapterIndex) => {
      const sections = chapter.sections
        .map((section, sectionIndex) => {
          const targets = (section.subsections && section.subsections.length)
            ? section.subsections.map((subsection, subsectionIndex) => ({ subsection, subsectionIndex }))
            : [{ subsection: null, subsectionIndex: -1 }];
          return targets.map(({ subsection, subsectionIndex }) => {
            const target = subsection || section;
            const draftKey = draftKeyFor(chapter, section, subsection);
            const draft = normalizeDraftContent(state.drafts[draftKey] || "", target);
            state.drafts[draftKey] = draft;
            const title = cleanHeadingTitle(target.title, target.number);
            return `
            <div class="writing-section">
              <div class="section-row">
                <div class="section-title">
                  <span>${target.number}</span>
                  <strong>${title}</strong>
                </div>
                <span class="word-chip">预计 ${target.estimated_words || section.estimated_words || 0}</span>
                <span class="actual-chip">实际 ${target.actual_words || section.actual_words || 0}</span>
                <div class="mini-actions">
                  <button data-action="expand" data-chapter="${chapterIndex}" data-section="${sectionIndex}" data-subsection="${subsectionIndex}">扩写</button>
                  <button data-action="rewrite" data-chapter="${chapterIndex}" data-section="${sectionIndex}" data-subsection="${subsectionIndex}">重写</button>
                  <button data-action="generate-table" data-chapter="${chapterIndex}" data-section="${sectionIndex}" data-subsection="${subsectionIndex}">生成表格</button>
                  <button data-action="save-draft" data-draft-key="${draftKey}">保存</button>
                  <span class="draft-save-state" data-draft-state="${draftKey}">${draft ? "已载入" : ""}</span>
                </div>
              </div>
              <textarea class="section-prompt" data-prompt-key="${draftKey}" placeholder="可选：填写本小节扩写/重写的补充要求，例如必须加入数据表、强调PDCA三轮迭代、避免分列式写法等。"></textarea>
              <div data-cite-dk="${draftKey}"></div>
              <textarea class="inline-draft" data-draft-key="${draftKey}" placeholder="本小节扩写内容会出现在这里，可编辑后保存。">${draft}</textarea>
            </div>
          `;
          }).join("");
        })
        .join("");
      return `
        <article class="chapter-card">
          <div class="chapter-head writing-chapter-head">
            <div>
              <strong>${chapterDisplayTitle(chapter)}</strong>
              <span class="stale-chapter-badge" data-stale-chapter="${chapter.number || chapterIndex + 1}" hidden>上游已变更</span>
              <small>一级目录 · 预计 ${chapter.estimated_words || 0} 字 · 实际 ${chapter.actual_words || 0} 字</small>
            </div>
          </div>
          ${sections}
        </article>
      `;
    })
    .join("");

  $("#writingList").innerHTML = content + renderCitationSummary();

  $$("#writingList button").forEach((button) => {
    if (button.dataset.action === "save-draft") {
      button.addEventListener("click", () => saveDraftFromButton(button));
    } else if (button.dataset.action === "generate-table") {
      button.addEventListener("click", () => openTableModal(button));
    } else {
      button.addEventListener("click", () => runWritingAction(button));
    }
  });
  $$("#writingList .inline-draft").forEach((textarea) => {
    textarea.addEventListener("input", () => scheduleDraftAutosave(textarea));
    textarea.addEventListener("blur", () => {
      const draftKey = textarea.dataset.draftKey;
      textarea.value = normalizeDraftContent(textarea.value);
      state.drafts[draftKey] = textarea.value;
      updateOutlineWordsFromDraft(draftKey, textarea.value);
      saveDraft(draftKey, textarea.value);
    });
  });
  populateAllCitationSelectors();
  bindCitationEvents();
}

async function bridgeChecklistToCitations() {
  state.citations = libState.checklist.map(c => ({
    formatted: c.formatted, title: c.title,
    authors: c.authors, year: c.year, type: c.ref_type || c.type,
  }));
  await api("/api/citations/save", {
    method: "POST",
    body: JSON.stringify({ citations: state.citations }),
  });
}

async function loadCitationsFromWorkspace() {
  try {
    const data = await api("/api/workspace");
    state.citations = (data.citations && data.citations.length)
      ? data.citations
      : (data.paper_citations || []);
  } catch (e) { /* ignore */ }
}

async function saveSectionCitations() {
  try {
    await api("/api/workspace/save-checklists", {
      method: "POST",
      body: JSON.stringify({ key: "section_citations", value: state.sectionCitations }),
    });
  } catch (e) { /* ignore */ }
}

async function loadSectionCitations() {
  try {
    const data = await api("/api/workspace");
    state.sectionCitations = data.section_citations || {};
  } catch (e) { /* ignore */ }
}

function buildCitationSelector(draftKey) {
  const allItems = state.citations || [];
  const selectedIds = state.sectionCitations[draftKey] || [];
  const box = document.createElement("div");
  box.setAttribute("data-cite-group", draftKey);
  box.style.cssText = "margin:4px 0 8px;border:1px solid #d8dde3;border-radius:4px;font-size:12px;";

  if (!allItems.length) {
    box.style.cssText += "padding:4px 8px;background:#fff3cd;font-size:11px;color:#856404;";
    box.textContent = "暂无引用文献，请先在引用页面添加引用清单";
    return box;
  }

  // Build global index map: card_id -> 1-based number
  const globalIdx = {};
  allItems.forEach((item, i) => {
    globalIdx[item.card_id] = i + 1;
    if (item.id) globalIdx[item.id] = i + 1;
  });

  // Resolve selectedIds to global items with their global indices
  const scopedItems = [];
  for (const cid of selectedIds) {
    const idx = allItems.findIndex(c => c.card_id === cid || c.id === cid);
    if (idx >= 0) {
      scopedItems.push({ item: allItems[idx], globalNum: idx + 1 });
    }
  }

  if (!scopedItems.length) {
    box.style.cssText += "padding:4px 8px;background:#fff8e1;font-size:11px;color:#946d00;";
    box.textContent = "本小节尚未分配引用，请先到引用页面为当前小节添加引用";
    return box;
  }

  const head = document.createElement("div");
  head.className = "cite-head";
  head.style.cssText = "padding:4px 10px;color:#5a7a9a;background:#f6f9fc;font-size:12px;border-bottom:1px solid #eef2f6;";
  head.textContent = `引用文献（本小节已选 ${scopedItems.length} 条，全局共 ${allItems.length} 条）`;
  box.appendChild(head);

  const grid = document.createElement("div");
  grid.style.cssText = "padding:4px 10px;max-height:200px;overflow-y:auto;";

  scopedItems.forEach(({ item, globalNum }) => {
    const row = document.createElement("div");
    row.className = "cite-row";
    row.style.cssText = "display:flex;align-items:flex-start;gap:6px;padding:2px 0;min-width:0;";

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.value = item.card_id || item.id || `_idx_${globalNum - 1}`;
    cb.checked = true;
    cb.setAttribute("data-cite-draft", draftKey);
    cb.style.cssText = "flex-shrink:0;margin-top:2px;width:13px;height:13px;";

    const text = `[${globalNum}] ${item.formatted || item.title || "(无)"}`;
    const span = document.createElement("span");
    span.style.cssText = "flex:1;min-width:0;font-size:11px;color:#333;line-height:1.6;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;";
    span.textContent = text;
    span.title = text;

    row.appendChild(cb);
    row.appendChild(span);
    grid.appendChild(row);
  });

  box.appendChild(grid);
  return box;
}

function populateAllCitationSelectors() {
  $$("[data-cite-dk]").forEach((anchor) => {
    const draftKey = anchor.getAttribute("data-cite-dk");
    if (!draftKey) return;
    anchor.replaceWith(buildCitationSelector(draftKey));
  });
}

function bindCitationEvents() {
  $$(".cite-row input[type=\"checkbox\"]").forEach((cb) => {
    if (cb.dataset.citeBound === "1") return;
    cb.dataset.citeBound = "1";
    cb.addEventListener("change", () => {
      const draftKey = cb.getAttribute("data-cite-draft");
      const ids = [];
      $$(`input[data-cite-draft="${CSS.escape(draftKey)}"]:checked`).forEach((c) => {
        ids.push(c.value);
      });
      state.sectionCitations[draftKey] = ids;
      saveSectionCitations();
      // Re-render the selector to reflect scoped view with global numbering
      const box = document.querySelector(`[data-cite-group="${CSS.escape(draftKey)}"]`);
      if (box) {
        const newBox = buildCitationSelector(draftKey);
        box.replaceWith(newBox);
        bindCitationEvents();
      }
    });
  });
}

function renderCitationSummary() {
  const items = state.citations || [];
  if (!items.length) {
    return "";
  }

  const chapterNumber = (state.outline?.chapters?.length || 0) + 1;
  const title = `第${chapterNumber}章 参考文献`;
  const listText = items
    .map((item, index) => `[${index + 1}] ${item.formatted || item.title || ""}`)
    .join("\n");

  return `
    <article class="chapter-card reference-card">
      <div class="chapter-head writing-chapter-head">
        <div>
          <strong>${title}</strong>
          <small>引用清单中的文献，正文角标序号与此对应</small>
        </div>
      </div>
      <textarea readonly>${escapeHtml(listText)}</textarea>
    </article>
  `;
}

async function runWritingAction(button) {
  const chapter = state.outline.chapters[Number(button.dataset.chapter)];
  const section = chapter.sections[Number(button.dataset.section)];
  const subsectionIndex = Number(button.dataset.subsection);
  const target = subsectionIndex >= 0 ? section.subsections[subsectionIndex] : section;
  const path = button.dataset.action === "rewrite" ? "/api/rewrite" : "/api/expand";
  button.disabled = true;
  const originalText = button.textContent;
  button.textContent = "生成中";
  const draftKey = draftKeyFor(chapter, section, subsectionIndex >= 0 ? target : null);
  const textarea = $(`textarea[data-draft-key="${CSS.escape(draftKey)}"]`);
  const sectionPrompt = $(`textarea[data-prompt-key="${CSS.escape(draftKey)}"]`)?.value.trim() || "";
  const citationIds = state.sectionCitations[draftKey] || [];
  const citationIndices = citationIds
    .map(id => {
      // Try card_id match first (new format)
      if (typeof id === "string" && !id.startsWith("_idx_")) {
        const cardIdx = state.citations.findIndex(c => c.card_id === id);
        if (cardIdx >= 0) return cardIdx;
      }
      // Fall back to legacy resolution
      const idx = state.citations.findIndex(c => c.id === id);
      if (idx >= 0) return idx;
      if (typeof id === "number") return id;
      if (typeof id === "string" && id.startsWith("_idx_")) return Number(id.slice(5));
      return -1;
    })
    .filter(i => i >= 0 && i < state.citations.length);
  textarea.value = "正在调用大模型生成，请稍候...";
  try {
    const data = await api(path, {
      method: "POST",
      body: JSON.stringify({
        topic: $("#topicInput").value.trim(),
        project_context: projectContextPayload(),
        chapter,
        section: target,
        methods: selectedMethodNames(),
        section_prompt: sectionPrompt,
        citations: state.citations,
        citation_indices: citationIndices,
      }),
    });
    textarea.value = normalizeDraftContent(data.content, target);
    state.drafts[draftKey] = textarea.value;
    updateOutlineWordsFromDraft(draftKey, textarea.value);
    const saveResult = await saveDraft(draftKey, textarea.value);
    renderConsistencyFeedback(data.consistency, data.citation_check, saveResult.stale_chapters);
  } catch (err) {
    textarea.value = `生成失败：${err.message || err}\n\n请稍后重试或检查 API 配置。`;
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

async function saveDraft(draftKey, content) {
  content = normalizeDraftContent(content);
  const data = await api("/api/drafts/save", {
    method: "POST",
    body: JSON.stringify({ draft_key: draftKey, content }),
  });
  const stateLabel = $(`[data-draft-state="${CSS.escape(draftKey)}"]`);
  if (stateLabel) stateLabel.textContent = `已于 ${nowTime()} 保存`;
  setWritingStatus(`已于 ${nowTime()} 保存`);
  if (data && data.stale_chapters && data.stale_chapters.length > 0) {
    renderStaleChapterWarnings(data.stale_chapters);
  }
  return data || {};
}

async function saveDraftFromButton(button) {
  const draftKey = button.dataset.draftKey;
  const textarea = $(`textarea[data-draft-key="${CSS.escape(draftKey)}"]`);
  textarea.value = normalizeDraftContent(textarea.value);
  state.drafts[draftKey] = textarea.value;
  await saveDraft(draftKey, textarea.value);
  button.classList.add("saved");
  button.textContent = "已保存";
  setTimeout(() => {
    button.textContent = "保存";
    button.classList.remove("saved");
  }, 1200);
}

function scheduleDraftAutosave(textarea) {
  const draftKey = textarea.dataset.draftKey;
  state.drafts[draftKey] = textarea.value;
  const stateLabel = $(`[data-draft-state="${CSS.escape(draftKey)}"]`);
  if (stateLabel) stateLabel.textContent = "编辑中，1 分钟内自动保存";
  clearTimeout(state.draftAutosaveTimers[draftKey]);
  state.draftAutosaveTimers[draftKey] = setTimeout(() => {
    saveDraft(draftKey, textarea.value);
  }, 60000);
}

async function completeAllWritingSerial() {
  if (state.writingAll || !state.outline) return;
  state.writingAll = true;
  $("#completeAllWriting").disabled = true;

  const buttons = $$("#writingList button[data-action='expand']");
  setSerialProgress(0, buttons.length, `准备串行扩写 0/${buttons.length}`);
  for (let index = 0; index < buttons.length; index += 1) {
    const button = buttons[index];
    const draftKey = draftKeyFor(
      state.outline.chapters[Number(button.dataset.chapter)],
      state.outline.chapters[Number(button.dataset.chapter)].sections[Number(button.dataset.section)],
      Number(button.dataset.subsection) >= 0
        ? state.outline.chapters[Number(button.dataset.chapter)].sections[Number(button.dataset.section)].subsections[Number(button.dataset.subsection)]
        : null
    );
    const existing = $(`textarea[data-draft-key="${CSS.escape(draftKey)}"]`)?.value.trim();
    if (existing && !existing.startsWith("正在调用大模型")) {
      setWritingStatus(`跳过已写小节 ${index + 1}/${buttons.length}`);
      setSerialProgress(index + 1, buttons.length, `跳过已写小节 ${index + 1}/${buttons.length}`);
      continue;
    }
    setWritingStatus(`正在串行扩写 ${index + 1}/${buttons.length}`);
    setSerialProgress(index, buttons.length, `正在串行扩写 ${index + 1}/${buttons.length}`);
    await runWritingAction(button);
    setSerialProgress(index + 1, buttons.length, `已完成 ${index + 1}/${buttons.length}`);
  }

  state.writingAll = false;
  $("#completeAllWriting").disabled = false;
  setWritingStatus(`一键串行完成，已于 ${nowTime()} 保存`);
  setSerialProgress(buttons.length, buttons.length, `一键串行完成，已于 ${nowTime()} 保存`);
  setTimeout(hideSerialProgress, 4000);
}

async function loadWorkspaceValue(key, defaultVal) {
  try {
    const data = await api("/api/workspace/value?key=" + encodeURIComponent(key));
    if (data && data.status === "ok" && data.value !== null && data.value !== undefined) {
      return data.value;
    }
  } catch (_) { /* fall through to default */ }
  return defaultVal !== undefined ? defaultVal : null;
}

async function loadWorkspace() {
  const data = await api("/api/workspace");
  state.drafts = data.drafts || {};
  // state.citations is now managed via sectionCitations + aggregateSubsectionCitations()
  if (data.project_context) {
    const appr = $("#projectApproachInput");
    const bg = $("#projectBgInput");
    // 解析合并存储的 project_context，拆分回两个独立输入框
    const raw = data.project_context;
    const bgMatch = raw.match(/##\s*项目背景\s*\n([\s\S]*?)(?=\n##\s*论文思路|$)/);
    const apprMatch = raw.match(/##\s*论文思路\s*\n([\s\S]*)/);
    if (bg && bgMatch) bg.value = bgMatch[1].trim();
    if (appr && apprMatch) appr.value = apprMatch[1].trim();
    // 如果没匹配到标题分隔，说明是旧格式，尝试按内容特征分配
    if (bg && !bgMatch && !apprMatch) {
      bg.value = raw;
    }
    syncPromptMethodsToOptions();
  }
  state.projects = data.projects || state.projects;
  state.currentProjectId = data.current_project_id || state.currentProjectId;
  if (data.current_direction) {
    state.currentDirection = data.current_direction;
    // 确保 name 与当前 DIRECTIONS 一致（修复历史数据中不一致的标签）
    const dirDef = (state.config.directions || []).find(
      (d) => d.id === state.currentDirection.id
    );
    if (dirDef) state.currentDirection.name = dirDef.name;
  }
  refreshDirectionDisplay();
  renderProjects();
  renderCitations();
  if (data.outline) {
    state.outline = data.outline;
    state.markdown = data.markdown || "";
    $("#downloadOutline").disabled = !state.markdown;
    renderOutline();
    renderWritingList();
    const staleChapters = data.thesis_memory?.stale_chapters || [];
    if (staleChapters.length > 0) {
      renderStaleChapterWarnings(staleChapters);
    }
    $("#outlineStatus").textContent = "已载入上次保存的大纲和草稿";
    if ($("#continueLast")) { $("#continueLast").disabled = false; $("#continueLast").textContent = "继续上次编写"; }
  }
  if (data.phase_methods) {
    for (const phase of ["discover", "solve", "validate"]) {
      const ids = data.phase_methods[phase] || [];
      state.methodAssignments[phase] = new Set(ids);
    }
  }
  if (data.method_pools) {
    for (const phase of ["discover", "solve", "validate"]) {
      const pool = data.method_pools[phase];
      if (pool && Array.isArray(pool)) {
        state.methodPools[phase] = new Set(pool);
      }
    }
  } else if (data.method_pool && Array.isArray(data.method_pool)) {
    state.methodPool = new Set(data.method_pool);
  }
  if (data.proposal_content) {
    state._proposalContent = data.proposal_content;
    const result = $("#proposalResult");
    if (result) {
      result.innerHTML = renderProposalMarkdown(data.proposal_content);
      $("#exportProposalMd").hidden = false;
      $("#exportProposalDocx").hidden = false;
    }
  }
  // Restore saved framework
  if (data.framework_svg) {
    state.frameworkSvg = data.framework_svg;
    renderSvgPreview();
    state.frameworkSaved = true;
  }
}

function downloadMarkdown() {
  downloadTextFile("thesis_outline.md", state.markdown || "", "text/markdown;charset=utf-8");
}

function getChatContext() {
  const direction = selectedDirection();
  return {
    current_step: $$(".step.active")[0]?.dataset?.step || "setup",
    topic: $("#topicInput")?.value?.trim() || "",
    direction: direction.name || "",
    methods: selectedMethodNames(),
    project_bg: $("#projectBgInput")?.value?.trim() || "",
    project_approach: $("#projectApproachInput")?.value?.trim() || "",
  };
}

async function testConnection() {
  const button = $("#testConnection");
  const status = $("#testStatus");
  if (!button || !status) return;

  button.disabled = true;
  button.textContent = "测试中...";
  status.textContent = "";
  status.className = "save-tip";

  try {
    const data = await api("/api/chat/test", { method: "POST", body: "{}" });
    if (data.status === "ok") {
      status.textContent = data.message;
      status.classList.add("progress-tip");
      button.textContent = "已连接";
      button.classList.add("connected");
      const welcome = [
        "### 连接成功！模型 deepseek-v4-pro 已就绪",
        "",
        "现在你可以点击右上角的 **「下一步」** 按钮进入论文信息配置，开始你的论文之旅。",
        "",
        "| 步骤 | 内容 |",
        "|------|------|",
        "| 论文信息 | 设定主题、研究方向和项目背景 |",
        "| 方法论选择 | 从知识库扫描可用研究方法 |",
        "| 研究框架 | 生成方法论与主题的映射框架图 |",
        "| 章节大纲 | 生成三级目录并分配字数 |",
        "| 引用生成 | 匹配本地文献生成 GB/T 7714 引用 |",
        "| 章节写作 | 逐节扩写，一键串行完成 |",
        "",
        "有任何疑问随时问我，我会全程陪伴你完成论文！"
      ].join("\n");
      openChatPanel(welcome);
    } else {
      status.textContent = data.message;
      button.disabled = false;
      button.textContent = "重新测试";
    }
  } catch (error) {
    status.textContent = `测试失败：${error.message}`;
    button.disabled = false;
    button.textContent = "重新测试";
  }
}

function openChatPanel(welcomeMessage) {
  const panel = $("#chatFloat");
  const bubble = $("#chatBubble");
  if (!panel) return;
  panel.hidden = false;
  panel.classList.remove("minimized");
  bubble.hidden = true;
  $(".shell").classList.add("has-chat");

  // 恢复默认位置
  panel.style.bottom = "24px";
  panel.style.right = "24px";
  panel.style.left = "";
  panel.style.top = "";

  if (!state.chatMessages.length) {
    state.chatMessages.push({
      role: "system-msg",
      content: welcomeMessage || "大模型已连接，你可以开始对话了。",
    });
  }
  renderChatMessages();
  setTimeout(() => {
    $("#chatInput")?.focus();
  }, 200);
}

function closeChatPanel() {
  const panel = $("#chatFloat");
  const bubble = $("#chatBubble");
  if (!panel) return;
  panel.hidden = true;
  bubble.hidden = false;
  $(".shell").classList.remove("has-chat");
}

function minimizeChat() {
  const panel = $("#chatFloat");
  const bubble = $("#chatBubble");
  if (!panel) return;
  panel.hidden = true;
  bubble.hidden = false;
}

// ---- Drag logic ----
function initChatDrag() {
  const panel = $("#chatFloat");
  const header = $("#chatFloatHeader");
  if (!panel || !header) return;

  let dragging = false;
  let startX, startY, startLeft, startTop;

  header.addEventListener("mousedown", (e) => {
    // 不拦截按钮点击
    if (e.target.tagName === "BUTTON") return;
    dragging = true;
    const rect = panel.getBoundingClientRect();
    startX = e.clientX;
    startY = e.clientY;
    startLeft = rect.left;
    startTop = rect.top;
    panel.style.transition = "none";
    e.preventDefault();
  });

  document.addEventListener("mousemove", (e) => {
    if (!dragging) return;
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;
    panel.style.left = startLeft + dx + "px";
    panel.style.top = startTop + dy + "px";
    panel.style.right = "";
    panel.style.bottom = "";
  });

  document.addEventListener("mouseup", () => {
    if (!dragging) return;
    dragging = false;
    panel.style.transition = "";
  });
}

async function savePractice(msgIndex) {
  const msg = state.chatMessages[msgIndex];
  if (!msg || msg.role !== "assistant") return;
  const content = String(msg.content || "");
  const firstLine = content.split("\n")[0].replace(/^#{1,4}\s*/, "").trim().slice(0, 80) || "未命名";
  try {
    const data = await api("/api/best-practices", {
      method: "POST",
      body: JSON.stringify({
        title: firstLine,
        content: content,
        tags: [],
        source_message: content.slice(0, 500),
      }),
    });
    if (data.status === "ok") {
      state.chatMessages[msgIndex].saved = true;
      state.chatMessages[msgIndex].practiceId = data.entry.id;
      renderChatMessages();
    }
  } catch (e) {
    // silently fail
  }
}

async function openBestPractices() {
  let panel = $("#bpPanel");
  if (!panel) {
    panel = document.createElement("aside");
    panel.id = "bpPanel";
    panel.className = "bp-panel";
    panel.innerHTML = `
      <div class="bp-panel-head">
        <h3>最佳实践经验库</h3>
        <button class="ghost icon-button" id="closeBpPanel">×</button>
      </div>
      <div class="bp-panel-list" id="bpList"></div>
    `;
    document.body.appendChild(panel);
    const overlay = document.createElement("div");
    overlay.className = "bp-overlay";
    overlay.id = "bpOverlay";
    document.body.appendChild(overlay);
    $("#closeBpPanel").addEventListener("click", closeBestPractices);
    $("#bpOverlay").addEventListener("click", closeBestPractices);
  }
  panel.classList.add("open");
  $("#bpOverlay")?.removeAttribute("hidden");
  await loadBestPractices();
}

function closeBestPractices() {
  $("#bpPanel")?.classList.remove("open");
  const overlay = $("#bpOverlay");
  if (overlay) overlay.hidden = true;
}

async function loadBestPractices() {
  const list = $("#bpList");
  if (!list) return;
  try {
    const data = await api("/api/best-practices");
    const practices = data.practices || [];
    if (!practices.length) {
      list.innerHTML = '<div class="chat-empty">暂无保存的经验。在聊天中点击助手消息旁的  按钮保存有价值的建议。</div>';
      return;
    }
    list.innerHTML = practices
      .map((p) => `
        <div class="bp-card">
          <h4>${htmlEscape(p.title)}</h4>
          <p>${htmlEscape((p.content || "").slice(0, 200))}...</p>
          <div class="bp-card-meta">
            <div class="bp-card-tags">${(p.tags || []).map((t) => `<span>${htmlEscape(t)}</span>`).join("")}<span style="background:#f0f0f0">${p.created_at || ""}</span></div>
            <button class="bp-card-delete" data-practice-id="${p.id}">删除</button>
          </div>
        </div>
      `)
      .join("");
    $$(".bp-card-delete").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await api("/api/best-practices", { method: "POST", body: JSON.stringify({ action: "delete", id: btn.dataset.practiceId }) });
        await loadBestPractices();
      });
    });
  } catch (e) {
    list.innerHTML = '<div class="chat-empty">加载失败，请重试。</div>';
  }
}

async function sendChatMessage() {
  if (state.chatLoading) return;
  const input = $("#chatInput");
  const text = input?.value?.trim();
  if (!text) return;

  input.value = "";
  state.chatMessages.push({ role: "user", content: text });
  renderChatMessages();

  state.chatLoading = true;
  const typing = document.createElement("div");
  typing.className = "chat-typing";
  typing.id = "chatTyping";
  typing.textContent = "思考中";
  $("#chatMessages")?.appendChild(typing);
  scrollChatToBottom();

  try {
    const data = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        messages: state.chatMessages.filter((msg) => msg.role !== "system-msg"),
        context: getChatContext(),
      }),
    });
    $("#chatTyping")?.remove();
    if (data.status === "ok" && data.message) {
      state.chatMessages.push(data.message);
    } else {
      state.chatMessages.push({
        role: "system-msg",
        content: data.message || "聊天请求失败，请重试。",
      });
    }
  } catch (error) {
    $("#chatTyping")?.remove();
    state.chatMessages.push({
      role: "system-msg",
      content: `请求失败：${error.message}`,
    });
  }

  state.chatLoading = false;
  renderChatMessages();
  $("#chatInput")?.focus();
}

function renderChatMessages() {
  const container = $("#chatMessages");
  if (!container) return;
  container.innerHTML = state.chatMessages
    .map((msg, index) => {
      const cls = `chat-msg ${msg.role}`;
      let content = String(msg.content || "");
      if (msg.role === "assistant" || msg.role === "system-msg") {
        content = renderMarkdown(content);
      } else {
        content = content
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/\n/g, "<br>");
      }
      const bookmark = msg.role === "assistant"
        ? `<button class="msg-bookmark${msg.saved ? ' saved' : ''}" data-msg-index="${index}" title="${msg.saved ? '已保存到经验库' : '保存到经验库'}">${msg.saved ? '' : ''}</button>`
        : "";
      return `<div class="${cls}">${content}${bookmark}</div>`;
    })
    .join("");
  scrollChatToBottom();

  $$(".msg-bookmark").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      savePractice(Number(btn.dataset.msgIndex));
    });
  });
}

function renderMarkdown(text) {
  let html = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  html = html.replace(/^### (.+)$/gm, "<h4>$1</h4>");
  html = html.replace(/^## (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  const lines = html.split("\n");
  const result = [];
  let inTable = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line.startsWith("|") && line.endsWith("|")) {
      if (!inTable) {
        result.push('<table class="chat-table">');
        inTable = true;
      }
      const cells = line.slice(1, -1).split("|").map((c) => c.trim());
      const isHeader =
        i + 1 < lines.length &&
        lines[i + 1].trim().match(/^\|[\s\-:]+\|[\s\-|]+\|$/);
      const tag = isHeader ? "th" : "td";
      result.push(
        "<tr>" +
          cells.map((c) => `<${tag}>${c}</${tag}>`).join("") +
          "</tr>"
      );
    } else {
      if (inTable && line.match(/^\|[\s\-:]+\|/)) continue;
      if (inTable) {
        result.push("</table>");
        inTable = false;
      }
      if (line === "") {
        result.push("<br>");
      } else {
        result.push(`<p>${line}</p>`);
      }
    }
  }
  if (inTable) result.push("</table>");

  return result.join("");
}

function scrollChatToBottom() {
  const container = $("#chatMessages");
  if (container) {
    requestAnimationFrame(() => {
      container.scrollTop = container.scrollHeight;
    });
  }
}

async function runRiskScan() {
  const status = $("#riskScanStatus");
  const summary = $("#riskScanSummary");
  const results = $("#riskScanResults");
  status.textContent = "正在扫描...";
  summary.hidden = true;
  results.innerHTML = "";

  try {
    // 收集所有已写作的章节内容
    const chapters = [];
    const outline = state.outline?.chapters || [];
    outline.forEach((chapter, ci) => {
      const chapterContent = [];
      (chapter.sections || []).forEach((section) => {
        (section.subsections || []).forEach((subsection) => {
          const key = draftKeyFor(chapter, section, subsection);
          const text = (state.drafts[key] || "").trim();
          if (text) chapterContent.push(text);
        });
        const secKey = draftKeyFor(chapter, section);
        const secText = (state.drafts[secKey] || "").trim();
        if (secText) chapterContent.push(secText);
      });
      if (chapterContent.length) {
        chapters.push({
          title: chapterDisplayTitle(chapter),
          number: String(ci + 1),
          content: chapterContent.join("\n\n"),
        });
      }
    });

    if (!chapters.length) {
      results.innerHTML = '<p class="hint">暂无已写作的章节内容。请先在"章节写作"面板生成至少一个小节。</p>';
      status.textContent = "无内容可扫描";
      return;
    }

    // 调用后端盲审检查接口
    const payload = { chapters };
    const data = await api("/api/blind-review-check", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    // 渲染总览
    const sevLabel = { critical: "致命", high: "高", medium: "中", low: "低" };
    const sevColor = { critical: "#9b1c1c", high: "#d03801", medium: "#b08700", low: "#2d6a4f" };
    summary.hidden = false;
    summary.innerHTML = `
      <div class="risk-summary-grid">
        <div class="risk-stat"><strong>${data.total_risks}</strong><small>检查项</small></div>
        <div class="risk-stat triggered"><strong>${data.triggered}</strong><small>触发风险</small></div>
        <div class="risk-stat critical"><strong>${data.critical_count || 0}</strong><small>致命</small></div>
        <div class="risk-stat high"><strong>${data.high_count || 0}</strong><small>高风险</small></div>
      </div>
    `;

    // 渲染各章节结果
    let html = "";
    (data.chapter_results || []).forEach((cr) => {
      const triggered = (cr.results || []).filter((r) => r.triggered);
      if (!triggered.length) return;
      html += `<div class="risk-chapter"><h3>${cr.chapter_title || cr.chapter_number}</h3>`;
      triggered.forEach((r) => {
        const c = sevColor[r.severity] || "#666";
        html += `<div class="risk-card" style="border-left:4px solid ${c}">
          <div class="risk-card-head">
            <span class="risk-sev" style="background:${c}">${sevLabel[r.severity] || r.severity}</span>
            <strong>${r.risk_name}</strong>
            <span class="risk-cat">${r.category || ""}</span>
          </div>`;
        if (r.evidence && r.evidence.length) {
          html += `<div class="risk-evidence"><small>相关片段：</small><ul>${r.evidence.map((e) => `<li>${e.substring(0, 200)}</li>`).join("")}</ul></div>`;
        }
        if (r.check_questions && r.check_questions.length) {
          html += `<details class="risk-detail"><summary>检查问题 (${r.check_questions.length})</summary><ul>${r.check_questions.map((q) => `<li>${q}</li>`).join("")}</ul></details>`;
        }
        if (r.fix_strategy && r.fix_strategy.length) {
          html += `<details class="risk-detail"><summary>修复建议 (${r.fix_strategy.length})</summary><ul>${r.fix_strategy.map((s) => `<li>${s}</li>`).join("")}</ul></details>`;
        }
        html += "</div>";
      });
      html += "</div>";
    });

    if (!html) {
      html = '<p class="hint" style="color:#2d6a4f">所有已写作章节未发现盲审风险。</p>';
    }
    results.innerHTML = html;
    status.textContent = "扫描完成";
  } catch (err) {
    status.textContent = "扫描失败";
    results.innerHTML = `<p class="hint" style="color:#9b1c1c">${err.message}</p>`;
  }
}

// Re-inject buttons after dynamic page rendering
const _origActiveStep = activeStep;
activeStep = function(id) {
  // License gate check before navigation
  if (id !== "setup" && id !== "license") {
    const lic = state.license;
    if (lic) {
      const features = lic.features || [];
      const hasAll = features.includes("all");
      const hasWorkflow = hasAll || features.includes("workflow");
      const hasAdvanced = hasAll || features.includes("advanced");
      const isTrial = lic.status === "trial";
      const advancedMenus = ["proposal", "ppt_proposal", "ppt_midterm", "ppt_defense"];
      const vipMenus = ["blind_review", "aigc_check", "aigc_reduce"];

      let blocked = false;
      let message = "";
      if (lic.status === "expired") {
        blocked = true;
        message = "试用已到期，请激活许可证";
      } else if (lic.status === "no_license") {
        blocked = true;
        message = "请先开始免费试用";
      } else if (vipMenus.includes(id) && !hasAll) {
        blocked = true;
        message = "此功能需要VIP版许可证";
      } else if (advancedMenus.includes(id) && !state.hasAdvanced) {
        blocked = true;
        message = "此功能需要畅想版及以上许可证";
      } else if (!state.hasWorkflow) {
        blocked = true;
        message = "此功能需要基础版及以上许可证";
      }

      if (blocked) {
        alert(message);
        activeStep("license");
        return;
      }
    }
  }

  _origActiveStep(id);
  // Submenu handling
  const serviceSubIds = ["proposal", "ppt_proposal", "ppt_midterm", "ppt_defense", "table_generator"];
  const vipSubIds = ["blind_review", "aigc_check", "aigc_reduce"];
  const sub = $("#servicesSub");
  const toggle = $("#servicesToggle");
  const chev = $("#servicesChevron");
  if (sub && toggle) {
    if (serviceSubIds.includes(id)) {
      sub.hidden = false;
      toggle.classList.add("active");
      if (chev) chev.textContent = "▾";
    } else if (!vipSubIds.includes(id)) {
      sub.hidden = true;
      toggle.classList.remove("active");
      if (chev) chev.textContent = "▸";
    }
  }
  // VIP submenu
  const vipSub = $("#vipSub");
  const vipToggle = $("#vipToggle");
  const vipChev = $("#vipChevron");
  if (vipSub && vipToggle) {
    if (vipSubIds.includes(id)) {
      vipSub.hidden = false;
      vipToggle.classList.add("active");
      if (vipChev) vipChev.textContent = "▾";
    } else if (!serviceSubIds.includes(id)) {
      vipSub.hidden = true;
      vipToggle.classList.remove("active");
      if (vipChev) vipChev.textContent = "▸";
    }
  }
};

function bindEvents() {
  // Sidebar collapse toggle
  if ($("#sidebarCollapseBtn")) {
    $("#sidebarCollapseBtn").addEventListener("click", () => {
      $$(".shell")[0]?.classList.toggle("sidebar-collapsed");
    });
  }

  $$("[data-next]").forEach((button) => {
    button.addEventListener("click", async () => {
      if ($$(".step.active")[0]?.dataset?.step === "paper_info") await saveProjectContext();
      activeStep(button.dataset.next);
    });
  });
  $$(".step").forEach((button) => {
    if (!button.dataset.step) return;
    button.addEventListener("click", async () => {
      if ($$(".step.active")[0]?.dataset?.step === "paper_info" && button.dataset.step !== "paper_info") {
        await saveProjectContext();
      }
      activeStep(button.dataset.step);
    });
  });
  const savePaperBtn = $("#savePaperInfo");
  if (savePaperBtn) {
    savePaperBtn.addEventListener("click", async () => {
      savePaperBtn.disabled = true;
      savePaperBtn.textContent = "保存中…";
      await saveProjectContext();
      savePaperBtn.textContent = "已保存";
      savePaperBtn.disabled = false;
      setTimeout(() => { savePaperBtn.textContent = "保存"; }, 1500);
    });
  }
  const bgInput = $("#projectBgInput");
  const approachInput = $("#projectApproachInput");
  if (bgInput) bgInput.addEventListener("blur", () => saveProjectContext());
  if (approachInput) approachInput.addEventListener("blur", () => saveProjectContext());

  $("#methodSearch").addEventListener("input", renderMethods);
  $$(".method-tab").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeMethodPhase = button.dataset.methodPhase;
      $$(".method-tab").forEach((item) => item.classList.toggle("active", item === button));
      renderMethods();
    });
    button.addEventListener("dragover", (event) => {
      event.preventDefault();
      button.classList.add("drag-over");
    });
    button.addEventListener("dragleave", () => button.classList.remove("drag-over"));
    button.addEventListener("drop", (event) => {
      event.preventDefault();
      const methodId = event.dataTransfer.getData("text/plain");
      const phase = button.dataset.methodPhase;
      button.classList.remove("drag-over");
      if (!methodId || !state.methods.some((item) => item.id === methodId)) return;
      state.methods = state.methods.map((item) =>
        item.id === methodId && !(item.phases || []).includes(phase)
          ? { ...item, phases: [...(item.phases || []), phase] }
          : item
      );
      state.methodAssignments[phase].add(methodId);
      state.activeMethodPhase = phase;
      $$(".method-tab").forEach((item) => item.classList.toggle("active", item === button));
      renderMethods();
    });
  });
  $("#saveMethodSelections").addEventListener("click", saveAllMethodSelections);
  $("#addCustomMethod").addEventListener("click", addCustomMethod);
  $("#customMethodInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") addCustomMethod();
  });
  $("#openNewProjectModal").addEventListener("click", openNewProjectModal);
  $("#closeNewProjectModal").addEventListener("click", closeNewProjectModal);
  $("#cancelNewProject").addEventListener("click", closeNewProjectModal);
  $("#confirmNewProject").addEventListener("click", createNewProject);
  $("#newProjectTopic").addEventListener("keydown", (event) => {
    if (event.key === "Enter") createNewProject();
    if (event.key === "Escape") closeNewProjectModal();
  });
  $("#projectSelect").addEventListener("change", (event) => switchProject(event.target.value));
  $("#saveConfig").addEventListener("click", saveConfig);
  $("#providerInput").addEventListener("change", onProviderChange);
  if ($("#continueLast")) $("#continueLast").addEventListener("click", () => activeStep("writing"));
  if ($("#servicesToggle")) $("#servicesToggle").addEventListener("click", () => {
    const sub = $("#servicesSub");
    const chev = $("#servicesChevron");
    if (!sub) return;
    sub.hidden = !sub.hidden;
    if (sub.hidden) {
      $("#servicesToggle").classList.remove("active");
      if (chev) chev.textContent = "▸";
    } else {
      $("#servicesToggle").classList.add("active");
      if (chev) chev.textContent = "▾";
    }
  });
  if ($("#vipToggle")) $("#vipToggle").addEventListener("click", () => {
    const sub = $("#vipSub");
    const chev = $("#vipChevron");
    if (!sub) return;
    sub.hidden = !sub.hidden;
    if (sub.hidden) {
      $("#vipToggle").classList.remove("active");
      if (chev) chev.textContent = "▸";
    } else {
      $("#vipToggle").classList.add("active");
      if (chev) chev.textContent = "▾";
    }
  });
  // License handlers
  if ($("#startTrialBtn")) $("#startTrialBtn").addEventListener("click", async () => {
    const btn = $("#startTrialBtn");
    const tip = $("#licenseTrialTip");
    btn.disabled = true;
    btn.textContent = "激活中...";
    try {
      const res = await api("/api/license/trial", { method: "POST", body: "{}" });
      state.license = res.license;
      updateLicenseUI();
      if (tip) tip.textContent = res.message || "试用已激活";
    } catch (e) {
      if (tip) tip.textContent = "激活失败: " + e.message;
    } finally {
      btn.disabled = false;
      btn.textContent = "开始免费试用";
    }
  });

  if ($("#activateLicenseBtn")) $("#activateLicenseBtn").addEventListener("click", async () => {
    const input = $("#licenseCodeInput");
    const tip = $("#licenseActivateTip");
    const code = (input?.value || "").trim();
    if (!code) {
      if (tip) tip.textContent = "请输入许可证激活码";
      return;
    }
    const btn = $("#activateLicenseBtn");
    btn.disabled = true;
    btn.textContent = "验证中...";
    try {
      const res = await api("/api/license/activate", { method: "POST", body: JSON.stringify({ code }) });
      state.license = res.license;
      updateLicenseUI();
      if (tip) tip.textContent = res.message || "激活成功";
      // Clear inputs
      if (input) input.value = "";
      const inlineInput = $("#licenseInlineCode");
      if (inlineInput) inlineInput.value = "";
    } catch (e) {
      if (tip) {
        try {
          const err = JSON.parse(e.message);
          tip.textContent = err.error || "激活失败";
        } catch (_) {
          tip.textContent = "激活失败: " + e.message;
        }
      }
    } finally {
      btn.disabled = false;
      btn.textContent = "激活";
    }
  });

  // Inline license activation on setup page
  if ($("#activateLicenseInlineBtn")) $("#activateLicenseInlineBtn").addEventListener("click", async () => {
    const input = $("#licenseInlineCode");
    const tip = $("#licenseInlineTip");
    const code = (input?.value || "").trim();
    if (!code) {
      if (tip) tip.textContent = "请输入许可证激活码";
      return;
    }
    const btn = $("#activateLicenseInlineBtn");
    btn.disabled = true;
    btn.textContent = "验证中...";
    try {
      const res = await api("/api/license/activate", { method: "POST", body: JSON.stringify({ code }) });
      state.license = res.license;
      updateLicenseUI();
      if (tip) tip.textContent = res.message || "激活成功";
      if (input) input.value = "";
    } catch (e) {
      if (tip) {
        try {
          const err = JSON.parse(e.message);
          tip.textContent = err.error || "激活失败";
        } catch (_) {
          tip.textContent = "激活失败: " + e.message;
        }
      }
    } finally {
      btn.disabled = false;
      btn.textContent = "激活";
    }
  });

  if ($("#startTrialInlineBtn")) $("#startTrialInlineBtn").addEventListener("click", async () => {
    const btn = $("#startTrialInlineBtn");
    btn.disabled = true;
    btn.textContent = "激活中...";
    try {
      const res = await api("/api/license/trial", { method: "POST", body: "{}" });
      state.license = res.license;
      updateLicenseUI();
    } catch (e) {
      const tip = $("#licenseInlineTip");
      if (tip) tip.textContent = "试用激活失败: " + e.message;
    } finally {
      btn.disabled = false;
      btn.textContent = "开始免费试用";
    }
  });

  // Gated button click — redirect to license page
  document.addEventListener("click", (e) => {
    const gatedBtn = e.target.closest(".gated");
    if (gatedBtn) {
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();
      activeStep("license");
    }
  }, true);


  $("#generateFramework").addEventListener("click", generateFramework);

  $("#downloadFrameworkPng").addEventListener("click", downloadFrameworkPng);

  $("#viewSvgBtn")?.addEventListener("click", () => {
    $("#viewSvgBtn").classList.add("active");
  });
  // Table generator
  $("#generateTableBtn")?.addEventListener("click", generateTableFromExcel);
  $("#copyTableBtn")?.addEventListener("click", copyTableToClipboard);
  $("#tableUploadBtn")?.addEventListener("click", () => $("#tableFileInput").click());
  $("#tableFileInput")?.addEventListener("change", () => {
    const name = $("#tableFileInput")?.files?.[0]?.name || "";
    if ($("#tableFileName")) $("#tableFileName").textContent = name;
  });
  // Table modal
  $("#closeTableModal")?.addEventListener("click", () => { $("#tableModal").hidden = true; });
  $("#cancelTableModal")?.addEventListener("click", () => { $("#tableModal").hidden = true; });
  $("#generateModalTableBtn")?.addEventListener("click", generateModalTable);
  $("#insertModalTableBtn")?.addEventListener("click", insertModalTable);
  // Drag-and-drop for table upload
  const tableZone = $("#tableUploadZone");
  if (tableZone) {
    tableZone.addEventListener("click", () => $("#tableFileInput").click());
    tableZone.addEventListener("dragover", (e) => { e.preventDefault(); tableZone.classList.add("drag-over"); });
    tableZone.addEventListener("dragleave", () => tableZone.classList.remove("drag-over"));
    tableZone.addEventListener("drop", (e) => {
      e.preventDefault();
      tableZone.classList.remove("drag-over");
      const files = e.dataTransfer.files;
      if (files.length) {
        $("#tableFileInput").files = files;
        if ($("#tableFileName")) $("#tableFileName").textContent = files[0].name;
      }
    });
  }
  $("#generateOutline").addEventListener("click", generateOutline);
  $("#generateAllSubsections").addEventListener("click", generateAllSubsectionsSerial);
  $("#saveOutline").addEventListener("click", () => saveOutlineState("手动保存完成"));
  $("#downloadOutline").addEventListener("click", downloadMarkdown);
  if ($("#saveCitations")) $("#saveCitations").addEventListener("click", saveCitations);
  $("#completeAllWriting").addEventListener("click", completeAllWritingSerial);
  $("#exportWord").addEventListener("click", () => {
    window.location.href = "/api/export/docx";
  });
  $("#exportPdf").addEventListener("click", () => {
    window.location.href = "/api/export/pdf";
  });
  $("#testConnection").addEventListener("click", testConnection);
  $("#runRiskScan").addEventListener("click", runRiskScan);
  $("#sendChat").addEventListener("click", sendChatMessage);
  $("#closeChat").addEventListener("click", closeChatPanel);
  $("#minimizeChat").addEventListener("click", minimizeChat);
  $("#chatBubble").addEventListener("click", () => {
    openChatPanel();
  });
  $("#viewBestPractices").addEventListener("click", openBestPractices);
  $("#chatInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendChatMessage();
    }
  });
  $("#generateProposal").addEventListener("click", generateProposal);
  $("#saveProposal").addEventListener("click", async () => {
    const content = state._proposalContent || "";
    if (!content) return;
    const btn = $("#saveProposal");
    btn.disabled = true;
    btn.textContent = "保存中…";
    await api("/api/proposal/save", { method: "POST", body: JSON.stringify({ content }) });
    btn.textContent = "已保存";
    setTimeout(() => { btn.disabled = false; btn.textContent = "保存"; }, 1500);
  });
  $("#exportProposalMd").addEventListener("click", () => exportProposal("md"));
  $("#exportProposalDocx").addEventListener("click", () => exportProposal("docx"));
  $("#generatePptProposal").addEventListener("click", () => generatePpt("proposal"));
  $("#generatePptMidterm").addEventListener("click", () => generatePpt("midterm"));
  $("#generatePptDefense").addEventListener("click", () => generatePpt("defense"));
  if ($("#runAigcCheck")) $("#runAigcCheck").addEventListener("click", runAigcCheck);
  if ($("#runAigcReduce")) $("#runAigcReduce").addEventListener("click", runAigcReduce);
}

function startGenProgress(statusEl, barId) {
  const bar = $(`#${barId}`);
  if (!bar) return;
  bar.style.width = "0%";
  let pct = 0;
  const timer = setInterval(() => {
    pct += Math.random() * 8;
    if (pct > 85) { clearInterval(timer); return; }
    bar.style.width = Math.min(85, pct) + "%";
  }, 600);
  return { finish: () => { clearInterval(timer); bar.style.width = "100%"; }, timer };
}

function injectGenProgress(containerId, barId) {
  const el = $(`#${containerId}`);
  if (!el || el.querySelector(".gen-progress")) return;
  const div = document.createElement("div");
  div.className = "gen-progress";
  div.innerHTML = `<div class="gen-bar-track"><div class="gen-bar-fill" id="${barId}"></div></div><span class="gen-status-text">等待大模型响应…</span>`;
  el.prepend(div);
}

// ============ 开题报告 ============


function collectChapterDrafts(chapter, chapterIndex) {
  const keys = [];
  (chapter.sections || []).forEach((section, si) => {
    const subs = (section.subsections && section.subsections.length) ? section.subsections : [null];
    subs.forEach((subsection, ssi) => {
      keys.push(draftKeyFor(chapter, section, subsection || section));
    });
  });
  return keys;
}

async function generateProposal() {
  const button = $("#generateProposal");
  const status = $("#proposalStatus");
  const result = $("#proposalResult");
  button.disabled = true;
  button.textContent = "排队中…";
  status.textContent = "";
  result.innerHTML = "";
  injectGenProgress("proposalResult", "genProposalBar");
  const prog = startGenProgress(null, "genProposalBar");

  try {
    const payload = {
      topic: $("#topicInput").value.trim() || state.currentProjectId,
      direction: (state.currentDirection || {}).name || "",
      methods: selectedMethodNames(),
      project_context: projectContextPayload(),
      project_approach: ($("#projectApproachInput")?.value || "").trim(),
      chapters: (state.outline?.chapters || []).slice(0, 2).map((ch, i) => {
        const draftKeys = collectChapterDrafts(ch, i);
        const content = draftKeys.map((k) => state.drafts[k] || "").join("\n\n");
        return { number: ch.number || (i + 1), title: ch.title || "", content };
      }),
    };

    const data = await api("/api/proposal", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    if (data.status !== "queued" || !data.task_id) {
      if (prog) prog.finish();
      result.innerHTML = `<div class="empty-state">启动失败：${escapeHtml(data.message || "未知错误")}</div>`;
      status.textContent = "启动失败";
      button.disabled = false;
      button.textContent = "生成开题报告";
      return;
    }

    pollProposalTask(data.task_id, button, status, result, prog);
  } catch (error) {
    if (prog) prog.finish();
    result.innerHTML = `<div class="empty-state">请求失败：${escapeHtml(error.message)}</div>`;
    status.textContent = "请求失败";
    button.disabled = false;
    button.textContent = "生成开题报告";
  }
}

async function pollProposalTask(taskId, button, status, result, prog) {
  const data = await api(`/api/tasks/${taskId}`);
  const pct = data.progress || 0;
  const msg = data.message || "";
  const bar = $("#genProposalBar");
  if (bar) bar.style.width = Math.min(95, pct) + "%";
  button.textContent = `生成中 ${pct}%…`;
  status.textContent = msg;

  if (data.status === "done") {
    if (prog) prog.finish();
    const content = (data.result || {}).content || "";
    state._proposalContent = content;
    result.innerHTML = renderProposalMarkdown(content);
    status.textContent = "生成完成（分三部分生成）";
    $("#exportProposalMd").hidden = false;
    $("#exportProposalDocx").hidden = false;
    button.disabled = false;
    button.textContent = "重新生成";
    return;
  }
  if (data.status === "error") {
    if (prog) prog.finish();
    result.innerHTML = `<div class="empty-state">生成失败：${escapeHtml(data.message || "未知错误")}</div>`;
    status.textContent = "生成失败";
    button.disabled = false;
    button.textContent = "重新生成";
    return;
  }
  setTimeout(() => pollProposalTask(taskId, button, status, result, prog), 2000);
}

function renderProposalMarkdown(md) {
  return md
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/^【(.+?)】\s*$/gm, "<h3>【$1】</h3>")
    .replace(/^## (.+)$/gm, "<h3>$1</h3>")
    .replace(/^### (.+)$/gm, "<h4>$1</h4>")
    .replace(/(?:^|\n)(\d+)\.\s+(.+?)(?=\n\d+\.|\n\n|$)/gs, (_, n, t) => `\n<li>${t.trim()}</li>`)
    .replace(/(<li>.*<\/li>\n?)+/g, "<ul>$&</ul>")
    .replace(/\n\n+/g, "</p><p>")
    .replace(/^(.+)$/gm, (line) => line.startsWith("<") ? line : `<p>${line}</p>`)
    .replace(/<p><\/p>/g, "");
}

function exportProposal(format) {
  const content = state._proposalContent || "";
  if (!content) return;
  if (format === "md") {
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "开题报告.md"; a.click();
    URL.revokeObjectURL(url);
  } else {
    fetch("/api/proposal/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    })
      .then(async (resp) => {
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          throw new Error(err.message || "导出失败");
        }
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "开题报告.docx";
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch((e) => alert("导出失败：" + e.message));
  }
}

// ============ PPT 生成 ============

async function generatePpt(pptType) {
  const ids = {
    proposal: { btn: "generatePptProposal", status: "pptProposalStatus", result: "pptProposalResult", dl: "downloadPptProposal", label: "开题PPT" },
    midterm: { btn: "generatePptMidterm", status: "pptMidtermStatus", result: "pptMidtermResult", dl: "downloadPptMidterm", label: "中期PPT" },
    defense: { btn: "generatePptDefense", status: "pptDefenseStatus", result: "pptDefenseResult", dl: "downloadPptDefense", label: "答辩PPT" },
  };
  const cfg = ids[pptType];
  const button = $(`#${cfg.btn}`);
  const status = $(`#${cfg.status}`);
  const result = $(`#${cfg.result}`);
  const dlBtn = $(`#${cfg.dl}`);

  button.disabled = true;
  button.textContent = "生成中…";
  status.textContent = "";
  dlBtn.hidden = true;
  result.innerHTML = "";
  const barId = `genPptBar${pptType}`;
  injectGenProgress(cfg.result, barId);
  const prog = startGenProgress(null, barId);

  try {
    const payload = {
      ppt_type: pptType,
      topic: $("#topicInput").value.trim(),
      direction: (state.currentDirection || {}).name || "",
      methods: selectedMethodNames(),
      project_context: projectContextPayload(),
      chapters: (state.outline?.chapters || []).map((ch, i) => {
        const draftKeys = collectChapterDrafts(ch, i);
        const content = draftKeys.map((k) => state.drafts[k] || "").join("\n\n");
        return { number: ch.number || (i + 1), title: ch.title || "", content };
      }),
    };

    if (pptType === "proposal") {
      payload.proposal_content = state._proposalContent || "";
    }

    const resp = await fetch("/api/ppt/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!resp.ok) {
      if (prog) prog.finish();
      const errData = await resp.json().catch(() => ({}));
      throw new Error(errData.message || `服务器错误 (${resp.status})`);
    }
    if (prog) prog.finish();

    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    dlBtn.onclick = () => {
      const a = document.createElement("a");
      a.href = url;
      a.download = `${cfg.label}.pptx`;
      a.click();
    };
    dlBtn.hidden = false;
    status.textContent = "生成完成，点击下载";
    result.innerHTML = `<p style="padding:20px;color:#2a7d4f;">${cfg.label}已生成，共 ${(blob.size / 1024).toFixed(0)} KB，点击下方按钮下载。</p>`;
  } catch (err) {
    if (prog) prog.finish();
    status.textContent = "生成失败";
    result.innerHTML = `<div class="empty-state">生成失败：${escapeHtml(err.message || "未知错误")}</div>`;
  } finally {
    button.disabled = false;
    button.textContent = "重新生成";
  }
}

// ============ AIGC 率评估 / AIGC 降重 ============

async function runAigcCheck() {
  const button = $("#runAigcCheck");
  const status = $("#aigcCheckStatus");
  const layout = $("#aigcCheckResult");
  const textPanel = $("#aigcTextPanel");
  const reasonPanel = $("#aigcReasonPanel");
  const empty = $("#aigcCheckEmpty");
  const barId = "aigcCheckBar";
  injectGenProgress("aigcTextPanel", barId);
  const prog = startGenProgress(null, barId);

  button.disabled = true;
  button.textContent = "检测中…";
  status.textContent = "";
  layout.hidden = true;
  if (empty) empty.hidden = true;

  try {
    const chapters = (state.outline?.chapters || []).map((ch, i) => {
      const draftKeys = collectChapterDrafts(ch, i);
      const content = draftKeys.map((k) => state.drafts[k] || "").join("\n\n");
      return { number: ch.number || (i + 1), title: ch.title || "", content };
    }).filter(ch => ch.content.trim());

    if (!chapters.length) {
      if (prog) prog.finish();
      status.textContent = "暂无已写内容";
      if (empty) { empty.hidden = false; empty.textContent = "请先在章节写作中完成至少一部分草稿后再进行AIGC检测。"; }
      return;
    }

    const resp = await fetch("/api/aigc/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chapters }),
    });
    const data = await resp.json();
    if (prog) prog.finish();

    if (data.status !== "ok") {
      status.textContent = "检测失败";
      if (empty) { empty.hidden = false; empty.textContent = data.message || "未知错误"; }
      return;
    }

    status.textContent = data.summary || `AIGC率得分: ${data.overall_score}`;

    // Build highlighted text for each chapter
    let textHtml = "";
    if (data.chapter_results) {
      data.chapter_results.forEach((ch, ci) => {
        const riskClass = (ch.risk_level || "低").toLowerCase();
        textHtml += `<div class="aigc-chapter" data-chapter="${ci}">
          <h4 class="aigc-chapter-title">
            ${escapeHtml(ch.chapter_number || "")} ${escapeHtml(ch.chapter_title || "")}
            <span class="aigc-risk-badge risk-${riskClass}">AIGC ${ch.risk_level || "低"} (${ch.score || "N/A"})</span>
          </h4>`;

        const fullText = ch.full_text || "";
        const spans = ch.spans || [];

        if (!spans.length) {
          textHtml += `<div class="aigc-chapter-text">${escapeHtml(fullText)}</div>`;
        } else {
          // Build text with <mark> highlights
          let lastEnd = 0;
          let html = "";
          spans.forEach((s, si) => {
            // Text before this span
            html += escapeHtml(fullText.slice(lastEnd, s.start));
            // Highlighted span
            const sevClass = s.severity === "high" ? "high" : s.severity === "medium" ? "medium" : "low";
            html += `<mark class="aigc-highlight aigc-${sevClass}" data-span="${ci}-${si}" title="${escapeHtml(s.label)}">`;
            html += escapeHtml(fullText.slice(s.start, s.end));
            html += `</mark>`;
            lastEnd = s.end;
          });
          // Remaining text
          html += escapeHtml(fullText.slice(lastEnd));
          textHtml += `<div class="aigc-chapter-text">${html}</div>`;
        }
        textHtml += "</div>";
      });
    }

    // Overall summary at top
    let summaryHtml = "";
    if (data.overall_score !== undefined) {
      const ovRisk = (data.risk_level || "低").toLowerCase();
      summaryHtml = `<div class="aigc-overall">
        整体AIGC率：<strong class="risk-${ovRisk}">${data.overall_score}</strong>
        — ${escapeHtml(data.interpretation || "")}
      </div>`;
    }

    textPanel.innerHTML = summaryHtml + textHtml;
    layout.hidden = false;

    // Reset reason panel
    reasonPanel.innerHTML = '<div class="aigc-reason-placeholder">点击左侧<span class="aigc-mark-dot"></span>黄色高亮区域查看疑似原因</div>';

    // Bind click handlers on highlights
    textPanel.querySelectorAll("mark.aigc-highlight").forEach((mark) => {
      mark.addEventListener("click", () => {
        // Deselect all
        textPanel.querySelectorAll("mark.aigc-highlight").forEach(m => m.classList.remove("selected"));
        // Select this one
        mark.classList.add("selected");

        const [ci, si] = (mark.dataset.span || "").split("-").map(Number);
        const ch = data.chapter_results?.[ci];
        const span = ch?.spans?.[si];
        if (span) {
          reasonPanel.innerHTML = `<div class="aigc-reason-card">
            <h5>🔍 ${escapeHtml(span.label || "疑似AI生成")}</h5>
            <p class="aigc-reason-severity">风险等级：<span class="risk-${(span.severity || 'low').toLowerCase()}">${span.severity || "low"}</span></p>
            <p class="aigc-reason-detail">${escapeHtml(span.reason || "")}</p>
            <div class="aigc-reason-snippet"><strong>原文片段：</strong><br>${escapeHtml(ch.full_text?.slice(Math.max(0, span.start - 30), Math.min(ch.full_text.length, span.end + 30)) || "")}</div>
          </div>`;
        }
      });
    });
  } catch (err) {
    if (prog) prog.finish();
    status.textContent = "检测失败";
    if (empty) { empty.hidden = false; empty.textContent = "请求失败：" + (err.message || ""); }
  } finally {
    button.disabled = false;
    button.textContent = "重新检测";
  }
}

async function runAigcReduce() {
  const button = $("#runAigcReduce");
  const status = $("#aigcReduceStatus");
  const result = $("#aigcReduceResult");
  const barId = "aigcReduceBar";
  injectGenProgress("aigcReduceResult", barId);
  const prog = startGenProgress(null, barId);

  button.disabled = true;
  button.textContent = "降重中…";
  status.textContent = "";
  result.innerHTML = "";

  try {
    const chapters = (state.outline?.chapters || []).map((ch, i) => {
      const draftKeys = collectChapterDrafts(ch, i);
      const content = draftKeys.map((k) => state.drafts[k] || "").join("\n\n");
      return { number: ch.number || (i + 1), title: ch.title || "", content };
    }).filter(ch => ch.content.trim());

    if (!chapters.length) {
      if (prog) prog.finish();
      status.textContent = "暂无已写内容";
      result.innerHTML = '<div class="empty-state">请先在章节写作中完成至少一部分草稿后再进行AIGC降重。</div>';
      return;
    }

    const resp = await fetch("/api/aigc/reduce", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chapters }),
    });
    const data = await resp.json();
    if (prog) prog.finish();

    if (data.status !== "ok") {
      status.textContent = "降重失败";
      result.innerHTML = `<div class="empty-state">${escapeHtml(data.message || "未知错误")}</div>`;
      return;
    }

    status.textContent = data.summary || "降重完成";
    let html = "";
    if (data.results) {
      data.results.forEach((r) => {
        html += `<div class="risk-section">
          <h4>${escapeHtml(r.chapter_title || "")} — ${escapeHtml(r.section_label || "")}</h4>
          <div class="rewrite-compare">
            <div class="rewrite-orig"><strong>原文：</strong><p>${escapeHtml(r.original || "")}</p></div>
            <div class="rewrite-new"><strong>改写：</strong><p>${escapeHtml(r.rewritten || "")}</p></div>
          </div>
        </div>`;
      });
    }
    result.innerHTML = html;
  } catch (err) {
    if (prog) prog.finish();
    status.textContent = "降重失败";
    result.innerHTML = `<div class="empty-state">请求失败：${escapeHtml(err.message || "")}</div>`;
  } finally {
    button.disabled = false;
    button.textContent = "重新降重";
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ============ Per-Subsection Citation Management ============

function buildCitationOutline() {
  const chapters = state.outline?.chapters || [];
  const targetChapters = chapters.slice(0, 2);

  return targetChapters.map((chapter, chapterIndex) => {
    const sectionsHtml = (chapter.sections || []).map((section) => {
      const subsections = (section.subsections || []);
      if (!subsections.length) return "";
      const subsHtml = subsections.map((subsection) => {
        const draftKey = draftKeyFor(chapter, section, subsection);
        const checklist = state.sectionCitations[draftKey] || [];
        const title = cleanHeadingTitle(subsection.title, subsection.number);
        const isActive = citationPageState.activeDraftKey === draftKey;
        return `
          <div class="cite-outline-row${isActive ? " active" : ""}" data-draft-key="${draftKey}">
            <span class="cite-outline-num">${subsection.number}</span>
            <span class="cite-outline-title" title="${escHtml(title)}">${escHtml(title)}</span>
            <span class="cite-outline-count">${checklist.length} 篇引用</span>
            <button class="ghost cite-manage-btn" data-draft-key="${draftKey}">引用管理</button>
          </div>`;
      }).join("");
      return `
        <div class="cite-outline-section">
          <div class="cite-outline-section-head">
            <strong>${section.number} ${escHtml(cleanHeadingTitle(section.title, section.number))}</strong>
          </div>
          ${subsHtml}
        </div>`;
    }).join("");

    return `
      <div class="cite-outline-chapter">
        <h3>${chapterDisplayTitle(chapter)}</h3>
        ${sectionsHtml}
      </div>`;
  }).join("");
}

function renderCitationOutline() {
  const el = $("#citationOutline");
  if (!el) return;
  el.innerHTML = buildCitationOutline();

  $$(".cite-manage-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const draftKey = btn.dataset.draftKey;
      openCitationSubsectionPanel(draftKey);
    });
  });
}

function openCitationSubsectionPanel(draftKey) {
  citationPageState.activeDraftKey = draftKey;

  // Resolve subsection display name
  let displayName = draftKey;
  const chapters = state.outline?.chapters || [];
  for (const ch of chapters) {
    for (const sec of (ch.sections || [])) {
      for (const sub of (sec.subsections || [])) {
        if (draftKeyFor(ch, sec, sub) === draftKey) {
          displayName = `${sub.number} ${cleanHeadingTitle(sub.title, sub.number)}`;
        }
      }
    }
  }

  const titleEl = $("#citationSubsectionTitle");
  if (titleEl) titleEl.textContent = `引用管理：${displayName}`;
  const panel = $("#citationSubsectionPanel");
  if (panel) panel.hidden = false;

  // Reset library offset
  libState.offset = 0;

  renderScopedChecklist(draftKey);
  loadLibrary();
  renderCitationOutline();

  // Scroll panel into view
  panel?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function closeCitationSubsectionPanel() {
  citationPageState.activeDraftKey = null;
  const panel = $("#citationSubsectionPanel");
  if (panel) panel.hidden = true;
  renderCitationOutline();
}

function renderScopedChecklist(draftKey) {
  const tbody = $("#scopedChecklistTableBody");
  const emptyEl = $("#scopedChecklistEmpty");
  const countEl = $("#scopedChecklistCount");
  if (!tbody) return;

  const cardIds = state.sectionCitations[draftKey] || [];
  if (countEl) countEl.textContent = `(已选 ${cardIds.length} 条)`;

  if (!cardIds.length) {
    tbody.innerHTML = "";
    if (emptyEl) emptyEl.hidden = false;
    return;
  }
  if (emptyEl) emptyEl.hidden = true;

  const cards = cardIds.map((cid) => {
    let card = citationPageState.cardCache[cid];
    if (!card) {
      card = libState.library.find((c) => c.card_id === cid);
    }
    return card || { card_id: cid, formatted: `[未找到: ${cid}]`, ref_type: "", year: "", verified: 0, quality_score: 0 };
  });

  tbody.innerHTML = cards.map((c) => {
    const labels = { "1": "已确认", "-2": "格式问题", "-1": "虚假", "0": "未校验" };
    const cls = { "1": "lib-status-ok", "-2": "lib-status-warn", "-1": "lib-status-fake", "0": "lib-status-pend" };
    const v = String(c.verified || 0);
    const score = (c.quality_score || 0).toFixed(1);
    return `<tr>
      <td class="lib-cell-text" title="${escHtml(c.formatted || "")}">${escHtml((c.formatted || c.title || "").substring(0, 200))}</td>
      <td>${escHtml(c.ref_type || "")}</td>
      <td>${escHtml(String(c.year || ""))}</td>
      <td><span class="${cls[v] || ""}">${labels[v] || "未校验"} ${score}</span></td>
      <td class="lib-actions-cell">
        <button class="ghost scoped-remove-btn" data-draft-key="${escHtml(draftKey)}" data-cardid="${escHtml(c.card_id)}">移除</button>
      </td>
    </tr>`;
  }).join("");

  tbody.querySelectorAll(".scoped-remove-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      removeFromSubsectionChecklist(btn.dataset.draftKey, btn.dataset.cardid);
    });
  });
}

function addToSubsectionChecklist(cardId) {
  const draftKey = citationPageState.activeDraftKey;
  if (!draftKey) return;

  const card = libState.library.find((c) => c.card_id === cardId);
  if (!card) return;

  citationPageState.cardCache[cardId] = { ...card };

  if (!state.sectionCitations[draftKey]) {
    state.sectionCitations[draftKey] = [];
  }
  if (state.sectionCitations[draftKey].includes(cardId)) return;

  state.sectionCitations[draftKey].push(cardId);
  renderScopedChecklist(draftKey);
  renderLibrary();
  renderCitationOutline();
  saveSectionCitations();
}

function removeFromSubsectionChecklist(draftKey, cardId) {
  if (!state.sectionCitations[draftKey]) return;
  state.sectionCitations[draftKey] = state.sectionCitations[draftKey].filter((id) => id !== cardId);
  renderScopedChecklist(draftKey);
  renderLibrary();
  renderCitationOutline();
  saveSectionCitations();
}

function clearSubsectionChecklist() {
  const draftKey = citationPageState.activeDraftKey;
  if (!draftKey) return;
  state.sectionCitations[draftKey] = [];
  renderScopedChecklist(draftKey);
  renderLibrary();
  renderCitationOutline();
  saveSectionCitations();
}

async function aggregateSubsectionCitations() {
  const allCardIds = new Set();
  for (const cardIds of Object.values(state.sectionCitations)) {
    if (Array.isArray(cardIds)) {
      for (const cid of cardIds) allCardIds.add(cid);
    }
  }

  if (!allCardIds.size) {
    state.citations = [];
    return;
  }

  // Check how many card_ids are unresolved
  let unresolved = 0;
  for (const cid of allCardIds) {
    if (!citationPageState.cardCache[cid] && !libState.library.find((c) => c.card_id === cid)) {
      unresolved++;
    }
  }

  // Fetch all needed card_ids in one batch request (fast path)
  if (unresolved > 0) {
    try {
      const data = await api("/api/citation-cards/batch", {
        method: "POST",
        body: JSON.stringify({ card_ids: [...allCardIds] }),
      });
      const cards = data.cards || [];
      for (const c of cards) {
        citationPageState.cardCache[c.card_id] = c;
        unresolved--;
      }
    } catch (e) { /* ignore */ }
    // Fallback: paginate if batch endpoint failed to resolve all
    if (unresolved > 0) {
      try {
        const pageSize = 200;
        let offset = 0;
        let total = pageSize;
        while (unresolved > 0 && offset < total) {
          const data = await api(`/api/citation-cards?limit=${pageSize}&offset=${offset}`);
          const cards = data.cards || [];
          if (!cards.length) break;
          total = data.total || 0;
          for (const c of cards) {
            if (allCardIds.has(c.card_id) && !citationPageState.cardCache[c.card_id]) {
              citationPageState.cardCache[c.card_id] = c;
              unresolved--;
            }
          }
          offset += pageSize;
        }
      } catch (e) { /* ignore */ }
    }
  }

  const uniqueCards = [];
  for (const cid of allCardIds) {
    let card = citationPageState.cardCache[cid];
    if (!card) {
      card = libState.library.find((c) => c.card_id === cid);
    }
    if (card) {
      uniqueCards.push({
        card_id: card.card_id,
        formatted: card.formatted,
        title: card.title,
        authors: card.authors,
        year: card.year,
        type: card.ref_type || card.type,
      });
    }
  }

  state.citations = uniqueCards;

  try {
    await api("/api/citations/save", {
      method: "POST",
      body: JSON.stringify({ citations: state.citations }),
    });
  } catch (e) { /* ignore */ }
}

// ============ Citation Library + Checklist ============
const libState = {
  library: [], total: 0, offset: 0, limit: 50,
  checklist: [],
  checklistIds: new Set(),
  customMethods: [],
  libDirection: "", libMethod: "", libKeyword: "", libVerified: "", libMinQuality: "0",
  libType: "", libYear: "",
};

function libActiveFilters() {
  return {
    direction: libState.libDirection,
    method: libState.libMethod,
    keyword: libState.libKeyword,
    verified: libState.libVerified,
    ref_type: libState.libType,
    year: libState.libYear,
    min_quality: libState.libMinQuality,
    limit: libState.limit,
  };
}

// --- Library (global citation_cards) ---

async function loadLibrary() {
  const f = libActiveFilters();
  const params = new URLSearchParams({
    direction: f.direction, method: f.method, keyword: f.keyword,
    verified: f.verified, ref_type: f.ref_type, year: f.year, min_quality: f.min_quality,
    offset: String(libState.offset), limit: String(f.limit),
  });
  try {
    const data = await api(`/api/citation-cards?${params.toString()}`);
    libState.library = data.cards || [];
    libState.total = data.total || 0;
    renderLibrary();
  } catch (e) {
    console.error("loadLibrary", e);
  }
}

function renderLibrary() {
  const tbody = $("#libraryTableBody");
  const count = libState.library.length;
  $("#libraryCount").textContent = `(共 ${libState.total} 条，当前 ${count} 条)`;

  if (!count) {
    tbody.innerHTML = `<tr><td colspan="5" class="lib-empty-cell">没有匹配的引用卡片</td></tr>`;
    return;
  }

  tbody.innerHTML = libState.library.map((c) => {
    const labels = {'1':'已确认', '-2':'格式问题', '-1':'虚假', '0':'未校验'};
    const cls = {'1':'lib-status-ok', '-2':'lib-status-warn', '-1':'lib-status-fake', '0':'lib-status-pend'};
    const v = String(c.verified || 0);
    const score = (c.quality_score || 0).toFixed(1);
    const activeDraftKey = citationPageState.activeDraftKey;
    const inChecklist = activeDraftKey
      ? (state.sectionCitations[activeDraftKey] || []).includes(c.card_id)
      : libState.checklistIds.has(c.card_id);
    return `<tr>
      <td class="lib-cell-text" title="${escHtml(c.formatted || '')}">${escHtml((c.formatted || c.title || '').substring(0, 200))}</td>
      <td>${escHtml(c.ref_type || '')}</td>
      <td>${escHtml(String(c.year || ''))}</td>
      <td><span class="${cls[v] || ''}" title="${escHtml(c.verification_note || '')}">${labels[v] || '未校验'} ${score}</span></td>
      <td class="lib-actions-cell">
        ${inChecklist
          ? `<span class="lib-added-label">已添加</span>`
          : `<button class="primary lib-add-btn" data-cardid="${escHtml(c.card_id)}">添加</button>`
        }
        <button class="ghost lib-edit-btn" data-cardid="${escHtml(c.card_id)}">编辑</button>
      </td>
    </tr>`;
  }).join("");

  tbody.querySelectorAll(".lib-add-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      if (citationPageState.activeDraftKey) {
        addToSubsectionChecklist(btn.dataset.cardid);
      } else {
        addToChecklist(btn.dataset.cardid);
      }
    });
  });
  tbody.querySelectorAll(".lib-edit-btn").forEach(btn => {
    btn.addEventListener("click", () => openLibraryEdit(btn.dataset.cardid));
  });

  // Pagination
  const totalPages = Math.ceil(libState.total / libState.limit) || 1;
  const curPage = Math.floor(libState.offset / libState.limit) + 1;
  $("#libraryPagination").innerHTML = `
    <button class="ghost" id="libPrev" ${libState.offset === 0 ? 'disabled' : ''}>上一页</button>
    <span>第 ${curPage}/${totalPages} 页 · 共 ${libState.total} 条</span>
    <button class="ghost" id="libNext" ${libState.offset + libState.limit >= libState.total ? 'disabled' : ''}>下一页</button>
  `;
  $("#libPrev").addEventListener("click", () => {
    libState.offset = Math.max(0, libState.offset - libState.limit);
    loadLibrary();
  });
  $("#libNext").addEventListener("click", () => {
    libState.offset += libState.limit;
    loadLibrary();
  });
}

// --- Checklist ---

function renderChecklist() {
  const tbody = $("#checklistTableBody");
  const count = libState.checklist.length;
  $("#checklistCount").textContent = `(已选 ${count} 条)`;

  if (!count) {
    tbody.innerHTML = "";
    $("#checklistEmpty").hidden = false;
    return;
  }
  $("#checklistEmpty").hidden = true;

  tbody.innerHTML = libState.checklist.map((c) => {
    const labels = {'1':'已确认', '-2':'格式问题', '-1':'虚假', '0':'未校验'};
    const cls = {'1':'lib-status-ok', '-2':'lib-status-warn', '-1':'lib-status-fake', '0':'lib-status-pend'};
    const v = String(c.verified || 0);
    const score = (c.quality_score || 0).toFixed(1);
    return `<tr>
      <td class="lib-cell-text" title="${escHtml(c.formatted || '')}">${escHtml((c.formatted || c.title || '').substring(0, 200))}</td>
      <td>${escHtml(c.ref_type || '')}</td>
      <td>${escHtml(String(c.year || ''))}</td>
      <td><span class="${cls[v] || ''}">${labels[v] || '未校验'} ${score}</span></td>
      <td class="lib-actions-cell">
        <button class="ghost checklist-remove-btn" data-cardid="${escHtml(c.card_id)}">移除</button>
      </td>
    </tr>`;
  }).join("");

  tbody.querySelectorAll(".checklist-remove-btn").forEach(btn => {
    btn.addEventListener("click", () => removeFromChecklist(btn.dataset.cardid));
  });
}

function addToChecklist(cardId) {
  const card = libState.library.find(c => c.card_id === cardId);
  if (!card || libState.checklistIds.has(cardId)) return;
  libState.checklist.push({ ...card });
  libState.checklistIds.add(cardId);
  renderChecklist();
  renderLibrary();
  saveChecklist();
}

function removeFromChecklist(cardId, opts = {}) {
  const { skipRender = false } = opts;
  libState.checklist = libState.checklist.filter(c => c.card_id !== cardId);
  libState.checklistIds.delete(cardId);
  if (!skipRender) {
    renderChecklist();
    renderLibrary();
    saveChecklist();
  }
}

async function saveChecklist() {
  try {
    await api("/api/workspace/save-checklists", {
      method: "POST",
      body: JSON.stringify({ key: "paper_citations", value: libState.checklist }),
    });
  } catch (e) {
    console.error("saveChecklist", e);
  }
}

async function loadChecklist() {
  try {
    const data = await api("/api/workspace");
    const saved = data.section_citations || {};

    // Load per-subsection checklists
    const hasSectionData = Object.keys(saved).length > 0;
    if (hasSectionData) {
      for (const [draftKey, cardIds] of Object.entries(saved)) {
        if (Array.isArray(cardIds) && cardIds.length) {
          state.sectionCitations[draftKey] = [...cardIds];
        }
      }
    }

    // Migrate legacy global checklist if no per-subsection data exists
    const legacy = data.paper_citations || [];
    if (!hasSectionData && legacy.length) {
      const legacyIds = legacy.map((c) => c.card_id).filter(Boolean);
      if (legacyIds.length) {
        state.sectionCitations["_legacy"] = legacyIds;
        legacy.forEach((c) => {
          if (c.card_id) citationPageState.cardCache[c.card_id] = c;
        });
      }
    }

    renderCitationOutline();
  } catch (e) {
    console.error("loadChecklist", e);
    renderCitationOutline();
  }
}

// --- Dropdown helpers ---

function populateDirectionDropdown() {
  const directions = (state.config && state.config.directions) || [];
  const sel = $("#libDirectionFilter");
  if (!sel) return;
  const current = sel.value || "";
  let html = '<option value="">全部</option>';
  directions.forEach(d => {
    html += `<option value="${escHtml(d.id)}" ${d.id === current ? 'selected' : ''}>${escHtml(d.name)}</option>`;
  });
  sel.innerHTML = html;
}

function populateMethodDropdown() {
  const selected = selectedMethodNames();
  const allNames = (state.methods || []).map(m => m.name).filter(Boolean);
  const names = [...new Set([...selected, ...allNames])];
  const sel = $("#libMethodFilter");
  if (!sel) return;
  const current = sel.value || "";
  let html = '<option value="">全部</option>';
  names.forEach(name => {
    html += `<option value="${escHtml(name)}" ${name === current ? 'selected' : ''}>${escHtml(name)}</option>`;
  });
  libState.customMethods.forEach(m => {
    html += `<option value="${escHtml(m.name)}" ${m.name === current ? 'selected' : ''}>${escHtml(m.name)} (自定义)</option>`;
  });
  sel.innerHTML = html;
}

// --- Edit modal ---

function openLibraryEdit(cardId) {
  const c = libState.library.find(x => x.card_id === cardId);
  if (!c) return;
  $("#cmEditCardId").textContent = cardId;
  $("#cmEditFormatted").value = c.formatted || '';
  $("#cmEditTitle").value = c.title || '';
  $("#cmEditAuthors").value = c.authors || '';
  $("#cmEditYear").value = c.year || '';
  $("#cmEditRefType").value = c.ref_type || '期刊文章';
  $("#cmEditSource").value = c.source_paper_title || '';
  $("#cmEditModal").hidden = false;
  $("#cmEditSave").onclick = async () => {
    const updated = {
      card_id: cardId,
      formatted: $("#cmEditFormatted").value.trim(),
      title: $("#cmEditTitle").value.trim(),
      authors: $("#cmEditAuthors").value.trim(),
      year: $("#cmEditYear").value.trim(),
      ref_type: $("#cmEditRefType").value,
    };
    await api("/api/citation-cards/update", {
      method: "POST",
      body: JSON.stringify(updated),
    });
    $("#cmEditModal").hidden = true;
    loadLibrary();
  };
}

// --- Event bindings ---

function bindLibraryEvents() {
  // Generate citations
  $("#generateCitationsBtn")?.addEventListener("click", () => generateCitations());

  // LLM classify
  $("#classifyCitationsBtn")?.addEventListener("click", async () => {
    const btn = $("#classifyCitationsBtn");
    btn.disabled = true;
    btn.textContent = "分类中...";
    try {
      const data = await api("/api/citation-cards/classify", { method: "POST", body: "{}" });
      pollClassifyTask(data.task_id, 0, btn);
    } catch (e) {
      btn.disabled = false;
      btn.textContent = "LLM分类";
      alert("分类任务创建失败：" + e.message);
    }
  });

  // Checklist: clear all (legacy, now handled per-subsection via #scopedClearChecklist)
  const checklistClearAll = $("#checklistClearAll");
  if (checklistClearAll) {
    checklistClearAll.addEventListener("click", () => {
      if (!libState.checklist.length) return;
      if (confirm("确定清空整个引用清单？已选中的引用将返回引用库。")) {
        libState.checklist = [];
        libState.checklistIds.clear();
        renderChecklist();
        renderLibrary();
        saveChecklist();
      }
    });
  }

  // Library filters — store values, don't auto-query
  $("#libDirectionFilter").addEventListener("change", () => {
    libState.libDirection = $("#libDirectionFilter").value;
  });

  $("#libMethodFilter").addEventListener("change", () => {
    libState.libMethod = $("#libMethodFilter").value;
  });

  // Custom method add
  $("#libAddCustomMethod").addEventListener("click", () => {
    const val = $("#libCustomMethodInput").value.trim();
    if (!val) return;
    const exists = libState.customMethods.some(m => m.name === val);
    if (!exists) {
      libState.customMethods.push({ id: "custom_" + Date.now(), name: val });
    }
    populateMethodDropdown();
    $("#libMethodFilter").value = val;
    libState.libMethod = val;
    $("#libCustomMethodInput").value = "";
  });

  $("#libKeywordFilter").addEventListener("input", () => {
    libState.libKeyword = $("#libKeywordFilter").value.trim();
  });

  $("#libVerifiedFilter").addEventListener("change", () => {
    libState.libVerified = $("#libVerifiedFilter").value;
  });

  $("#libTypeFilter").addEventListener("change", () => {
    libState.libType = $("#libTypeFilter").value;
  });

  $("#libYearFilter").addEventListener("input", () => {
    libState.libYear = $("#libYearFilter").value.trim();
  });

  $("#libMinQuality").addEventListener("change", () => {
    libState.libMinQuality = $("#libMinQuality").value || "0";
  });

  $("#libLimit").addEventListener("change", () => {
    libState.limit = Number($("#libLimit").value);
  });

  // Search button — applies all filters and queries
  $("#libSearch").addEventListener("click", () => {
    libState.offset = 0;
    loadLibrary();
  });

  // Edit modal controls
  $("#cmEditClose").addEventListener("click", () => { $("#cmEditModal").hidden = true; });
  $("#cmEditCancel").addEventListener("click", () => { $("#cmEditModal").hidden = true; });
  $("#cmEditDelete").addEventListener("click", async () => {
    const cardId = $("#cmEditCardId").textContent.trim();
    if (cardId && confirm("从全局引用库中删除此卡片？")) {
      await api("/api/citation-cards/delete", {
        method: "POST",
        body: JSON.stringify({ card_ids: [cardId] }),
      });
      removeFromChecklist(cardId, { skipRender: true });
      $("#cmEditModal").hidden = true;
      await loadLibrary();
    }
  });
  $("#cmEditModal").addEventListener("click", (e) => {
    if (e.target === $("#cmEditModal")) $("#cmEditModal").hidden = true;
  });

}

// Override: load library when entering citations page
const _origActiveStep2 = activeStep;
activeStep = function(id) {
  _origActiveStep2(id);
  if (id === "citations") {
    populateDirectionDropdown();
    populateMethodDropdown();
    loadChecklist().then(() => {
      renderCitationOutline();
      // Wire scoped panel events
      const closeBtn = $("#citationSubsectionClose");
      if (closeBtn) closeBtn.onclick = closeCitationSubsectionPanel;
      const clearBtn = $("#scopedClearChecklist");
      if (clearBtn) clearBtn.onclick = clearSubsectionChecklist;
    });
    loadLibrary();
  }
  if (id === "writing" && state.outline) {
    loadSectionCitations().then(() => {
      aggregateSubsectionCitations().then(() => renderWritingList());
    });
  }
};

function escHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

async function init() {
  bindEvents();
  bindLibraryEvents();
  initChatDrag();
  loadProjectContext();
  await loadProjects();
  await loadConfig();
  await loadLicense();
  await loadMethods();
  await loadWorkspace();
  window._saveFramework = saveFrameworkToWorkspace;
}

init().catch((error) => {
  document.body.innerHTML = `<pre style="padding:24px;color:#9b1c1c">${error.stack || error}</pre>`;
});
