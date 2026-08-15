import requests, sys, os, json, time, random

# Mimic agent_client.py init
sys.stdout.reconfigureencoding = lambda: None
sys.stdout.reconfigure(errors='replace')
sys.stderr.reconfigure(errors='replace')

SERVER = "http://localhost:5000"
ROOM = "meeting"
UID = f"agent_{random.randint(1000, 9999)}"
NAME = os.environ.get("AGENT_NAME") or input("你的名字: ").strip() or f"Agent_{UID}"

print(f"[DIAG] UID={UID} NAME={NAME}", flush=True)

try:
    r = requests.post(f"{SERVER}/api/room/{ROOM}/join", json={"uid": UID, "name": NAME}, timeout=10)
    print(f"[DIAG] join status={r.status_code} body={r.text[:200]}", flush=True)
    data = r.json()
    print(f"[DIAG] ok={data.get('ok')} seq={data.get('seq')} phase={data.get('phase')}", flush=True)
except Exception as e:
    print(f"[DIAG] join FAILED: {e}", flush=True)
    sys.exit(1)

time.sleep(2)

try:
    d = requests.get(f"{SERVER}/api/room/{ROOM}/messages?since=0", timeout=10).json()
    print(f"[DIAG] messages count={len(d['messages'])} phase={d['phase']}", flush=True)
    for m in d['messages']:
        print(f"  seq={m['seq']} {m['from']['name']} | {m.get('content','')[:50]}", flush=True)
except Exception as e:
    print(f"[DIAG] messages FAILED: {e}", flush=True)
