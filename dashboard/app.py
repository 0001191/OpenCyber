"""
OpenCyber 逆向分析仪表盘
========================
总览展示：题目统计、分析进度、成功率、最近分析记录
"""

import sqlite3
import time
from pathlib import Path

import streamlit as st
import pandas as pd

# ── 数据库路径 ──────────────────────────────────────────
DB_PATH = "E:/知识产物(必保存)/课设/数据库/opencyber.db"

# ── 配色（适配深色/浅色） ──────────────────────────────
STATUS_COLORS = {
    "success": "#00cc66",
    "failed": "#ff4b4b",
    "running": "#ffa500",
    "pending": "#888888",
    "not_run": "#cccccc",
}
DIFF_COLORS = {
    "basic": "#4caf50",
    "medium": "#ff9800",
    "hard": "#f44336",
}


# ── 数据库工具函数 ─────────────────────────────────────
@st.cache_data(ttl=10)
def load_overview():
    """总览统计数据"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 题目总数
    cur.execute("SELECT COUNT(*) FROM samples")
    total = cur.fetchone()[0]

    # 各难度数量
    cur.execute(
        "SELECT difficulty, COUNT(*) as cnt FROM samples GROUP BY difficulty"
    )
    diff_counts = {r["difficulty"]: r["cnt"] for r in cur.fetchall()}

    # 执行结果统计
    cur.execute("""
        SELECT
            t.result,
            COUNT(*) as cnt
        FROM tasks t
        JOIN (
            SELECT sample_id, MAX(id) as max_id FROM tasks GROUP BY sample_id
        ) latest ON t.id = latest.max_id
        GROUP BY t.result
    """)
    result_counts = {r["result"]: r["cnt"] for r in cur.fetchall()}
    solved = result_counts.get("success", 0)
    failed = result_counts.get("failed", 0)
    no_run = total - solved - failed

    # 平均耗时（仅成功）
    cur.execute("""
        SELECT AVG(t.duration_ms) as avg_ms
        FROM tasks t
        JOIN (
            SELECT sample_id, MAX(id) as max_id FROM tasks GROUP BY sample_id
        ) latest ON t.id = latest.max_id
        WHERE t.result = 'success'
    """)
    row = cur.fetchone()
    avg_ms = round(row["avg_ms"]) if row and row["avg_ms"] else 0

    conn.close()
    return {
        "total": total,
        "solved": solved,
        "failed": failed,
        "no_run": no_run,
        "success_rate": round(solved / total * 100, 1) if total else 0,
        "avg_duration_ms": avg_ms,
        "diff_counts": diff_counts,
    }


@st.cache_data(ttl=10)
def load_challenges():
    """所有题目及最新执行状态"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT
            s.id,
            s.name,
            s.difficulty,
            COALESCE(t.status, 'not_run')  AS status,
            t.result,
            t.duration_ms,
            t.finished_at,
            r.flag,
            t.error_msg,
            s.tags,
            s.file_type,
            s.arch
        FROM samples s
        LEFT JOIN tasks t
            ON t.sample_id = s.id
            AND t.id = (SELECT MAX(id) FROM tasks WHERE sample_id = s.id)
        LEFT JOIN results r ON r.task_id = t.id
        ORDER BY s.id
        """,
        conn,
    )
    conn.close()

    # 格式化耗时
    def fmt_dur(ms):
        if pd.isna(ms):
            return "-"
        if ms < 1000:
            return f"{int(ms)}ms"
        if ms < 60000:
            return f"{ms/1000:.1f}s"
        return f"{int(ms//60000)}m{int((ms%60000)/1000)}s"

    df["duration_display"] = df["duration_ms"].apply(fmt_dur)
    df["flag_display"] = df["flag"].apply(
        lambda x: f"`{x}`" if pd.notna(x) else ""
    )
    return df


@st.cache_data(ttl=10)
def load_recent_tasks(limit=10):
    """最近执行记录"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        f"""
        SELECT
            s.name             AS challenge,
            s.difficulty,
            t.status,
            t.result,
            t.duration_ms,
            t.turn_count,
            t.finished_at,
            t.error_msg
        FROM tasks t
        JOIN samples s ON t.sample_id = s.id
        ORDER BY t.finished_at DESC
        LIMIT {limit}
        """,
        conn,
    )
    conn.close()

    def fmt_dur(ms):
        if pd.isna(ms):
            return "-"
        if ms < 1000:
            return f"{int(ms)}ms"
        return f"{ms/1000:.1f}s"

    if not df.empty:
        df["duration_display"] = df["duration_ms"].apply(fmt_dur)
    return df


@st.cache_data(ttl=10)
def load_difficulty_stats():
    """按难度的统计数据"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT
            s.difficulty,
            COUNT(*)                                 AS total,
            SUM(CASE WHEN t.result='success' THEN 1 ELSE 0 END) AS solved,
            SUM(CASE WHEN t.result='failed'  THEN 1 ELSE 0 END) AS failed,
            ROUND(AVG(CASE WHEN t.result='success' THEN 1.0 ELSE 0.0 END) * 100, 1)
                                                       AS success_rate,
            AVG(CASE WHEN t.result='success' THEN t.duration_ms END)
                                                       AS avg_duration_ms
        FROM samples s
        LEFT JOIN tasks t
            ON t.sample_id = s.id
            AND t.id = (SELECT MAX(id) FROM tasks WHERE sample_id = s.id)
        GROUP BY s.difficulty
        ORDER BY
            CASE s.difficulty
                WHEN 'basic'  THEN 1
                WHEN 'medium' THEN 2
                WHEN 'hard'   THEN 3
                ELSE 4
            END
        """,
        conn,
    )
    conn.close()

    def fmt_dur(ms):
        if pd.isna(ms):
            return "-"
        if ms < 1000:
            return f"{int(ms)}ms"
        return f"{ms/1000:.1f}s"

    if not df.empty:
        df["duration_display"] = df["avg_duration_ms"].apply(fmt_dur)
        df["solved_display"] = df.apply(
            lambda r: f"{int(r['solved'])}/{int(r['total'])}", axis=1
        )
        df["progress"] = df.apply(
            lambda r: int(r["solved"] / r["total"] * 100) if r["total"] else 0,
            axis=1,
        )
    return df


# ══════════════════════════════════════════════════════════
#  页面布局
# ══════════════════════════════════════════════════════════

st.set_page_config(
    page_title="OpenCyber 逆向分析面板",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── 标题区 ────────────────────────────────────────────
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem; font-weight: 700; margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1rem; color: #888; margin-bottom: 1.5rem;
    }
    .metric-card {
        background: #f5f5f5; border-radius: 12px; padding: 1.2rem 1.5rem;
        text-align: center; border: 1px solid #e0e0e0;
    }
    .metric-value {
        font-size: 2rem; font-weight: 700; line-height: 1.2;
    }
    .metric-label {
        font-size: 0.85rem; color: #666; margin-top: 0.2rem;
    }
    .status-dot {
        display: inline-block; width: 10px; height: 10px;
        border-radius: 50%; margin-right: 6px;
    }
    .diff-tag {
        display: inline-block; padding: 2px 10px; border-radius: 10px;
        font-size: 0.75rem; font-weight: 600; color: white;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

col1, col2 = st.columns([3, 1])
with col1:
    st.markdown('<div class="main-header">🛡️ OpenCyber 逆向分析仪表盘</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">AI 驱动的二进制逆向分析平台 · 分析结果总览</div>',
        unsafe_allow_html=True,
    )
with col2:
    if st.button("🔄 刷新数据", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── 加载数据 ──────────────────────────────────────────
try:
    overview = load_overview()
    challenges = load_challenges()
    recent = load_recent_tasks(10)
    diff_stats = load_difficulty_stats()
except Exception as e:
    st.error(f"❌ 数据库连接失败：{e}")
    st.info(f"请确认数据库路径：`{DB_PATH}`")
    st.stop()

# ══════════════════════════════════════════════════════════
#  第一部分：总览 Metrics 卡片
# ══════════════════════════════════════════════════════════

st.subheader("📊 总览")

m1, m2, m3, m4, m5 = st.columns(5)

with m1:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-value">{overview['total']}</div>
            <div class="metric-label">题目总数</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with m2:
    pct = overview["success_rate"]
    solved = overview["solved"]
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-value" style="color:#00cc66">{solved}</div>
            <div class="metric-label">已解决 ✅</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with m3:
    failed = overview["failed"]
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-value" style="color:#ff4b4b">{failed}</div>
            <div class="metric-label">失败 ❌</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with m4:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-value" style="color:{'#00cc66' if pct >= 50 else '#ff9800'}">{pct}%</div>
            <div class="metric-label">成功率</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with m5:
    avg = overview["avg_duration_ms"]
    if avg >= 60000:
        avg_display = f"{avg//60000}m{avg%60000//1000}s"
    elif avg >= 1000:
        avg_display = f"{avg/1000:.1f}s"
    else:
        avg_display = f"{avg}ms"
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-value">{avg_display}</div>
            <div class="metric-label">平均耗时（成功）</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.divider()

# ══════════════════════════════════════════════════════════
#  第二部分：难度分布
# ══════════════════════════════════════════════════════════

st.subheader("📈 按难度分布")
if not diff_stats.empty:
    cols = st.columns(len(diff_stats))
    for i, (_, row) in enumerate(diff_stats.iterrows()):
        color = DIFF_COLORS.get(row["difficulty"], "#888")
        with cols[i]:
            st.markdown(
                f"""
                <div class="metric-card" style="border-left: 4px solid {color};">
                    <div style="margin-bottom: 8px;">
                        <span class="diff-tag" style="background:{color}">
                            {row['difficulty'].upper()}
                        </span>
                    </div>
                    <div class="metric-value">{row['solved_display']}</div>
                    <div class="metric-label">已解决 / 总数</div>
                    <div style="margin-top: 8px; font-size:0.85rem; color:{color}">
                        成功率 {row['success_rate']}%
                    </div>
                    <div style="font-size:0.8rem; color:#888">
                        平均 {row['duration_display']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # 可视化进度条
    st.markdown("#### 解决进度")
    for _, row in diff_stats.iterrows():
        color = DIFF_COLORS.get(row["difficulty"], "#888")
        label = row["difficulty"].upper()
        pct = row["progress"]
        st.markdown(
            f"""
            <div style="margin:8px 0">
                <div style="display:flex;justify-content:space-between;font-size:0.85rem">
                    <span><span class="diff-tag" style="background:{color}">{label}</span></span>
                    <span>{row['solved_display']} ({pct}%)</span>
                </div>
                <div style="background:#e0e0e0;border-radius:8px;height:10px;margin-top:4px;overflow:hidden">
                    <div style="background:{color};width:{pct}%;height:100%;border-radius:8px;transition:width 0.5s"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
else:
    st.info("暂无难度统计数据")

st.divider()

# ══════════════════════════════════════════════════════════
#  第三部分：全部题目列表
# ══════════════════════════════════════════════════════════

st.subheader("📋 全部题目")
if not challenges.empty:
    # 筛选控件
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        diff_filter = st.multiselect(
            "难度筛选",
            options=sorted(challenges["difficulty"].unique()),
            default=[],
        )
    with col_f2:
        status_filter = st.multiselect(
            "状态筛选",
            options=sorted(challenges["status"].unique()),
            default=[],
        )
    with col_f3:
        search = st.text_input("🔍 搜索题目名称", placeholder="输入关键字...")

    # 应用筛选
    filtered = challenges.copy()
    if diff_filter:
        filtered = filtered[filtered["difficulty"].isin(diff_filter)]
    if status_filter:
        filtered = filtered[filtered["status"].isin(status_filter)]
    if search:
        filtered = filtered[
            filtered["name"].str.contains(search, case=False, na=False)
        ]

    # 显示为表格
    display_cols = {
        "id": "ID",
        "name": "题目名称",
        "difficulty": "难度",
        "status": "状态",
        "duration_display": "耗时",
        "flag_display": "Flag",
        "finished_at": "完成时间",
    }
    table = filtered[list(display_cols.keys())].copy()
    table.columns = list(display_cols.values())

    # 美化状态列
    def color_status(val):
        if val == "success":
            return f'🟢 success'
        elif val == "failed":
            return f'🔴 failed'
        elif val == "running":
            return f'🟡 running'
        elif val == "not_run":
            return f'⚪ not_run'
        return val

    def color_diff(val):
        c = DIFF_COLORS.get(val, "#888")
        return f'<span class="diff-tag" style="background:{c}">{val.upper()}</span>'

    table["状态"] = table["状态"].apply(color_status)
    table["难度"] = table["难度"].apply(color_diff)

    st.markdown(table.to_html(escape=False, index=False), unsafe_allow_html=True)

    st.caption(f"共 {len(filtered)} 条 / 总 {len(challenges)} 条")
else:
    st.info("暂无题目数据")

st.divider()

# ══════════════════════════════════════════════════════════
#  第四部分：最近分析记录
# ══════════════════════════════════════════════════════════

st.subheader("🕐 最近分析记录")
if not recent.empty:
    # 把 error_msg 列截短显示
    if "error_msg" in recent.columns:
        recent["error_display"] = recent["error_msg"].apply(
            lambda x: (str(x)[:100] + "...") if pd.notna(x) and len(str(x)) > 100 else (str(x) if pd.notna(x) else "")
        )
    else:
        recent["error_display"] = ""

    rcols = {
        "challenge": "题目",
        "difficulty": "难度",
        "result": "结果",
        "duration_display": "耗时",
        "turn_count": "轮次",
        "finished_at": "时间",
        "error_display": "错误信息",
    }
    rtable = recent[list(rcols.keys())].copy()
    rtable.columns = list(rcols.values())

    def color_result(val):
        if val == "success":
            return f'🟢 success'
        elif val == "failed":
            return f'🔴 failed'
        elif val == "running":
            return f'🟡 running'
        return str(val)

    rtable["结果"] = rtable["结果"].apply(color_result)

    st.markdown(rtable.to_html(escape=False, index=False), unsafe_allow_html=True)
else:
    st.info("暂无执行记录 — Agent 尚未分析过题目")

st.divider()
st.caption(f"🔄 数据自动刷新，每 10 秒更新 ｜ 数据库：`{DB_PATH}` ｜ OpenCyber v1.0")
