
// ===========================================================================
// 内联索引数据 (无外部请求)。
// 注意: prompt / prompt_zh 全文只存在于图卡 DOM 中各一份, 不重复灌入 JSON,
//       lightbox 与导出所需文本一律用 readPrompt() 从 DOM 读取。
// ===========================================================================
const ITEMS = [{"file": "w01_1.png", "writing_no": "1", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_EAMnAi6TQztQfPqpFqf9YRkas2kJl4SB/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w01_1.png", "zh_fallback": false}, {"file": "w01_2.png", "writing_no": "1", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_KzaPVoYmfi0PkP3OCuZhv1PIAbdsM43I/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w01_2.png", "zh_fallback": false}, {"file": "w02_1.png", "writing_no": "2", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_Yp7QzXr1C2VSOG0lxbY4zcCVK31Ox8yl/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w02_1.png", "zh_fallback": false}, {"file": "w02_2.png", "writing_no": "2", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_N0WmAdoUuvLWNpiiXRINsH2aLPgUtvq2/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w02_2.png", "zh_fallback": false}, {"file": "w03_1.png", "writing_no": "3", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_aEEaVzWCRMuVtQ0A8iQJE0Trkh2CVmQ5/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w03_1.png", "zh_fallback": false}, {"file": "w03_2.png", "writing_no": "3", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_XwZXu6q7wqADaVGLVC6XZStudME8cIJY/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w03_2.png", "zh_fallback": false}, {"file": "w04_1.png", "writing_no": "4", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_XrqEDv51I2ZgkHZXL6fj527g2prxp7Fa/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w04_1.png", "zh_fallback": false}, {"file": "w04_2.png", "writing_no": "4", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_pD7b3NujfUSDJdMnrGUoMnMTTA1zAM8w/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w04_2.png", "zh_fallback": false}, {"file": "w05_1.png", "writing_no": "5", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_kQUbsFLwuEuBjq9MI8UR6d1vzeQin5TS/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w05_1.png", "zh_fallback": false}, {"file": "w05_2.png", "writing_no": "5", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_1HAFT85L4IY7Byarbp9i7nJbUEgpJ1Sq/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w05_2.png", "zh_fallback": false}, {"file": "w06_1.png", "writing_no": "6", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_wbw0a5IfOuKPvL013BS3F3YXbvOJqZei/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w06_1.png", "zh_fallback": false}, {"file": "w06_2.png", "writing_no": "6", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_OwKqNB75ARuaWGpHDR8lxnppkm5st0mk/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w06_2.png", "zh_fallback": false}, {"file": "w07_1.png", "writing_no": "7", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_PuouwI99GlFpeLROMfpnlAXcmW6JMp3D/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w07_1.png", "zh_fallback": false}, {"file": "w07_2.png", "writing_no": "7", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_si52s8CKW5HLO1ITiElC3lNdurJ8ryNX/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w07_2.png", "zh_fallback": false}, {"file": "w08_1.png", "writing_no": "8", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_zjkGWMcpxEbWpKNhF4suzHTujGryBKkQ/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w08_1.png", "zh_fallback": false}, {"file": "w08_2.png", "writing_no": "8", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_n01zevyd40eX3TptAH9bw0OWV77VSfD4/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w08_2.png", "zh_fallback": false}, {"file": "w09_1.png", "writing_no": "9", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_NPAwIrnxKK6Jjb7bpMtD9dg4zYv12BX2/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w09_1.png", "zh_fallback": false}, {"file": "w09_2.png", "writing_no": "9", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_jhONn2xR7okoL4KsDfslqr2Kd174cjfR/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w09_2.png", "zh_fallback": false}, {"file": "w10_1.png", "writing_no": "10", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_V7sxAoytZnaR2tIWRJFOpiZnLanoRvyP/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w10_1.png", "zh_fallback": false}, {"file": "w10_2.png", "writing_no": "10", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_vT0QKFIK52HawABKI8Flejjembs9HxPC/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w10_2.png", "zh_fallback": false}, {"file": "w11_1.png", "writing_no": "11", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_cGKLzuN9qs2caf8QCkFOEVUlfWMZ2eKg/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w11_1.png", "zh_fallback": false}, {"file": "w11_2.png", "writing_no": "11", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_F0qxWNdQKqHyDNYwVt6R6lUhzJ3D0nbj/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w11_2.png", "zh_fallback": false}, {"file": "w12_1.png", "writing_no": "12", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_wjDdpBmpNyQNGn1Cl3S0DHSKlanfXgPO/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w12_1.png", "zh_fallback": false}, {"file": "w12_2.png", "writing_no": "12", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_lkfzcOn2QB7qsg7TE8znExpag9fjqm9x/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w12_2.png", "zh_fallback": false}, {"file": "w13_1.png", "writing_no": "13", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_5XuAA3u3dEjQPIadetDgl7gc0gvXQcf1/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w13_1.png", "zh_fallback": false}, {"file": "w13_2.png", "writing_no": "13", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_Hx3pWrmxK3mfSxar6FGJlrBd64IbIA93/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w13_2.png", "zh_fallback": false}, {"file": "w14_1.png", "writing_no": "14", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_b9UampMaML1AttkbZYkj3sIT3llDMLKK/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w14_1.png", "zh_fallback": false}, {"file": "w14_2.png", "writing_no": "14", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_hluuXjvvUPVG5AfvYqOOHS1l3It7GuTb/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w14_2.png", "zh_fallback": false}, {"file": "w15_1.png", "writing_no": "15", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_1H1UIEpuSYZbagQVPoljUKcsZUGpzUhH/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w15_1.png", "zh_fallback": false}, {"file": "w15_2.png", "writing_no": "15", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_UYCC5N0H0Y0KD2QBz0wQkHtuSsHbSd3o/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w15_2.png", "zh_fallback": false}, {"file": "w16_1.png", "writing_no": "16", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_w0OTPtvrvX1UfVFKUBvr3Y3xqH4qbpcv/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w16_1.png", "zh_fallback": false}, {"file": "w16_2.png", "writing_no": "16", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_qW5RoGEEjOqNxfXpWuxpzJPeCvLpsX4y/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w16_2.png", "zh_fallback": false}, {"file": "w17_1.png", "writing_no": "17", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_vhKSlyjzhhJmepWDE9dOXHgLOZ8oDTE4/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w17_1.png", "zh_fallback": false}, {"file": "w17_2.png", "writing_no": "17", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_Y2NAnHQB6EVl2qsGbhLPC0k5oQyFUTO7/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w17_2.png", "zh_fallback": false}, {"file": "w18_1.png", "writing_no": "18", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_jucVoUz7QYW39RuvXYG6Br7cASH1vRlS/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w18_1.png", "zh_fallback": false}, {"file": "w18_2.png", "writing_no": "18", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_shJ70FKymACJEY78dst4oKn7fHrOlhjg/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w18_2.png", "zh_fallback": false}, {"file": "w19_1.png", "writing_no": "19", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_irPPfo1dco21crKxaRWKq1Hg2ZwIpVbN/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w19_1.png", "zh_fallback": false}, {"file": "w19_2.png", "writing_no": "19", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_P8C2cWhZzUkYq9tWLv0LfS61riu8PSrX/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w19_2.png", "zh_fallback": false}, {"file": "w20_1.png", "writing_no": "20", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_tCcWPqkjf2OuXV4tY2ctOSRN7F56b5ks/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w20_1.png", "zh_fallback": false}, {"file": "w20_2.png", "writing_no": "20", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_U0Uog7CN5HqGOIyZzteQYurQ4Fn2aofI/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w20_2.png", "zh_fallback": false}, {"file": "w21_1.png", "writing_no": "21", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_eAUVDCABhrdBXvYMTpRWaWpMiTb6jvlN/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w21_1.png", "zh_fallback": false}, {"file": "w21_2.png", "writing_no": "21", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_lo3YeRlWwZmKtbVOL05ROK9Gl7LPdqIg/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w21_2.png", "zh_fallback": false}, {"file": "w22_1.png", "writing_no": "22", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_5SyUSjiGVgAJegNG76HREqVyiEVKsckN/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w22_1.png", "zh_fallback": false}, {"file": "w22_2.png", "writing_no": "22", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_HQqIimAaWOuHHkEIdPBYZwsepR1LVKg2/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w22_2.png", "zh_fallback": false}, {"file": "w23_1.png", "writing_no": "23", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_5Qgjr8DoknWH2T6ZERXSGLySh22ZCR2y/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w23_1.png", "zh_fallback": false}, {"file": "w23_2.png", "writing_no": "23", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_UKzR4RoFfrKG8ByxlTNgmYT6eighAAwh/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w23_2.png", "zh_fallback": false}, {"file": "w24_1.png", "writing_no": "24", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_0lV3pHDYxDIsXKPGISFBmhKNv0PE6Q8Z/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w24_1.png", "zh_fallback": false}, {"file": "w24_2.png", "writing_no": "24", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_nCs8F7iVVZUnOgWNKXbOHlDv8zxcK3cQ/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w24_2.png", "zh_fallback": false}, {"file": "w25_1.png", "writing_no": "25", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_WXlD0uYKLIEXd6GSfE8anoRDfeUP9aFl/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w25_1.png", "zh_fallback": false}, {"file": "w25_2.png", "writing_no": "25", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_cOjykZ9Cb5uvCyTouxMM2MZqy6vgRI8P/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w25_2.png", "zh_fallback": false}, {"file": "w26_1.png", "writing_no": "26", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_bwam2IvZ2I2uiAGXy4NWpkS5uPyLhH18/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w26_1.png", "zh_fallback": false}, {"file": "w26_2.png", "writing_no": "26", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_b3VYEbaN2Z3LA3QucxcAcjXqFLwvcEjQ/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w26_2.png", "zh_fallback": false}, {"file": "w27_1.png", "writing_no": "27", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_pIEfhjwMZhpCLnnn6wqBI6uEqxBtv1MF/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w27_1.png", "zh_fallback": false}, {"file": "w27_2.png", "writing_no": "27", "url": "https://platform-outputs.agnes-ai.space/images/i2i/task_YvCtHnzBPHSmp2TD5XOfQE38KmdcFTdl/output.png", "rel_path": "01_配方训练/实验批次/batch-001/out/w27_2.png", "zh_fallback": false}];
const REFS = [{"file": "charA_front.png", "rel_path": "01_配方训练/角色参考图/charA_front.png"}, {"file": "charA_side.png", "rel_path": "01_配方训练/角色参考图/charA_side.png"}];
const GROUP_KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25", "26", "27"];

const STORAGE_KEY = "training_panel_adoption_batch001_v2";
const STORAGE_KEY_V1 = "training_panel_adoption_batch001";

const IMG_STATES = ["primary", "backup", "discard"];
const IMG_LABEL = { primary: "主图", backup: "备选", discard: "弃" };
const GROUP_STATES = ["reject", "pending", "adopt"];
const GROUP_LABEL = { reject: "不采纳", pending: "待定", adopt: "采纳" };
const DEFAULT_IMG_STATE = "discard";
const DEFAULT_GROUP_STATE = "pending";

// ===== 索引表 =====
const ITEM_MAP = {};      // file -> item
const FILE_GROUP = {};    // file -> 写法号
const GROUP_FILES = {};   // 写法号 -> [file, ...] (按文件名顺序)
ITEMS.forEach(function (it) {
  ITEM_MAP[it.file] = it;
  FILE_GROUP[it.file] = it.writing_no;
  if (!GROUP_FILES[it.writing_no]) GROUP_FILES[it.writing_no] = [];
  GROUP_FILES[it.writing_no].push(it.file);
});

const CARD_MAP = {};      // file -> .card 元素 (Python 预渲染)
const GROUP_MAP = {};     // 写法号 -> .group 元素
document.querySelectorAll(".card").forEach(function (card) {
  CARD_MAP[card.dataset.file] = card;
});
document.querySelectorAll(".group").forEach(function (grp) {
  GROUP_MAP[grp.dataset.writing] = grp;
});

// ===========================================================================
// 持久化 (AC-6): { imgState: {file: state}, groupState: {写法号: state} }
// ===========================================================================
function loadStore() {
  const st = { imgState: {}, groupState: {} };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object") {
        if (parsed.imgState && typeof parsed.imgState === "object") st.imgState = parsed.imgState;
        if (parsed.groupState && typeof parsed.groupState === "object") st.groupState = parsed.groupState;
      }
      return st;
    }
  } catch (e) {
    console.warn("[面板] 读取本地状态失败, 使用空状态", e);
    return st;
  }
  // 无 v2 记录时, 尝试从 T-15 (v1 单层三态) 迁移: v1 的 adopt 视为「好图」
  try {
    const rawV1 = localStorage.getItem(STORAGE_KEY_V1);
    if (rawV1) {
      const v1 = JSON.parse(rawV1) || {};
      let migrated = 0;
      Object.keys(v1).forEach(function (f) {
        if (v1[f] === "adopt" && ITEM_MAP[f]) { st.imgState[f] = "backup"; migrated++; }
      });
      GROUP_KEYS.forEach(function (g) {
        const good = (GROUP_FILES[g] || []).filter(function (f) { return !!st.imgState[f]; });
        if (good.length > 0) st.groupState[g] = "adopt";
      });
      if (migrated > 0) console.log("[面板] 已从 T-15 记录迁移", migrated, "张为「备选」, 请复核主图归属");
    }
  } catch (e) {
    console.warn("[面板] v1 迁移失败, 忽略", e);
  }
  return st;
}

