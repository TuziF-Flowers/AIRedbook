const $ = (selector) => document.querySelector(selector);

const form = $("#search-form");
const keywordInput = $("#keyword");
const competitorInput = $("#competitor-input");
const competitorChips = $("#competitor-chips");
const addCompetitorButton = $("#add-competitor");
const searchButton = $("#search-button");
const analyzeButton = $("#analyze-button");
const resultsSection = $("#collection");
const resultsGrid = $("#results-grid");
const resultsTitle = $("#results-title");
const resultsMeta = $("#results-meta");
const message = $("#message");
const sessionStatus = $("#session-status");
const analysisSection = $("#analysis");
const analysisContent = $("#analysis-content");
const analysisMode = $("#analysis-mode");
const reportPreview = $("#report-preview");
const summaryList = $("#summary-list");
const artifactStatus = $("#artifact-status");
const metricsOverview = $("#metrics-overview");
const metricsOverviewMeta = $("#metrics-overview-meta");
const metricsOverviewContent = $("#metrics-overview-content");
const copyReportButton = $("#copy-report");
const downloadJsonButton = $("#download-json");
const downloadReportButton = $("#download-report");
const dialog = $("#detail-dialog");
const detailContent = $("#detail-content");
const closeDialogButton = $("#close-dialog");
const sideNavLinks = Array.from(document.querySelectorAll(".side-nav [data-nav-key]"));
const competitorTabs = $("#competitor-tabs");
const collectionSort = $("#collection-sort");
const hotTagList = $("#hot-tag-list");
const productBriefInput = $("#product-brief");
const productBriefCount = $("#product-brief-count");
const productImagesInput = $("#product-images");
const productImageDropzone = $("#product-image-dropzone");
const productImageFeedback = $("#product-image-feedback");
const productImagePreview = $("#product-image-preview");
const creationSection = $("#creation");
const creationEntryButton = $("#creation-entry-button");
const generatePromotionButton = $("#generate-promotion-button");
const creationMessage = $("#creation-message");
const promotionCopy = $("#promotion-copy");
const promotionImages = $("#promotion-images");
const copyPromotionButton = $("#copy-promotion-button");
const creationModel = $("#creation-model");

const MAX_PRODUCT_IMAGES = 6;
const MAX_PRODUCT_IMAGE_BYTES = 8 * 1024 * 1024;
const PRODUCT_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

