-- ============================================================
-- OpenCyber CTF Agent 数据库 Schema
-- 7 张核心表：samples / tasks / tool_calls / observations /
--            agent_memory / results / evaluation_stats
-- 使用方式：sqlite3 opencyber.db < schema.sql
-- ============================================================

-- 1. 题目元数据
CREATE TABLE IF NOT EXISTS samples (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,              -- 文件名
    file_path   TEXT NOT NULL,              -- 样本绝对路径
    file_type   TEXT,                       -- file 命令结果
    arch        TEXT,                       -- x86 / x64 / ARM / MIPS
    bits        INTEGER,                    -- 32 / 64
    endian      TEXT,                       -- little / big
    entry_point TEXT,                       -- 入口点地址
    stripped    INTEGER DEFAULT 0,          -- 是否 strip
    packer      TEXT,                       -- 加壳类型（如有）
    difficulty  TEXT DEFAULT 'basic',       -- basic / medium / hard
    tags        TEXT,                       -- 题型标签，逗号分隔
    source      TEXT DEFAULT 'manual',      -- 来源：manual / ctf_import
    ctfd_id     INTEGER,                    -- CTFd 平台上的题目 ID
    created_at  TEXT DEFAULT (datetime('now'))
);

-- 2. 分析任务
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id   INTEGER NOT NULL REFERENCES samples(id),
    status      TEXT DEFAULT 'pending',     -- pending / running / success / failed
    started_at  TEXT,
    finished_at TEXT,
    duration_ms INTEGER,                    -- 执行耗时（毫秒）
    result      TEXT,                       -- success / failed / timeout
    error_msg   TEXT,                       -- 失败原因
    turn_count  INTEGER DEFAULT 0,          -- Agent 执行轮次
    created_at  TEXT DEFAULT (datetime('now'))
);

-- 3. 工具调用记录
CREATE TABLE IF NOT EXISTS tool_calls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL REFERENCES tasks(id),
    tool_name   TEXT NOT NULL,              -- file / strings / readelf / objdump / gdb / angr / z3 / curl / sqlite3
    parameters  TEXT,                       -- JSON 格式参数
    output      TEXT,                       -- 工具输出摘要
    success     INTEGER DEFAULT 1,          -- 1 = 成功, 0 = 失败
    duration_ms INTEGER,                    -- 耗时
    called_at   TEXT DEFAULT (datetime('now'))
);

-- 4. 中间分析观察结果
CREATE TABLE IF NOT EXISTS observations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL REFERENCES tasks(id),
    content     TEXT NOT NULL,              -- 观察/分析结论
    category    TEXT DEFAULT 'general',     -- general / string / function / crypto / flag / hint
    confidence  REAL DEFAULT 0.5,           -- 置信度 0~1
    turn_index  INTEGER,                    -- 发生在第几轮
    created_at  TEXT DEFAULT (datetime('now'))
);

-- 5. Agent 记忆（线索/经验/失败路径）
CREATE TABLE IF NOT EXISTS agent_memory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         INTEGER NOT NULL REFERENCES tasks(id),
    memory_type     TEXT DEFAULT 'working', -- working / episodic / semantic
    content         TEXT NOT NULL,          -- 记忆内容
    turn_index      INTEGER,               -- 发生在第几轮
    is_key_insight  INTEGER DEFAULT 0,     -- 1 = 关键线索
    source          TEXT,                   -- 来源：tool / analysis / user
    created_at      TEXT DEFAULT (datetime('now'))
);

-- 6. 最终结果
CREATE TABLE IF NOT EXISTS results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL REFERENCES tasks(id),
    flag        TEXT,                       -- 最终 flag
    flag_format INTEGER DEFAULT 0,          -- 格式是否匹配 flag{...}
    conclusion  TEXT,                       -- 破解结论描述
    evidence    TEXT,                       -- 可复核的分析证据
    confidence  REAL DEFAULT 0.0,           -- 置信度 0~1
    submitted   INTEGER DEFAULT 0,          -- 是否已提交 CTFd 平台
    submitted_at TEXT,                      -- 提交时间
    created_at  TEXT DEFAULT (datetime('now'))
);

-- 7. 评测统计
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

-- 索引：加速查询
CREATE INDEX IF NOT EXISTS idx_tasks_sample      ON tasks(sample_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status       ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tool_calls_task    ON tool_calls(task_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_name    ON tool_calls(tool_name);
CREATE INDEX IF NOT EXISTS idx_observations_task  ON observations(task_id);
CREATE INDEX IF NOT EXISTS idx_memory_task        ON agent_memory(task_id);
CREATE INDEX IF NOT EXISTS idx_memory_type        ON agent_memory(memory_type);
CREATE INDEX IF NOT EXISTS idx_results_task       ON results(task_id);
CREATE INDEX IF NOT EXISTS idx_results_flag       ON results(flag);

-- 视图：按难度统计成功率（方便直接查询）
CREATE VIEW IF NOT EXISTS v_evaluation_summary AS
SELECT
    s.difficulty,
    COUNT(*)                                         AS total,
    SUM(CASE WHEN t.result = 'success' THEN 1 ELSE 0 END) AS solved,
    SUM(CASE WHEN t.result = 'failed'  THEN 1 ELSE 0 END) AS failed,
    ROUND(AVG(CASE WHEN t.result = 'success' THEN 1.0 ELSE 0.0 END) * 100, 2) AS success_rate,
    AVG(t.duration_ms)                               AS avg_duration
FROM tasks t
JOIN samples s ON t.sample_id = s.id
GROUP BY s.difficulty;
