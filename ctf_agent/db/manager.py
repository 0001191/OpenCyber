"""
CTF Agent 数据库模块

7 类核心数据表：
- samples:       题目元数据
- tasks:          分析任务
- tool_calls:     工具调用记录
- observations:   中间分析结果
- agent_memory:   Agent 记忆与线索
- results:        最终答案与破解结论
- evaluation_stats: 评测统计
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'db', 'opencyber.db')

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS samples (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,              -- 文件名
    file_path   TEXT NOT NULL,              -- 绝对路径
    file_type   TEXT,                       -- file 命令结果
    arch        TEXT,                       -- x86 / x64 / ARM / MIPS
    bits        INTEGER,                    -- 32 / 64
    endian      TEXT,                       -- little / big
    entry_point TEXT,                       -- 入口点地址
    stripped    INTEGER DEFAULT 0,          -- 是否 strip
    packer      TEXT,                       -- 加壳类型（如有）
    difficulty  TEXT DEFAULT 'basic',       -- basic / medium / hard
    tags        TEXT,                       -- 题型标签，逗号分隔
    source      TEXT,                       -- 来源（CTFd / 手动导入）
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id   INTEGER NOT NULL REFERENCES samples(id),
    status      TEXT DEFAULT 'pending',     -- pending / running / success / failed
    started_at  TEXT,
    finished_at TEXT,
    duration_ms INTEGER,                    -- 执行耗时
    result      TEXT,                       -- success / failed / timeout
    error_msg   TEXT,                       -- 失败原因
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL REFERENCES tasks(id),
    tool_name   TEXT NOT NULL,              -- file/strings/readelf/objdump/gdb/ghidra/angr/z3
    parameters  TEXT,                       -- JSON 参数
    output      TEXT,                       -- 工具输出
    success     INTEGER DEFAULT 1,
    duration_ms INTEGER,
    called_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS observations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL REFERENCES tasks(id),
    content     TEXT NOT NULL,              -- 观察/分析结论
    category    TEXT DEFAULT 'general',     -- general / string / function / crypto / flag
    confidence  REAL DEFAULT 0.5,           -- 置信度 0-1
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agent_memory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         INTEGER NOT NULL REFERENCES tasks(id),
    memory_type     TEXT DEFAULT 'working', -- working / episodic / semantic
    content         TEXT NOT NULL,          -- 记忆内容
    turn_index      INTEGER,               -- Agent 轮次
    is_key_insight  INTEGER DEFAULT 0,     -- 是否是关键线索
    source          TEXT,                  -- 来源（工具/分析/用户）
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL REFERENCES tasks(id),
    flag        TEXT,                       -- 最终 flag
    flag_format INTEGER DEFAULT 0,          -- 格式是否匹配
    conclusion  TEXT,                       -- 破解结论描述
    evidence    TEXT,                       -- 可复核的分析证据
    confidence  REAL DEFAULT 0.0,           -- 置信度
    submitted   INTEGER DEFAULT 0,          -- 是否已提交 CTFd
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS evaluation_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    difficulty      TEXT NOT NULL,           -- basic / medium / hard / all
    total_samples   INTEGER DEFAULT 0,
    solved          INTEGER DEFAULT 0,
    failed          INTEGER DEFAULT 0,
    success_rate    REAL DEFAULT 0.0,
    avg_duration_ms INTEGER DEFAULT 0,
    evaluated_at    TEXT DEFAULT (datetime('now'))
);

-- 索引：加速跨任务/跨进程查询
CREATE INDEX IF NOT EXISTS idx_tasks_sample ON tasks(sample_id);
CREATE INDEX IF NOT EXISTS idx_observations_task ON observations(task_id);
CREATE INDEX IF NOT EXISTS idx_memory_task ON agent_memory(task_id);
CREATE INDEX IF NOT EXISTS idx_memory_type ON agent_memory(memory_type);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tool_calls_task ON tool_calls(task_id);
CREATE INDEX IF NOT EXISTS idx_results_task ON results(task_id);
"""


def get_connection(db_path=None):
    """获取数据库连接"""
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_database(db_path=None):
    """初始化数据库表结构"""
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    return True


