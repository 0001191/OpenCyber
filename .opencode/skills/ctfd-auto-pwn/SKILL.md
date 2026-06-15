---
name: ctfd-auto-pwn
description: 端到端 CTFd 自动化 — 给定 URL，自动登录、拉题目、下载到指定目录、分析并提交 flag。适用于 CTFd 平台批量解逆向题。
---

# CTFd 自动拉题 → 分析 → 提交

给定任意 CTFd 地址，自动完成全套流程：登录 → 列表 → 下载 → 分析 → 提交。

---

## 核心工作流

```
用户输入: CTFd URL + 凭证（可选，默认 admin/OpenCyber@2026Admin）
         + 目标目录（可选，默认 E:/知识产物(必保存)/课设/基准测试/逆向/）

  1. 连接测试 ────→ GET / 检查是否 CTFd
  2. 登录 ─────────→ 表单登录获取 Session + Bearer Token
  3. 列题 ─────────→ 列出所有可访问的题目
  4. 下载 ─────────→ 逐个下载附件到目标目录
  5. 分析 ─────────→ 对每个已下载的二进制运行 4 阶段分析
  6. 提交 ─────────→ 找到 flag 后提交回 CTFd
  7. 记录 ─────────→ 结果写入 opencyber.db
```

---

## 1. 连接测试

```python
def check_ctfd(url):
    """验证目标地址是 CTFd 平台"""
    import requests
    try:
        r = requests.get(url, timeout=10)
        if r.status_code in (200, 302, 403):
            return True
        return False
    except Exception as e:
        return False
```

---

## 2. 登录（兼容任意 CTFd）

```python
def ctfd_login(url, user="admin", password="OpenCyber@2026Admin"):
    """登录任意 CTFd 实例，返回 (session, token, headers)"""
    import requests, re
    s = requests.Session()

    # Step 1: 探测 CSRF nonce 字段名
    r = s.get(f"{url}/login", timeout=10)
    nonce_field = None
    for pattern in [r'name="nonce"[^>]*value="([^"]+)"',
                    r'name="_csrf_token"[^>]*value="([^"]+)"',
                    r'csrfNonce[^"]*"([a-f0-9]+)"']:
        m = re.search(pattern, r.text)
        if m:
            nonce_field = ("nonce" if "nonce" in pattern else "_csrf_token", m.group(1))
            break
    if not nonce_field:
        return None

    # Step 2: 登录
    s.post(f"{url}/login", data={"name": user, "password": password, nonce_field[0]: nonce_field[1]}, timeout=10)

    # Step 3: 获取 API token
    r = s.get(f"{url}/settings", timeout=10)
    m = re.search(r'csrfNonce[^"]*"([a-f0-9]+)"', r.text)
    if not m:
        # 可能已经自动登录，尝试直接访问 admin
        r = s.get(f"{url}/admin/challenges", timeout=10)
        m = re.search(r'csrfNonce[^"]*"([a-f0-9]+)"', r.text)
        if not m:
            return None
    csrf = m.group(1)
    r2 = s.post(f"{url}/api/v1/tokens",
        headers={"CSRF-Token": csrf, "Content-Type": "application/json"},
        json={"expiration": "2099-12-31"}, timeout=10)
    token = r2.json()["data"]["value"]
    return s, token, {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
```

---

## 3. 列题 + 下载

```python
def list_challenges(url, headers):
    """返回所有 'reverse' / '逆向' 分类的题目列表"""
    import requests
    r = requests.get(f"{url}/api/v1/challenges", headers=headers, timeout=10)
    challenges = []
    for c in r.json().get("data", []):
        cat = c.get("category", "").lower()
        if "reverse" in cat or "逆向" in cat or not cat:  # 无分类也算逆向
            challenges.append(c)
    return challenges


def download_challenge(url, headers, challenge, dest_dir):
    """下载题目附件到指定目录"""
    import requests, os, json
    cid = challenge["id"]
    name = challenge["name"]

    # 查题目详情拿到文件列表
    r = requests.get(f"{url}/api/v1/challenges/{cid}", headers=headers, timeout=10)
    data = r.json().get("data", {})

    # 创建题目目录
    challenge_dir = os.path.join(dest_dir, name)
    os.makedirs(challenge_dir, exist_ok=True)

    # 下载附件
    files = data.get("files", [])
    if not files:
        # 尝试直接访问文件 API
        try:
            r2 = requests.get(f"{url}/api/v1/challenges/{cid}/files", headers=headers, timeout=10)
            files = r2.json().get("data", [])
        except:
            pass

    downloaded = []
    for f_url in files:
        f_url = f_url.strip()
        if not f_url.startswith("http"):
            f_url = f"{url}{f_url}"
        fname = os.path.basename(f_url.split("?")[0])
        fpath = os.path.join(challenge_dir, fname)
        try:
            r3 = requests.get(f_url, timeout=30)
            with open(fpath, "wb") as f:
                f.write(r3.content)
            downloaded.append(fpath)
        except Exception as e:
            pass

    # 保存题目信息
    info = {"name": name, "id": cid, "category": data.get("category", ""),
            "value": data.get("value", 0), "description": data.get("description", "")}
    with open(os.path.join(challenge_dir, "题目.txt"), "w", encoding="utf-8") as f:
        f.write(f"名称: {name}\nID: {cid}\n分值: {info['value']}\n描述: {info['description']}\n")

    return challenge_dir, downloaded
```

---

## 4. 分析并提交

