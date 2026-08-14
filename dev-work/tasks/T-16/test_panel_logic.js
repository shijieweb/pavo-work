/**
 * T-16 面板逻辑自测 (Node, 无第三方依赖).
 *
 * 做法: 从「实际生成的 training_panel.html」中抽出 <script> 块, 用最小 DOM stub
 * 真实执行, 然后逐条验证 AC-1/3/4/5/6 的状态机行为。
 * 不 mock 任何被测逻辑 —— 被测代码就是面板里跑的那份。
 *
 * 运行: node test_panel_logic.js
 */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const PANEL = path.join(
  "C:", "Users", "67972", "projects", "short-drama-training", "training_panel.html"
);

// ---------------------------------------------------------------------------
// 断言工具
// ---------------------------------------------------------------------------
let passed = 0;
const failures = [];
function check(name, cond, detail) {
  if (cond) {
    passed++;
    console.log("  [PASS] " + name);
  } else {
    failures.push(name + (detail ? "  -> " + detail : ""));
    console.log("  [FAIL] " + name + (detail ? "  -> " + detail : ""));
  }
}
function eq(name, got, want) {
  check(name, got === want, "got=" + JSON.stringify(got) + " want=" + JSON.stringify(want));
}

// ---------------------------------------------------------------------------
// 最小 DOM stub
// ---------------------------------------------------------------------------
class El {
  constructor(tag, opts) {
    opts = opts || {};
    this.tagName = tag;
    this.dataset = opts.dataset || {};
    this.role = opts.role || null;
    this.parentClass = opts.parentClass || null;
    this.parent = null;
    this.children = [];
    this._cls = new Set(opts.cls || []);
    this.style = {};
    this.hidden = false;
    this.textContent = opts.text || "";
    this._attrs = {};
    this.listeners = {};
  }
  get className() { return Array.from(this._cls).join(" "); }
  set className(v) {
    this._cls = new Set(String(v).split(/\s+/).filter(Boolean));
  }
  get classList() {
    const self = this;
    return {
      add: function () { for (const c of arguments) self._cls.add(c); },
      remove: function () { for (const c of arguments) self._cls.delete(c); },
      contains: function (c) { return self._cls.has(c); }
    };
  }
  setAttribute(k, v) { this._attrs[k] = String(v); }
  getAttribute(k) { return this._attrs[k] !== undefined ? this._attrs[k] : null; }
  appendChild(c) { c.parent = this; this.children.push(c); return c; }
  removeChild(c) {
    const i = this.children.indexOf(c);
    if (i >= 0) this.children.splice(i, 1);
    return c;
  }
  addEventListener(type, fn) {
    (this.listeners[type] = this.listeners[type] || []).push(fn);
  }
  click() { this.clicked = (this.clicked || 0) + 1; }
  fire(type, ev) { (this.listeners[type] || []).forEach((fn) => fn(ev)); }
  descendants() {
    const out = [];
    const walk = (n) => n.children.forEach((c) => { out.push(c); walk(c); });
    walk(this);
    return out;
  }
  matches(sel) {
    const roleM = sel.match(/^\[data-role="([^"]+)"\]$/);
    if (roleM) return this.role === roleM[1];
    if (sel === ".card") return this._cls.has("card");
    if (sel === ".group") return this._cls.has("group");
    if (sel === ".switch button[data-set]") {
      return this.tagName === "button" && this.parentClass === "switch" &&
             this.dataset.set !== undefined;
    }
    if (sel === ".group-switch button[data-group-set]") {
      return this.tagName === "button" && this.parentClass === "group-switch" &&
             this.dataset.groupSet !== undefined;
    }
    if (sel === ".switch button") {
      return this.tagName === "button" && this.parentClass === "switch";
    }
    if (sel === ".group-switch button") {
      return this.tagName === "button" && this.parentClass === "group-switch";
    }
    return false;
  }
  querySelector(sel) {
    return this.descendants().find((n) => n.matches(sel)) || null;
  }
  querySelectorAll(sel) {
    return this.descendants().filter((n) => n.matches(sel));
  }
  closest(sel) {
    let n = this;
    while (n) { if (n.matches && n.matches(sel)) return n; n = n.parent; }
    return null;
  }
}