const state = {
  keyword: "",
  competitors: [],
  loading: false,
  analyzing: false,
  generating: false,
  notes: [],
  analysis: null,
  promotion: null,
  activeTab: "title",
  activeCompetitor: "all",
  collectionSort: "heat",
  productBrief: "",
  productImages: [],
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function setStep(step) {
  document.querySelectorAll(".pipeline li").forEach((item) => {
    const itemStep = Number(item.dataset.step);
    item.classList.toggle("active", itemStep === step);
    item.classList.toggle("done", itemStep < step);
  });
}

function setActiveSideNav(key) {
  sideNavLinks.forEach((link) => {
    const active = link.dataset.navKey === key;
    link.classList.toggle("active", active);
    if (active) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  });
}

function setPipelineStepForNav(key) {
  const stepByNav = {
    overview: 1,
    collection: 2,
    analysis: 3,
    report: 3,
  };
  setStep(stepByNav[key] || 1);
}

let navFrameRequested = false;

function updateSideNavFromScroll() {
  navFrameRequested = false;
  const marker = window.scrollY + Math.min(window.innerHeight * 0.35, 300);
  let activeKey = "overview";

  if (!resultsSection.hidden && resultsSection.offsetTop <= marker) {
    activeKey = "collection";
  }
  if (!analysisSection.hidden && analysisSection.offsetTop <= marker) {
    activeKey = "analysis";
  }
  if (!metricsOverview.hidden && metricsOverview.offsetTop <= marker) {
    activeKey = "report";
  }
  if (!creationSection.hidden && creationSection.offsetTop <= marker) {
    activeKey = "creation";
  }

  setActiveSideNav(activeKey);
  setPipelineStepForNav(activeKey);
}

function scheduleSideNavUpdate() {
  if (navFrameRequested) return;
  navFrameRequested = true;
  window.requestAnimationFrame(updateSideNavFromScroll);
}

function formatCount(value) {
  const number = Number(value || 0);
  if (number >= 10000) {
    const short = number / 10000;
    return `${short >= 10 ? Math.round(short) : short.toFixed(1)}万`;
  }
  if (number >= 1000) return `${(number / 1000).toFixed(1)}k`;
  return String(number);
}

function addCompetitor(value) {
  const competitor = value.trim();
  if (!competitor) return true;
  if (state.competitors.some((item) => item.toLowerCase() === competitor.toLowerCase())) {
    competitorInput.value = "";
    return true;
  }
  if (state.competitors.length >= 3) {
    competitorInput.setCustomValidity("最多添加 3 个竞品标签。");
    competitorInput.reportValidity();
    return false;
  }
  competitorInput.setCustomValidity("");
  state.competitors.push(competitor);
  competitorInput.value = "";
  renderCompetitorChips();
  return true;
}

function removeCompetitor(index) {
  state.competitors.splice(index, 1);
  competitorInput.setCustomValidity("");
  renderCompetitorChips();
}

function renderCompetitorChips() {
  competitorChips.replaceChildren();
  state.competitors.forEach((competitor, index) => {
    const chip = element("span", "competitor-chip");
    chip.append(element("span", "", competitor));
    const remove = element("button", "", "×");
    remove.type = "button";
    remove.setAttribute("aria-label", `删除竞品 ${competitor}`);
    remove.addEventListener("click", () => removeCompetitor(index));
    chip.append(remove);
    competitorChips.append(chip);
  });
  competitorInput.placeholder = state.competitors.length
    ? "继续添加竞品"
    : "输入品牌或型号后按回车";
}

function setProductImageFeedback(message, kind = "") {
  productImageFeedback.textContent = message;
  productImageFeedback.className = `product-image-feedback${kind ? ` ${kind}` : ""}`;
}

function removeProductImage(id) {
  const index = state.productImages.findIndex((item) => item.id === id);
  if (index === -1) return;
  URL.revokeObjectURL(state.productImages[index].previewUrl);
  state.productImages.splice(index, 1);
  renderProductImages();
  updateCreationReadiness();
}

function renderProductImages(message = "", kind = "") {
  productImagePreview.replaceChildren();
  productImagePreview.hidden = state.productImages.length === 0;

  state.productImages.forEach((item, index) => {
    const figure = element("figure", "product-image-item");
    const preview = element("img");
    preview.src = item.previewUrl;
    preview.alt = `产品图片 ${index + 1}`;

    const remove = element("button", "", "×");
    remove.type = "button";
    remove.title = `删除 ${item.file.name}`;
    remove.setAttribute("aria-label", `删除产品图片 ${index + 1}`);
    remove.addEventListener("click", () => removeProductImage(item.id));
    figure.append(preview, remove);
    productImagePreview.append(figure);
  });

  if (message) {
    setProductImageFeedback(message, kind);
  } else if (state.productImages.length) {
    setProductImageFeedback(`已添加 ${state.productImages.length} / ${MAX_PRODUCT_IMAGES} 张`);
  } else {
    setProductImageFeedback("尚未添加图片");
  }
}

function addProductImages(fileList) {
  const files = Array.from(fileList || []);
  if (!files.length) return;

  let invalidCount = 0;
  let duplicateCount = 0;
  let overflowCount = 0;
  const existingKeys = new Set(
    state.productImages.map(({ file }) => `${file.name}:${file.size}:${file.lastModified}`),
  );

  files.forEach((file) => {
    const key = `${file.name}:${file.size}:${file.lastModified}`;
    if (!PRODUCT_IMAGE_TYPES.has(file.type) || file.size > MAX_PRODUCT_IMAGE_BYTES) {
      invalidCount += 1;
      return;
    }
    if (existingKeys.has(key)) {
      duplicateCount += 1;
      return;
    }
    if (state.productImages.length >= MAX_PRODUCT_IMAGES) {
      overflowCount += 1;
      return;
    }

    existingKeys.add(key);
    state.productImages.push({
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      file,
      previewUrl: URL.createObjectURL(file),
    });
  });

  const issues = [];
  if (invalidCount) issues.push(`${invalidCount} 张格式或大小不符合要求`);
  if (duplicateCount) issues.push(`${duplicateCount} 张重复图片`);
  if (overflowCount) issues.push(`${overflowCount} 张超出数量限制`);
  const message = issues.length
    ? `已添加 ${state.productImages.length} / ${MAX_PRODUCT_IMAGES} 张；${issues.join("，")}。`
    : "";
  renderProductImages(message, issues.length ? "error" : "");
  updateCreationReadiness();
  productImagesInput.value = "";
}

function creationRequirements() {
  const missing = [];
  if (!state.productBrief.trim()) missing.push("产品信息");
  if (!state.productImages.length) missing.push("产品图片");
  if (!state.analysis || state.analysis.analysis_mode !== "ai") missing.push("真实 AI 分析");
  return missing;
}

function updateCreationReadiness() {
  const missing = creationRequirements();
  const ready = missing.length === 0;
  creationEntryButton.disabled = !ready || state.generating;
  generatePromotionButton.disabled = !ready || state.generating;
  if (!state.generating && !state.promotion) {
    setCreationProgress(
      0,
      ready ? "素材已就绪" : "等待生成",
      ready ? "可以开始生成真实 AI 文案与宣传图" : `还需要：${missing.join("、")}`,
    );
  }
}

function image(url, alt, className = "") {
  const img = element("img", className);
  img.alt = alt;
  img.loading = "lazy";
  img.referrerPolicy = "no-referrer";
  if (url) img.src = `/api/images/proxy?url=${encodeURIComponent(url)}`;
  img.addEventListener("error", () => {
    if (url && img.dataset.directFallback !== "true") {
      img.dataset.directFallback = "true";
      img.src = url;
      return;
    }
    img.remove();
  });
  return img;
}

function showMessage(text, kind = "error") {
  message.hidden = false;
  message.className = `message ${kind}`;
  message.textContent = text;
}

function hideMessage() {
  message.hidden = true;
  message.textContent = "";
}

function renderSkeletons() {
  for (let index = 0; index < 10; index += 1) {
    const card = element("div", "skeleton-card");
    card.append(
      element("div", "skeleton skeleton-image"),
      element("div", "skeleton skeleton-line"),
      element("div", "skeleton skeleton-line short"),
    );
    resultsGrid.append(card);
  }
}

function createCard(note, index) {
  const card = element("button", "note-card");
  card.type = "button";
  card.setAttribute("aria-label", `查看笔记：${note.title}`);

  const imageWrap = element("div", "card-image");
  if (note.cover_url) imageWrap.append(image(note.cover_url, note.title));
  imageWrap.append(element("span", "rank-badge", `TOP ${index + 1}`));
  imageWrap.append(element("span", "type-badge", "图文"));

  const body = element("div", "card-body");
  if (note.competitor) {
    body.append(element("span", "card-competitor", note.competitor));
  }
  body.append(element("h3", "card-title", note.title || "无标题"));

  const authorRow = element("div", "author-row");
  authorRow.append(
    image(note.author?.avatar_url, "", "author-avatar"),
    element("span", "author-name", note.author?.nickname || "未知作者"),
  );
  body.append(authorRow);

  const stats = element("div", "stats-row");
  stats.append(
    element("span", "", `♥ ${formatCount(note.stats?.likes)}`),
    element("span", "", `评 ${formatCount(note.stats?.comments)}`),
    element("span", "", `藏 ${formatCount(note.stats?.collects)}`),
  );
  body.append(stats);
  card.append(imageWrap, body);
  card.addEventListener("click", () => openDetail(note));
  return card;
}

async function parseResponse(response) {
  const data = await response.json().catch(() => ({
    message: "服务返回了无法解析的数据。",
  }));
  if (!response.ok) {
    const error = new Error(data.message || "请求失败，请稍后重试。");
    error.hint = data.hint;
    throw error;
  }
  return data;
}

function setCollectionProgress(percent, title, meta) {
  $("#collection-progress-percent").textContent = `${percent}%`;
  $("#collection-progress-fill").style.width = `${percent}%`;
  $("#collection-progress-title").textContent = title;
  $("#collection-progress-meta").textContent = meta;
}

let collectionProgressFrame = null;

function stopCollectionProgressAnimation() {
  if (collectionProgressFrame !== null) {
    window.cancelAnimationFrame(collectionProgressFrame);
    collectionProgressFrame = null;
  }
}

function startCollectionProgressAnimation() {
  stopCollectionProgressAnimation();
  const startedAt = window.performance.now();
  let lastPercent = -1;

  const tick = (now) => {
    const elapsed = now - startedAt;
    const percent = Math.min(92, 8 + Math.floor(84 * (1 - Math.exp(-elapsed / 15000))));
    if (percent !== lastPercent) {
      lastPercent = percent;
      if (percent < 30) {
        setCollectionProgress(
          percent,
          "正在搜索竞品种草内容",
          `${state.competitors.length} 个竞品 · 正在获取高互动图文`,
        );
      } else if (percent < 60) {
        setCollectionProgress(percent, "正在补全笔记信息", "读取标签、封面和公开详情数据");
      } else if (percent < 80) {
        setCollectionProgress(percent, "正在筛选单品种草内容", "排除测评、对比、避雷和合集内容");
      } else {
        setCollectionProgress(percent, "正在整理竞品结果", "按互动表现排序并准备展示");
      }
    }
    collectionProgressFrame = window.requestAnimationFrame(tick);
  };
  collectionProgressFrame = window.requestAnimationFrame(tick);
}

function sortedCollectionNotes() {
  const notes = state.activeCompetitor === "all"
    ? [...state.notes]
    : state.notes.filter((note) => note.competitor === state.activeCompetitor);
  const valueFor = {
    heat: (note) => Number(note.stats?.likes || 0) + Number(note.stats?.collects || 0),
    likes: (note) => Number(note.stats?.likes || 0),
    collects: (note) => Number(note.stats?.collects || 0),
    comments: (note) => Number(note.stats?.comments || 0),
  }[state.collectionSort];
  return notes.sort((left, right) => valueFor(right) - valueFor(left));
}

function renderCollectionNotes() {
  resultsGrid.replaceChildren();
  const notes = sortedCollectionNotes();
  notes.forEach((note, index) => resultsGrid.append(createCard(note, index)));
  if (!notes.length && state.notes.length) {
    resultsGrid.append(element("div", "collection-empty", "这个竞品暂时没有符合条件的种草图文。"));
  }
}

function renderCompetitorTabs() {
  competitorTabs.replaceChildren();
  const entries = [
    ["all", "全部竞品", state.notes.length],
    ...state.competitors.map((competitor) => [
      competitor,
      competitor,
      state.notes.filter((note) => note.competitor === competitor).length,
    ]),
  ];
  entries.forEach(([key, label, count]) => {
    const button = element("button", key === state.activeCompetitor ? "active" : "");
    button.type = "button";
    button.textContent = `${label} (${count})`;
    button.addEventListener("click", () => {
      state.activeCompetitor = key;
      renderCompetitorTabs();
      renderCollectionNotes();
    });
    competitorTabs.append(button);
  });
}

function renderHotTags() {
  const counts = new Map();
  state.notes.forEach((note) => {
    (note.topic_tags || []).forEach((tag) => {
      const cleaned = String(tag).replace(/^#/, "").trim();
      if (cleaned) counts.set(cleaned, (counts.get(cleaned) || 0) + 1);
    });
  });
  const ranked = [...counts.entries()]
    .sort((left, right) => right[1] - left[1])
    .slice(0, 10);
  hotTagList.replaceChildren();
  if (!ranked.length) {
    hotTagList.append(element("span", "empty-tags", "当前样本没有可用公开标签"));
    return;
  }
  const maximum = ranked[0][1];
  ranked.forEach(([tag, count], index) => {
    const row = element("div", "hot-tag-row");
    const heading = element("div");
    heading.append(
      element("span", "", `${index + 1}. #${tag}`),
      element("strong", "", `${count} 篇`),
    );
    const track = element("div", "hot-tag-track");
    const fill = element("span");
    fill.style.width = `${Math.max(12, Math.round((count / maximum) * 100))}%`;
    track.append(fill);
    row.append(heading, track);
    hotTagList.append(row);
  });
}

function renderCollectionOverview() {
  const totals = state.notes.reduce(
    (summary, note) => {
      summary.likes += Number(note.stats?.likes || 0);
      summary.collects += Number(note.stats?.collects || 0);
      summary.comments += Number(note.stats?.comments || 0);
      return summary;
    },
    { likes: 0, collects: 0, comments: 0 },
  );
  $("#collected-count").textContent = state.notes.length;
  $("#total-likes").textContent = formatCount(totals.likes);
  $("#total-collects").textContent = formatCount(totals.collects);
  $("#total-comments").textContent = formatCount(totals.comments);
  $("#collection-updated-at").textContent = new Date().toLocaleString("zh-CN", {
    hour12: false,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
  renderCompetitorTabs();
  renderHotTags();
  renderCollectionNotes();
}

async function runSearch() {
  if (state.loading || state.analyzing) return;
  state.loading = true;
  state.analysis = null;
  state.promotion = null;
  state.notes = [];
  hideMessage();
  searchButton.disabled = true;
  searchButton.firstElementChild.textContent = "采集中…";
  analyzeButton.disabled = true;
  copyReportButton.disabled = true;
  downloadJsonButton.disabled = true;
  downloadReportButton.disabled = true;
  artifactStatus.textContent = "AI 洞察完成后会自动保存本地 JSON。";
  resultsGrid.replaceChildren();
  renderSkeletons();
  analysisSection.hidden = true;
  creationSection.hidden = true;
  metricsOverview.hidden = true;
  creationEntryButton.disabled = true;
  setStep(2);

  resultsSection.hidden = false;
  resultsTitle.textContent = `“${state.keyword}” 的高互动图文`;
  resultsMeta.textContent = `正在采集：${state.competitors.join("、")}`;
  setCollectionProgress(8, "正在准备竞品采集", `${state.competitors.length} 个竞品 · 合计上限 20 篇`);
  resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
  scheduleSideNavUpdate();
  startCollectionProgressAnimation();

  try {
    const response = await fetch("/api/collect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        product_name: state.keyword,
        competitors: state.competitors,
      }),
    });
    const data = await parseResponse(response);
    state.notes = data.items;
    state.activeCompetitor = "all";
    state.collectionSort = "heat";
    collectionSort.value = "heat";
    renderCollectionOverview();
    stopCollectionProgressAnimation();
    setCollectionProgress(
      100,
      "竞品种草内容采集完成",
      `${state.competitors.length} 个竞品 · 已筛选 ${data.items.length} 篇`,
    );
    resultsMeta.textContent = data.items.length
      ? `已筛选 ${data.items.length} 篇，支持按竞品标签查看和排序`
      : "未找到符合条件的单品种草图文";
    analyzeButton.disabled = data.items.length === 0;

    if (data.items.length === 0) {
      showMessage(
        "没有找到符合条件的单品种草图文，可以更换品牌、型号或具体产品名。",
        "empty",
      );
    }
  } catch (error) {
    stopCollectionProgressAnimation();
    resultsGrid.replaceChildren();
    const detail = error.hint ? `${error.message} ${error.hint}` : error.message;
    showMessage(detail);
    resultsMeta.textContent = "采集未完成";
    setCollectionProgress(0, "采集未完成", "请检查登录状态或更换竞品关键词");
  } finally {
    stopCollectionProgressAnimation();
    state.loading = false;
    searchButton.disabled = false;
    searchButton.firstElementChild.textContent = "开始采集";
  }
}

function setAnalysisProgress(percent, title, meta) {
  $("#analysis-progress-percent").textContent = `${percent}%`;
  $("#progress-fill").style.width = `${percent}%`;
  $("#analysis-progress-title").textContent = title;
  $("#analysis-progress-meta").textContent = meta;
}

let analysisProgressFrame = null;

function stopAnalysisProgressAnimation() {
  if (analysisProgressFrame !== null) {
    window.cancelAnimationFrame(analysisProgressFrame);
    analysisProgressFrame = null;
  }
}

function startAnalysisProgressAnimation() {
  stopAnalysisProgressAnimation();
  const startedAt = window.performance.now();
  let lastPercent = -1;

  const tick = (now) => {
    const elapsed = now - startedAt;
    const percent = Math.min(92, 10 + Math.floor(82 * (1 - Math.exp(-elapsed / 30000))));
    if (percent !== lastPercent) {
      lastPercent = percent;
      if (percent < 28) {
        setAnalysisProgress(percent, "正在整理竞品样本", `已加载 ${state.notes.length} 篇高互动图文`);
      } else if (percent < 50) {
        setAnalysisProgress(percent, "正在分析标题与正文", "提炼关键词、内容结构与文案表达");
      } else if (percent < 72) {
        setAnalysisProgress(percent, "正在分析互动与竞品表现", "汇总点赞、收藏、评论与竞品差异");
      } else if (percent < 86) {
        setAnalysisProgress(percent, "正在生成视觉洞察", "识别封面、视觉风格与图内文案");
      } else {
        setAnalysisProgress(percent, "正在生成竞品总结", "组合各维度洞察并写入本地 JSON");
      }
    }
    analysisProgressFrame = window.requestAnimationFrame(tick);
  };
  analysisProgressFrame = window.requestAnimationFrame(tick);
}

async function runAnalysis() {
  if (state.analyzing || !state.notes.length) return;
  state.analyzing = true;
  analyzeButton.disabled = true;
  analyzeButton.lastElementChild.textContent = "正在分析…";
  analysisSection.hidden = false;
  metricsOverview.hidden = true;
  setStep(3);
  setAnalysisProgress(10, "正在准备竞品分析", `已加载 ${state.notes.length} 篇高互动图文`);
  analysisContent.innerHTML = '<div class="analysis-loading"><span>✦</span><strong>AI 正在提炼爆款规律</strong><small>分析标题、正文结构、图片数量与互动表现</small></div>';
  analysisSection.scrollIntoView({ behavior: "smooth", block: "start" });
  scheduleSideNavUpdate();

  startAnalysisProgressAnimation();

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keyword: state.keyword, notes: state.notes }),
    });
    state.analysis = await parseResponse(response);
    stopAnalysisProgressAnimation();
    setAnalysisProgress(
      100,
      "竞品规律分析完成",
      `已分析 ${state.analysis.source_count} 篇笔记 · ${state.analysis.mode_label}`,
    );
    analysisMode.textContent = state.analysis.analysis_mode === "ai" ? "AI 深度分析" : "本地规则分析";
    reportPreview.textContent = state.analysis.report_markdown;
    artifactStatus.textContent = state.analysis.artifact_id
      ? `JSON 已保存 · ${state.analysis.artifact_id}`
      : "本次分析未生成 JSON 文件。";
    renderSummary(state.analysis.summary);
    renderMetricsOverview(state.analysis);
    copyReportButton.disabled = false;
    downloadJsonButton.disabled = !state.analysis.json_download_url;
    downloadReportButton.disabled = false;
    renderAnalysisTab(state.activeTab);
    creationSection.hidden = false;
    updateCreationReadiness();
    scheduleSideNavUpdate();
  } catch (error) {
    stopAnalysisProgressAnimation();
    const detail = error.hint ? `${error.message} ${error.hint}` : error.message;
    analysisContent.replaceChildren(element("div", "analysis-empty error", detail));
    setAnalysisProgress(0, "分析未完成", "请检查服务配置后重试");
    creationSection.hidden = true;
    updateCreationReadiness();
  } finally {
    stopAnalysisProgressAnimation();
    state.analyzing = false;
    analyzeButton.disabled = false;
    analyzeButton.lastElementChild.textContent = "重新生成分析";
  }
}