let store = loadStore();

function saveStore() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  } catch (e) {
    console.warn("[面板] 保存失败", e);
  }
}

// ===== 状态读取 =====
function getImgState(file) {
  const s = store.imgState[file];
  return IMG_STATES.indexOf(s) >= 0 ? s : DEFAULT_IMG_STATE;
}
function getGroupState(g) {
  const s = store.groupState[g];
  return GROUP_STATES.indexOf(s) >= 0 ? s : DEFAULT_GROUP_STATE;
}
function isGood(file) {
  const s = getImgState(file);
  return s === "primary" || s === "backup";
}
function filesOf(g) { return GROUP_FILES[g] || []; }
function goodFiles(g) { return filesOf(g).filter(isGood); }
function primaryFiles(g) {
  return filesOf(g).filter(function (f) { return getImgState(f) === "primary"; });
}
function backupFiles(g) {
  return filesOf(g).filter(function (f) { return getImgState(f) === "backup"; });
}
/** AC-4: 组内 >=2 张被标为好 (主图/备选) 即为「双图优」派生态。 */
function isDualGood(g) { return goodFiles(g).length >= 2; }

// ===========================================================================
// AC-4 核心派生规则归一化:
//   1) 唯一主图: 组内主图多于 1 张时, 保留首张, 其余降级「备选」;
//   2) 两张都好 -> 组自动「采纳」(双图优), 且强制恰好 1 张主图 (无主图则首张good升为主图);
//   3) 组为「采纳」但一张好图都没有 -> 回落「待定」(采纳必须有好图);
//   4) 组为「采纳」且有好图但无主图 -> 首张好图升为主图 (保证导出必有主图)。
// ===========================================================================
function normalizeGroup(g) {
  const files = filesOf(g);
  let prims = files.filter(function (f) { return getImgState(f) === "primary"; });
  if (prims.length > 1) {
    prims.slice(1).forEach(function (f) { store.imgState[f] = "backup"; });
    prims = [prims[0]];
  }
  const goods = files.filter(isGood);
  if (goods.length >= 2) {
    store.groupState[g] = "adopt";
    if (prims.length === 0) store.imgState[goods[0]] = "primary";
    return;
  }
  if (getGroupState(g) === "adopt") {
    if (goods.length === 0) {
      store.groupState[g] = DEFAULT_GROUP_STATE;
    } else if (prims.length === 0) {
      store.imgState[goods[0]] = "primary";
    }
  }
}
function normalizeAllGroups() { GROUP_KEYS.forEach(normalizeGroup); }

