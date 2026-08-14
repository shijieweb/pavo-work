/**
 * T-16 QA 独立行为核验 (QA 自写, 不复用研发 test_panel_logic.js 的 DOM stub).
 *
 * 手法差异 (刻意与研发脚本不同, 保证独立性):
 *   研发: 手写 El 类模拟真实 DOM 树 -> 覆盖 UI 同步路径。
 *   QA  : Proxy 万能 stub 吞掉视图层, 只把「状态机 + 导出」当纯模型拷问,
 *         专打对抗性边界 (取消 confirm / 脏 localStorage / 采纳门槛回落 / 自定随机种子 fuzz)。
 *
 * 被测代码 = 从实际 training_panel.html 抽出的内联 JS, 未做任何改写。
 * 只读文件, 不改源码。
 *
 * 运行: node qa_verify_behavior.js   退出码 0=全通过 1=有 FAIL
 */
"use strict";

const fs = require("fs");
const vm = require("vm");

const PANEL = "C:\\Users\\67972\\projects\\short-drama-training\\training_panel.html";

let passed = 0;
const failures = [];
function check(name, cond, detail) {
  if (cond) { passed++; console.log("  [PASS] " + name); }
  else { failures.push(name + (detail ? "  -> " + detail : "")); console.log("  [FAIL] " + name + (detail ? "  -> " + detail : "")); }
}
function eq(name, got, want) {
  check(name, got === want, "got=" + JSON.stringify(got) + " want=" + JSON.stringify(want));
}

// ---------------------------------------------------------------------------
// Proxy 万能 DOM stub: 任何属性/调用都返回可继续链式访问的 stub, 永不抛错。
// ---------------------------------------------------------------------------
function stub(label) {
  const t = function () { return stub(label + "()"); };
  t.__label = label;
  t.__bag = {};
  return new Proxy(t, {
    get(target, prop) {
      if (prop === Symbol.toPrimitive) return () => "";
      if (prop === Symbol.iterator) return function* () {};
      if (prop === "then" || prop === "constructor") return undefined;
      if (prop === "length") return 0;
      if (prop in target.__bag) return target.__bag[prop];
      if (prop === "dataset" || prop === "style") return (target.__bag[prop] = {});
      if (prop === "textContent" || prop === "innerHTML" || prop === "value") return "";
      if (prop === "hidden") return true;
      return stub(label + "." + String(prop));
    },
    set(target, prop, v) { target.__bag[prop] = v; return true; },
    apply() { return stub(label + "()"); },
    has() { return true; },
  });
}

const memStore = new Map();
const localStorage = {
  getItem: (k) => (memStore.has(k) ? memStore.get(k) : null),
  setItem: (k, v) => memStore.set(k, String(v)),
  removeItem: (k) => memStore.delete(k),
};

let CONFIRM_ANSWER = true;         // QA 可控: confirm 返回值
const alerts = [];
const confirms = [];

const document = {
  // 关键: 返回真数组, 让 CARD_MAP / GROUP_MAP 为空但不崩 (视图层被 stub 掉)
  querySelectorAll: () => [],
  querySelector: () => stub("document.querySelector"),
  getElementById: () => stub("document.getElementById"),
  addEventListener: () => {},
  createElement: () => stub("document.createElement"),
  body: stub("document.body"),
  documentElement: stub("document.documentElement"),
};

const sandbox = {
  document,
  localStorage,
  window: { addEventListener: () => {}, matchMedia: () => stub("mm") },
  alert: (m) => { alerts.push(String(m)); },
  confirm: (m) => { confirms.push(String(m)); return CONFIRM_ANSWER; },
  console,
  Blob: function () { return stub("Blob"); },
  URL: { createObjectURL: () => "blob:qa", revokeObjectURL: () => {} },
  setTimeout, clearTimeout, JSON, Math, Date, Object, Array, String, Number, Boolean, Map, Set, RegExp, Error, isNaN, parseInt, parseFloat,
};
sandbox.globalThis = sandbox;
sandbox.window.document = document;
sandbox.window.localStorage = localStorage;

// ---------------------------------------------------------------------------
// 抽取内联 <script> 并注入 QA 探针 epilogue (同词法作用域, 故可见 const/let)
// ---------------------------------------------------------------------------
const html = fs.readFileSync(PANEL, "utf8");
const blocks = [];
const re = /<script\b([^>]*)>([\s\S]*?)<\/script>/gi;
let m;
while ((m = re.exec(html)) !== null) {
  if (/\bsrc\s*=/.test(m[1])) continue;
  blocks.push(m[2]);
}
console.log("抽出内联 <script> 块: " + blocks.length + " 个, 合计 " + blocks.reduce((a, b) => a + b.length, 0) + " 字符\n");