function setCreationProgress(percent, title, meta) {
  $("#creation-progress-percent").textContent = `${percent}%`;
  $("#creation-progress-fill").style.width = `${percent}%`;
  $("#creation-progress-title").textContent = title;
  $("#creation-progress-meta").textContent = meta;
}

function showCreationMessage(text) {
  creationMessage.hidden = false;
  creationMessage.textContent = text;
}

function hideCreationMessage() {
  creationMessage.hidden = true;
  creationMessage.textContent = "";
}

function promotionCopyText() {
  if (!state.promotion) return "";
  const copy = state.promotion.promotion_copy;
  const tags = copy.hashtags.map((tag) => `#${tag}`).join(" ");
  return `${copy.title}\n\n${copy.body}\n\n${tags}`;
}

function renderPromotion(result) {
  const copy = result.promotion_copy;
  promotionCopy.className = "promotion-copy";
  promotionCopy.replaceChildren(
    element("h3", "promotion-title", copy.title),
    element("p", "promotion-body", copy.body),
  );
  const tags = element("div", "promotion-tags");
  copy.hashtags.forEach((tag) => tags.append(element("span", "", `#${tag}`)));
  promotionCopy.append(tags);

  promotionImages.replaceChildren();
  result.images.forEach((item, index) => {
    const figure = element("figure", "promotion-image-item");
    const img = element("img");
    img.src = item.data_url;
    img.alt = `AI 生成宣传图 ${index + 1}`;
    const actions = element("figcaption");
    actions.append(element("span", "", `方案 ${String(index + 1).padStart(2, "0")}`));
    const download = element("button", "secondary-button", "下载图片");
    download.type = "button";
    download.addEventListener("click", () => {
      const link = document.createElement("a");
      link.href = item.data_url;
      link.download = `${state.keyword || "宣传产品"}-AI宣传图-${index + 1}.png`;
      link.click();
    });
    actions.append(download);
    figure.append(img, actions);
    promotionImages.append(figure);
  });
  creationModel.textContent = result.image_model;
  copyPromotionButton.disabled = false;
}

