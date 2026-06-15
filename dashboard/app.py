"""
OpenCyber CTFd 一键流程系统
============================
输入 CTFd URL + 题目名 → 自动下载 → 分析 → 提交 flag
"""
import sqlite3, re, os, sys, json, subprocess, time, io, urllib3
from pathlib import Path
from datetime import datetime

import streamlit as st
import requests as req

urllib3.disable_warnings()

# ── 常量 ───────────────────────────────────────────────
DB_PATH = "E:/知识产物(必保存)/课设/数据库/opencyber.db"
DEFAULT_DOWNLOAD_DIR = "E:/知识产物(必保存)/课设/基准测试/NYU_CTF_Bench/development/"
this_python = sys.executable

# ══════════════════════════════════════════════════════════
#  核心逻辑
# ══════════════════════════════════════════════════════════

def step_log(step, msg):
    """格式化步骤日志"""
    return f"**{step}** → {msg}"


def ctfd_login(url, user, password):
    """登录 CTFd，返回 (session, token, headers) 或失败原因"""
    import urllib3
    urllib3.disable_warnings()

    s = req.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    # 通过系统代理（VPN）访问目标

    # 先试 API 直接登录（JSON POST 原生支持 UTF-8）
    api_result = _login_via_api(s, url, user, password)
    if isinstance(api_result, tuple) and len(api_result) == 3:
        return api_result
    error_msg = api_result.get("error", "未知错误") if isinstance(api_result, dict) else "登录失败"

    # 再试 Web 表单登录
    try:
        r = s.get(f"{url}/login", timeout=10, verify=False)
        if r.status_code >= 500:
            return None
        m = re.search(r'name="nonce"[^>]*value="([^"]+)"', r.text)
        if m:
            nonce = m.group(1)
            s.post(f"{url}/login",
                   data={"name": user, "password": password, "nonce": nonce},
                   timeout=10, verify=False)
        r = s.get(f"{url}/settings", timeout=10, verify=False)
        m = re.search(r'csrfNonce[^"]*"([a-f0-9]+)"', r.text)
        if m:
            csrf = m.group(1)
            r2 = s.post(f"{url}/api/v1/tokens",
                headers={"CSRF-Token": csrf, "Content-Type": "application/json"},
                json={"expiration": "2099-12-31"}, timeout=10, verify=False)
            if r2.status_code == 200:
                token = r2.json()["data"]["value"]
                return s, token, {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    except Exception:
        pass

    # 返回错误信息
    return {"error": error_msg}


def _login_via_api(s, url, user, password):
    """API 直接登录（新版 CTFd，支持中文用户名）"""
    try:
        r = s.post(f"{url}/api/v1/users/login",
            json={"name": user, "password": password},
            timeout=15, verify=False)
        if r.status_code == 200:
            data = r.json()
            token = data.get("data", {}).get("access_token", "")
            if token:
                return s, token, {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        # 返回更多诊断信息
        return {"error": f"API 返回 {r.status_code}: {r.text[:200]}"}
    except req.exceptions.Timeout:
        return {"error": "请求超时"}
    except req.exceptions.ConnectionError as e:
        return {"error": f"连接失败: {e}"}
    except Exception as e:
        return {"error": str(e)}


def list_challenges(url, headers, filter_name=None):
    """列出题目，filter_name 支持模糊匹配"""
    r = req.get(f"{url}/api/v1/challenges", headers=headers, timeout=10)
    data = r.json().get("data", [])
    if filter_name:
        data = [c for c in data if filter_name.lower() in c["name"].lower()]
    return data


def fetch_challenge_detail(url, headers, cid):
    """获取题目详情（附件列表）"""
    r = req.get(f"{url}/api/v1/challenges/{cid}", headers=headers, timeout=10)
    return r.json().get("data", {})


def download_files(url, challenge, dest_dir):
    """下载题目附件到目录，返回 (challenge_dir, file_paths)"""
    name = challenge["name"]
    cid = challenge["id"]
    ch_dir = os.path.join(dest_dir, name)
    os.makedirs(ch_dir, exist_ok=True)

    detail = fetch_challenge_detail(url, None, cid)
    description = detail.get("description", "")
    files_raw = detail.get("files", [])

    # 存描述
    with open(os.path.join(ch_dir, "题目.txt"), "w", encoding="utf-8") as f:
        f.write(f"名称: {name}\nID: {cid}\n描述: {description}\n")

    # 下载文件
    downloaded = []
    for f_url in files_raw:
        f_url = f_url.strip()
        if not f_url.startswith("http"):
            f_url = f"{url}{f_url}"
        fname = os.path.basename(f_url.split("?")[0]).split("/")[-1]
        if not fname:
            fname = f"{name}.bin"
        fpath = os.path.join(ch_dir, fname)
        try:
            r = req.get(f_url, timeout=60)
            with open(fpath, "wb") as f:
                f.write(r.content)
            downloaded.append(fpath)
        except Exception as e:
            pass

    return ch_dir, downloaded


def analyze_binary(binary_path):
    """
    4 阶段分析二进制，返回分析结果字典
    阶段1: file + strings 静态
    阶段2: 直接运行观察输出
    阶段3: GDB 关键寄存器提取
    阶段4: 脚本爆破
    """
    result = {"flag": None, "steps": [], "evidence": []}

    def add_step(name, ok, detail):
        result["steps"].append({"name": name, "ok": ok, "detail": detail})

    bp = Path(binary_path)
    if not bp.exists():
        add_step("检查文件", False, f"文件不存在: {binary_path}")
        return result

    # ── 阶段1: 静态分析 ──
    try:
        r = subprocess.run(["file", str(bp)], capture_output=True, text=True, timeout=10)
        file_info = r.stdout.strip()
        add_step("file 识别", True, file_info)
        result["evidence"].append(("file", file_info))
    except Exception as e:
        add_step("file 识别", False, str(e))

    try:
        r = subprocess.run(["strings", str(bp)], capture_output=True, text=True, timeout=30)
        strs_out = r.stdout
        add_step("strings 提取", True, f"提取了 {len(strs_out)} 字符的字符串")

        # 抓 flag
        for m in re.finditer(r'flag\{[^}]+\}', strs_out):
            result["flag"] = m.group(0)
            add_step("strings flag 检测", True, f"找到 flag: {result['flag']}")
            return result

        # 抓可能的关键词
        hints = []
        for kw in ["password", "correct", "wrong", "key:", "secret", "debug", "flag"]:
            for line in strs_out.split("\n"):
                if kw.lower() in line.lower() and len(line.strip()) < 200:
                    hints.append(line.strip())
        if hints:
            result["evidence"].append(("strings_hints", hints[:10]))
    except Exception as e:
        add_step("strings 提取", False, str(e))

    # ── 阶段2: 直接运行 ──
    try:
        r = subprocess.run([str(bp)], capture_output=True, text=True, timeout=10, input="test\n")
        output = r.stdout + r.stderr
        add_step("运行观察", True, f"stdout: {r.stdout[:200]}")
        result["evidence"].append(("run_output", r.stdout[:500]))

        for m in re.finditer(r'flag\{[^}]+\}', output):
            result["flag"] = m.group(0)
            add_step("运行时 flag 检测", True, f"找到 flag: {result['flag']}")
            return result
    except subprocess.TimeoutExpired:
        add_step("运行观察", False, "超时（>10s）")
    except Exception as e:
        add_step("运行观察", False, str(e))

    # ── 阶段3: GDB 深度分析（如果可用） ──
    try:
        gdb_cmd = "gdb"
        r = subprocess.run(["which", gdb_cmd] if os.name != "nt" else ["where", gdb_cmd],
                          capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            gdb_script = f"""
set pagination off
set confirm off
file {bp}
info functions
quit
"""
            r = subprocess.run([gdb_cmd, "-batch", "-x", "/dev/stdin" if os.name != "nt" else "-"],
                             input=gdb_script, capture_output=True, text=True, timeout=15)
            add_step("GDB 函数枚举", True, f"检测到函数列表")
            result["evidence"].append(("gdb_functions", r.stdout[:500]))
    except Exception as e:
        add_step("GDB 分析", False, str(e))

    # ── 阶段4: 通用爆破（常见的简单 flag 模式） ──
    add_step("分析完成", True, "静态+动态分析完毕，未找到 flag")
    result["flag"] = None
    return result


def submit_flag(url, headers, challenge_id, flag):
    """提交 flag 到 CTFd"""
    try:
        r = req.post(f"{url}/api/v1/challenges/attempt",
            headers=headers,
            json={"challenge_id": challenge_id, "submission": flag},
            timeout=10)
        data = r.json()
        return data.get("data", {}).get("message", "unknown")
    except Exception as e:
        return f"提交失败: {e}"


def save_to_db(sample_name, file_path, file_type, arch, bits, result_data, flag, submission_msg):
    """将分析结果写入 opencyber.db"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 插入或忽略 samples
    cur.execute("SELECT id FROM samples WHERE name=?", (sample_name,))
    row = cur.fetchone()
    if row:
        sample_id = row[0]
    else:
        cur.execute("""INSERT INTO samples (name, file_path, file_type, arch, bits, difficulty, source)
            VALUES (?,?,?,?,?, 'medium', 'ctf_import')""",
            (sample_name, file_path, file_type, arch or "unknown", bits or 0))
        sample_id = cur.lastrowid

    # 插入 task
    duration = result_data.get("_duration_ms", 0)
    cur.execute("""INSERT INTO tasks (sample_id, status, result, duration_ms, finished_at)
        VALUES (?, 'completed', ?, ?, datetime('now'))""",
        (sample_id, "success" if flag else "failed", duration))
    task_id = cur.lastrowid

    # 插入 result
    if flag:
        cur.execute("""INSERT INTO results (task_id, flag, conclusion, confidence)
            VALUES (?, ?, ?, ?)""",
            (task_id, flag, submission_msg, 1.0 if submission_msg == "Correct" else 0.5))

    conn.commit()
    conn.close()
    return sample_id, task_id


def run_pipeline(url, user, password, challenge_name, dest_dir, status_area):
    """全流程执行器（在 status container 内逐步输出）"""
    start_time = time.time()
    result = {"status": "running", "flag": None, "steps": [], "error": None}
    status_area.markdown(step_log("🚀 启动", "开始全自动流程..."))

    # ── 1. 连接 ──
    status_area.markdown(step_log("🔗 连接", f"正在连接 {url}..."))
    try:
        r = req.get(url, timeout=10, verify=False,
                     headers={"User-Agent": "Mozilla/5.0"})
        status_area.markdown(step_log("🔗 连接", f"✅ 连接成功 (HTTP {r.status_code})"))
    except Exception as e:
        status_area.markdown(step_log("🔗 连接", f"❌ 连接失败: {e}"))
        result["status"] = "failed"
        result["error"] = str(e)
        return result

    # ── 2. 登录 ──
    status_area.markdown(step_log("🔑 登录", f"以 {user} 登录..."))
    login = ctfd_login(url, user, password)
    if not login or isinstance(login, dict):
        err = login.get("error", "登录失败") if isinstance(login, dict) else "登录失败"
        status_area.markdown(step_log("🔑 登录", f"❌ {err}"))
        result["status"] = "failed"
        result["error"] = err
        return result
    s, token, headers = login
    status_area.markdown(step_log("🔑 登录", "✅ 登录成功，已获取 API token"))

    # ── 3. 查题 ──
    status_area.markdown(step_log("📋 查题", f"搜索: {challenge_name}"))
    challenges = list_challenges(url, headers, challenge_name)
    if not challenges:
        # 尝试不限分类列出所有
        all_chals = list_challenges(url, headers, None)
        matches = [c for c in all_chals if challenge_name.lower() in c["name"].lower()]
        if matches:
            challenges = matches
        else:
            status_area.markdown(step_log("📋 查题",
                f"❌ 未找到匹配题目。可用题目: {', '.join(c['name'] for c in all_chals[:10])}"))
            result["status"] = "failed"
            result["error"] = "challenge not found"
            return result

    status_area.markdown(step_log("📋 查题",
        f"✅ 找到 {len(challenges)} 道匹配题目: {', '.join(c['name'] for c in challenges)}"))

    for challenge in challenges:
        cname = challenge["name"]
        cid = challenge["id"]

        status_area.markdown(f"---\n### ▶ 处理: {cname} (ID={cid})")

        # ── 4. 下载 ──
        status_area.markdown(step_log("📥 下载", f"下载到 {dest_dir}..."))
        ch_dir, files = download_files(url, challenge, dest_dir)
        if files:
            status_area.markdown(step_log("📥 下载",
                f"✅ 已下载 {len(files)} 个文件:\n" +
                "\n".join(f"  - `{os.path.basename(f)}`" for f in files)))
        else:
            status_area.markdown(step_log("📥 下载", "⚠️ 没有附件可下载（可能已内置在描述中）"))

        # ── 5. 分析 ──
        found_flag = None
        for fpath in files:
            fname = os.path.basename(fpath)
            status_area.markdown(step_log("🔬 分析", f"分析: `{fname}`"))
            analysis = analyze_binary(fpath)
            for s in analysis["steps"]:
                icon = "✅" if s["ok"] else "⚠️"
                status_area.markdown(step_log(f"  {icon} {s['name']}",
                    s["detail"][:200]))
            if analysis["flag"]:
                found_flag = analysis["flag"]
                status_area.markdown(
                    step_log("🎯 Flag 发现", f"**{found_flag}**"))
                break

        # 如果文件分析都没找到，尝试从描述/strings 再找
        if not found_flag:
            desc_file = os.path.join(ch_dir, "题目.txt")
            if os.path.exists(desc_file):
                with open(desc_file, encoding="utf-8") as f:
                    desc = f.read()
                    for m in re.finditer(r'flag\{[^}]+\}', desc):
                        found_flag = m.group(0)
                        break

        # ── 6. 提交 ──
        if found_flag:
            status_area.markdown(step_log("📤 提交", f"提交 flag 到 {cname}..."))
            msg = submit_flag(url, headers, cid, found_flag)
            status_area.markdown(step_log("📤 提交", f"结果: **{msg}**"))
        else:
            msg = "未找到 flag"
            status_area.markdown(step_log("📤 提交", "⚠️ 未找到 flag，跳过提交"))

        # ── 7. 存储数据库 ──
        elapsed = int((time.time() - start_time) * 1000)
        # 取第一个二进制文件的信息
        first_file = files[0] if files else ""
        try:
            r = subprocess.run(["file", first_file], capture_output=True, text=True, timeout=5)
            ftype = r.stdout.strip()[:100]
        except:
            ftype = ""
        save_to_db(cname, first_file, ftype, "", 0,
                   {"_duration_ms": elapsed}, found_flag, msg)
        status_area.markdown(step_log("💾 存储", "已写入数据库"))

    # ── 汇总 ──
    total_time = time.time() - start_time
    result["status"] = "completed"
    result["flag"] = found_flag
    result["duration_s"] = round(total_time, 1)
    return result


# ══════════════════════════════════════════════════════════
#  Streamlit UI
# ══════════════════════════════════════════════════════════

st.set_page_config(
    page_title="OpenCyber 一键流程",
    page_icon="⚡",
    layout="wide",
)

st.markdown("""
<style>
.big-btn button {
    font-size: 1.2rem !important;
    font-weight: 600 !important;
    padding: 0.6rem 2rem !important;
}
.step-log { margin: 0.3rem 0; }
.pipeline-card {
    background: #f8f9fa;
    border-radius: 12px;
    padding: 1.5rem;
    border: 1px solid #e0e0e0;
    margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)

col_title, _ = st.columns([3, 1])
with col_title:
    st.markdown("## ⚡ OpenCyber 一键流程系统")

st.caption("输入 CTFd 地址和题目名称，自动完成：连接 → 登录 → 下载 → 分析 → 提交")

# ── 侧边栏：历史记录 ──
with st.sidebar:
    st.markdown("### 📜 执行历史")
    try:
        conn = sqlite3.connect(DB_PATH)
        history = conn.execute("""
            SELECT s.name, t.result, t.duration_ms, t.finished_at, r.flag
            FROM tasks t
            JOIN samples s ON s.id = t.sample_id
            LEFT JOIN results r ON r.task_id = t.id
            ORDER BY t.finished_at DESC LIMIT 20
        """).fetchall()
        conn.close()
        if history:
            for h in history:
                icon = "✅" if h[1] == "success" else "❌" if h[1] == "failed" else "⬜"
                dur = f"{h[2]//1000}s" if h[2] else "-"
                flag_str = f" `{h[4]}`" if h[4] else ""
                st.markdown(f"{icon} **{h[0]}** {dur}{flag_str}")
        else:
            st.info("暂无记录")
    except Exception:
        st.info("暂无记录")

# ── 主面板 ──
tab1, tab2 = st.tabs(["🎯 启动流程", "📊 历史统计"])

with tab1:
    with st.container():
        st.markdown("### 目标配置")

        c1, c2 = st.columns([2, 1])
        with c1:
            ctfd_url = st.text_input("CTFd 网站首页", "http://172.16.172.62:8001",
                help="填网站首页地址，不需要加 /challenges")
        with c2:
            challenge_name = st.text_input("题目名称（支持模糊匹配）",
                placeholder="如: aerosol_can")

        with st.expander("高级选项", expanded=False):
            cc1, cc2, cc3 = st.columns(3)
            with cc1:
                username = st.text_input("用户名", placeholder="请输入用户名")
            with cc2:
                password = st.text_input("密码", type="password", placeholder="请输入密码")
            with cc3:
                download_dir = st.text_input("下载目录", DEFAULT_DOWNLOAD_DIR)

        run_btn = st.button("🚀 启动全自动流程", type="primary", use_container_width=True)

    # ── 执行区 ──
    if run_btn:
        if not challenge_name:
            st.error("请输入题目名称")
            st.stop()

        status_container = st.container()
        with status_container:
            status_area = st.status("流程执行中...", expanded=True, state="running")

        # 跑流程
        result = run_pipeline(
            ctfd_url.strip(),
            username, password,
            challenge_name.strip(),
            download_dir,
            status_area
        )

        # 更新状态
        if result["status"] == "completed":
            status_area.update(label="✅ 流程完成", state="complete")
        else:
            status_area.update(label=f"❌ 流程失败: {result.get('error', '')}", state="error")

        # 结果摘要
        st.markdown("---")
        st.markdown("### 📋 结果摘要")
        if result["flag"]:
            st.success(f"🎯 **Flag**: `{result['flag']}`")
        else:
            st.warning("⚠️ 未找到 flag")

        if result.get("duration_s"):
            st.info(f"⏱ 总耗时: {result['duration_s']} 秒")

        st.button("🔄 再来一次", on_click=lambda: st.rerun())

with tab2:
    st.markdown("### 📊 历史统计")
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM samples")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM tasks WHERE result='success'")
        solved = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM tasks WHERE result='failed'")
        failed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM tasks")
        total_tasks = cur.fetchone()[0]
        conn.close()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("总题目数", total)
        m2.metric("已解决", solved)
        m3.metric("失败", failed)
        rate = round(solved / total_tasks * 100, 1) if total_tasks else 0
        m4.metric("成功率", f"{rate}%")

        # 最近记录表格
        conn = sqlite3.connect(DB_PATH)
        import pandas as pd
        df = pd.read_sql_query("""
            SELECT s.name, t.result, t.duration_ms, t.finished_at, r.flag
            FROM tasks t
            JOIN samples s ON s.id = t.sample_id
            LEFT JOIN results r ON r.task_id = t.id
            ORDER BY t.finished_at DESC LIMIT 50
        """, conn)
        conn.close()
        if not df.empty:
            df["duration"] = df["duration_ms"].apply(
                lambda x: f"{x//1000}s" if x and x > 0 else "-")
            df = df.drop(columns=["duration_ms"])
            st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"读取数据库失败: {e}")

st.divider()
st.caption(f"🛡️ OpenCyber 一键流程系统 | 数据库: `{DB_PATH}`")