// ===== 状态写入 =====
/** 设置单图状态; 设为主图时同组原主图自动降级备选 (AC-4 唯一主图)。 */
function setImgState(file, st) {
  if (IMG_STATES.indexOf(st) < 0) return;
  const g = FILE_GROUP[file];
  if (st === "primary") {
    filesOf(g).forEach(function (f) {
      if (f !== file && getImgState(f) === "primary") store.imgState[f] = "backup";
    });
  }
  store.imgState[file] = st;
  normalizeGroup(g);
  saveStore();
  syncGroup(g);
  updateStats();
  applyFilters();
}

/** 设置组决策; 采纳需至少 1 张好图, 双图优组改判需先重置图片状态。 */
function setGroupState(g, st) {
  if (GROUP_STATES.indexOf(st) < 0) return;
  if (st === "adopt" && goodFiles(g).length === 0) {
    alert("无法采纳写法号 " + g + "：\n\n按规则，一组要标「采纳」必须至少有 1 张图被标为「主图」或「备选」。\n请先在该组图片上做标记。");
    return;
  }
  if (st !== "adopt" && isDualGood(g)) {
    const ok = confirm(
      "写法号 " + g + " 当前两张图均为「主图/备选」，属自动派生的「采纳 · 双图优」。\n\n" +
      "改判为「" + GROUP_LABEL[st] + "」将把该组图片状态全部重置为「弃」。是否继续？"
    );
    if (!ok) return;
    filesOf(g).forEach(function (f) { store.imgState[f] = "discard"; });
  }
  store.groupState[g] = st;
  normalizeGroup(g);
  saveStore();
  syncGroup(g);
  updateStats();
  applyFilters();
}

