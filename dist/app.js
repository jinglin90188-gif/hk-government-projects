const CATEGORY_ORDER = ["全部", "中央入口", "部门招标", "政策局及机构", "招标预报", "已批合约"];
const QUICK_NAMES = [
  "政府物流服务署——电子投标箱",
  "政府电子投标系统",
  "政府主要采购预览",
  "运输署",
  "运输署——顾问研究及工程招标预报",
  "机电工程署",
  "全政府——中央批标查询",
  "发展局——工程及顾问招标总入口",
];

let items = [];
let activeCategory = "全部";

const search = document.querySelector("#search");
const clearSearch = document.querySelector("#clearSearch");
const focusOnly = document.querySelector("#focusOnly");
const filters = document.querySelector("#categoryFilters");
const grid = document.querySelector("#linkGrid");
const quickGrid = document.querySelector("#quickLinks");
const resultCount = document.querySelector("#resultCount");
const emptyState = document.querySelector("#emptyState");

function badgeClass(category) {
  if (category === "招标预报") return "badge badge--forecast";
  if (category === "已批合约") return "badge badge--award";
  if (category === "部门招标") return "badge badge--tender";
  return "badge";
}

function linkCard(item) {
  const card = document.createElement("article");
  card.className = "link-card";
  const title = item.focus ? `<span class="focus-mark" title="重点部门">★</span>${item.name}` : item.name;
  card.innerHTML = `
    <div class="link-card__top">
      <h3>${title}</h3>
      <span class="${badgeClass(item.category)}">${item.category}</span>
    </div>
    <a href="${item.url}" target="_blank" rel="noopener noreferrer">打开政府官网 ↗</a>
  `;
  return card;
}

function renderFilters() {
  filters.replaceChildren();
  CATEGORY_ORDER.forEach(category => {
    const count = category === "全部" ? items.length : items.filter(item => item.category === category).length;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip";
    button.dataset.category = category;
    button.setAttribute("aria-pressed", String(category === activeCategory));
    button.textContent = `${category} ${count}`;
    button.addEventListener("click", () => {
      activeCategory = category;
      renderFilters();
      renderGrid();
    });
    filters.append(button);
  });
}

function renderGrid() {
  const keyword = search.value.trim().toLowerCase();
  const filtered = items.filter(item => {
    const categoryMatch = activeCategory === "全部" || item.category === activeCategory;
    const focusMatch = !focusOnly.checked || item.focus;
    const searchMatch = !keyword || `${item.name} ${item.category}`.toLowerCase().includes(keyword);
    return categoryMatch && focusMatch && searchMatch;
  });

  grid.replaceChildren(...filtered.map(linkCard));
  resultCount.textContent = `显示 ${filtered.length} / ${items.length} 个官方入口`;
  emptyState.hidden = filtered.length !== 0;
}

function renderQuickLinks() {
  const used = new Set();
  const selected = QUICK_NAMES.map(name => items.find(item => item.name === name && !used.has(item.url)))
    .filter(item => item && !used.has(item.url) && used.add(item.url));
  quickGrid.replaceChildren(...selected.map((item, index) => {
    const link = document.createElement("a");
    link.className = "quick-card";
    link.href = item.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.innerHTML = `
      <span class="quick-card__icon">${String(index + 1).padStart(2, "0")}</span>
      <strong>${item.name}</strong>
      <span>进入官网 ↗</span>
    `;
    return link;
  }));
}

search.addEventListener("input", renderGrid);
clearSearch.addEventListener("click", () => { search.value = ""; search.focus(); renderGrid(); });
focusOnly.addEventListener("change", renderGrid);

fetch("links.json")
  .then(response => {
    if (!response.ok) throw new Error("资料读取失败");
    return response.json();
  })
  .then(data => {
    items = data.items;
    document.querySelector("#updatedDate").textContent = data.updated;
    renderQuickLinks();
    renderFilters();
    renderGrid();
  })
  .catch(error => {
    resultCount.textContent = error.message;
    emptyState.hidden = false;
  });