```python
def analyze_and_submit(url, headers, challenge_dir, challenge_name, challenge_id):
    """
    对下载的二进制文件运行 4 阶段分析流程：
    1. 信息收集（静态 + 动态）
    2. 规划执行路径
    3. 破解拿到 flag
    4. 提交到 CTFd
    """
    from pathlib import Path
    import subprocess, os, json, requests

    # 查找二进制文件（排除 题目.txt 和描述文件）
    files = [f for f in Path(challenge_dir).iterdir()
             if f.is_file() and f.name not in ("题目.txt", "info.json")]

    if not files:
        return {"status": "skipped", "reason": "no files to analyze"}

    binary = str(files[0])
    result = {"name": challenge_name, "status": "pending", "flag": None, "steps": []}

    # ── 阶段 1：信息收集 ──
    result["steps"].append({"phase": "info_collection", "action": "file_type"})
    r = subprocess.run(["file", binary], capture_output=True, text=True, timeout=10)
    file_info = r.stdout.strip()

    result["steps"].append({"phase": "info_collection", "action": "strings"})
    r = subprocess.run(["strings", binary], capture_output=True, text=True, timeout=30)
    strings_out = r.stdout

    # 初步 flag 检测
    import re as regex
    flag_match = regex.search(r'flag\{[^}]+\}', strings_out)
    if flag_match:
        result["flag"] = flag_match.group(0)
        result["status"] = "solved_static"

    # ── 阶段 2：动态分析 ──
    if not result["flag"]:
        result["steps"].append({"phase": "dynamic", "action": "run_and_observe"})
        try:
            r = subprocess.run([binary], capture_output=True, text=True, timeout=10)
            output = r.stdout + r.stderr
            flag_match = regex.search(r'flag\{[^}]+\}', output)
            if flag_match:
                result["flag"] = flag_match.group(0)
                result["status"] = "solved_dynamic"
        except:
            pass

    # ── 阶段 3：脚本破解 ──
    if not result["flag"]:
        result["steps"].append({"phase": "bruteforce", "action": "script_attempt"})
        # 尝试运行脚本（如果存在 solver 模式）
        pass

    # ── 阶段 4：提交 ──
    if result["flag"]:
        r = requests.post(f"{url}/api/v1/challenges/attempt",
            headers=headers,
            json={"challenge_id": challenge_id, "submission": result["flag"]},
            timeout=10)
        msg = r.json().get("data", {}).get("message", "unknown")
        result["submission"] = msg
        result["status"] = "submitted" if msg == "Correct" else "wrong_flag"

    return result
```

---

## 5. 一键执行

```python
def ctfd_auto(url, dest_dir, user="admin", password="OpenCyber@2026Admin"):
    """全自动流程：登录 → 列题 → 下载 → 分析 → 提交"""
    import os, json

    print(f"[*] 连接 {url}...")
    if not check_ctfd(url):
        print("[!] 无法连接")
        return

    print(f"[*] 登录...")
    login = ctfd_login(url, user, password)
    if not login:
        print("[!] 登录失败")
        return
    s, token, headers = login

    print(f"[*] 获取题目列表...")
    challenges = list_challenges(url, headers)
    print(f"    共 {len(challenges)} 道逆向题")

    os.makedirs(dest_dir, exist_ok=True)
    all_results = []

    for c in challenges:
        name = c["name"]
        print(f"\n[→] 处理: {name}")

        # 下载
        ch_dir, files = download_challenge(url, headers, c, dest_dir)
        print(f"    下载到: {ch_dir}")
        for f in files:
            print(f"      - {os.path.basename(f)}")

        # 分析
        result = analyze_and_submit(url, headers, ch_dir, name, c["id"])
        all_results.append(result)

        if result["flag"]:
            print(f"    ✅ Flag: {result['flag']}")
            print(f"    提交结果: {result.get('submission', 'N/A')}")
        else:
            print(f"    ❌ 未找到 flag")

    # 汇总
    solved = sum(1 for r in all_results if r["flag"])
    print(f"\n{'='*40}")
    print(f"完成! 已解 {solved}/{len(challenges)}")
    return all_results
```

---

## 6. 快速使用

```bash
# 默认使用本地 CTFd（localhost:8000），下载到默认目录
ctfd_auto("http://localhost:8000", "E:/知识产物(必保存)/课设/基准测试/逆向/")

# 指定远程 CTFd 和凭证
ctfd_auto("http://192.168.1.100:8000", "./downloads", user="player1", password="xxx")

# 只下载不分析
login = ctfd_login(url, user, passwd)
if login:
    s, token, headers = login
    challenges = list_challenges(url, headers)
    for c in challenges[:3]:  # 只下前 3 道
        download_challenge(url, headers, c, "./downloads")
```

---

## 7. 注意点

- **token 可能过期**：401 时重新 `ctfd_login()`
- **大文件下载**：requests 默认 30s 超时，大文件时递增 timeout
- **CTFd 版本差异**：较老版本（<3.0）的 API endpoint 可能不同，`/api/v1/challenges/{id}/files` 可能需要改用 `/api/v1/files?challenge_id={id}`
- **非 ELF 文件**：Windows PE 文件用本地分析，ELF 通过 WSL `safe-run`
- **题目分类**：如果 URL 里既有逆向又有 PWN 题，可以过 `list_challenges` 的 category 参数筛选
- **记录数据库**：分析完后调用 `database-recorder` skill 将结果写入 `opencyber.db`
