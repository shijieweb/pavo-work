#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量队列调度器（带 cron 语义），单进程内常驻后台 worker 消费。

特性：
- 持久化：队列落 JSON 文件，进程重启可续跑（pending 任务重跑）。
- 任务类型：render_shot / pipeline_project / tune_project / rebuild。
- 调度：schedule="immediate"(默认,尽快) / "nightly"(仅本地 02:00-06:00 窗口执行) /
        run_at="ISO时间"精确触发。
- 线程安全：内部 exec_lock 保证后台 worker 与手动 drain 不会并发执行两个任务
            （生成管线同一时间只能跑一个），process_due 单任务原子消费避免重复。
- 执行：executor(job) 由 server 注入（需访问 server 全局 ACTIVE/SPEC/生成函数）。
"""
import os, json, time, uuid, threading, datetime

NIGHTLY_START_HOUR = 2   # 02:00
NIGHTLY_END_HOUR = 6     # 06:00


def _now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _parse_iso(s):
    try:
        return datetime.datetime.fromisoformat(s)
    except Exception:
        # 兼容无时区后缀
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


class BatchQueue:
    def __init__(self, queue_path):
        self.queue_path = queue_path
        self.lock = threading.Lock()        # 元数据锁（消费判定/状态切换）
        self.exec_lock = threading.Lock()   # 执行锁（保证同时只跑一个任务）
        self._jobs = {}
        self._load()

    def _load(self):
        try:
            with open(self.queue_path, encoding="utf-8") as f:
                data = json.load(f)
            self._jobs = {j["id"]: j for j in data.get("jobs", [])}
        except Exception:
            self._jobs = {}

    def _save(self):
        tmp = self.queue_path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"jobs": list(self._jobs.values())}, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.queue_path)
        except Exception:
            pass

    def enqueue(self, job_type, payload=None, schedule="immediate", run_at=None,
                project=None, max_attempts=1, note=""):
        job = {
            "id": uuid.uuid4().hex[:12],
            "type": job_type,
            "payload": payload or {},
            "status": "pending",
            "schedule": schedule,
            "run_at": run_at,
            "project": project,
            "max_attempts": int(max_attempts or 1),
            "attempts": 0,
            "note": note,
            "created_at": _now_iso(),
            "started_at": None,
            "done_at": None,
            "progress": 0,
            "result": None,
            "error": None,
        }
        with self.lock:
            self._jobs[job["id"]] = job
            self._save()
        return job

    def cancel(self, job_id):
        with self.lock:
            j = self._jobs.get(job_id)
            if j and j["status"] in ("pending", "running"):
                j["status"] = "cancelled"
                self._save()
                return True
        return False

    def list(self, status=None):
        with self.lock:
            js = list(self._jobs.values())
        if status:
            js = [j for j in js if j["status"] == status]
        return sorted(js, key=lambda j: j["created_at"])

    def _due(self, job, now):
        if job["status"] != "pending":
            return False
        if job.get("schedule") == "nightly":
            h = now.hour
            if not (NIGHTLY_START_HOUR <= h < NIGHTLY_END_HOUR):
                return False
        run_at = job.get("run_at")
        if run_at:
            try:
                if now < _parse_iso(run_at):
                    return False
            except Exception:
                pass
        return True

    def process_due(self, executor):
        """在 lock 内原子取出一个到期任务并标记 running，再在 exec_lock 内执行。
        返回被处理的 job；无到期任务返回 None。同一任务不会被 worker 与手动 drain 重复消费。"""
        with self.lock:
            now = datetime.datetime.now()
            due = [j for j in self._jobs.values() if self._due(j, now)]
            if not due:
                return None
            job = due[0]
            job["status"] = "running"
            job["started_at"] = _now_iso()
            job["attempts"] += 1
            self._save()
        # 在 lock 外、exec_lock 内执行（避免阻塞队列元数据与其他任务）
        with self.exec_lock:
            try:
                res = executor(job)
                job["result"] = res
                job["status"] = "done"
                job["error"] = None
            except Exception as e:
                job["error"] = str(e)
                if job["attempts"] >= job["max_attempts"]:
                    job["status"] = "failed"
                else:
                    job["status"] = "pending"  # 允许重试
        job["done_at"] = _now_iso()
        with self.lock:
            self._save()
        return job

    def run_worker(self, executor, poll=3, stop=None, is_paused=None):
        """常驻后台循环（daemon 线程调用）。
        stop: 可调用，返回 True 即终止线程（干净退出）。
        is_paused: 可调用，返回 True 时跳过消费、仅空转（用于暂停/恢复，不杀线程）。"""
        while not (stop and stop()):
            if is_paused and is_paused():
                time.sleep(poll)
                continue
            try:
                self.process_due(executor)
            except Exception:
                pass
            time.sleep(poll)


if __name__ == "__main__":
    import tempfile
    qp = os.path.join(tempfile.gettempdir(), "bq_test.json")
    bq = BatchQueue(qp)
    j = bq.enqueue("render_shot", {"id": 1})
    print("enqueued:", j["id"], bq.list())