// ---- 依据真实面板结构 (27 组 x 2 图) 搭建 DOM ----
const GROUPS = [];
for (let g = 1; g <= 27; g++) GROUPS.push(String(g));
const pad = (n) => String(n).padStart(2, "0");

const root = new El("div", { cls: ["root"] });
const groupsEl = new El("div", { cls: ["groups-container"] });
root.appendChild(groupsEl);
const byId = { groups: groupsEl };
const cardsByFile = {};

GROUPS.forEach((g) => {
  const grp = new El("div", { cls: ["group"], dataset: { writing: g } });
  groupsEl.appendChild(grp);
  grp.appendChild(new El("span", {
    role: "group-state-tag", cls: ["group-state-tag", "pending"], text: "待定"
  }));
  const badge = new El("span", { role: "dual-badge", cls: ["dual-badge"] });
  badge.hidden = true;
  grp.appendChild(badge);
  ["reject", "pending", "adopt"].forEach((s) => {
    grp.appendChild(new El("button", {
      dataset: { groupSet: s }, parentClass: "group-switch"
    }));
  });
  grp.appendChild(new El("span", { role: "group-meta" }));

  for (let i = 1; i <= 2; i++) {
    const file = "w" + pad(Number(g)) + "_" + i + ".png";
    const card = new El("div", { cls: ["card"], dataset: { file: file, writing: g } });
    grp.appendChild(card);
    card.appendChild(new El("span", {
      role: "state-tag", cls: ["state-tag", "discard"], text: "弃"
    }));
    card.appendChild(new El("div", {
      role: "prompt-zh", text: "同一个齐肩黑发年轻女性[ZH-" + file + "]"
    }));
    card.appendChild(new El("div", {
      role: "prompt-en", text: "the same young woman [EN-" + file + "]"
    }));
    ["primary", "backup", "discard"].forEach((s) => {
      card.appendChild(new El("button", {
        dataset: { set: s }, parentClass: "switch"
      }));
    });
    cardsByFile[file] = card;
  }
});

[
  "stat-total", "stat-adopt", "stat-reject", "stat-rate",
  "stat-group-adopt", "stat-dual",
  "lb-stage", "lb-file", "lb-meta", "lb-zh", "lb-en",
  "btn-adopt-all", "btn-clear-all", "btn-export-json", "btn-export-csv"
].forEach((id) => { byId[id] = new El("div"); });

const lightbox = new El("div", { cls: ["lightbox"] });
lightbox.hidden = true;
byId["lightbox"] = lightbox;

function mkSelect(id, val) {
  const s = new El("select");
  s.value = val;
  byId[id] = s;
  return s;
}
mkSelect("filter-writing", "all");
mkSelect("filter-imgstate", "all");
mkSelect("filter-groupstate", "all");

const refGrid = new El("div", { cls: ["ref-grid"] });

// ---- localStorage / 对话框 / Blob stub ----
const lsData = new Map();
const localStorage = {
  getItem: (k) => (lsData.has(k) ? lsData.get(k) : null),
  setItem: (k, v) => lsData.set(k, String(v)),
  removeItem: (k) => lsData.delete(k)
};

const calls = { alert: [], confirm: [], blob: [] };
let confirmReturn = true;

const documentStub = {
  body: new El("body"),
  listeners: {},
  getElementById: (id) => byId[id] || null,
  querySelector: (sel) => {
    if (sel === ".ref-grid") return refGrid;
    return root.querySelector(sel);
  },
  querySelectorAll: (sel) => root.querySelectorAll(sel),
  createElement: (tag) => new El(tag),
  addEventListener: function (t, fn) {
    (this.listeners[t] = this.listeners[t] || []).push(fn);
  }
};

const sandbox = {
  document: documentStub,
  localStorage: localStorage,
  console: console,
  alert: (m) => calls.alert.push(String(m)),
  confirm: (m) => { calls.confirm.push(String(m)); return confirmReturn; },
  setTimeout: () => 0,
  Blob: function (parts) { calls.blob.push(parts.join("")); this.parts = parts; },
  URL: { createObjectURL: () => "blob:stub", revokeObjectURL: () => {} },
  JSON: JSON, Object: Object, Array: Array, String: String, Number: Number,
  Math: Math, Date: Date, globalThis: null
};
sandbox.globalThis = sandbox;
sandbox.window = sandbox;