// ===========================================================================
// 视图同步
// ===========================================================================
function syncCard(file) {
  const card = CARD_MAP[file];
  if (!card) return;
  const cur = getImgState(file);
  card.classList.remove("st-primary", "st-backup", "st-discard");
  card.classList.add("st-" + cur);
  const tag = card.querySelector('[data-role="state-tag"]');
  if (tag) {
    tag.className = "state-tag " + cur;
    tag.textContent = IMG_LABEL[cur];
  }
  card.querySelectorAll(".switch button").forEach(function (b) {
    b.className = (b.dataset.set === cur) ? ("sel-" + cur) : "";
  });
}

function syncGroup(g) {
  const grp = GROUP_MAP[g];
  filesOf(g).forEach(syncCard);
  if (!grp) return;
  const st = getGroupState(g);
  const dual = isDualGood(g);
  grp.classList.remove("g-adopt", "g-reject", "g-pending");
  grp.classList.add("g-" + st);
  const tag = grp.querySelector('[data-role="group-state-tag"]');
  if (tag) {
    tag.className = "group-state-tag " + st;
    tag.textContent = GROUP_LABEL[st];
  }
  const badge = grp.querySelector('[data-role="dual-badge"]');
  if (badge) badge.hidden = !dual;
  grp.querySelectorAll(".group-switch button").forEach(function (b) {
    b.className = (b.dataset.groupSet === st) ? ("gsel-" + st) : "";
  });
  const meta = grp.querySelector('[data-role="group-meta"]');
  if (meta) {
    const prim = primaryFiles(g);
    const back = backupFiles(g);
    meta.textContent = "主图：" + (prim.length ? prim[0] : "—") +
                       "　备选：" + (back.length ? back.join("、") : "—");
  }
}