const epilogue = `
;globalThis.__QA__ = {
  get store() { return store; },
  reset: function () { store = { imgState: {}, groupState: {} }; saveStore(); },
  reloadFromStorage: function () { store = loadStore(); normalizeAllGroups(); },
  injectRaw: function (obj) { store = obj; normalizeAllGroups(); },
  setImgState: setImgState, setGroupState: setGroupState,
  getImgState: getImgState, getGroupState: getGroupState,
  isDualGood: isDualGood, filesOf: filesOf, goodFiles: goodFiles,
  primaryFiles: primaryFiles, backupFiles: backupFiles,
  groupRecord: groupRecord, bulkAdoptAll: bulkAdoptAll, bulkClearAll: bulkClearAll,
  exportCsv: exportCsv, exportJson: exportJson,
  GROUP_KEYS: GROUP_KEYS, GROUP_FILES: GROUP_FILES, FILE_GROUP: FILE_GROUP,
  IMG_STATES: IMG_STATES, GROUP_STATES: GROUP_STATES,
  STORAGE_KEY: STORAGE_KEY, DEFAULT_GROUP_STATE: DEFAULT_GROUP_STATE,
  ITEMS_LEN: ITEMS.length,
  lastDownload: null,
  muteViews: function () {
    syncGroup = function () {}; syncCard = function () {}; syncAll = function () {};
    updateStats = function () {}; applyFilters = function () {};
    download = function (n, c, t) { globalThis.__QA__.lastDownload = { name: n, content: c, mime: t }; };
  }
};
`;

const ctx = vm.createContext(sandbox);
try {
  vm.runInContext(blocks.join("\n;\n") + epilogue, ctx, { filename: "panel.inline.qa.js" });
} catch (e) {
  console.log("  [FATAL] 内联 JS 执行失败: " + e.message);
  process.exit(1);
}
const QA = sandbox.__QA__;
QA.muteViews();

console.log("[0] 模型装载");
eq("ITEMS 条数 = 54", QA.ITEMS_LEN, 54);
eq("GROUP_KEYS 长度 = 27", QA.GROUP_KEYS.length, 27);
check("每组恰好 2 张图", QA.GROUP_KEYS.every((g) => QA.filesOf(g).length === 2), "");

// ---------------------------------------------------------------------------
// 不变量扫描器 (QA 自定义, 独立于研发断言)
// ---------------------------------------------------------------------------
function violations() {
  const v = [];
  QA.GROUP_KEYS.forEach(function (g) {
    const prim = QA.primaryFiles(g).length;
    const good = QA.goodFiles(g).length;
    const st = QA.getGroupState(g);
    if (prim > 1) v.push("I1 组" + g + " 多主图=" + prim);
    if (st === "adopt" && good < 1) v.push("I2a 组" + g + " 采纳但0好图");
    if (st === "adopt" && prim !== 1) v.push("I2b 组" + g + " 采纳但主图数=" + prim);
    if (QA.isDualGood(g) && st !== "adopt") v.push("I3 组" + g + " 双图优但组态=" + st);
    QA.filesOf(g).forEach(function (f) {
      if (QA.IMG_STATES.indexOf(QA.getImgState(f)) < 0) v.push("I4 " + f + " 非法图态");
    });
    if (QA.GROUP_STATES.indexOf(st) < 0) v.push("I4 组" + g + " 非法组态");
  });
  return v;
}

// ---------------------------------------------------------------------------
console.log("\n[1] AC-4 门槛: 全弃组不得采纳");
QA.reset();
alerts.length = 0;
const g1 = "1", f1a = QA.filesOf("1")[0], f1b = QA.filesOf("1")[1];
QA.setGroupState(g1, "adopt");
eq("全弃组点采纳被拒, 组态保持默认", QA.getGroupState(g1), QA.DEFAULT_GROUP_STATE);
check("弹出规则 alert 提示",
  alerts.length === 1 && /至少有 1 张/.test(alerts[0]) && /主图/.test(alerts[0]) && /备选/.test(alerts[0]),
  JSON.stringify(alerts));

console.log("\n[2] AC-4 单张好图可采纳");
QA.setImgState(f1a, "primary");
QA.setGroupState(g1, "adopt");
eq("单主图组采纳成功", QA.getGroupState(g1), "adopt");
eq("主图数 = 1", QA.primaryFiles(g1).length, 1);
eq("非双图优", QA.isDualGood(g1), false);