// ---------------------------------------------------------------------------
// 抽出面板 JS 并执行
// ---------------------------------------------------------------------------
const htmlText = fs.readFileSync(PANEL, "utf8");
const start = htmlText.indexOf("<script>");
const end = htmlText.indexOf("</script>", start);
if (start < 0 || end < 0) { console.error("未找到 <script> 块"); process.exit(1); }
let js = htmlText.slice(start + "<script>".length, end);

// 把词法作用域里的内部函数导出, 供测试调用 (const/let 不会自动挂到全局)
js += `
globalThis.__T = {
  getImgState, getGroupState, setImgState, setGroupState,
  isDualGood, goodFiles, primaryFiles, backupFiles, filesOf,
  normalizeGroup, normalizeAllGroups, bulkAdoptAll, bulkClearAll,
  groupRecord, exportJson, exportCsv, updateStats, applyFilters,
  openLightbox, closeLightbox, readPrompt,
  GROUP_KEYS, ITEMS, getStore: function(){ return store; },
  lbEl: lb, lbImgEl: lbImg
};
`;

const ctx = vm.createContext(sandbox);
try {
  vm.runInContext(js, ctx, { filename: "training_panel.inline.js" });
} catch (e) {
  console.error("面板 JS 执行失败: " + e.message);
  console.error(e.stack);
  process.exit(1);
}
const T = sandbox.__T;

console.log("\n=== T-16 面板逻辑自测 ===\n");
console.log("[0] 面板 JS 载入");
eq("JS 语法正确并成功执行 (无异常)", typeof T.setImgState, "function");
eq("ITEMS 条数", T.ITEMS.length, 54);
eq("GROUP_KEYS 组数", T.GROUP_KEYS.length, 27);

// ---------------------------------------------------------------------------
console.log("\n[1] 初始状态");
eq("初始 stat-total", byId["stat-total"].textContent, 54);
eq("初始已采纳图 = 0", byId["stat-adopt"].textContent, 0);
eq("初始未采纳图 = 54", byId["stat-reject"].textContent, 54);
eq("初始写法号采纳数 = 0/27", byId["stat-group-adopt"].textContent, "0/27");
eq("初始双图优数 = 0", byId["stat-dual"].textContent, 0);
eq("初始图状态 = discard", T.getImgState("w01_1.png"), "discard");
eq("初始组状态 = pending", T.getGroupState("1"), "pending");

// ---------------------------------------------------------------------------
console.log("\n[2] AC-4 单张标好: 不触发自动采纳");
T.setImgState("w01_1.png", "primary");
eq("w01_1 = primary", T.getImgState("w01_1.png"), "primary");
eq("组1 仍为 pending (仅 1 张好图, 非双图优)", T.getGroupState("1"), "pending");
eq("组1 主图数 = 1", T.primaryFiles("1").length, 1);
eq("组1 未判定为双图优", T.isDualGood("1"), false);

// ---------------------------------------------------------------------------
console.log("\n[3] AC-4 两张都好 -> 自动「采纳·双图优」+ 强制唯一主图");
T.setImgState("w01_2.png", "backup");
eq("组1 自动升为 adopt", T.getGroupState("1"), "adopt");
eq("组1 双图优 = true", T.isDualGood("1"), true);
eq("组1 主图恰好 1 张", T.primaryFiles("1").length, 1);
eq("组1 主图 = w01_1.png", T.primaryFiles("1")[0], "w01_1.png");
eq("组1 备选 = w01_2.png", T.backupFiles("1")[0], "w01_2.png");
eq("双图优角标已显示", GROUPS.length && groupsEl.children[0].querySelector('[data-role="dual-badge"]').hidden, false);
eq("组状态角标文案", groupsEl.children[0].querySelector('[data-role="group-state-tag"]').textContent, "采纳");
check("组 meta 含主图/备选文件名",
  groupsEl.children[0].querySelector('[data-role="group-meta"]').textContent.indexOf("w01_1.png") >= 0 &&
  groupsEl.children[0].querySelector('[data-role="group-meta"]').textContent.indexOf("w01_2.png") >= 0,
  groupsEl.children[0].querySelector('[data-role="group-meta"]').textContent);