async function generatePromotion() {
  if (state.generating) return;
  const missing = creationRequirements();
  if (missing.length) {
    showCreationMessage(`请先补充：${missing.join("、")}。`);
    return;
  }

  state.generating = true;
  state.promotion = null;
  hideCreationMessage();
  setStep(4);
  updateCreationReadiness();
  generatePromotionButton.lastElementChild.textContent = "AI 正在创作…";
  copyPromotionButton.disabled = true;
  setCreationProgress(12, "正在策划宣传文案", "真实 AI 正在组合产品卖点与竞品内容规律");
  creationSection.scrollIntoView({ behavior: "smooth", block: "start" });
  promotionCopy.className = "promotion-copy is-empty";
  promotionCopy.replaceChildren(
    element("strong", "", "AI 正在撰写标题、正文和话题标签"),
    element("p", "", "文案完成后会继续生成两张高质量竖版宣传图。"),
  );
  promotionImages.replaceChildren();
  [1, 2].forEach((index) => {
    const placeholder = element("div", "promotion-image-placeholder is-loading");
    placeholder.append(
      element("span", "", String(index).padStart(2, "0")),
      element("small", "", "AI 图片生成中"),
    );
    promotionImages.append(placeholder);
  });

  let progress = 12;
  const progressTimer = window.setInterval(() => {
    progress = Math.min(90, progress + (progress < 55 ? 7 : 3));
    const generatingImages = progress >= 45;
    setCreationProgress(
      progress,
      generatingImages ? "正在生成宣传图片" : "正在策划宣传文案",
      generatingImages ? "保持产品外观，生成两套原创竖版视觉" : "提炼标题、正文和视觉创意",
    );
  }, 2500);

  try {
    const formData = new FormData();
    formData.append("product_brief", state.productBrief.trim());
    formData.append("analysis_json", JSON.stringify(state.analysis));
    state.productImages.forEach(({ file }) => formData.append("images", file, file.name));
    const response = await fetch("/api/generate-promotion", {
      method: "POST",
      body: formData,
    });
    const result = await parseResponse(response);
    state.promotion = result;
    renderPromotion(result);
    setCreationProgress(
      100,
      "宣传内容生成完成",
      `${result.text_model} 文案 · ${result.image_model} 图片 · ${result.images.length} 个方案`,
    );
  } catch (error) {
    const detail = error.hint ? `${error.message} ${error.hint}` : error.message;
    showCreationMessage(detail);
    setCreationProgress(0, "生成未完成", "未使用本地或模拟结果，请检查 AI 服务后重试");
    promotionCopy.className = "promotion-copy is-empty";
    promotionCopy.replaceChildren(
      element("strong", "", "真实 AI 生成失败"),
      element("p", "", "调整配置或素材后可重新生成。"),
    );
  } finally {
    window.clearInterval(progressTimer);
    state.generating = false;
    generatePromotionButton.lastElementChild.textContent = state.promotion
      ? "重新生成"
      : "生成宣传内容";
    updateCreationReadiness();
  }
}

