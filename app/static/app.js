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
const metricsOverview = $("#metrics-overview");
const metricsOverviewMeta = $("#metrics-overview-meta");
const metricsOverviewContent = $("#metrics-overview-content");
const copyReportButton = $("#copy-report");
const downloadReportButton = $("#download-report");
const dialog = $("#detail-dialog");
const detailContent = $("#detail-content");
const closeDialogButton = $("#close-dialog");
const sideNavLinks = Array.from(document.querySelectorAll(".side-nav [data-nav-key]"));
const competitorTabs = $("#competitor-tabs");
const collectionSort = $("#collection-sort");
const hotTagList = $("#hot-tag-list");
const monitoringSection = $("#monitoring");
const monitoringCreateForm = $("#monitoring-create-form");
const monitoringUrlInput = $("#monitoring-url");
const monitoringMessage = $("#monitoring-message");
const monitoringTaskList = $("#monitoring-task-list");
const monitoringDashboard = $("#monitoring-dashboard");
const monitoringMetricCards = $("#monitoring-metric-cards");
const monitoringChart = $("#monitoring-chart");
const monitoringRefreshButton = $("#monitoring-refresh");
const monitoringDeleteButton = $("#monitoring-delete");

const state = {
  keyword: "",
  competitors: [],
  loading: false,
  analyzing: false,
  notes: [],
  analysis: null,
  activeTab: "title",
  activeCompetitor: "all",
  collectionSort: "heat",
  monitoringTasks: [],
  monitoringTask: null,
  monitoringMetric: "likes",
  monitoringRange: "30d",
  monitoringChart: null,
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
  if (monitoringSection.offsetTop <= marker) activeKey = "monitoring";

  setActiveSideNav(activeKey);
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
  state.notes = [];
  hideMessage();
  searchButton.disabled = true;
  searchButton.firstElementChild.textContent = "采集中…";
  analyzeButton.disabled = true;
  resultsGrid.replaceChildren();
  renderSkeletons();
  analysisSection.hidden = true;
  metricsOverview.hidden = true;
  setStep(2);

  resultsSection.hidden = false;
  resultsTitle.textContent = `“${state.keyword}” 的高互动图文`;
  resultsMeta.textContent = `正在采集：${state.competitors.join("、")}`;
  setCollectionProgress(
    18,
    "正在搜索竞品种草内容",
    `${state.competitors.length} 个竞品 · 合计上限 20 篇`,
  );
  resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
  scheduleSideNavUpdate();

  const progressTimer = window.setTimeout(() => {
    setCollectionProgress(68, "正在筛选与补全笔记详情", "排除测评、对比、避雷和合集内容");
  }, 600);

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
    resultsGrid.replaceChildren();
    const detail = error.hint ? `${error.message} ${error.hint}` : error.message;
    showMessage(detail);
    resultsMeta.textContent = "采集未完成";
    setCollectionProgress(0, "采集未完成", "请检查登录状态或更换竞品关键词");
  } finally {
    window.clearTimeout(progressTimer);
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

async function runAnalysis() {
  if (state.analyzing || !state.notes.length) return;
  state.analyzing = true;
  analyzeButton.disabled = true;
  analyzeButton.lastElementChild.textContent = "正在分析…";
  analysisSection.hidden = false;
  metricsOverview.hidden = true;
  setStep(3);
  setAnalysisProgress(28, "正在整理竞品样本", `已加载 ${state.notes.length} 篇高互动图文`);
  analysisContent.innerHTML = '<div class="analysis-loading"><span>✦</span><strong>AI 正在提炼爆款规律</strong><small>分析标题、正文结构、图片数量与互动表现</small></div>';
  analysisSection.scrollIntoView({ behavior: "smooth", block: "start" });
  scheduleSideNavUpdate();

  const progressTimer = window.setTimeout(() => {
    setAnalysisProgress(72, "正在生成竞品总结", "组合标题、内容、图片与互动洞察");
  }, 500);

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keyword: state.keyword, notes: state.notes }),
    });
    state.analysis = await parseResponse(response);
    setAnalysisProgress(
      100,
      "竞品规律分析完成",
      `已分析 ${state.analysis.source_count} 篇笔记 · ${state.analysis.mode_label}`,
    );
    analysisMode.textContent = state.analysis.analysis_mode === "ai" ? "AI 深度分析" : "本地规则分析";
    reportPreview.textContent = state.analysis.report_markdown;
    renderSummary(state.analysis.summary);
    renderMetricsOverview(state.analysis);
    copyReportButton.disabled = false;
    downloadReportButton.disabled = false;
    renderAnalysisTab(state.activeTab);
  } catch (error) {
    const detail = error.hint ? `${error.message} ${error.hint}` : error.message;
    analysisContent.replaceChildren(element("div", "analysis-empty error", detail));
    setAnalysisProgress(0, "分析未完成", "请检查服务配置后重试");
  } finally {
    window.clearTimeout(progressTimer);
    state.analyzing = false;
    analyzeButton.disabled = false;
    analyzeButton.lastElementChild.textContent = "重新生成分析";
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
    panel = renderStandardTab(
      "图片结构分析",
      "基于图组规模与图文组织方式生成素材建议",
      data.image_insights,
    );
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

function monitoringTaskId(task) {
  return task?.id || task?.task_id || "";
}

function monitoringSnapshots(task) {
  return [...(task?.snapshots || [])].sort(
    (left, right) => new Date(left.collected_at) - new Date(right.collected_at),
  );
}

function monitoringMetricValue(snapshot, metric = state.monitoringMetric) {
  return Number(snapshot?.[metric] || 0);
}

function showMonitoringMessage(text, kind = "error") {
  monitoringMessage.hidden = false;
  monitoringMessage.className = `monitoring-message ${kind}`;
  monitoringMessage.textContent = text;
}

function hideMonitoringMessage() {
  monitoringMessage.hidden = true;
  monitoringMessage.textContent = "";
}

function formatMonitoringDate(value) {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "numeric",
    day: "numeric",
  }).format(new Date(value));
}