# ── CRUD 操作 ─────────────────────────────────

class SampleManager:
    """题目元数据管理"""

    def __init__(self, conn):
        self.conn = conn

    def create(self, name, file_path, file_type=None, arch=None, bits=None,
               endian=None, entry_point=None, stripped=0, packer=None,
               difficulty='basic', tags=None, source='manual'):
        cur = self.conn.execute("""
            INSERT INTO samples (name, file_path, file_type, arch, bits, endian,
                                 entry_point, stripped, packer, difficulty, tags, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, file_path, file_type, arch, bits, endian,
              entry_point, stripped, packer, difficulty, tags or '', source))
        self.conn.commit()
        return cur.lastrowid

    def get(self, sample_id):
        cur = self.conn.execute("SELECT * FROM samples WHERE id=?", (sample_id,))
        return cur.fetchone()

    def list_all(self, difficulty=None):
        if difficulty:
            cur = self.conn.execute("SELECT * FROM samples WHERE difficulty=? ORDER BY id", (difficulty,))
        else:
            cur = self.conn.execute("SELECT * FROM samples ORDER BY id")
        return cur.fetchall()

    def update_tags(self, sample_id, tags):
        self.conn.execute("UPDATE samples SET tags=? WHERE id=?", (tags, sample_id))
        self.conn.commit()

    def delete(self, sample_id):
        self.conn.execute("DELETE FROM samples WHERE id=?", (sample_id,))
        self.conn.commit()


class TaskManager:
    """分析任务管理"""

    def __init__(self, conn):
        self.conn = conn

    def create(self, sample_id):
        cur = self.conn.execute("""
            INSERT INTO tasks (sample_id, started_at) VALUES (?, datetime('now'))
        """, (sample_id,))
        self.conn.commit()
        return cur.lastrowid

    def update_status(self, task_id, status, result=None, error_msg=None):
        now = datetime.now().isoformat()
        self.conn.execute("""
            UPDATE tasks SET status=?, finished_at=?, result=?, error_msg=?,
                             duration_ms=CAST((julianday(?) - julianday(started_at)) * 86400000 AS INTEGER)
            WHERE id=?
        """, (status, now, result, error_msg, now, task_id))
        self.conn.commit()

    def get(self, task_id):
        cur = self.conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
        return cur.fetchone()

    def list_by_sample(self, sample_id):
        cur = self.conn.execute("SELECT * FROM tasks WHERE sample_id=? ORDER BY id DESC", (sample_id,))
        return cur.fetchall()

    def list_recent(self, limit=20):
        cur = self.conn.execute("SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (limit,))
        return cur.fetchall()

    def get_unfinished(self):
        """用于断点续跑：获取未完成的任务"""
        cur = self.conn.execute("SELECT * FROM tasks WHERE status IN ('pending','running')")
        return cur.fetchall()


class ToolCallRecorder:
    """工具调用记录"""

    def __init__(self, conn):
        self.conn = conn

    def record(self, task_id, tool_name, parameters=None, output=None, success=1, duration_ms=None):
        cur = self.conn.execute("""
            INSERT INTO tool_calls (task_id, tool_name, parameters, output, success, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (task_id, tool_name, parameters, output, success, duration_ms))
        self.conn.commit()
        return cur.lastrowid

    def get_by_task(self, task_id):
        cur = self.conn.execute("SELECT * FROM tool_calls WHERE task_id=? ORDER BY id", (task_id,))
        return cur.fetchall()


class MemoryManager:
    """Agent 记忆管理"""

    def __init__(self, conn):
        self.conn = conn

    def write(self, task_id, content, memory_type='working', turn_index=None,
              is_key_insight=0, source=None):
        cur = self.conn.execute("""
            INSERT INTO agent_memory (task_id, memory_type, content, turn_index, is_key_insight, source)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (task_id, memory_type, content, turn_index, is_key_insight, source))
        self.conn.commit()
        return cur.lastrowid

    def read_working(self, task_id):
        """读回当前任务的工作记忆"""
        cur = self.conn.execute("""
            SELECT * FROM agent_memory
            WHERE task_id=? AND memory_type='working'
            ORDER BY turn_index ASC
        """, (task_id,))
        return cur.fetchall()

    def read_semantic(self, tags=None, limit=10):
        """跨任务检索语义记忆（经验复用）"""
        if tags:
            cur = self.conn.execute("""
                SELECT * FROM agent_memory
                WHERE memory_type='semantic' AND content LIKE ?
                ORDER BY created_at DESC LIMIT ?
            """, (f'%{tags}%', limit))
        else:
            cur = self.conn.execute("""
                SELECT * FROM agent_memory WHERE memory_type='semantic'
                ORDER BY created_at DESC LIMIT ?
            """, (limit,))
        return cur.fetchall()

    def read_failures(self, sample_id=None, limit=10):
        """跨任务检索失败路径（策略复用）"""
        if sample_id:
            cur = self.conn.execute("""
                SELECT m.* FROM agent_memory m
                JOIN tasks t ON m.task_id = t.id
                WHERE t.sample_id=? AND m.is_key_insight=1
                ORDER BY m.created_at DESC LIMIT ?
            """, (sample_id, limit))
        else:
            cur = self.conn.execute("""
                SELECT m.*, t.sample_id FROM agent_memory m
                JOIN tasks t ON m.task_id = t.id
                WHERE t.result='failed' AND m.is_key_insight=1
                ORDER BY m.created_at DESC LIMIT ?
            """, (limit,))
        return cur.fetchall()


class ResultManager:
    """结果管理"""

    def __init__(self, conn):
        self.conn = conn

    def save(self, task_id, flag, conclusion='', evidence='', confidence=0.0):
        flag_format = 1 if (flag or '').startswith('flag{') else 0
        cur = self.conn.execute("""
            INSERT INTO results (task_id, flag, flag_format, conclusion, evidence, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (task_id, flag, flag_format, conclusion, evidence, confidence))
        self.conn.commit()
        return cur.lastrowid

    def get_by_task(self, task_id):
        cur = self.conn.execute("SELECT * FROM results WHERE task_id=? ORDER BY id DESC", (task_id,))
        return cur.fetchone()


class EvaluationManager:
    """评测统计管理"""

    def __init__(self, conn):
        self.conn = conn

    def compute_stats(self, difficulty=None):
        """按难度统计成功率"""
        if difficulty:
            cur = self.conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN t.result='success' THEN 1 ELSE 0 END) as solved,
                    SUM(CASE WHEN t.result='failed' THEN 1 ELSE 0 END) as failed,
                    AVG(CASE WHEN t.duration_ms THEN t.duration_ms ELSE NULL END) as avg_ms
                FROM tasks t JOIN samples s ON t.sample_id = s.id
                WHERE s.difficulty=?
            """, (difficulty,))
        else:
            cur = self.conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN t.result='success' THEN 1 ELSE 0 END) as solved,
                    SUM(CASE WHEN t.result='failed' THEN 1 ELSE 0 END) as failed,
                    AVG(CASE WHEN t.duration_ms THEN t.duration_ms ELSE NULL END) as avg_ms
                FROM tasks t
            """)
        return cur.fetchone()

    def save_snapshot(self):
        """保存当前评测快照到 statistics 表"""
        for diff in ['basic', 'medium', 'hard', None]:
            stats = self.compute_stats(diff)
            if stats['total'] > 0:
                rate = round(stats['solved'] / stats['total'] * 100, 2)
                self.conn.execute("""
                    INSERT INTO evaluation_stats (difficulty, total_samples, solved, failed, success_rate, avg_duration_ms)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (diff or 'all', stats['total'], stats['solved'], stats['failed'], rate,
                      int(stats['avg_ms']) if stats['avg_ms'] else 0))
        self.conn.commit()

    def get_failure_examples(self, limit=10):
        """获取典型失败样例"""
        cur = self.conn.execute("""
            SELECT s.name, s.difficulty, t.error_msg, t.duration_ms
            FROM tasks t JOIN samples s ON t.sample_id = s.id
            WHERE t.result='failed'
            ORDER BY t.duration_ms DESC LIMIT ?
        """, (limit,))
        return cur.fetchall()
