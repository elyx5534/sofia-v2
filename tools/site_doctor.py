import os, sys, time, json, socket
import http.client as httplib
from urllib.parse import urlparse

API=os.getenv("SOFIA_API_BASE","http://127.0.0.1:8016")
TRADE=os.getenv("SOFIA_TRADE_BASE",API)
METRICS=os.getenv("SOFIA_METRICS","http://127.0.0.1:8016")
SYMBOL=os.getenv("SOFIA_TEST_SYMBOL","BTCUSDT")
WS_URL=os.getenv("SOFIA_WS_URL","ws://127.0.0.1:8016/ws")

def check_http(url, path="/health"):
    try:
        u=urlparse(url)
        conn=httplib.HTTPConnection(u.hostname,u.port or 80, timeout=3)
        conn.request("GET", path)
        r=conn.getresponse(); data=r.read()
        return (200 <= r.status < 300, f"{r.status} {r.reason}", data[:200])
    except Exception as e:
        return (False, str(e), b"")

def check_post(url, path, payload):
    try:
        u=urlparse(url)
        body=json.dumps(payload).encode()
        headers={"Content-Type":"application/json"}
        conn=httplib.HTTPConnection(u.hostname,u.port or 80, timeout=3)
        conn.request("POST", path, body=body, headers=headers)
        r=conn.getresponse(); data=r.read()
        ok = (200 <= r.status < 300)
        return (ok, f"{r.status} {r.reason}", data[:300])
    except Exception as e:
        return (False, str(e), b"")

def tcp_ping(host,port, timeout=2.0):
    try:
        s=socket.create_connection((host,port), timeout=timeout)
        s.close(); return True
    except: return False

def show():
    print("ENV:", {k:v for k,v in os.environ.items() if k.startswith("SOFIA_")})

def run():
    report=[]
    ok,msg,_ = check_http(API, "/health"); report.append(("API /health", ok, msg))
    ok2,msg2,body2 = check_post(API, "/ai/score", {"symbol":SYMBOL, "horizon":"15m"})
    report.append(("/ai/score", ok2, msg2 if ok2 else (msg2+" "+body2.decode(errors="ignore"))))
    ok3,msg3,body3 = check_http(TRADE, "/trade/account"); report.append(("/trade/account", ok3, msg3 if ok3 else body3.decode(errors="ignore")))
    ok4,msg4,_ = check_http(METRICS, "/metrics"); report.append(("/metrics", ok4, msg4))

    # tcp checks
    redis_ok = tcp_ping(os.getenv("REDIS_HOST","127.0.0.1"), int(os.getenv("REDIS_PORT","6379")))
    qdb_ok   = tcp_ping(os.getenv("QUESTDB_HOST","127.0.0.1"), int(os.getenv("QUESTDB_PG","8812")))
    ts_ok    = tcp_ping(os.getenv("PG_HOST","127.0.0.1"), int(os.getenv("PG_PORT","5432")))
    report.append(("Redis tcp", redis_ok, "6379"))
    report.append(("QuestDB tcp", qdb_ok, "8812"))
    report.append(("Timescale tcp", ts_ok, "5432"))

    print("\n=== SOFIA SITE DOCTOR ===")
    fail=False
    for name,ok,msg in report:
        status = '[OK]' if ok else '[FAIL]'
        print(f"{status} {name}: {msg}")
        if not ok: fail=True
    print()
    if fail: print("Some checks FAILED. Fix them in the next steps.")
    else: print("All green. If UI still off, check browser console & CORS/WS.")

if __name__=="__main__":
    show(); run()