console.log("\n[3] AC-4 核心「两张都可以」: 两张都设备选 -> 自动采纳+唯一主图");
QA.reset();
const g3 = "5", f3a = QA.filesOf("5")[0], f3b = QA.filesOf("5")[1];
QA.setImgState(f3a, "backup");
QA.setImgState(f3b, "backup");
eq("组自动升级为采纳", QA.getGroupState(g3), "adopt");
eq("识别为双图优", QA.isDualGood(g3), true);
eq("强制恰好 1 张主图", QA.primaryFiles(g3).length, 1);
eq("另一张为备选", QA.backupFiles(g3).length, 1);

console.log("\n[4] AC-4 两张都点「主图」-> 后点者为主图, 前者降备选");
QA.reset();
const g4 = "9", f4a = QA.filesOf("9")[0], f4b = QA.filesOf("9")[1];
QA.setImgState(f4a, "primary");
QA.setImgState(f4b, "primary");
eq("主图唯一", QA.primaryFiles(g4).length, 1);
eq("主图 = 后点击那张", QA.primaryFiles(g4)[0], f4b);
eq("先点那张降为备选", QA.getImgState(f4a), "backup");
eq("组态 = 采纳", QA.getGroupState(g4), "adopt");
eq("双图优", QA.isDualGood(g4), true);

console.log("\n[5] 对抗: 双图优组改判「不采纳」+ confirm 取消 -> 状态零变更");
QA.reset();
const g5 = "12", f5a = QA.filesOf("12")[0], f5b = QA.filesOf("12")[1];
QA.setImgState(f5a, "primary"); QA.setImgState(f5b, "backup");
const before5 = JSON.stringify([QA.getGroupState(g5), QA.getImgState(f5a), QA.getImgState(f5b)]);
CONFIRM_ANSWER = false; confirms.length = 0;
QA.setGroupState(g5, "reject");
const after5 = JSON.stringify([QA.getGroupState(g5), QA.getImgState(f5a), QA.getImgState(f5b)]);
check("触发二次确认弹窗", confirms.length === 1, "confirms=" + confirms.length);
eq("取消后状态完全不变", after5, before5);

console.log("\n[6] 双图优组改判「不采纳」+ confirm 同意 -> 图态全部重置为弃");
CONFIRM_ANSWER = true;
QA.setGroupState(g5, "reject");
eq("组态 = 不采纳", QA.getGroupState(g5), "reject");
eq("两张图均为弃", QA.goodFiles(g5).length, 0);
eq("无残留主图", QA.primaryFiles(g5).length, 0);
check("不留「采纳但0好图」矛盾", violations().length === 0, violations().join("; "));

console.log("\n[7] 采纳组撤掉唯一好图 -> 组态自动回落, 不留矛盾");
QA.reset();
const g7 = "19", f7a = QA.filesOf("19")[0];
QA.setImgState(f7a, "primary");
QA.setGroupState(g7, "adopt");
eq("先置为采纳", QA.getGroupState(g7), "adopt");
QA.setImgState(f7a, "discard");
eq("撤掉好图后组态回落默认", QA.getGroupState(g7), QA.DEFAULT_GROUP_STATE);
check("无不变量违例", violations().length === 0, violations().join("; "));

console.log("\n[8] AC-6 脏 localStorage 注入 -> normalize 后自愈");
QA.reset();
const dirty = { imgState: {}, groupState: {} };
dirty.groupState["3"] = "adopt";                       // 采纳但无好图
dirty.imgState[QA.filesOf("4")[0]] = "primary";
dirty.imgState[QA.filesOf("4")[1]] = "primary";        // 双主图
dirty.groupState["4"] = "reject";                      // 与双图优矛盾
dirty.imgState["w99_9.png"] = "primary";               // 不存在的文件
dirty.groupState["999"] = "adopt";                     // 不存在的组
QA.injectRaw(dirty);
eq("组3 采纳无好图 -> 回落", QA.getGroupState("3"), QA.DEFAULT_GROUP_STATE);
eq("组4 双主图 -> 收敛为 1", QA.primaryFiles("4").length, 1);
eq("组4 双图优 -> 强制采纳", QA.getGroupState("4"), "adopt");
check("脏数据注入后全局零违例", violations().length === 0, violations().join("; "));

console.log("\n[9] AC-6 localStorage 往返持久化");
QA.reset();
QA.setImgState(QA.filesOf("7")[0], "primary");
QA.setImgState(QA.filesOf("7")[1], "backup");
const raw = localStorage.getItem(QA.STORAGE_KEY);
check("localStorage 已写入", !!raw, "raw=" + raw);
QA.reloadFromStorage();
eq("重载后主图保持", QA.primaryFiles("7").length, 1);
eq("重载后备选保持", QA.backupFiles("7").length, 1);
eq("重载后组态 = 采纳", QA.getGroupState("7"), "adopt");