function renderSummary(items) {
  summaryList.replaceChildren();
  items.forEach((item) => summaryList.append(element("li", "", item)));
}

function insightCards(items) {
  const grid = element("div", "insight-grid");
  items.forEach((item, index) => {
    const card = element("article", "insight-card");
    card.append(
      element("span", "insight-index", String(index + 1).padStart(2, "0")),
      element("h3", "", item.title),
      element("p", "", item.description),
    );
    grid.append(card);
  });
  return grid;
}

function renderTitleAnalysis(data) {
  const wrapper = element("div", "tab-panel");
  wrapper.append(
    sectionTitle("标题规律分析", `基于 ${data.source_count} 篇高互动笔记，提取高频词、模板和表达特点`),
  );
  const topGrid = element("div", "title-analysis-grid");

  const cloudCard = element("article", "analysis-card keyword-card");
  cloudCard.append(element("h3", "", "标题关键词 TOP 20"));
  const cloud = element("div", "keyword-cloud");
  data.keywords.forEach((item) => {
    const word = element("span", `weight-${item.weight}`, item.term);
    word.title = `出现权重 ${item.count}`;
    cloud.append(word);
  });
  cloudCard.append(cloud, element("small", "card-note", "词频综合标题、标签和可见正文计算"));

  const templateCard = element("article", "analysis-card");
  templateCard.append(element("h3", "", "高互动标题模板"));
  const templateList = element("ol", "template-list");
  data.title_templates.forEach((item) => {
    const row = element("li");
    const copy = element("div");
    copy.append(element("strong", "", item.template), element("small", "", `示例：${item.example}`));
    row.append(copy, element("span", "evidence-count", `${item.evidence_count} 篇`));
    templateList.append(row);
  });
  templateCard.append(templateList);

  topGrid.append(cloudCard, templateCard);
  wrapper.append(topGrid, sectionTitle("标题特点", "可直接用于内容选题与标题改写"));
  wrapper.append(insightCards(data.title_traits));
  return wrapper;
}

