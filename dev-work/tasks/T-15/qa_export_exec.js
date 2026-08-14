// T-15 独立导出逻辑实跑 (QA 自写, 复用面板内联 JS 的 exportJson/exportCsv)
// 不依赖研发 test_panel_logic.js；自建最小 DOM/Blob/URL/localStorage stub。
'use strict';
const fs = require('fs');
const path = require('path');

const HTML_PATH = path.join(
  'C:\\Users\\67972\\projects\\short-drama-training', 'training_panel.html');
const htmlText = fs.readFileSync(HTML_PATH, 'utf8');
const scripts = [...htmlText.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const js = scripts[scripts.length - 1];

// ---- 自建最小 DOM stub (与研发测试无代码耦合) ----
function mkEl(tag) {
  return {
    tag, attrs: {}, dataset: {}, style: {}, children: [], _text: '',
    _cls: new Set(),
    get textContent() { return this._text; },
    set textContent(v) { this._text = String(v); },
    get className() { return [...this._cls].join(' '); },
    set className(v) { this._cls = new Set(String(v).split(/\s+/).filter(Boolean)); },
    get classList() {
      const s = this._cls;
      return { add: (...c) => c.forEach(x => s.add(x)),
               remove: (...c) => c.forEach(x => s.delete(x)),
               contains: c => s.has(c) };
    },
    addEventListener() {}, appendChild(c) { this.children.push(c); return c; },
    removeChild() {}, click() {},
    querySelector() { return mkEl('stub'); },
    querySelectorAll() { return []; },
    closest() { return null; },
  };
}
const byId = {};
['filter-writing','filter-state','btn-adopt-all','btn-clear-all',
 'btn-export-json','btn-export-csv','groups','stat-total','stat-adopt',
 'stat-reject','stat-pending','stat-rate','foot-hint'].forEach(id => byId[id] = mkEl('div'));

// 预渲染 54 张 card (供 CARD_MAP 索引)
const cardDefs = [...htmlText.matchAll(/<div class="card" data-file="([^"]+)" data-writing="([^"]+)">/g)]
  .map(m => ({ file: m[1], writing: m[2] }));
const cards = cardDefs.map(d => { const e = mkEl('div'); e.dataset.file = d.file; e.dataset.writing = d.writing; return e; });

const root = mkEl('root');
const documentStub = {
  getElementById: id => byId[id] || (byId[id] = mkEl('div')),
  querySelectorAll: sel => sel === '.card' ? cards : [],
  querySelector: () => mkEl('stub'),
  createElement: () => mkEl('a'),
  body: mkEl('body'),
};
const store = {};
const localStorageStub = {
  getItem: k => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: k => { delete store[k]; },
};
let lastDownload = null;
const sandbox = {
  document: documentStub, localStorage: localStorageStub, console,
  alert: () => {}, confirm: () => true, setTimeout: () => {},
  Blob: class { constructor(parts) { this._content = parts.join(''); } },
  URL: { createObjectURL: b => { lastDownload = b._content; return 'blob:stub'; },
         revokeObjectURL: () => {} },
  Date, Math, JSON, Object, parseInt, isNaN, String, Array,
};

const vm = require('vm');
const ctx = vm.createContext(sandbox);
vm.runInContext(js, ctx);

let fails = 0;
function check(name, cond, detail) {
  if (!cond) fails++;
  console.log(`  [${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ' :: ' + detail : ''}`);
}
const call = e => vm.runInContext(e, ctx);

console.log('=== T-15 独立导出逻辑实跑 (QA) ===');
console.log(`预渲染 card 数=${cards.length}, STORAGE_KEY 逻辑存在=${js.includes('training_panel_adoption_batch001')}`);
console.log('');

// ---- JSON 导出 ----
call('exportJson()');
const jsonText = lastDownload;
const payload = JSON.parse(jsonText);
check('JSON total == 54', payload.total === 54, `total=${payload.total}`);
check('JSON records 长度 == 54', payload.records.length === 54, `len=${payload.records.length}`);
check('JSON adopted == 0 (初始全待定)', payload.adopted === 0, `adopted=${payload.adopted}`);
check('JSON rejected == 0', payload.rejected === 0, `rejected=${payload.rejected}`);
check('JSON pending == 54', payload.pending === 54, `pending=${payload.pending}`);
const allFields = payload.records.every(r =>
  r.file && r.writing_no && r.state && r.state_label && r.prompt && r.url && r.rel_path);
check('每条记录含 6 字段(file/writing_no/state/state_label/prompt/url/rel_path)',
  payload.records.length === 54 && allFields);
check('每条 prompt 非截断(长度>100)', payload.records.every(r => r.prompt.length > 100),
  `最短=${Math.min(...payload.records.map(r => r.prompt.length))}`);
const uniqFiles = new Set(payload.records.map(r => r.file));
check('JSON 含 54 个唯一 file', uniqFiles.size === 54, `唯一=${uniqFiles.size}`);

// ---- CSV 导出 ----
call('exportCsv()');
const csv = lastDownload;
check('CSV 首字符为 UTF-8 BOM(0xFEFF)', csv.charCodeAt(0) === 0xFEFF);
const csvBody = csv.replace(/^\uFEFF/, '');
const csvLines = csvBody.split('\r\n');
check('CSV 行数 == 55 (表头+54)', csvLines.length === 55, `lines=${csvLines.length}`);
check('CSV 表头正确',
  csvLines[0] === '"file","写法号","采纳状态","prompt","url","本地相对路径"', csvLines[0]);
// 校验每条数据行均能解析出 6 个字段 (按 RFC4180 双引号配对)
function countCells(line) {
  let n = 0, inQ = false;
  for (const ch of line) { if (ch === '"') inQ = !inQ; else if (ch === ',' && !inQ) n++; }
  return n + 1;
}
const dataLines = csvLines.slice(1);
const cellsOk = dataLines.length === 54 && dataLines.every(l => countCells(l) === 6);
check('CSV 全部 54 数据行均 6 字段', cellsOk, `行数=${dataLines.length}`);
// CSV 含全部 54 文件名
const missingInCsv = cardDefs.map(d => d.file).filter(f => !csv.includes(f));
check('CSV 含全部 54 文件名', missingInCsv.length === 0, `缺失=${missingInCsv.length}`);

// ---- localStorage 键名逻辑存在 ----
check('localStorage 键名 training_panel_adoption_batch001 存在于源码',
  js.includes('training_panel_adoption_batch001'));

console.log('\n' + '='.repeat(52));
if (fails === 0) console.log('独立导出实跑全部 PASS ✔');
else console.log(`独立导出实跑存在 ${fails} 条失败 ✘`);
console.log('='.repeat(52));
process.exit(fails === 0 ? 0 : 1);
