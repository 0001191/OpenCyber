"""Agent memory: working memory and failure path review."""

import json
from ..database.repository import Repository


class AgentMemory:
    def __init__(self, repo=None):
        self.repo = repo or Repository()
        self._task_id = None
        self._short_term = []

    def set_task(self, task_id):
        self._task_id = task_id
        self._short_term = []

    def record(self, round_number, memory_type, content, context=None):
        self._short_term.append((memory_type, content))
        if len(self._short_term) > 50:
            self._short_term = self._short_term[-50:]
        self.repo.save_memory(self._task_id, round_number, memory_type, content)

    def get_recent(self):
        return self._short_term[-10:]

    def review_failures(self, task_id):
        with self.repo.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_memory WHERE task_id=? AND memory_type='failure_review' ORDER BY id",
                (task_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_context_for_llm(self):
        parts = []
        for mtype, content in self._short_term[-8:]:
            parts.append(f"[{mtype}] {str(content)[:500]}")
        return "\n".join(parts)
