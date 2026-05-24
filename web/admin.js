/**
 * ThesisMind Admin Module
 *
 * All admin-only functionality (10 管理员权限).
 * For public release, simply delete admin.js and admin.css.
 */
(function () {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  function init() {
    injectAdminSidebar();
    injectAdminPages();
    injectAdminButtons();
    installHooks();
    bindAdminEvents();
  }

  // ═══════════════════════════════════════════
  // Paper management state
  // ═══════════════════════════════════════════

  const paperState = { list: [], total: 0, selectedId: "", pipelineTaskId: "", pipelineTimer: null };

  // ═══════════════════════════════════════════
  // UI Injection
  // ═══════════════════════════════════════════

  function injectAdminSidebar() {
    const sidebar = document.querySelector(".sidebar");
    if (!sidebar) return;

    // Insert before license badge
    const badge = document.getElementById("licenseBadge");
    const container = document.createElement("div");
    container.innerHTML = `
      <nav class="steps" aria-label="管理">
        <button class="step admin-toggle" id="adminToggle" style="display:none"><span>10</span>管理员权限 <span class="chevron" id="adminChevron">▸</span></button>
      </nav>
      <nav class="services-sub" id="adminSub" hidden>
        <button class="step sub-item" data-step="kb_init">知识库初始化</button>
        <button class="step sub-item" data-step="paper_manager">论文管理</button>
        <button class="step sub-item" data-step="license">许可证管理</button>
      </nav>`;
    if (badge && badge.parentElement) {
      badge.parentElement.insertBefore(container, badge);
    } else if (sidebar) {
      sidebar.appendChild(container);
    }
  }

  function injectAdminPages() {
    const workspace = document.querySelector(".workspace");
    if (!workspace) return;

    const pages = document.createElement("div");
    pages.innerHTML = `
      <section class="panel page" id="kb_init">
        <div class="page-head compact">
          <div>
            <p class="eyebrow">系统管理</p>
            <h2>知识库初始化</h2>
          </div>
        </div>
        <p class="hint">扫描知识库目录，构建向量索引。首次使用或更换论文库后需要运行。</p>
        <div class="actions">
          <button class="primary" id="initKnowledgeBase" type="button">开始初始化</button>
          <span class="save-tip" id="initKbStatus"></span>
        </div>
        <div id="initKbLog" class="task-log"></div>

        <hr style="margin: 32px 0 20px; border-color: var(--line);" />
        <div class="page-head compact">
          <div>
            <p class="eyebrow">引用管理</p>
            <h2>LLM 引用生成</h2>
          </div>
        </div>
        <p class="hint">基于当前论文方向和方法论，自动检索并生成学术引用文献。</p>
        <div class="actions">
          <label class="lib-field">
            <span>期望数量</span>
            <input id="kbCitationCount" type="number" min="10" max="150" value="100" style="width:100px" />
          </label>
          <button class="primary" id="kbGenerateCitationsBtn">AI生成引用</button>
          <span class="save-tip" id="kbCitationStatus"></span>
        </div>
        <div id="kbCitationProgress" class="serial-progress" hidden>
          <div class="snail-track">
            <div class="snail" id="kbCitationSnail" aria-hidden="true">
              <span class="snail-shell"></span>
              <span class="snail-body"></span>
              <span class="snail-eye"></span>
            </div>
          </div>
          <div class="serial-progress-text" id="kbCitationProgressText">准备生成引用</div>
        </div>
        <div id="kbCitationLog" class="task-log" hidden></div>
      </section>

      <section class="panel page" id="paper_manager">
        <div class="page-head compact">
          <div>
            <p class="eyebrow">系统管理</p>
            <h2>论文管理</h2>
          </div>
          <button class="ghost" id="refreshPapers">刷新列表</button>
        </div>

        <div class="paper-upload-zone" id="paperUploadZone">
          <div class="paper-upload-inner">
            <p class="paper-upload-icon">📁</p>
            <p class="paper-upload-label">拖拽 PDF / DOCX 至此，或点击选择文件</p>
            <p class="paper-upload-hint">上传后将自动转换为 Markdown 格式</p>
            <input type="file" id="paperFileInput" accept=".pdf,.docx,.doc" hidden />
            <button class="ghost" id="paperUploadBtn">选择文件并上传</button>
          </div>
          <span class="save-tip" id="paperUploadTip"></span>
        </div>

        <div class="paper-list-section">
          <div class="paper-list-head">
            <h3>论文列表 <span id="paperCount"></span></h3>
            <div class="paper-list-filters">
              <select id="paperDirectionFilter">
                <option value="">全部方向</option>
              </select>
              <input id="paperKeywordFilter" placeholder="搜索标题/摘要…" />
              <button class="ghost" id="paperSearchBtn">搜索</button>
            </div>
          </div>
          <div class="library-table-wrap">
            <table class="library-table">
              <thead>
                <tr>
                  <th>标题</th>
                  <th class="lib-col-type">年份</th>
                  <th class="lib-col-type">方向</th>
                  <th class="lib-col-type">引用数</th>
                  <th class="lib-col-type">质量分</th>
                  <th class="lib-col-actions">操作</th>
                </tr>
              </thead>
              <tbody id="paperTableBody"></tbody>
            </table>
          </div>
          <div class="library-empty" id="paperListEmpty">暂无论文，请上传 PDF 或 DOCX 文件。</div>
        </div>

        <div id="paperPipelineSection" class="paper-pipeline" hidden>
          <div class="paper-pipeline-head">
            <h4>运行流水线: <span id="paperPipelineTitle"></span></h4>
            <button class="primary" id="runPaperPipeline">运行完整流水线</button>
          </div>
          <div id="paperPipelineLog" class="task-log"></div>
        </div>

        <div id="paperDetailRow" class="paper-detail-row" hidden></div>
      </section>`;

    // Append pages after the last existing page section
    const lastPage = workspace.querySelector(".panel.page:last-of-type");
    if (lastPage) {
      lastPage.after(...pages.children);
    } else {
      workspace.appendChild(pages);
    }

    // Inject license admin sections into license page
    const licensePage = document.getElementById("license");
    if (licensePage) {
      const adminSections = document.createElement("div");
      adminSections.innerHTML = `
        <div class="license-admin-section" id="licenseGenerateSection" hidden>
          <h3>生成许可证</h3>
          <p class="hint">管理员可生成各等级许可证激活码</p>
          <div class="license-generate-form">
            <label class="field">
              <span>许可证等级</span>
              <select id="licenseGenTier">
                <option value="basic">基础版 (1年)</option>
                <option value="pro">畅想版 (2年)</option>
                <option value="vip">VIP版 (2年)</option>
                <option value="admin">管理员版 (10年)</option>
              </select>
            </label>
            <label class="field">
              <span>用户邮箱 (可选)</span>
              <input id="licenseGenEmail" placeholder="user@example.com" />
            </label>
            <button class="primary" id="licenseGenBtn">生成许可证</button>
          </div>
          <div class="generated-code" id="generatedCodeBox" hidden>
            <div class="generated-code-label">激活码</div>
            <code id="generatedCodeText"></code>
            <button class="ghost" id="copyGeneratedCode">复制激活码</button>
            <span class="save-tip" id="genCodeTip"></span>
          </div>
        </div>

        <div class="license-admin-section" id="licenseHistorySection" hidden>
          <h3>许可证历史</h3>
          <div class="library-table-wrap">
            <table class="library-table">
              <thead>
                <tr>
                  <th>操作</th>
                  <th>类型</th>
                  <th>用户邮箱</th>
                  <th>激活码</th>
                  <th>生成/激活时间</th>
                  <th>有效期至</th>
                </tr>
              </thead>
              <tbody id="licenseHistoryBody"></tbody>
            </table>
          </div>
          <div class="library-empty" id="licenseHistoryEmpty" style="display:none">暂无许可证生成/激活记录</div>
        </div>`;
      licensePage.appendChild(adminSections);
    }
  }

  function injectAdminButtons() {
    // Add admin-only buttons to citations page
    const headActions = document.querySelector("#citations .head-actions");
    if (headActions) {
      const scoreBtn = document.createElement("button");
      scoreBtn.className = "ghost";
      scoreBtn.id = "scoreAllCitationsBtn";
      scoreBtn.textContent = "全库评分";

      const lastBtn = headActions.querySelector("button:last-of-type");
      if (lastBtn) {
        lastBtn.after(scoreBtn);
      } else {
        headActions.appendChild(scoreBtn);
      }

      // Bind score-all event (admin only)
      scoreBtn.addEventListener("click", async () => {
        if (!confirm("确定要重新评估全库引用质量？此操作不可撤销。")) return;
        scoreBtn.disabled = true;
        scoreBtn.textContent = "评分中...";
        try {
          const data = await api("/api/citation-cards/score-batch", {
            method: "POST",
            body: JSON.stringify({ verify_external: false }),
          });
          alert(`评分完成：共 ${data.total || "?"} 条引用已更新`);
          if (typeof loadLibrary === "function") loadLibrary();
        } catch (e) {
          alert("评分失败：" + e.message);
        }
        scoreBtn.disabled = false;
        scoreBtn.textContent = "全库评分";
      });
    }
  }

  // ═══════════════════════════════════════════
  // Hook installation
  // ═══════════════════════════════════════════

  function installHooks() {
    // Hook updateLicenseUI for admin gating
    if (typeof updateLicenseUI === "function") {
      const _orig = updateLicenseUI;
      updateLicenseUI = function () {
        _orig();
        const lic = state.license || {};
        const features = lic.features || [];
        const hasAdmin = features.includes("admin");
        const hasAll = features.includes("all");
        const hasAdvanced = hasAll || features.includes("advanced");

        state.hasAdmin = hasAdmin;

        // Gate kb_init sidebar button
        const kbBtn = document.querySelector('.step[data-step="kb_init"]');
        if (kbBtn) {
          if (!hasAdmin) {
            kbBtn.classList.add("gated");
            kbBtn.title = "需要管理员许可证";
          } else {
            kbBtn.classList.remove("gated");
            kbBtn.title = "";
          }
        }

        // Gate paper_manager
        const paperBtn = document.querySelector('.step[data-step="paper_manager"]');
        if (paperBtn) {
          if (!hasAdvanced) {
            paperBtn.classList.add("gated");
            paperBtn.title = "需要畅想版及以上许可证";
          } else {
            paperBtn.classList.remove("gated");
            paperBtn.title = "";
          }
        }

        toggleAdminSections(hasAdmin, lic.status);
      };
    }

    // Hook activeStep for admin gate checks and submenu
    if (typeof activeStep === "function") {
      const _orig = activeStep;
      activeStep = function (id) {
        // Admin gate check before navigation
        if (id === "kb_init") {
          const lic = state.license;
          if (lic && !(lic.features || []).includes("admin")) {
            // Redirect to license page
            if (typeof activeStepRedirect === "undefined") {
              _orig("license");
              return;
            }
          }
        }

        // Paper manager trigger
        if (id === "paper_manager") {
          populatePaperDirectionDropdown();
          loadPapers();
        }

        _orig(id);

        // Admin submenu toggle
        const adminSubIds = ["kb_init", "paper_manager", "license"];
        const adminSub = document.getElementById("adminSub");
        const adminToggle = document.getElementById("adminToggle");
        const adminChev = document.getElementById("adminChevron");
        if (adminSub && adminToggle) {
          if (adminSubIds.includes(id)) {
            adminSub.hidden = false;
            adminToggle.classList.add("active");
            if (adminChev) adminChev.textContent = "▾";
          } else {
            adminSub.hidden = true;
            adminToggle.classList.remove("active");
            if (adminChev) adminChev.textContent = "▸";
          }
        }
      };
    }

    // Hook license page navigation to load history
    const licenseBtn = document.querySelector('.step[data-step="license"]');
    if (licenseBtn) {
      licenseBtn.addEventListener("click", () => {
        setTimeout(loadLicenseHistory, 100);
      });
    }
  }

  // ═══════════════════════════════════════════
  // Admin sections toggle
  // ═══════════════════════════════════════════

  function toggleAdminSections(hasAdmin, _licStatus) {
    const genSection = document.getElementById("licenseGenerateSection");
    const histSection = document.getElementById("licenseHistorySection");
    if (genSection) genSection.hidden = !hasAdmin;
    if (histSection) histSection.hidden = !hasAdmin;
    // Hide admin sidebar toggle for non-admin users
    const adminToggle = document.getElementById("adminToggle");
    const adminSub = document.getElementById("adminSub");
    if (adminToggle) adminToggle.style.display = hasAdmin ? "" : "none";
    if (adminSub && !hasAdmin) adminSub.hidden = true;
  }

  // ═══════════════════════════════════════════
  // Paper Management
  // ═══════════════════════════════════════════

  function populatePaperDirectionDropdown() {
    const sel = document.getElementById("paperDirectionFilter");
    if (!sel || sel.options.length > 1) return;
    sel.innerHTML = '<option value="">全部方向</option>';
    const dirs = [
      { id: "quality_management", label: "质量管理" },
      { id: "risk_management", label: "风险管理" },
      { id: "schedule_management", label: "进度管理" },
      { id: "requirements_management", label: "需求管理" },
      { id: "process_optimization", label: "流程优化" },
      { id: "cost_management", label: "成本管理" },
      { id: "supply_chain_logistics", label: "供应链与物流" },
    ];
    dirs.forEach(d => {
      const opt = document.createElement("option");
      opt.value = d.id;
      opt.textContent = d.label;
      sel.appendChild(opt);
    });
  }

  async function loadPapers() {
    const dir = document.getElementById("paperDirectionFilter")?.value || "";
    const kw = document.getElementById("paperKeywordFilter")?.value?.trim() || "";
    const params = new URLSearchParams();
    if (dir) params.set("direction", dir);
    if (kw) params.set("keyword", kw);
    params.set("limit", "100");
    params.set("offset", "0");
    try {
      const data = await api("/api/papers/list?" + params.toString());
      paperState.list = data.papers || [];
      paperState.total = data.total || 0;
      renderPaperList();
    } catch (_) {
      paperState.list = [];
      paperState.total = 0;
      renderPaperList();
    }
    try {
      const stats = await api("/api/papers/stats");
      const count = document.getElementById("paperCount");
      if (count) count.textContent = `(${stats.papers || 0} 篇论文 · ${stats.cards || 0} 引用卡片)`;
    } catch (_) {}
  }

  function renderPaperList() {
    const tbody = document.getElementById("paperTableBody");
    const empty = document.getElementById("paperListEmpty");
    if (!tbody) return;
    if (!paperState.list.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="lib-empty-cell">暂无论文，请上传 PDF 或 DOCX 文件。</td></tr>';
      if (empty) empty.style.display = "block";
      return;
    }
    if (empty) empty.style.display = "none";
    tbody.innerHTML = paperState.list.map(p => {
      const methods = (p.methods || []).slice(0, 3).map(m => `<span style="font-size:10px;background:#edf7ff;padding:1px 6px;border-radius:4px;margin-right:2px">${escHtml(m)}</span>`).join("");
      return `<tr>
        <td>
          <div style="font-weight:600;color:var(--text)">${escHtml(p.title || "未知标题")}</div>
          <div style="font-size:11px;color:var(--muted);margin-top:2px">${methods || "无方法标签"}</div>
        </td>
        <td>${p.year || "-"}</td>
        <td>${escHtml(p.direction_label || "-")}</td>
        <td>${p.reference_count || 0}</td>
        <td><span style="font-weight:600;color:${p.quality_score > 0.6 ? '#2d9a68' : p.quality_score > 0.3 ? '#d97706' : '#94a3b8'}">${(p.quality_score || 0).toFixed(1)}</span></td>
        <td>
          <div class="lib-actions-cell" style="gap:4px">
            <button class="ghost paper-run-btn" data-doc-id="${escHtml(p.doc_id)}" title="运行流水线">▶</button>
            <button class="ghost paper-detail-btn" data-doc-id="${escHtml(p.doc_id)}" title="详情">📋</button>
            <button class="ghost paper-delete-btn" data-doc-id="${escHtml(p.doc_id)}" title="删除" style="color:#c44">✕</button>
          </div>
        </td>
      </tr>`;
    }).join("");
  }

  async function uploadPaper() {
    const input = document.getElementById("paperFileInput");
    const tip = document.getElementById("paperUploadTip");
    if (!input || !input.files.length) {
      if (tip) tip.textContent = "请先选择文件";
      return;
    }
    const file = input.files[0];
    const formData = new FormData();
    formData.append("file", file);
    const btn = document.getElementById("paperUploadBtn");
    if (btn) { btn.disabled = true; btn.textContent = "上传中..."; }
    if (tip) tip.textContent = "上传中...";
    try {
      const res = await fetch("/api/papers/upload", { method: "POST", body: formData });
      const data = await res.json();
      if (data.status === "ok") {
        if (tip) tip.textContent = `上传成功: ${data.file_name}`;
        input.value = "";
        await loadPapers();
        if (data.saved_path && tip) tip.textContent += " 可在论文列表中点击 ▶ 运行流水线";
      } else {
        if (tip) tip.textContent = "上传失败: " + (data.message || "未知错误");
      }
    } catch (e) {
      if (tip) tip.textContent = "上传失败: " + e.message;
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "选择文件并上传"; }
    }
  }

  async function deletePaper(docId) {
    if (!docId) return;
    try {
      const res = await api("/api/papers/delete", {
        method: "POST",
        body: JSON.stringify({ doc_id: docId }),
      });
      if (res.deleted) {
        await loadPapers();
        const pipelineSection = document.getElementById("paperPipelineSection");
        if (pipelineSection) pipelineSection.hidden = true;
      }
    } catch (e) {
      alert("删除失败: " + e.message);
    }
  }

  async function togglePaperDetail(docId) {
    const detailRow = document.getElementById("paperDetailRow");
    if (!detailRow) return;
    if (paperState.selectedId === docId) {
      detailRow.hidden = !detailRow.hidden;
      return;
    }
    paperState.selectedId = docId;
    try {
      const data = await api(`/api/papers/detail?doc_id=${encodeURIComponent(docId)}`);
      const p = data.paper;
      if (!p) { detailRow.hidden = true; return; }
      const methods = (p.methods || []).join(", ") || "无";
      const theories = (p.theory_frameworks || []).join(", ") || "无";
      const sections = (p.sections || []).map(s => `<li>${escHtml(s)}</li>`).join("") || "<li>无</li>";
      const keywords = (p.keywords || []).join(", ") || "无";
      detailRow.innerHTML = `
        <div class="paper-detail-card">
          <h4>${escHtml(p.title)}</h4>
          <div class="paper-detail-grid">
            <div class="paper-detail-field"><span>作者</span> ${escHtml((p.authors || []).join(", ") || "未知")}</div>
            <div class="paper-detail-field"><span>年份</span> ${p.year || "未知"}</div>
            <div class="paper-detail-field"><span>方向</span> ${escHtml(p.direction_label || "未分类")}</div>
            <div class="paper-detail-field"><span>语言</span> ${p.language || "zh"}</div>
            <div class="paper-detail-field"><span>质量分</span> ${(p.quality_score || 0).toFixed(2)}</div>
            <div class="paper-detail-field"><span>引用数</span> ${p.reference_count || 0}</div>
            <div class="paper-detail-field"><span>字数</span> ${p.word_count || 0}</div>
            <div class="paper-detail-field"><span>本地化分</span> ${(p.localization_score || 0).toFixed(2)}</div>
          </div>
          <div class="paper-detail-field"><span>关键词</span> ${keywords}</div>
          <div class="paper-detail-field"><span>方法</span> ${methods}</div>
          <div class="paper-detail-field"><span>理论框架</span> ${theories}</div>
          <div class="paper-detail-field"><span>摘要</span> ${escHtml(p.abstract || "无")}</div>
          <div class="paper-detail-field"><span>章节</span><ul>${sections}</ul></div>
          <button class="ghost" onclick="document.getElementById('paperDetailRow').hidden = true">关闭</button>
        </div>`;
      detailRow.hidden = false;
      const pipelineSection = document.getElementById("paperPipelineSection");
      if (pipelineSection) {
        pipelineSection.hidden = false;
        const title = document.getElementById("paperPipelineTitle");
        if (title) title.textContent = p.title || docId;
      }
    } catch (e) {
      detailRow.innerHTML = `<div class="paper-detail-card"><p>加载失败: ${e.message}</p></div>`;
      detailRow.hidden = false;
    }
  }

  async function runPaperPipeline() {
    const docId = paperState.selectedId;
    if (!docId) { alert("请先在论文列表中点击详情选择一篇论文"); return; }
    const logBox = document.getElementById("paperPipelineLog");
    if (logBox) logBox.innerHTML = "";
    const btn = document.getElementById("runPaperPipeline");
    if (btn) { btn.disabled = true; btn.textContent = "启动中..."; }
    try {
      const res = await api("/api/papers/pipeline/start", {
        method: "POST",
        body: JSON.stringify({ doc_id: docId }),
      });
      paperState.pipelineTaskId = res.task_id;
      if (btn) btn.textContent = "运行中...";
      pollPaperPipeline();
    } catch (e) {
      if (btn) { btn.disabled = false; btn.textContent = "运行完整流水线"; }
      alert("启动流水线失败: " + e.message);
    }
  }

  function pollPaperPipeline() {
    if (!paperState.pipelineTaskId) return;
    if (paperState.pipelineTimer) clearTimeout(paperState.pipelineTimer);
    (async () => {
      try {
        const data = await api(`/api/tasks/${paperState.pipelineTaskId}`);
        const logBox = document.getElementById("paperPipelineLog");
        if (data.logs && logBox) {
          logBox.innerHTML = data.logs.map(l => `<div><time>${l.time || ""}</time><span>${escHtml(l.message || "")}</span></div>`).join("");
          logBox.scrollTop = logBox.scrollHeight;
        }
        if (data.status === "done" || data.status === "error") {
          const btn = document.getElementById("runPaperPipeline");
          if (btn) { btn.disabled = false; btn.textContent = "运行完整流水线"; }
          paperState.pipelineTaskId = "";
          await loadPapers();
          return;
        }
        paperState.pipelineTimer = setTimeout(pollPaperPipeline, 1500);
      } catch (_) {
        paperState.pipelineTimer = setTimeout(pollPaperPipeline, 3000);
      }
    })();
  }

  // ═══════════════════════════════════════════
  // License Admin
  // ═══════════════════════════════════════════

  async function generateLicenseCode() {
    const tier = document.getElementById("licenseGenTier")?.value || "basic";
    const email = document.getElementById("licenseGenEmail")?.value?.trim() || "";
    const btn = document.getElementById("licenseGenBtn");
    const box = document.getElementById("generatedCodeBox");
    const codeText = document.getElementById("generatedCodeText");
    const tip = document.getElementById("genCodeTip");
    if (btn) { btn.disabled = true; btn.textContent = "生成中..."; }
    try {
      const res = await api("/api/license/generate", {
        method: "POST",
        body: JSON.stringify({ license_type: tier, user_email: email }),
      });
      if (res.license_code && codeText) codeText.textContent = res.license_code;
      if (box) box.hidden = false;
      if (tip) tip.textContent = "生成成功";
    } catch (e) {
      if (tip) tip.textContent = "生成失败: " + e.message;
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "生成许可证"; }
    }
  }

  function copyGeneratedCode() {
    const codeText = document.getElementById("generatedCodeText");
    if (!codeText || !codeText.textContent) return;
    navigator.clipboard.writeText(codeText.textContent).then(() => {
      const tip = document.getElementById("genCodeTip");
      if (tip) { tip.textContent = "已复制到剪贴板"; setTimeout(() => { tip.textContent = ""; }, 2000); }
    });
  }

  async function loadLicenseHistory() {
    const tbody = document.getElementById("licenseHistoryBody");
    const empty = document.getElementById("licenseHistoryEmpty");
    if (!tbody) return;
    try {
      const data = await api("/api/license/history");
      const history = data.history || [];
      if (!history.length) {
        tbody.innerHTML = "";
        if (empty) empty.style.display = "block";
        return;
      }
      if (empty) empty.style.display = "none";
      tbody.innerHTML = history.reverse().map(h => {
        const codePreview = (h.code_preview || "").length > 24 ? (h.code_preview || "").slice(0, 24) + "..." : (h.code_preview || "-");
        const actionLabel = h.action === "generate" ? "生成" : h.action === "activate" ? "激活" : h.action || "-";
        const typeLabel = h.license_type || (h.action === "activate" ? "激活" : "-");
        return `<tr>
          <td><span style="font-weight:600;color:${h.action === 'generate' ? 'var(--primary)' : '#2d9a68'}">${actionLabel}</span></td>
          <td>${escHtml(typeLabel)}</td>
          <td>${escHtml(h.user_email || "-")}</td>
          <td style="font-family:monospace;font-size:11px">${escHtml(codePreview)}</td>
          <td>${escHtml((h.generated_at || h.saved_at || "-").slice(0, 16))}</td>
          <td>${escHtml((h.expires_at || "-").slice(0, 10))}</td>
        </tr>`;
      }).join("");
    } catch (e) {
      if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="lib-empty-cell">加载失败: ${e.message}</td></tr>`;
    }
  }

  // ═══════════════════════════════════════════
  // Knowledge Base Init
  // ═══════════════════════════════════════════

  async function initKnowledgeBase() {
    const button = document.getElementById("initKnowledgeBase");
    const status = document.getElementById("initKbStatus");
    const logBox = document.getElementById("initKbLog");
    if (!button || !status || !logBox) return;

    const lic = state.license || {};
    if (!(lic.features || []).includes("admin")) {
      status.innerHTML = "🔒 需要管理员许可证";
      activeStep("license");
      return;
    }

    button.disabled = true;
    button.classList.add("loading");
    status.classList.add("progress-tip");
    status.innerHTML = `<span class="cute-loader">初始化中<span></span><span></span><span></span></span>`;
    logBox.innerHTML = "";
    try {
      const data = await api("/api/knowledge-base/init", { method: "POST" });
      if (!data.task_id) throw new Error("未能获取任务 ID");
      status.textContent = `初始化任务已创建：${data.task_id}`;
      await pollKnowledgeBaseTask(data.task_id, 0);
    } catch (error) {
      status.innerHTML = `❌ 初始化失败：${escHtml(error?.message || String(error))}`;
      button.disabled = false;
      button.classList.remove("loading");
    }
  }

  async function pollKnowledgeBaseTask(taskId, count) {
    const status = document.getElementById("initKbStatus");
    const logBox = document.getElementById("initKbLog");
    const button = document.getElementById("initKnowledgeBase");
    if (!status || !logBox || !button) return;

    const data = await api(`/api/tasks/${taskId}`);
    status.textContent = `${data.message || data.status} · 已检查 ${Math.max(count, 1)} 次`;
    renderTaskLog(data.logs || [], "#initKbLog");

    if (data.status === "done") {
      const conversion = data.result?.conversion || {};
      const templates = data.result?.templates?.templates?.length ?? 0;
      const documents = data.result?.vector_index?.documents ?? 0;
      const chunks = data.result?.vector_index?.chunks ?? 0;
      const entries = data.result?.citation_index?.entry_count ?? 0;
      const mdCount = (conversion.converted_files ?? 0) + (conversion.reused_files ?? 0);
      const outlineTotal = data.result?.outline_index?.total ?? 0;
      const directionCount = Object.keys(data.result?.outline_index?.directions || {}).length;

      status.innerHTML = `✅ 初始化完成 · ${mdCount} 文档 · ${documents} 向量文档(${chunks}块) · ${entries} 引用卡片${templates ? " · " + templates + " 模板" : ""}${outlineTotal ? " · " + outlineTotal + " 大纲(" + directionCount + "方向)" : ""}`;
      button.disabled = false;
      button.classList.remove("loading");
      return;
    }

    if (data.status === "error") {
      status.innerHTML = `❌ 初始化失败：${data.message || "未知错误"}`;
      button.disabled = false;
      button.classList.remove("loading");
      return;
    }

    setTimeout(() => pollKnowledgeBaseTask(taskId, count + 1), 2000);
  }

  // ═══════════════════════════════════════════
  // KB Citation Generation
  // ═══════════════════════════════════════════

  function setKbCitationProgress(done, total, message) {
    const box = document.getElementById("kbCitationProgress");
    if (!box) return;
    const percent = total ? Math.min(100, Math.max(0, Math.round((done / total) * 100))) : 0;
    box.hidden = false;
    const snail = document.getElementById("kbCitationSnail");
    if (snail) snail.style.left = `calc(${percent}% - 18px)`;
    const text = document.getElementById("kbCitationProgressText");
    if (text) text.textContent = message || `正在生成引用 ${done}/${total}`;
  }

  function hideKbCitationProgress() {
    const box = document.getElementById("kbCitationProgress");
    if (box) box.hidden = true;
  }

  async function generateCitationsKb() {
    const direction = typeof selectedDirection === "function" ? selectedDirection() : { id: "", name: "" };
    const btn = document.getElementById("kbGenerateCitationsBtn");
    if (btn) { btn.disabled = true; btn.textContent = "生成中..."; }
    const status = document.getElementById("kbCitationStatus");
    if (status) status.textContent = "正在创建引用生成任务...";
    const logEl = document.getElementById("kbCitationLog");
    if (logEl) logEl.innerHTML = "";
    try {
      const countEl = document.getElementById("kbCitationCount");
      const expectedCount = Math.max(10, Math.min(150, Number((countEl && countEl.value) || 100)));
      const data = await api("/api/citations/generate", {
        method: "POST",
        body: JSON.stringify({
          topic: document.getElementById("topicInput")?.value?.trim() || "",
          project_context: typeof projectContextPayload === "function" ? projectContextPayload() : {},
          direction: direction.id,
          direction_name: direction.name,
          methods: typeof selectedMethodNames === "function" ? selectedMethodNames() : [],
          phase_methods: typeof phaseMethodsPayload === "function" ? phaseMethodsPayload() : {},
          expected_count: expectedCount,
        }),
      });
      if (!data.task_id) throw new Error("未能创建引用生成任务");
      pollCitationTaskKb(data.task_id, 0);
    } catch (error) {
      if (status) status.textContent = `引用生成失败：${error.message}`;
      if (btn) { btn.disabled = false; btn.textContent = "AI生成引用"; }
    }
  }

  async function pollCitationTaskKb(taskId, count) {
    const data = await api(`/api/tasks/${taskId}`);
    const status = document.getElementById("kbCitationStatus");
    if (status) status.textContent = `${data.message || data.status} · ${Math.max(count, 1)} 次检查`;
    renderTaskLog(data.logs || [], "#kbCitationLog");

    const progress = data.progress || 0;
    setKbCitationProgress(progress, 100, data.message || "正在生成引用...");

    if (data.status === "done") {
      const result = data.result || {};
      if (status) status.textContent = `${result.message || "引用已生成"} · 方向 ${result.direction_count || 0} 条 + 方法 ${(result.local_count || 0) - (result.direction_count || 0)} 条 + LLM ${result.llm_count || 0} 条`;
      setKbCitationProgress(100, 100, "引用生成完成");
      setTimeout(hideKbCitationProgress, 4000);
      const btn = document.getElementById("kbGenerateCitationsBtn");
      if (btn) { btn.disabled = false; btn.textContent = "重新生成"; }
      return;
    }

    if (data.status === "error") {
      if (status) status.textContent = `引用生成失败：${data.message || "未知错误"}`;
      hideKbCitationProgress();
      const btn = document.getElementById("kbGenerateCitationsBtn");
      if (btn) { btn.disabled = false; btn.textContent = "重试"; }
      return;
    }

    setTimeout(() => pollCitationTaskKb(taskId, count + 1), 1500);
  }

  // ═══════════════════════════════════════════
  // Event bindings
  // ═══════════════════════════════════════════

  function bindAdminEvents() {
    // Sidebar admin toggle
    const adminToggle = document.getElementById("adminToggle");
    if (adminToggle) {
      adminToggle.addEventListener("click", () => {
        const sub = document.getElementById("adminSub");
        const chev = document.getElementById("adminChevron");
        if (!sub) return;
        sub.hidden = !sub.hidden;
        if (sub.hidden) {
          adminToggle.classList.remove("active");
          if (chev) chev.textContent = "▸";
        } else {
          adminToggle.classList.add("active");
          if (chev) chev.textContent = "▾";
        }
      });
    }

    // Fix admin sub-item click handlers (data-step may be missing)
    const adminSub = document.getElementById("adminSub");
    if (adminSub) {
      Array.from(adminSub.children).forEach((btn) => {
        btn.addEventListener("click", (e) => {
          const text = btn.textContent;
          if (text.includes("知识库")) activeStep("kb_init");
          else if (text.includes("论文管理")) activeStep("paper_manager");
          else if (text.includes("许可证")) activeStep("license");
        });
      });
    }

    // Knowledge base init
    const initKb = document.getElementById("initKnowledgeBase");
    if (initKb) initKb.addEventListener("click", initKnowledgeBase);

    // KB citation generation
    const kbGenBtn = document.getElementById("kbGenerateCitationsBtn");
    if (kbGenBtn) kbGenBtn.addEventListener("click", generateCitationsKb);

    // Paper management
    const uploadBtn = document.getElementById("paperUploadBtn");
    if (uploadBtn) uploadBtn.addEventListener("click", () => { document.getElementById("paperFileInput")?.click(); });
    const fileInput = document.getElementById("paperFileInput");
    if (fileInput) fileInput.addEventListener("change", uploadPaper);
    const refreshBtn = document.getElementById("refreshPapers");
    if (refreshBtn) refreshBtn.addEventListener("click", loadPapers);
    const searchBtn = document.getElementById("paperSearchBtn");
    if (searchBtn) searchBtn.addEventListener("click", loadPapers);
    const kwFilter = document.getElementById("paperKeywordFilter");
    if (kwFilter) kwFilter.addEventListener("keydown", (e) => { if (e.key === "Enter") loadPapers(); });

    // Paper table delegated events
    const tableBody = document.getElementById("paperTableBody");
    if (tableBody) {
      tableBody.addEventListener("click", (e) => {
        const runBtn = e.target.closest(".paper-run-btn");
        const detailBtn = e.target.closest(".paper-detail-btn");
        const deleteBtn = e.target.closest(".paper-delete-btn");
        if (runBtn) { togglePaperDetail(runBtn.dataset.docId).then(() => runPaperPipeline()); }
        if (detailBtn) togglePaperDetail(detailBtn.dataset.docId);
        if (deleteBtn) {
          const docId = deleteBtn.dataset.docId;
          if (confirm("确定要删除此论文及其关联引用卡片吗？此操作不可撤销。")) {
            deletePaper(docId).then(() => {
              if (paperState.selectedId === docId) {
                paperState.selectedId = "";
                const detailRow = document.getElementById("paperDetailRow");
                const pipelineSection = document.getElementById("paperPipelineSection");
                if (detailRow) detailRow.hidden = true;
                if (pipelineSection) pipelineSection.hidden = true;
              }
            });
          }
        }
      });
    }

    const runPipeline = document.getElementById("runPaperPipeline");
    if (runPipeline) runPipeline.addEventListener("click", runPaperPipeline);

    // License admin
    const genBtn = document.getElementById("licenseGenBtn");
    if (genBtn) genBtn.addEventListener("click", generateLicenseCode);
    const copyBtn = document.getElementById("copyGeneratedCode");
    if (copyBtn) copyBtn.addEventListener("click", copyGeneratedCode);

  }
})();