function syncAll() { GROUP_KEYS.forEach(syncGroup); }

// ===========================================================================
// AC-5 统计条
// ===========================================================================
function updateStats() {
  let adoptImg = 0;
  ITEMS.forEach(function (it) { if (isGood(it.file)) adoptImg++; });
  const total = ITEMS.length;
  const rejectImg = total - adoptImg;
  const rate = total ? Math.round((adoptImg / total) * 100) : 0;
  let groupAdopt = 0, dual = 0;
  GROUP_KEYS.forEach(function (g) {
    if (getGroupState(g) === "adopt") groupAdopt++;
    if (isDualGood(g)) dual++;
  });
  document.getElementById("stat-total").textContent = total;
  document.getElementById("stat-adopt").textContent = adoptImg;
  document.getElementById("stat-reject").textContent = rejectImg;
  document.getElementById("stat-rate").textContent = rate + "%";
  document.getElementById("stat-group-adopt").textContent = groupAdopt + "/" + GROUP_KEYS.length;
  document.getElementById("stat-dual").textContent = dual;
}

// ===========================================================================
// 筛选 (写法号 / 图片状态 / 组决策)
// ===========================================================================
function applyFilters() {
  const fw = document.getElementById("filter-writing").value;
  const fi = document.getElementById("filter-imgstate").value;
  const fg = document.getElementById("filter-groupstate").value;
  document.querySelectorAll(".group").forEach(function (grp) {
    const g = grp.dataset.writing;
    const okG = (fg === "all") || (getGroupState(g) === fg);
    const okW = (fw === "all") || (g === fw);
    let visible = 0;
    grp.querySelectorAll(".card").forEach(function (card) {
      const okI = (fi === "all") || (getImgState(card.dataset.file) === fi);
      const show = okG && okW && okI;
      card.style.display = show ? "" : "none";
      if (show) visible++;
    });
    grp.style.display = (okG && okW && visible > 0) ? "" : "none";
  });
}

