"""Repository: full CRUD for all 7 tables."""

import json
from .schema import Database
from ..config import DB_PATH


class Repository:
    def __init__(self, db_path=None):
        self.db = Database(db_path or DB_PATH)

    # ----- Sample CRUD -----
    def create_sample(self, name, file_path, **kwargs):
        with self.db.connect() as conn:
            c = conn.execute(
                """INSERT INTO samples (name, file_path, file_size, sha256, arch, bits, endian, difficulty, tags)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (name, file_path, kwargs.get("file_size"), kwargs.get("sha256"),
                 kwargs.get("arch"), kwargs.get("bits"), kwargs.get("endian"),
                 kwargs.get("difficulty", "unknown"), json.dumps(kwargs.get("tags", [])))
            )
            return c.lastrowid

    def get_sample(self, sample_id):
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM samples WHERE id=?", (sample_id,)).fetchone()
            return dict(row) if row else None

    def list_samples(self):
        with self.db.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM samples ORDER BY id DESC").fetchall()]

    # ----- Task CRUD -----
    def create_task(self, sample_id, task_type="full_analysis"):
        with self.db.connect() as conn:
            c = conn.execute(
                "INSERT INTO tasks (sample_id, task_type) VALUES (?,?)",
                (sample_id, task_type)
            )
            return c.lastrowid

    def get_task(self, task_id):
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            return dict(row) if row else None

    def start_task(self, task_id):
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE tasks SET status='running', started_at=CURRENT_TIMESTAMP WHERE id=?",
                (task_id,)
            )

    def complete_task(self, task_id, success, flag=None, elapsed=0, error=None):
        with self.db.connect() as conn:
            conn.execute(
                """UPDATE tasks SET status=?, flag=?, elapsed_seconds=?,
                   error_message=?, completed_at=CURRENT_TIMESTAMP WHERE id=?""",
                ("completed" if success else "error", flag, elapsed, error, task_id)
            )

    # ----- Tool Calls -----
    def record_tool_call(self, task_id, round_num, tool_name, arguments, output, success=True):
        with self.db.connect() as conn:
            c = conn.execute(
                """INSERT INTO tool_calls (task_id, round_number, tool_name, arguments, output, success)
                   VALUES (?,?,?,?,?,?)""",
                (task_id, round_num, tool_name, json.dumps(arguments or {}),
                 json.dumps(output) if isinstance(output, dict) else str(output), int(success))
            )
            return c.lastrowid

    def get_tool_calls(self, task_id):
        with self.db.connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM tool_calls WHERE task_id=? ORDER BY id", (task_id,)
            ).fetchall()]

    # ----- Intermediate Results -----
    def save_result(self, task_id, result_type, data, source=""):
        with self.db.connect() as conn:
            c = conn.execute(
                "INSERT INTO intermediate_results (task_id, result_type, data, source) VALUES (?,?,?,?)",
                (task_id, result_type, json.dumps(data) if isinstance(data, dict) else str(data), source)
            )
            return c.lastrowid

    def cross_task_read(self, task_id, result_type=None, exclude_current=True, limit=50):
        with self.db.connect() as conn:
            if result_type:
                rows = conn.execute(
                    f"""SELECT * FROM intermediate_results
                       WHERE result_type=? AND task_id!=? ORDER BY created_at DESC LIMIT {limit}""",
                    (result_type, task_id)
                ).fetchall()
            else:
                rows = conn.execute(
                    f"""SELECT * FROM intermediate_results
                       WHERE task_id!=? ORDER BY created_at DESC LIMIT {limit}""",
                    (task_id,)
                ).fetchall()
            return [dict(r) for r in rows]

    # ----- Agent Memory -----
    def save_memory(self, task_id, round_number, memory_type, content, context=None):
        with self.db.connect() as conn:
            c = conn.execute(
                """INSERT INTO agent_memory (task_id, round_number, memory_type, content, context)
                   VALUES (?,?,?,?,?)""",
                (task_id, round_number, memory_type, content, json.dumps(context or {}))
            )
            return c.lastrowid

    # ----- Answers -----
    def save_answer(self, task_id, flag, explanation="", confidence=0.0):
        with self.db.connect() as conn:
            c = conn.execute(
                "INSERT INTO answers (task_id, flag, explanation, confidence) VALUES (?,?,?,?)",
                (task_id, flag, explanation, confidence)
            )
            return c.lastrowid

    # ----- Statistics -----
    def compute_statistics(self, question_set):
        with self.db.connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
            tasks = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            success = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='completed'").fetchone()[0]
            rate = (success / tasks * 100) if tasks > 0 else 0

            diffs = {}
            for r in conn.execute("SELECT difficulty, COUNT(*) as c FROM samples GROUP BY difficulty"):
                diffs[r["difficulty"]] = r["c"]

            archs = {}
            for r in conn.execute("SELECT arch, COUNT(*) as c FROM samples GROUP BY arch"):
                archs[r["arch"]] = r["c"]

            conn.execute(
                "INSERT INTO statistics (question_set, total_samples, total_tasks, successful_tasks, success_rate, by_difficulty, by_arch) VALUES (?,?,?,?,?,?,?)",
                (question_set, total, tasks, success, rate, json.dumps(diffs), json.dumps(archs))
            )

    def get_latest_statistics(self, question_set):
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM statistics WHERE question_set=? ORDER BY computed_at DESC LIMIT 1",
                (question_set,)
            ).fetchone()
            return dict(row) if row else None

    def get_overall_stats(self):
        with self.db.connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
            tasks = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            success = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='completed'").fetchone()[0]
            return {"total_samples": total, "total_tasks": tasks, "successful": success}