function sectionTitle(title, description) {
  const heading = element("div", "panel-heading");
  heading.append(element("h2", "", title), element("p", "", description));
  return heading;
}

function renderMetricCards(metrics) {
  const grid = element("div", "metric-grid");
  [
    ["平均点赞", metrics.average_likes, "♥"],
    ["平均收藏", metrics.average_collects, "★"],
    ["平均评论", metrics.average_comments, "●"],
    ["平均综合互动", metrics.average_engagement, "↗"],
  ].forEach(([label, value, icon], index) => {
    const card = element("article", `metric-card tone-${index + 1}`);
    const bar = element("div", "metric-bar");
    bar.style.width = `${Math.min(92, 42 + index * 13)}%`;
    card.append(
      element("span", "metric-label", `${icon} ${label}`),
      element("strong", "", formatCount(value)),
      bar,
    );
    grid.append(card);
  });
  return grid;
}

function renderMetricsOverview(data) {
  metricsOverviewMeta.textContent =
    `基于 ${data.source_count} 篇高互动图文 · 点赞、收藏、评论均为样本平均值`;
  metricsOverviewContent.replaceChildren(renderMetricCards(data.metrics));
  metricsOverview.hidden = false;
  scheduleSideNavUpdate();
}

function renderStandardTab(title, description, items, extra = null) {
  const wrapper = element("div", "tab-panel");
  wrapper.append(sectionTitle(title, description));
  if (extra) wrapper.append(extra);
  wrapper.append(insightCards(items));
  return wrapper;
}