function visibleMonitoringSnapshots(task) {
  const snapshots = monitoringSnapshots(task);
  if (state.monitoringRange === "all" || !snapshots.length) return snapshots;
  const days = state.monitoringRange === "7d" ? 7 : 30;
  const latest = new Date(snapshots[snapshots.length - 1].collected_at);
  const threshold = new Date(latest);
  threshold.setDate(threshold.getDate() - (days - 1));
  return snapshots.filter((snapshot) => new Date(snapshot.collected_at) >= threshold);
}

function renderMonitoringMetricCards(task) {
  monitoringMetricCards.replaceChildren();
  const latest = monitoringSnapshots(task).at(-1);
  [
    ["likes", "点赞"],
    ["collects", "收藏"],
    ["comments", "评论"],
  ].forEach(([metric, label]) => {
    const card = element("button", `monitoring-metric-card${metric === state.monitoringMetric ? " active" : ""}`);
    card.type = "button";
    card.dataset.monitoringMetric = metric;
    card.append(element("span", "", label), element("strong", "", formatCount(monitoringMetricValue(latest, metric))));
    monitoringMetricCards.append(card);
  });
}

function renderMonitoringTasks() {
  monitoringTaskList.replaceChildren();
  if (!state.monitoringTasks.length) {
    monitoringTaskList.append(element("p", "monitoring-empty", "尚未创建监测任务。"));
    return;
  }
  state.monitoringTasks.forEach((task) => {
    const active = monitoringTaskId(task) === monitoringTaskId(state.monitoringTask);
    const card = element("button", `monitoring-task-card${active ? " active" : ""}`);
    card.type = "button";
    card.append(
      element("strong", "", task.title || task.note_title || "已发布笔记"),
      element("span", "", task.status === "failed" ? "更新失败" : "监测中"),
      element("small", "", `${monitoringSnapshots(task).length} 条快照`),
    );
    card.addEventListener("click", () => openMonitoringTask(task));
    monitoringTaskList.append(card);
  });
}

function renderMonitoringChartMessage(message) {
  state.monitoringChart?.dispose();
  state.monitoringChart = null;
  monitoringChart.replaceChildren();
  monitoringChart.append(element("p", "monitoring-chart-empty", message));
}

function renderMonitoringChart(task) {
  const snapshots = visibleMonitoringSnapshots(task);
  if (snapshots.length < 2) {
    renderMonitoringChartMessage(
      snapshots.length
        ? "已记录首个快照，下一次更新后将展示趋势。"
        : "暂无互动快照，更新任务后将展示趋势。",
    );
    return;
  }
  if (!window.echarts) {
    renderMonitoringChartMessage("图表组件尚未加载。");
    return;
  }
  if (!state.monitoringChart) {
    monitoringChart.replaceChildren();
    state.monitoringChart = window.echarts.init(monitoringChart);
  }
  const labels = snapshots.map((snapshot) => formatMonitoringDate(snapshot.collected_at));
  const values = snapshots.map((snapshot) => monitoringMetricValue(snapshot));
  const option = {
    animation: !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    tooltip: {
      trigger: "axis",
      formatter: (items) => {
        const index = items[0]?.dataIndex || 0;
        const value = values[index];
        const delta = index ? value - values[index - 1] : null;
        const change = delta === null ? "首个可见快照" : `较前次 ${delta >= 0 ? "+" : ""}${delta}`;
        return `${labels[index]}（北京时间）<br />${items[0]?.marker || ""}${items[0]?.seriesName || "互动"}：${value}<br />${change}`;
      },
    },
    xAxis: { type: "category", data: labels },
    yAxis: { type: "value", minInterval: 1 },
    dataZoom: [{ type: "inside" }, { type: "slider", height: 18 }],
    series: [{
      name: { likes: "点赞", collects: "收藏", comments: "评论" }[state.monitoringMetric],
      type: "line",
      smooth: true,
      areaStyle: { opacity: 0.16 },
      data: values,
    }],
  };
  state.monitoringChart.setOption(option, true);
}