// ---------------------------------------------------------------------------
console.log("\n[4] AC-4 唯一主图: 改设另一张为主图 -> 原主图自动降为备选");
T.setImgState("w01_2.png", "primary");
eq("w01_2 = primary", T.getImgState("w01_2.png"), "primary");
eq("w01_1 自动降级为 backup", T.getImgState("w01_1.png"), "backup");
eq("组1 主图仍恰好 1 张", T.primaryFiles("1").length, 1);
eq("组1 仍为 adopt", T.getGroupState("1"), "adopt");
eq("组1 仍双图优", T.isDualGood("1"), true);

// ---------------------------------------------------------------------------
console.log("\n[5] AC-4 两张都标「备选」-> 仍强制恰好 1 张主图");
T.setImgState("w02_1.png", "backup");
T.setImgState("w02_2.png", "backup");
eq("组2 自动 adopt", T.getGroupState("2"), "adopt");
eq("组2 双图优", T.isDualGood("2"), true);
eq("组2 主图恰好 1 张 (首张好图自动升主图)", T.primaryFiles("2").length, 1);
eq("组2 好图数 = 2", T.goodFiles("2").length, 2);

// ---------------------------------------------------------------------------
console.log("\n[6] AC-4 采纳门槛: 无好图不得采纳");
const alertsBefore = calls.alert.length;
T.setGroupState("5", "adopt");
check("弹出阻断提示", calls.alert.length === alertsBefore + 1, "alerts=" + calls.alert.length);
eq("组5 仍为 pending (采纳被拒绝)", T.getGroupState("5"), "pending");

// ---------------------------------------------------------------------------
console.log("\n[7] AC-4 单张备选 + 手工采纳 -> 自动补主图 (保证导出必有主图)");
T.setImgState("w06_1.png", "backup");
T.setGroupState("6", "adopt");
eq("组6 = adopt", T.getGroupState("6"), "adopt");
eq("组6 主图恰好 1 张", T.primaryFiles("6").length, 1);
eq("组6 主图 = w06_1.png", T.primaryFiles("6")[0], "w06_1.png");
eq("组6 非双图优 (只有 1 张好图)", T.isDualGood("6"), false);
eq("组6 导出主图非空", T.groupRecord("6").primary_file, "w06_1.png");

// ---------------------------------------------------------------------------
console.log("\n[8] AC-4 双图优改判: confirm=false 不改动");
confirmReturn = false;
const g1Before = JSON.stringify([T.getGroupState("1"), T.getImgState("w01_1.png"), T.getImgState("w01_2.png")]);
T.setGroupState("1", "reject");
eq("取消后组1 状态不变", JSON.stringify([T.getGroupState("1"), T.getImgState("w01_1.png"), T.getImgState("w01_2.png")]), g1Before);

console.log("\n[9] AC-4 双图优改判: confirm=true -> 图片重置并改判");
confirmReturn = true;
T.setGroupState("1", "reject");
eq("组1 = reject", T.getGroupState("1"), "reject");
eq("组1 图片重置为 discard", T.getImgState("w01_1.png"), "discard");
eq("组1 不再双图优", T.isDualGood("1"), false);
eq("组1 好图数 = 0", T.goodFiles("1").length, 0);

// ---------------------------------------------------------------------------
console.log("\n[10] AC-6 持久化");
const rawSaved = localStorage.getItem("training_panel_adoption_batch001_v2");
check("localStorage 已写入", !!rawSaved);
const parsedSaved = JSON.parse(rawSaved || "{}");
check("含 imgState 键", !!parsedSaved.imgState);
check("含 groupState 键", !!parsedSaved.groupState);
eq("持久化的组1决策", parsedSaved.groupState["1"], "reject");