console.log("\n[10] AC-6 导出 CSV 真实内容 (含组决策+主图+备选)");
QA.reset();
QA.bulkAdoptAll();
QA.exportCsv();
const csv = QA.lastDownload && QA.lastDownload.content;
check("导出触发下载", !!csv, "");
const csvLines = String(csv).replace(/^\ufeff/, "").split("\r\n").filter(Boolean);
eq("CSV 行数 = 1 表头 + 27 组", csvLines.length, 28);
check("含 UTF-8 BOM", String(csv).charCodeAt(0) === 0xfeff, "首字符码=" + String(csv).charCodeAt(0));
check("表头含 写法号/组决策/主图文件名/备选文件名",
  /写法号/.test(csvLines[0]) && /组决策/.test(csvLines[0]) && /主图文件名/.test(csvLines[0]) && /备选文件名/.test(csvLines[0]),
  csvLines[0]);
const row1 = csvLines[1].split(",");
check("首行组决策含「采纳」", /采纳/.test(csvLines[1]), csvLines[1]);
check("首行含主图 png 文件名", /w\d{2}_\d\.png/.test(csvLines[1]), csvLines[1]);
const rowsMissingPrimary = csvLines.slice(1).filter((l) => !/w\d{2}_\d\.png/.test(l));
check("27 组导出行全部带主图文件名", rowsMissingPrimary.length === 0, "缺主图行数=" + rowsMissingPrimary.length);

console.log("\n[11] AC-6 导出 JSON 结构");
QA.exportJson();
const js = QA.lastDownload && QA.lastDownload.content;
let payload = null;
try { payload = JSON.parse(String(js)); } catch (e) { /* noop */ }
check("JSON 可解析", !!payload, "");
if (payload) {
  eq("groups 长度 = 27", payload.groups.length, 27);
  eq("images 长度 = 54", payload.images.length, 54);
  check("summary 含 dual_good_groups", "dual_good_groups" in payload.summary, JSON.stringify(payload.summary));
  const g0 = payload.groups[0];
  check("组记录含 写法号/组决策/主图/备选 四要素",
    "writing_no" in g0 && "group_state_label" in g0 && "primary_file" in g0 && "backup_files" in g0,
    JSON.stringify(g0).slice(0, 200));
  const noPrim = payload.groups.filter((r) => r.group_state === "adopt" && !r.primary_file);
  eq("无「采纳却无主图」的导出组", noPrim.length, 0);
}

console.log("\n[12] AC-4 不变量 fuzz (QA 自定种子, 1200 次随机操作)");
QA.reset();
let seed = 20260815;
function rnd() { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; }
const imgStates = QA.IMG_STATES.slice();
const grpStates = QA.GROUP_STATES.slice();
let worst = [];
let confirmFlips = 0;
for (let i = 0; i < 1200; i++) {
  CONFIRM_ANSWER = rnd() < 0.5;          // 随机同意/取消二次确认
  if (CONFIRM_ANSWER) confirmFlips++;
  const g = QA.GROUP_KEYS[Math.floor(rnd() * 27)];
  if (rnd() < 0.65) {
    const files = QA.filesOf(g);
    QA.setImgState(files[Math.floor(rnd() * files.length)], imgStates[Math.floor(rnd() * imgStates.length)]);
  } else {
    QA.setGroupState(g, grpStates[Math.floor(rnd() * grpStates.length)]);
  }
  const v = violations();
  if (v.length) { worst = v; break; }
}
check("1200 次随机操作 (含随机 confirm 取消) 零不变量违例", worst.length === 0, worst.join("; "));
console.log("       (随机同意二次确认 " + confirmFlips + " 次)");

console.log("\n[13] 批量操作后不变量");
QA.bulkAdoptAll();
check("bulkAdoptAll 后零违例", violations().length === 0, violations().join("; "));
eq("全部 27 组采纳", QA.GROUP_KEYS.filter((g) => QA.getGroupState(g) === "adopt").length, 27);
CONFIRM_ANSWER = true;
QA.bulkClearAll();
check("bulkClearAll 后零违例", violations().length === 0, violations().join("; "));
eq("清空后无采纳组", QA.GROUP_KEYS.filter((g) => QA.getGroupState(g) === "adopt").length, 0);
eq("清空后无好图", QA.GROUP_KEYS.reduce((a, g) => a + QA.goodFiles(g).length, 0), 0);

console.log("\n===== QA 独立行为核验汇总 =====");
console.log("通过: " + passed + " 条");
console.log("失败: " + failures.length + " 条");
if (failures.length) { console.log("\n失败明细:"); failures.forEach((f) => console.log("  - " + f)); }
console.log("[结果] " + (failures.length ? "存在 FAIL, 需打回" : "QA 独立行为核验全部通过"));
process.exit(failures.length ? 1 : 0);