function openMonitoringTask(task) {
  state.monitoringTask = task;
  monitoringDashboard.hidden = false;
  renderMonitoringTasks();
  renderMonitoringMetricCards(task);
  document.querySelectorAll("[data-monitoring-metric]").forEach((button) => {
    button.classList.toggle("active", button.dataset.monitoringMetric === state.monitoringMetric);
  });
  document.querySelectorAll("[data-monitoring-range]").forEach((button) => {
    button.classList.toggle("active", button.dataset.monitoringRange === state.monitoringRange);
  });
  renderMonitoringChart(task);
}

async function loadMonitoringTasks() {
  try {
    const response = await fetch("/api/monitoring/tasks");
    const data = await parseResponse(response);
    state.monitoringTasks = Array.isArray(data) ? data : data.tasks || data.items || [];
    const selected = state.monitoringTasks.find(
      (task) => monitoringTaskId(task) === monitoringTaskId(state.monitoringTask),
    );
    renderMonitoringTasks();
    if (selected) openMonitoringTask(selected);
    else if (!state.monitoringTask) {
      const firstActive = state.monitoringTasks.find((task) => task.status !== "deleted" && task.status !== "completed");
      if (firstActive) openMonitoringTask(firstActive);
    }
  } catch (error) {
    showMonitoringMessage(error.hint ? `${error.message} ${error.hint}` : error.message);
  }
}

async function createMonitoringTask() {
  const webUrl = monitoringUrlInput.value.trim();
  if (!webUrl) return;
  hideMonitoringMessage();
  try {
    const response = await fetch("/api/monitoring/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ web_url: webUrl }),
    });
    const data = await parseResponse(response);
    const task = data.task || data;
    state.monitoringTask = task;
    monitoringUrlInput.value = "";
    await loadMonitoringTasks();
    openMonitoringTask(state.monitoringTasks.find((item) => monitoringTaskId(item) === monitoringTaskId(task)) || task);
  } catch (error) {
    showMonitoringMessage(error.hint ? `${error.message} ${error.hint}` : error.message);
  }
}

async function refreshMonitoringTask() {
  const id = monitoringTaskId(state.monitoringTask);
  if (!id) return;
  hideMonitoringMessage();
  monitoringRefreshButton.disabled = true;
  try {
    const response = await fetch(`/api/monitoring/tasks/${encodeURIComponent(id)}/refresh`, { method: "POST" });
    const data = await parseResponse(response);
    state.monitoringTask = data.task || data;
    await loadMonitoringTasks();
  } catch (error) {
    showMonitoringMessage(error.hint ? `${error.message} ${error.hint}` : error.message);
  } finally {
    monitoringRefreshButton.disabled = false;
  }
}

async function deleteMonitoringTask() {
  const id = monitoringTaskId(state.monitoringTask);
  if (!id || !window.confirm("删除后将永久移除该任务及全部历史快照，确定继续吗？")) return;
  hideMonitoringMessage();
  try {
    const response = await fetch(`/api/monitoring/tasks/${encodeURIComponent(id)}`, { method: "DELETE" });
    await parseResponse(response);
    state.monitoringTask = null;
    monitoringDashboard.hidden = true;
    if (state.monitoringChart) {
      state.monitoringChart.dispose();
      state.monitoringChart = null;
    }
    await loadMonitoringTasks();
  } catch (error) {
    showMonitoringMessage(error.hint ? `${error.message} ${error.hint}` : error.message);
  }
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
  link.addEventListener("click", () => setActiveSideNav(link.dataset.navKey));
});
window.addEventListener("scroll", scheduleSideNavUpdate, { passive: true });
window.addEventListener("resize", () => {
  scheduleSideNavUpdate();
  state.monitoringChart?.resize();
});

analyzeButton.addEventListener("click", runAnalysis);
copyReportButton.addEventListener("click", async () => {
  if (!state.analysis) return;
  await navigator.clipboard.writeText(state.analysis.report_markdown);
  copyReportButton.textContent = "已复制";
  window.setTimeout(() => {
    copyReportButton.textContent = "复制报告";
  }, 1400);
});
downloadReportButton.addEventListener("click", downloadReport);
closeDialogButton.addEventListener("click", () => dialog.close());
dialog.addEventListener("click", (event) => {
  if (event.target === dialog) dialog.close();
});
monitoringCreateForm.addEventListener("submit", (event) => {
  event.preventDefault();
  createMonitoringTask();
});
document.querySelectorAll("[data-monitoring-metric]").forEach((button) => {
  button.addEventListener("click", () => {
    state.monitoringMetric = button.dataset.monitoringMetric;
    if (state.monitoringTask) openMonitoringTask(state.monitoringTask);
  });
});
document.querySelectorAll("[data-monitoring-range]").forEach((button) => {
  button.addEventListener("click", () => {
    state.monitoringRange = button.dataset.monitoringRange;
    if (state.monitoringTask) openMonitoringTask(state.monitoringTask);
  });
});
monitoringRefreshButton.addEventListener("click", refreshMonitoringTask);
monitoringDeleteButton.addEventListener("click", deleteMonitoringTask);

loadSession();
loadMonitoringTasks();
scheduleSideNavUpdate();