// ---------------------------------------------------------------------------
console.log("\n[11] AC-3/5 批量全选采纳");
T.bulkAdoptAll();
eq("已采纳图 = 54", byId["stat-adopt"].textContent, 54);
eq("未采纳图 = 0", byId["stat-reject"].textContent, 0);
eq("采纳率 = 100%", byId["stat-rate"].textContent, "100%");
eq("写法号采纳数 = 27/27", byId["stat-group-adopt"].textContent, "27/27");
eq("双图优数 = 27", byId["stat-dual"].textContent, 27);
let uniqPrimaryOk = true, adoptHasPrimary = true;
T.GROUP_KEYS.forEach((g) => {
  if (T.primaryFiles(g).length !== 1) uniqPrimaryOk = false;
  if (T.getGroupState(g) === "adopt" && T.primaryFiles(g).length !== 1) adoptHasPrimary = false;
});
check("全部 27 组均恰好 1 张主图 (不变量)", uniqPrimaryOk);
check("所有采纳组均有唯一主图", adoptHasPrimary);

// ---------------------------------------------------------------------------
console.log("\n[12] AC-6 导出 CSV: 1 行/组");
calls.blob.length = 0;
T.exportCsv();
const csvText = calls.blob[calls.blob.length - 1];
const csvLines = csvText.replace(/^\ufeff/, "").split("\r\n").filter((l) => l.length);
eq("CSV 行数 = 1 表头 + 27 组", csvLines.length, 28);
eq("CSV 表头", csvLines[0], '"写法号","组决策","主图文件名","备选文件名","图片数","采纳图片数"');
const csvCols = csvLines[1].split('","').length;
eq("CSV 列数 = 6", csvCols, 6);
check("CSV 首行组决策含「采纳」与「双图优」", csvLines[1].indexOf("采纳") >= 0 && csvLines[1].indexOf("双图优") >= 0, csvLines[1]);
check("CSV 首行含主图文件名 w01_", csvLines[1].indexOf("w01_") >= 0, csvLines[1]);
check("CSV 带 UTF-8 BOM (Excel 中文不乱码)", csvText.charCodeAt(0) === 0xfeff);

// ---------------------------------------------------------------------------
console.log("\n[13] AC-6 导出 JSON: 含组层级 + 图层级");
calls.blob.length = 0;
T.exportJson();
const jsonPayload = JSON.parse(calls.blob[calls.blob.length - 1]);
eq("groups 长度 = 27", jsonPayload.groups.length, 27);
eq("images 长度 = 54", jsonPayload.images.length, 54);
eq("summary.total_groups", jsonPayload.summary.total_groups, 27);
eq("summary.adopted_groups", jsonPayload.summary.adopted_groups, 27);
eq("summary.dual_good_groups", jsonPayload.summary.dual_good_groups, 27);
eq("summary.adopted_images", jsonPayload.summary.adopted_images, 54);
const gr0 = jsonPayload.groups[0];
check("组记录含 写法号/决策/主图/备选",
  gr0.writing_no !== undefined && gr0.group_state !== undefined &&
  gr0.primary_file !== undefined && gr0.backup_files !== undefined,
  JSON.stringify(gr0));
eq("组记录主图非空", gr0.primary_file.length > 0, true);
eq("组记录备选数 = 1", gr0.backup_files.length, 1);
const im0 = jsonPayload.images[0];
check("图记录含中文 prompt (自 DOM 读取)", im0.prompt_zh.indexOf("同一个齐肩黑发") >= 0, im0.prompt_zh);
check("图记录含英文 prompt (自 DOM 读取)", im0.prompt.indexOf("the same young woman") >= 0, im0.prompt);

// ---------------------------------------------------------------------------
console.log("\n[14] AC-1 lightbox");
eq("初始 lightbox 隐藏", T.lbEl.hidden, true);
T.openLightbox("w03_1.png");
eq("打开后 lightbox 可见", T.lbEl.hidden, false);
eq("大图 src 指向该图相对路径", T.lbImgEl.src.indexOf("w03_1.png") >= 0, true);
eq("lightbox 文件名", byId["lb-file"].textContent, "w03_1.png");
check("lightbox 显示中文 prompt", byId["lb-zh"].textContent.indexOf("同一个齐肩黑发") >= 0, byId["lb-zh"].textContent);
check("lightbox 显示英文 prompt", byId["lb-en"].textContent.indexOf("the same young woman") >= 0, byId["lb-en"].textContent);
check("lightbox meta 含写法号与状态", byId["lb-meta"].textContent.indexOf("写法号 3") >= 0, byId["lb-meta"].textContent);
eq("打开时锁定 body 滚动", documentStub.body.style.overflow, "hidden");

