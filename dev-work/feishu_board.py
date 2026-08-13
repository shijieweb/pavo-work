#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
feishu_board.py - 飞书多维表格(Bitable) 看板客户端

把本地看板(dev-work/tasks + current_state.md)迁移/同步到飞书多维表格，
并支持阿编自动更新任务状态。仅依赖标准库(urllib)，已绕过本机 AGNES 代理。

凭证从 ~/.workbuddy/.env 读取(绝不写死)：
  FEISHU_APP_ID      飞书自建应用 app_id
  FEISHU_APP_SECRET  飞书自建应用 app_secret
  FEISHU_BASE_TOKEN  多维表格 app_token（留空则脚本自动创建一个新表）
  FEISHU_BASE_TABLE  表ID（留空则使用第一个表）

飞书字段类型枚举(用到的)：
  1=文本, 3=单选, 5=日期, 11=人员, 15=超链接, 17=附件

用法(见文件底部 __main__)：
  python feishu_board.py setup     # 建表(若需) + 建字段 + 建看板视图
  python feishu_board.py sync      # 从 dev-work 导入/更新任务记录
  python feishu_board.py token     # 仅打印 tenant_access_token，验证凭证可用
"""
import os
import sys
import json
import urllib.request
import urllib.parse

ENV_FILE = os.path.expanduser("~/.workbuddy/.env")
FEISHU_HOST = "https://open.feishu.cn"

# 强制不走代理：清掉所有可能存在的代理环境变量
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
           "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"):
    os.environ.pop(_k, None)


# ---------------------------------------------------------------------------
# 配置读取
# ---------------------------------------------------------------------------
def get_env(key: str) -> str:
    try:
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith(key + "="):
                    return line[len(key) + 1:].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return os.environ.get(key, "")


def persist_env(key: str, value: str):
    """把解析到的 app_token 等写回 ~/.workbuddy/.env，避免每次重跑 setup 都建新表。"""
    try:
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []
    out, found = [], False
    for line in lines:
        if line.strip().startswith(key + "="):
            out.append(f"{key}={value}\n")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}\n")
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(out)


# ---------------------------------------------------------------------------
# 低层 HTTP
# ---------------------------------------------------------------------------
def _request(method: str, path: str, token: str = None,
             json_body: dict = None, query: dict = None) -> dict:
    url = FEISHU_HOST + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = (json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            if json_body is not None else None)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        raise RuntimeError(f"HTTP {e.code}: {body}")
    except Exception as e:
        raise RuntimeError(f"请求失败 {method} {path}: {e}")


def get_tenant_access_token(app_id: str = None, app_secret: str = None) -> str:
    app_id = app_id or get_env("FEISHU_APP_ID")
    app_secret = app_secret or get_env("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        raise RuntimeError("缺少 FEISHU_APP_ID / FEISHU_APP_SECRET（应在 ~/.workbuddy/.env）")
    r = _request("POST", "/open-apis/auth/v3/tenant_access_token/internal",
                 json_body={"app_id": app_id, "app_secret": app_secret})
    if r.get("code") != 0:
        raise RuntimeError(f"获取 tenant_access_token 失败: {r}")
    return r["tenant_access_token"]


# ---------------------------------------------------------------------------
# 多维表格 / 表 / 字段 / 视图
# ---------------------------------------------------------------------------
def ensure_app(token: str, app_token: str = None, name: str = "项目看板") -> str:
    """返回可用的 app_token；若未提供则自动创建一个新多维表格。"""
    if app_token:
        # 探活：能读到 app 信息即有效（注意端点不是 /meta）
        r = _request("GET", f"/open-apis/bitable/v1/apps/{app_token}", token=token)
        if r.get("code") == 0:
            return app_token
        print(f"[warn] 提供的 app_token 无效({r.get('msg')})，将自动创建新表")
    # 创建新多维表格（建在应用根目录，folder_token 省略）
    r = _request("POST", "/open-apis/bitable/v1/apps",
                 token=token, json_body={"name": name})
    if r.get("code") != 0:
        raise RuntimeError(f"创建多维表格失败: {r}")
    new_token = r["data"]["app"]["app_token"]
    print(f"[ok] 已创建多维表格 app_token={new_token}")
    return new_token


def list_tables(token: str, app_token: str):
    r = _request("GET", f"/open-apis/bitable/v1/apps/{app_token}/tables", token=token)
    if r.get("code") != 0:
        raise RuntimeError(f"列出数据表失败: {r}")
    return r["data"]["items"]


def ensure_table(token: str, app_token: str, table_id: str = None,
                 name: str = "任务看板") -> str:
    tables = list_tables(token, app_token)
    if table_id:
        for t in tables:
            if t["table_id"] == table_id:
                return table_id
        raise RuntimeError(f"指定的 table_id={table_id} 不存在")
    # 取第一个表；若不存在则创建
    if tables:
        return tables[0]["table_id"]
    r = _request("POST", f"/open-apis/bitable/v1/apps/{app_token}/tables",
                 token=token, json_body={"name": name})
    if r.get("code") != 0:
        raise RuntimeError(f"创建数据表失败: {r}")
    return r["data"]["table_id"]


# 看板字段定义： (字段名, 类型, 单选选项列表或None)
BOARD_FIELDS = [
    ("任务ID", 1, None),
    ("标题", 1, None),
    ("状态", 3, ["待办", "进行中", "待验证", "已验证", "完成", "挂起", "阻塞"]),
    ("负责人", 1, None),
    ("优先级", 3, ["P0", "P1", "P2", "P3"]),
    ("类型", 3, ["项目", "主任务", "子任务"]),
    ("父任务", 1, None),
    ("截止", 5, None),
    ("完成时间", 5, None),
    ("备注", 1, None),
    ("关联文档", 1, None),
]


def ensure_fields(token: str, app_token: str, table_id: str):
    # 读取已有字段
    r = _request("GET", f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
                 token=token)
    if r.get("code") != 0:
        raise RuntimeError(f"读取字段失败: {r}")
    existing = {f["field_name"]: f for f in r["data"]["items"]}
    for fname, ftype, options in BOARD_FIELDS:
        # 类型不匹配（如之前误建为 url 现改文本）：删旧建新
        if fname in existing and existing[fname].get("type") != ftype:
            fid = existing[fname]["field_id"]
            _request("DELETE",
                     f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{fid}",
                     token=token)
            del existing[fname]
        if fname in existing:
            continue
        body = {"field_name": fname, "type": ftype}
        if options:
            body["property"] = {"options": [{"name": o} for o in options]}
        rr = _request("POST",
                      f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
                      token=token, json_body=body)
        if rr.get("code") != 0:
            print(f"[warn] 建字段 {fname} 失败: {rr.get('msg')}")
        else:
            print(f"[ok] 建字段 {fname}")


def ensure_kanban_view(token: str, app_token: str, table_id: str,
                       group_field: str = "状态"):
    # 尝试创建看板视图（按状态分组）。已存在则忽略。
    body = {
        "view_type": "kanban",
        "view_name": "看板",
        "property": {"group_field": group_field},
    }
    r = _request("POST",
                 f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/views",
                 token=token, json_body=body)
    if r.get("code") == 0:
        print(f"[ok] 已建看板视图（按「{group_field}」分组）")
    else:
        print(f"[info] 看板视图：{r.get('msg')}（可忽略，也可在飞书UI手动切到看板视图）")


# ---------------------------------------------------------------------------
# 记录读写
# ---------------------------------------------------------------------------
def list_records(token: str, app_token: str, table_id: str, page_size: int = 100):
    items = []
    page = 1
    while True:
        r = _request("GET",
                     f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
                     token=token, query={"page_size": page_size, "page": page})
        if r.get("code") != 0:
            raise RuntimeError(f"读取记录失败: {r}")
        items.extend(r["data"]["items"])
        if not r["data"].get("has_more"):
            break
        page += 1
    return items


def upsert_by_task_id(token: str, app_token: str, table_id: str,
                      task_id: str, fields: dict):
    """按 任务ID 唯一键 upsert。空值(None/空串)不传，避免日期等字段校验失败。"""
    fields = {k: v for k, v in fields.items() if v not in (None, "")}
    existing = list_records(token, app_token, table_id, page_size=100)
    match = None
    for rec in existing:
        if rec.get("fields", {}).get("任务ID") == task_id:
            match = rec
            break
    if match:
        rid = match["record_id"]
        r = _request("PUT",
                     f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{rid}",
                     token=token, json_body={"fields": fields})
        return "update" if r.get("code") == 0 else f"ERR {r.get('msg')}"
    r = _request("POST",
                 f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
                 token=token, json_body={"fields": fields})
    return "create" if r.get("code") == 0 else f"ERR {r.get('msg')}"


# ---------------------------------------------------------------------------
def purge_junk(token: str, app_token: str, table_id: str):
    """删除无任务ID/测试残留记录，保证 sync 幂等、不产生垃圾。"""
    try:
        items = list_records(token, app_token, table_id, page_size=200)
    except Exception:
        return
    junk = [it["record_id"] for it in items
            if (it.get("fields", {}).get("任务ID") in (None, "", "__test__"))]
    for rid in junk:
        try:
            _request("DELETE",
                     f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{rid}",
                     token=token)
        except Exception:
            pass
    if junk:
        print(f"[clean] 已清理 {len(junk)} 条垃圾/测试记录")


# CLI
# ---------------------------------------------------------------------------
def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sync"
    token = get_tenant_access_token()

    if cmd == "token":
        print("tenant_access_token OK:", token[:12] + "...")
        return

    app_token = ensure_app(token, get_env("FEISHU_BASE_TOKEN"))
    if not get_env("FEISHU_BASE_TOKEN"):
        persist_env("FEISHU_BASE_TOKEN", app_token)
    table_id = ensure_table(token, app_token, get_env("FEISHU_BASE_TABLE"))

    if cmd == "setup":
        ensure_fields(token, app_token, table_id)
        ensure_kanban_view(token, app_token, table_id)
        print(f"\n[完成] 多维表格已就绪：")
        print(f"  app_token = {app_token}")
        print(f"  table_id  = {table_id}")
        print(f"  打开：https://www.feishu.cn/base/{app_token}  (或在飞书搜索表名)")
        return
    if cmd == "sync":
        purge_junk(token, app_token, table_id)
        # 延迟导入，避免无 dev-work 时也能跑 setup
        from feishu_import import build_records
        records = build_records()
        print(f"[info] 从 dev-work 解析到 {len(records)} 条任务")
        ok = 0
        for rec in records:
            res = upsert_by_task_id(token, app_token, table_id,
                                    rec["任务ID"], rec)
            if res in ("create", "update"):
                ok += 1
            else:
                print(f"  [失败] {rec['任务ID']}: {res}")
        print(f"[完成] 同步 {ok}/{len(records)} 条到飞书多维表格")
        return
    print("未知命令，可用：token / setup / sync")


if __name__ == "__main__":
    main()
