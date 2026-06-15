"""Evaluation statistics: compute success rate, coverage, failure details."""

import json
from ..database.repository import Repository


class EvaluationStats:
    def __init__(self, repo=None):
        self.repo = repo or Repository()

    def evaluate(self, question_set):
        self.repo.compute_statistics(question_set)
        return self.repo.get_latest_statistics(question_set)

    def get_failure_details(self, question_set):
        with self.repo.db.connect() as conn:
            rows = conn.execute(
                """SELECT t.id, t.status, t.error_message, t.elapsed_seconds, s.name
                   FROM tasks t JOIN samples s ON t.sample_id=s.id
                   WHERE t.status='error'""").fetchall()
            return [dict(r) for r in rows]
