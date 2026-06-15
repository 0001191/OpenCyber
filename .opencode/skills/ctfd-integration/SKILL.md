---
name: ctfd-integration
description: CTFd 平台快速登录与 API 操作 — 本地 CTFd(localhost:8000) 管理员会话管理、题目操作、Flag 提交。Agent 需要在 CTFd 上获取样本、提交结果时使用。
---

# CTFd 快速登录与 API 操作

适用于本地 CTFd 实例：**http://localhost:8000**
管理员凭证：`admin` / `OpenCyber@2026Admin`

---

## 核心机制：Session + Token 双通道

CTFd 有两种认证方式：
- **Session Cookie**：用于 Web 页面操作（设置、上传文件、获取页面 CSRF nonce）
- **Bearer Token**：用于 API 调用（创建题目、提交 flag、上传文件）

流程：Session 登录 → 获取 CSRF nonce → 创建 API token → 用 token 调 API

---

## 1. 快速登录（Session + Token 一次搞定）

```python
import requests, re, urllib3
urllib3.disable_warnings()

CTFD = "http://localhost:8000"
USER = "admin"
PASS = "OpenCyber@2026Admin"

s = requests.Session()

# Step 1: 登录（表单提交，带 CSRF nonce）
r = s.get(f"{CTFD}/login")
nonce = re.search(r'name="nonce"[^>]*value="([^"]+)"', r.text).group(1)
s.post(f"{CTFD}/login", data={"name": USER, "password": PASS, "nonce": nonce})

# Step 2: 从 Settings 页面获取 CSRF token 再创建 API token
r = s.get(f"{CTFD}/settings")
csrf = re.search(r'csrfNonce[^"]*"([a-f0-9]+)"', r.text).group(1)
r2 = s.post(f"{CTFD}/api/v1/tokens",
    headers={"CSRF-Token": csrf, "Content-Type": "application/json"},
    json={"expiration": "2099-12-31", "description": "agent-token"})
TOKEN = r2.json()["data"]["value"]

# TOKEN 可用于后续所有 API 调用
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
```

---

## 2. 常用 API 操作

### 2.1 列出所有题目
```python
r = requests.get(f"{CTFD}/api/v1/challenges", headers=HEADERS)
for c in r.json()["data"]:
    print(f"ID={c['id']}  {c['name']}  [{c['category']}]  {c['value']}pts")
```

### 2.2 创建题目（仅管理员）
```python
payload = {
    "name": "challenge-name",
    "category": "reverse",
    "description": "...",
    "value": 300,
    "state": "visible",
    "type": "standard"
}
r = requests.post(f"{CTFD}/api/v1/challenges", headers=HEADERS, json=payload)
cid = r.json()["data"]["id"]  # 返回新题目 ID
```

### 2.3 上传附件文件（用 session + CSRF token 或 Bearer token）
```python
# 方法 A：用 Bearer token（推荐）
with open("file.bin", "rb") as f:
    files = {"file": ("file.bin", f, "application/octet-stream")}
    data = {"challenge_id": str(cid), "type": "challenge"}
    r = requests.post(f"{CTFD}/api/v1/files",
        headers={"Authorization": f"Bearer {TOKEN}"},
        files=files, data=data, timeout=30)

# 方法 B：用 session cookie + CSRF token（大文件上传遇到超时用）
with open("file.bin", "rb") as f:
    # 用 curl 绕过 requests 超时
    import subprocess
    cmd = (
        f'curl -s -X POST "{CTFD}/api/v1/files" '
        f'-H "Authorization: Bearer {TOKEN}" '
        f'-F "file=@filepath" '
        f'-F "challenge_id={cid}" '
        f'-F "type=challenge"'
    )
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
```

### 2.4 提交 Flag
```python
r = requests.post(f"{CTFD}/api/v1/challenges/attempt",
    headers=HEADERS,
    json={"challenge_id": cid, "submission": "flag{...}"})
msg = r.json()["data"]["message"]  # "Correct" 或 "Incorrect"
```

### 2.5 查看题目附件
```python
r = requests.get(f"{CTFD}/api/v1/challenges/{cid}", headers=HEADERS)
# 附件的下载链接在 response 的 data.files 字段
```

---

## 3. 一键登录工具函数

```python
def ctfd_login():
    """返回 (session, token, headers)，登录失败返回 None"""
    import requests, re
    s = requests.Session()
    try:
        r = s.get(f"{CTFD}/login", timeout=10)
        nonce = re.search(r'name="nonce"[^>]*value="([^"]+)"', r.text).group(1)
        s.post(f"{CTFD}/login", data={"name": USER, "password": PASS, "nonce": nonce}, timeout=10)
        
        r = s.get(f"{CTFD}/settings", timeout=10)
        csrf = re.search(r'csrfNonce[^"]*"([a-f0-9]+)"', r.text).group(1)
        r2 = s.post(f"{CTFD}/api/v1/tokens",
            headers={"CSRF-Token": csrf, "Content-Type": "application/json"},
            json={"expiration": "2099-12-31"}, timeout=10)
        token = r2.json()["data"]["value"]
        return s, token, {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    except Exception as e:
        return None
```

---

## 4. 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| login 返回 404 | CSRF nonce 名称不对 | 检查 form 中 `name="nonce"` 还是 `name="_csrf_token"` |
| 创建题目返回 403 | 不是管理员 | 用 admin / OpenCyber@2026Admin 登录 |
| 上传文件超时 | 文件大或用 requests 直接传 | 改用 curl subprocess |
| Token 失效 | 过期 / 容器重启 | 重新调用 `ctfd_login()` |
| Docker 容器重启 | 所有数据丢失 | 重新 setup（CSRF nonce = "nonce"） |

---

## 5. 快速测试脚本

```bash
curl -s http://localhost:8000/api/v1/challenges | python -c "import sys,json; d=json.load(sys.stdin); print(f'成功: {d[\"success\"]}, 题目数: {len(d.get(\"data\",[]))}')"
```

如果返回 `成功: False`，说明需要先登录。完整测试：

```bash
cd D:\OpenCyber\OpenCyber\dashboard && /d/python3.11/python.exe -c "
import requests, re
s = requests.Session()
s.get('http://localhost:8000/login')
nonce = re.search(r'name=\"nonce\"[^>]*value=\"([^\"]+)\"', s.get('http://localhost:8000/login').text).group(1)
s.post('http://localhost:8000/login', data={'name':'admin','password':'OpenCyber@2026Admin','nonce':nonce})
r = s.get('http://localhost:8000/settings')
csrf = re.search(r'csrfNonce[^\"]*\"([a-f0-9]+)\"', r.text).group(1)
r2 = s.post('http://localhost:8000/api/v1/tokens', headers={'CSRF-Token':csrf,'Content-Type':'application/json'}, json={'expiration':'2099-12-31'})
t = r2.json()['data']['value']
r3 = requests.get('http://localhost:8000/api/v1/challenges', headers={'Authorization':f'Bearer {t}'})
print(f\"题目数: {len(r3.json()['data'])}\")
for c in r3.json()['data']:
    print(f\"  {c['name']} ({c['value']}pts)\")
"
```