// ===========================================================================
// 批量操作
// ===========================================================================
/** 全选采纳: 每组 -> 采纳; 组内第 1 张主图, 第 2 张备选 (其余备选)。 */
function bulkAdoptAll() {
  GROUP_KEYS.forEach(function (g) {
    filesOf(g).forEach(function (f, idx) {
      store.imgState[f] = (idx === 0) ? "primary" : "backup";
    });
    store.groupState[g] = "adopt";
    normalizeGroup(g);
  });
  saveStore();
  syncAll();
  updateStats();
  applyFilters();
}

/** 全部清除: 图片回「弃」, 组回「待定」, 并清空本地存储。 */
function bulkClearAll() {
  store = { imgState: {}, groupState: {} };
  try { localStorage.removeItem(STORAGE_KEY); } catch (e) { console.warn(e); }
  syncAll();
  updateStats();
  applyFilters();
}

// ===========================================================================
// AC-1 lightbox: 全尺寸大图 + 中英文 prompt
// 大图 <元素> 由 JS 动态创建 (不写死在 HTML 文本), 以保证静态图片标签计数精确。
// ===========================================================================
const lb = document.getElementById("lightbox");
const lbStage = document.getElementById("lb-stage");
const lbImg = document.createElement("img");
lbImg.className = "lb-img";
lbImg.id = "lb-img";
lbImg.setAttribute("alt", "全尺寸大图");
lbStage.appendChild(lbImg);

/** 从预渲染 DOM 读取该图的 prompt 文本 (role: prompt-zh | prompt-en)。 */
function readPrompt(file, role) {
  const card = CARD_MAP[file];
  if (!card) return "";
  const el = card.querySelector('[data-role="' + role + '"]');
  return el ? el.textContent : "";
}