function renderCopywritingAnalysis(data) {
  const wrapper = element("div", "tab-panel");
  wrapper.append(
    sectionTitle(
      "文案内容分析",
      "拆解开头钩子、用户痛点、卖点表达、信任证据、内容口吻和行动引导",
    ),
    insightCards(data.copywriting_insights),
    sectionTitle(
      "高互动文案骨架",
      "根据当前竞品样本整理的五段式写作结构，可用于后续内容创作",
    ),
    insightCards(data.copywriting_framework),
  );
  return wrapper;
}

function renderVisualList(title, description, items, className = "") {
  const section = element("section", `visual-list ${className}`.trim());
  section.append(sectionTitle(title, description));
  const list = element("ol");
  items.forEach((item) => list.append(element("li", "", item)));
  section.append(list);
  return section;
}

function renderVisualAnalysis(data) {
  const visual = data.visual_analysis;
  if (!visual || visual.status === "not_requested" || visual.status === "unavailable") {
    const message = visual?.status_message || "暂未启用图片视觉分析。";
    return renderStandardTab(
      "视觉洞察暂不可用",
      message,
      data.image_insights,
    );
  }

  const wrapper = element("div", "tab-panel visual-analysis");
  const strategy = visual.sample_strategy || {};
  wrapper.append(
    sectionTitle(
      "爆款视觉洞察",
      visual.status_message || "已基于封面与代表性配图提炼视觉规律",
    ),
    element(
      "p",
      "visual-sample-note",
      `分析样本：${strategy.cover_notes || 0} 张封面 · ${strategy.gallery_notes || 0} 篇图集 · 实际读取 ${strategy.sampled_images || 0} 张图片`,
    ),
  );

  if (visual.cover?.length) {
    wrapper.append(sectionTitle("封面图维度", "构图、主体、配色与首图点击要素"), insightCards(visual.cover));
  }
  if (visual.cover_formulas?.length) {
    wrapper.append(
      renderVisualList("可直接套用的封面公式", "将以下结构替换为产品卖点与真实场景", visual.cover_formulas, "formula-list"),
    );
  }
  if (visual.style?.length) {
    wrapper.append(sectionTitle("视觉风格", "色调、滤镜、角度与光影的品类共性"), insightCards(visual.style));
  }
  if (visual.in_image_copy?.length) {
    wrapper.append(sectionTitle("图内文案", "文字密度、视觉字体类别、布局与信息分层"), insightCards(visual.in_image_copy));
  }
  return wrapper;
}

function renderAnalysisTab(tab) {
  if (!state.analysis) return;
  const data = state.analysis;
  state.activeTab = tab;
  let panel;
  if (tab === "title") {
    panel = renderTitleAnalysis(data);
  } else if (tab === "content") {
    panel = renderStandardTab(
      "正文结构分析",
      "从篇幅、场景、分点和阅读节奏中提炼内容骨架",
      data.content_insights,
    );
  } else if (tab === "copywriting") {
    panel = renderCopywritingAnalysis(data);
  } else if (tab === "image") {
    panel = renderVisualAnalysis(data);
  } else if (tab === "interaction") {
    panel = renderStandardTab(
      "互动数据分析",
      "用点赞、收藏和评论判断内容吸引力与决策价值",
      data.interaction_insights,
    );
  } else if (tab === "competitors") {
    panel = renderStandardTab(
      "竞品表现对比",
      "比较各竞品的样本数量、平均互动表现和当前领先内容",
      data.competitor_insights,
    );
  } else {
    panel = renderStandardTab(
      "综合策略结论",
      "把样本洞察收束为下一步可执行内容方向",
      data.summary.map((description, index) => ({
        title: `策略 ${index + 1}`,
        description,
      })),
    );
  }
  analysisContent.replaceChildren(panel);
}

async function openDetail(note) {
  detailContent.replaceChildren(element("div", "detail-loading", "正在读取笔记详情…"));
  dialog.showModal();

  try {
    const response = await fetch("/api/notes/detail", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ web_url: note.web_url }),
    });
    const detail = await parseResponse(response);
    renderDetail(detail);
  } catch (error) {
    const text = error.hint ? `${error.message} ${error.hint}` : error.message;
    detailContent.replaceChildren(element("div", "detail-loading", text));
  }
}

function renderDetail(detail) {
  const layout = element("div", "detail-layout");
  const gallery = element("div", "detail-gallery");
  const galleryUrls = detail.image_urls?.length
    ? detail.image_urls
    : [detail.cover_url].filter(Boolean);
  if (galleryUrls.length) {
    galleryUrls.forEach((url, index) => {
      gallery.append(image(url, `${detail.title} - 图片 ${index + 1}`));
    });
  } else {
    gallery.append(element("div", "detail-loading", "这篇笔记没有可展示的图片"));
  }

  const info = element("article", "detail-info");
  const author = element("div", "detail-author");
  author.append(image(detail.author?.avatar_url, "", "author-avatar"));
  const authorText = element("div");
  authorText.append(
    element("strong", "", detail.author?.nickname || "未知作者"),
    element("small", "", detail.ip_location || "小红书作者"),
  );
  author.append(authorText);
  info.append(author, element("h2", "", detail.title || "无标题"));
  info.append(
    element("div", "detail-description", detail.description || "这篇笔记没有提供正文内容。"),
  );

  if (detail.tags?.length) {
    const tags = element("div", "tag-list");
    detail.tags.forEach((tag) => tags.append(element("span", "", `#${tag}`)));
    info.append(tags);
  }

  const stats = element("div", "detail-stats");
  [
    ["点赞", detail.stats?.likes],
    ["评论", detail.stats?.comments],
    ["收藏", detail.stats?.collects],
    ["分享", detail.stats?.shares],
  ].forEach(([label, value]) => {
    const item = element("span", "", label);
    item.prepend(element("strong", "", formatCount(value)));
    stats.append(item);
  });
  info.append(stats);

  const link = element("a", "original-link", "在小红书中打开 ↗");
  link.href = detail.web_url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  info.append(link);
  layout.append(gallery, info);
  detailContent.replaceChildren(layout);
}