// ESC 关闭
(documentStub.listeners["keydown"] || []).forEach((fn) => fn({ key: "Escape" }));
eq("ESC 关闭 lightbox", T.lbEl.hidden, true);
eq("关闭后恢复 body 滚动", documentStub.body.style.overflow, "");

// 点空白 (backdrop) 关闭
T.openLightbox("w04_2.png");
eq("再次打开", T.lbEl.hidden, false);
const backdrop = new El("div", { role: "lb-close" });
lightbox.appendChild(backdrop);
lightbox.fire("click", { target: backdrop });
eq("点空白处关闭 lightbox", T.lbEl.hidden, true);

// 点缩略图打开 (走真实事件委托)
const thumb = new El("img", { role: "thumb" });
cardsByFile["w07_1.png"].appendChild(thumb);
groupsEl.fire("click", { target: thumb });
eq("点缩略图经事件委托打开 lightbox", T.lbEl.hidden, false);
eq("lightbox 文件名 = w07_1.png", byId["lb-file"].textContent, "w07_1.png");
T.closeLightbox();

// ---------------------------------------------------------------------------
console.log("\n[15] 事件委托: 图/组三态按钮");
const primBtn = cardsByFile["w09_1.png"].querySelectorAll(".switch button")
  .find((b) => b.dataset.set === "primary");
groupsEl.fire("click", { target: primBtn });
eq("点「主图」按钮生效", T.getImgState("w09_1.png"), "primary");
const rejBtn = groupsEl.children[8].querySelectorAll(".group-switch button")
  .find((b) => b.dataset.groupSet === "reject");
confirmReturn = true;
groupsEl.fire("click", { target: rejBtn });
eq("点组「不采纳」按钮生效", T.getGroupState("9"), "reject");

// ---------------------------------------------------------------------------
console.log("\n[16] 批量全部清除 + 不变量总扫");
T.bulkClearAll();
eq("清除后已采纳图 = 0", byId["stat-adopt"].textContent, 0);
eq("清除后写法号采纳数 = 0/27", byId["stat-group-adopt"].textContent, "0/27");
eq("清除后双图优数 = 0", byId["stat-dual"].textContent, 0);
eq("清除后 localStorage 已移除", localStorage.getItem("training_panel_adoption_batch001_v2"), null);
let invOk = true, invMsg = "";
T.ITEMS.forEach((it) => {
  if (T.getImgState(it.file) !== "discard") { invOk = false; invMsg = it.file; }
});
check("全部 54 图回到 discard", invOk, invMsg);

// 不变量: 任意随机操作序列后, 每组主图数 <= 1; 采纳组主图 == 1
const rnd = (() => { let s = 42; return () => (s = (s * 1103515245 + 12345) % 2147483648) / 2147483648; })();
const states = ["primary", "backup", "discard"];
for (let i = 0; i < 400; i++) {
  const g = T.GROUP_KEYS[Math.floor(rnd() * 27)];
  const files = T.filesOf(g);
  const f = files[Math.floor(rnd() * files.length)];
  if (rnd() < 0.75) {
    T.setImgState(f, states[Math.floor(rnd() * 3)]);
  } else {
    T.setGroupState(g, ["reject", "pending", "adopt"][Math.floor(rnd() * 3)]);
  }
}
let vio1 = 0, vio2 = 0, vio3 = 0;
T.GROUP_KEYS.forEach((g) => {
  if (T.primaryFiles(g).length > 1) vio1++;
  if (T.getGroupState(g) === "adopt" && T.primaryFiles(g).length !== 1) vio2++;
  if (T.isDualGood(g) && T.getGroupState(g) !== "adopt") vio3++;
});
eq("400 次随机操作后: 无组出现多主图", vio1, 0);
eq("400 次随机操作后: 采纳组必有唯一主图", vio2, 0);
eq("400 次随机操作后: 双图优组必为采纳", vio3, 0);

// ---------------------------------------------------------------------------
console.log("\n===== 汇总 =====");
console.log("通过: " + passed + " 条");
console.log("失败: " + failures.length + " 条");
if (failures.length) {
  failures.forEach((f) => console.log("  - " + f));
  process.exit(1);
}
console.log("[结果] T-16 面板逻辑自测全部通过 ✔");
process.exit(0);