function openLightbox(file) {
  const it = ITEM_MAP[file];
  if (!it) return;
  const g = FILE_GROUP[file];
  lbImg.src = it.rel_path;
  lbImg.setAttribute("alt", file);
  document.getElementById("lb-file").textContent = file;
  document.getElementById("lb-meta").textContent =
    "写法号 " + g + "　·　图片状态：" + IMG_LABEL[getImgState(file)] +
    "　·　组决策：" + GROUP_LABEL[getGroupState(g)] + (isDualGood(g) ? "（双图优）" : "");
  document.getElementById("lb-zh").textContent = readPrompt(file, "prompt-zh") || "（无中文 prompt）";
  document.getElementById("lb-en").textContent = readPrompt(file, "prompt-en") || "（无英文 prompt）";
  showLightbox();
}

function openRefLightbox(relPath, name) {
  lbImg.src = relPath;
  lbImg.setAttribute("alt", name);
  document.getElementById("lb-file").textContent = name;
  document.getElementById("lb-meta").textContent = "角色参考图（一致性比对基准）";
  document.getElementById("lb-zh").textContent = "该图为角色参考图，非候选生成图，无 prompt。";
  document.getElementById("lb-en").textContent = "Character reference image (no prompt).";
  showLightbox();
}

function showLightbox() {
  lb.hidden = false;
  lb.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
}

function closeLightbox() {
  lb.hidden = true;
  lb.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
}

// ===========================================================================
// AC-6 导出 (JSON 含组层级 + 图层级; CSV 1 行/组)
// ===========================================================================
function nowStamp() {
  const d = new Date();
  const p = function (n) { return String(n).padStart(2, "0"); };
  return d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + "_" +
         p(d.getHours()) + p(d.getMinutes()) + p(d.getSeconds());
}

function download(filename, content, mime) {
  const blob = new Blob([content], { type: mime });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(function () { URL.revokeObjectURL(a.href); }, 2000);
  alert("已下载：" + filename + "\n请存入 04_采纳区/ 目录。");
}

/** 构造单组的导出记录 (组决策 + 主图 + 备选)。 */
function groupRecord(g) {
  const files = filesOf(g);
  const prim = primaryFiles(g);
  const back = backupFiles(g);
  const st = getGroupState(g);
  const dual = isDualGood(g);
  return {
    writing_no: g,
    group_state: st,
    group_state_label: GROUP_LABEL[st] + (dual ? " · 双图优" : ""),
    dual_good: dual,
    primary_file: prim.length ? prim[0] : "",
    backup_files: back,
    image_count: files.length,
    adopted_image_count: goodFiles(g).length
  };
}

function exportJson() {
  const groups = GROUP_KEYS.map(groupRecord);
  const images = ITEMS.map(function (it) {
    const s = getImgState(it.file);
    return {
      file: it.file,
      writing_no: it.writing_no,
      img_state: s,
      img_state_label: IMG_LABEL[s],
      adopted: isGood(it.file),
      group_state: getGroupState(it.writing_no),
      prompt: readPrompt(it.file, "prompt-en"),
      prompt_zh: readPrompt(it.file, "prompt-zh"),
      zh_fallback: !!it.zh_fallback,
      url: it.url,
      rel_path: it.rel_path
    };
  });
  const adoptedImages = images.filter(function (r) { return r.adopted; }).length;
  const payload = {
    batch: "batch-001",
    schema: "training-panel-adoption/v2",
    exported_at: new Date().toISOString(),
    summary: {
      total_images: images.length,
      adopted_images: adoptedImages,
      rejected_images: images.length - adoptedImages,
      adopt_rate: images.length ? Math.round((adoptedImages / images.length) * 100) + "%" : "0%",
      total_groups: groups.length,
      adopted_groups: groups.filter(function (r) { return r.group_state === "adopt"; }).length,
      dual_good_groups: groups.filter(function (r) { return r.dual_good; }).length,
      pending_groups: groups.filter(function (r) { return r.group_state === "pending"; }).length,
      rejected_groups: groups.filter(function (r) { return r.group_state === "reject"; }).length
    },
    groups: groups,
    images: images
  };
  download("采纳记录_batch-001_" + nowStamp() + ".json",
           JSON.stringify(payload, null, 2), "application/json");
}