async function loadSession() {
  try {
    const response = await fetch("/api/session");
    const data = await parseResponse(response);
    sessionStatus.className = "session-badge connected";
    sessionStatus.lastElementChild.textContent = `${data.nickname} · 已连接`;
  } catch (error) {
    sessionStatus.className = "session-badge error";
    sessionStatus.lastElementChild.textContent = "未连接小红书";
    sessionStatus.title = error.hint || error.message;
  }
}

function downloadReport() {
  if (!state.analysis) return;
  const blob = new Blob([state.analysis.report_markdown], {
    type: "text/markdown;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${state.keyword}-小红书竞品分析.md`;
  link.click();
  URL.revokeObjectURL(url);
}

function downloadAnalysisJson() {
  if (!state.analysis?.json_download_url) return;
  const link = document.createElement("a");
  link.href = state.analysis.json_download_url;
  link.download = `${state.keyword}-竞品分析.json`;
  link.click();
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const keyword = keywordInput.value.trim();
  if (!keyword) return;
  if (competitorInput.value.trim() && !addCompetitor(competitorInput.value)) return;
  if (!state.competitors.length) addCompetitor(keyword);
  state.keyword = keyword;
  runSearch();
});

competitorInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === "，" || event.key === ",") {
    event.preventDefault();
    addCompetitor(competitorInput.value.replace(/[，,]+$/, ""));
  } else if (event.key === "Backspace" && !competitorInput.value && state.competitors.length) {
    removeCompetitor(state.competitors.length - 1);
  }
});
addCompetitorButton.addEventListener("click", () => addCompetitor(competitorInput.value));

productBriefInput.addEventListener("input", () => {
  state.productBrief = productBriefInput.value;
  productBriefCount.textContent = `${productBriefInput.value.length} / 1200`;
  updateCreationReadiness();
});

productImagesInput.addEventListener("change", () => addProductImages(productImagesInput.files));
productImageDropzone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    productImagesInput.click();
  }
});
productImageDropzone.addEventListener("dragover", (event) => {
  event.preventDefault();
  productImageDropzone.classList.add("is-dragging");
});
productImageDropzone.addEventListener("dragleave", () => {
  productImageDropzone.classList.remove("is-dragging");
});
productImageDropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  productImageDropzone.classList.remove("is-dragging");
  addProductImages(event.dataTransfer.files);
});
window.addEventListener("beforeunload", () => {
  state.productImages.forEach((item) => URL.revokeObjectURL(item.previewUrl));
});

document.querySelectorAll("[data-keyword]").forEach((button) => {
  button.addEventListener("click", () => {
    keywordInput.value = button.dataset.keyword;
    state.competitors = [];
    addCompetitor(button.dataset.keyword);
    form.requestSubmit();
  });
});

collectionSort.addEventListener("change", () => {
  state.collectionSort = collectionSort.value;
  renderCollectionNotes();
});

document.querySelectorAll("[data-tab]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-tab]").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    renderAnalysisTab(button.dataset.tab);
  });
});

sideNavLinks.forEach((link) => {
  link.addEventListener("click", () => {
    const key = link.dataset.navKey;
    setActiveSideNav(key);
    setPipelineStepForNav(key);
  });
});
window.addEventListener("scroll", scheduleSideNavUpdate, { passive: true });
window.addEventListener("resize", scheduleSideNavUpdate);

analyzeButton.addEventListener("click", runAnalysis);
creationEntryButton.addEventListener("click", () => {
  creationSection.scrollIntoView({ behavior: "smooth", block: "start" });
  setStep(4);
});
generatePromotionButton.addEventListener("click", generatePromotion);
copyPromotionButton.addEventListener("click", async () => {
  const text = promotionCopyText();
  if (!text) return;
  await navigator.clipboard.writeText(text);
  copyPromotionButton.textContent = "已复制";
  window.setTimeout(() => {
    copyPromotionButton.textContent = "复制文案";
  }, 1400);
});
copyReportButton.addEventListener("click", async () => {
  if (!state.analysis) return;
  await navigator.clipboard.writeText(state.analysis.report_markdown);
  copyReportButton.textContent = "已复制";
  window.setTimeout(() => {
    copyReportButton.textContent = "复制报告";
  }, 1400);
});
downloadReportButton.addEventListener("click", downloadReport);
downloadJsonButton.addEventListener("click", downloadAnalysisJson);
closeDialogButton.addEventListener("click", () => dialog.close());
dialog.addEventListener("click", (event) => {
  if (event.target === dialog) dialog.close();
});

loadSession();
updateCreationReadiness();
scheduleSideNavUpdate();