function csvCell(v) {
  const s = String(v == null ? "" : v).replace(/"/g, '""');
  return '"' + s + '"';
}

/** CSV: 1 行/组, 列 = 写法号,组决策,主图文件名,备选文件名,图片数,采纳图片数 */
function exportCsv() {
  const header = ["写法号", "组决策", "主图文件名", "备选文件名", "图片数", "采纳图片数"];
  const lines = [header.map(csvCell).join(",")];
  GROUP_KEYS.forEach(function (g) {
    const r = groupRecord(g);
    lines.push([
      r.writing_no,
      r.group_state_label,
      r.primary_file,
      r.backup_files.join("|"),
      r.image_count,
      r.adopted_image_count
    ].map(csvCell).join(","));
  });
  download("采纳记录_batch-001_" + nowStamp() + ".csv",
           "\ufeff" + lines.join("\r\n"), "text/csv;charset=utf-8");
}

// ===========================================================================
// 事件绑定 (统一事件委托)
// ===========================================================================
document.getElementById("groups").addEventListener("click", function (ev) {
  const imgBtn = ev.target.closest(".switch button[data-set]");
  if (imgBtn) {
    const card = imgBtn.closest(".card");
    if (card) setImgState(card.dataset.file, imgBtn.dataset.set);
    return;
  }
  const grpBtn = ev.target.closest(".group-switch button[data-group-set]");
  if (grpBtn) {
    const grp = grpBtn.closest(".group");
    if (grp) setGroupState(grp.dataset.writing, grpBtn.dataset.groupSet);
    return;
  }
  const thumb = ev.target.closest('[data-role="thumb"]');
  if (thumb) {
    const card = thumb.closest(".card");
    if (card) openLightbox(card.dataset.file);
  }
});

document.querySelector(".ref-grid").addEventListener("click", function (ev) {
  const rt = ev.target.closest('[data-role="ref-thumb"]');
  if (rt) openRefLightbox(rt.getAttribute("src"), rt.getAttribute("alt"));
});

lb.addEventListener("click", function (ev) {
  if (ev.target.closest('[data-role="lb-close"]')) closeLightbox();
});

document.addEventListener("keydown", function (ev) {
  if (ev.key === "Escape" && !lb.hidden) closeLightbox();
});

document.getElementById("filter-writing").addEventListener("change", applyFilters);
document.getElementById("filter-imgstate").addEventListener("change", applyFilters);
document.getElementById("filter-groupstate").addEventListener("change", applyFilters);
document.getElementById("btn-adopt-all").addEventListener("click", function () {
  if (confirm("确认把全部 " + GROUP_KEYS.length + " 个写法号标为「采纳」？\n每组第 1 张设为主图，第 2 张设为备选。")) {
    bulkAdoptAll();
  }
});
document.getElementById("btn-clear-all").addEventListener("click", function () {
  if (confirm("确认清除全部标记？\n图片重置为「弃」，写法号重置为「待定」。")) bulkClearAll();
});
document.getElementById("btn-export-json").addEventListener("click", exportJson);
document.getElementById("btn-export-csv").addEventListener("click", exportCsv);

// ===========================================================================
// 初始化: 图卡与分组均由生成器预渲染, 此处仅归一化 + 恢复状态 + 刷新视图。
// ===========================================================================
normalizeAllGroups();
saveStore();
syncAll();
updateStats();
applyFilters();
console.log("[训练线采纳面板 T-16] 图卡 =", Object.keys(CARD_MAP).length,
            "/ 数据项 =", ITEMS.length,
            "/ 分组 =", GROUP_KEYS.length,
            "/ 参考图 =", REFS.length);
