"""Static Analyzer: disassembly, function identification, call graph."""

import subprocess
import json
import os
from ..config import TOOL_PATHS


class StaticAnalyzer:
    def _run_cmd(self, cmd, *args):
        exe = TOOL_PATHS.get(cmd, cmd)
        try:
            result = subprocess.run([exe] + list(args), capture_output=True,
                                   text=False, timeout=60, shell=os.name == "nt")
            return result.stdout.decode("utf-8", errors="replace") if result.stdout else "[no output]"
        except FileNotFoundError:
            return json.dumps({"error": f"disassembly failed: tool '{cmd}' not found"})
        except Exception as e:
            return json.dumps({"error": f"disassembly failed: {e}"})

    def disassemble(self, path, section=".text"):
        try:
            output = self._run_cmd("objdump", "-d", "-M", "intel", path)
            return output
        except Exception as e:
            return json.dumps({"error": f"disassembly failed: {e}"})

    def list_functions(self, path):
        output = self._run_cmd("objdump", "-t", path)
        return output

    def analyze_imports(self, path):
        output = self._run_cmd("objdump", "-T", path)
        return output

    def call_graph(self, path):
        output = self._run_cmd("objdump", "-d", path)
        return output

    def analyze(self, task_id, file_path, repo):
        results = {
            "disassembly": self.disassemble(file_path),
            "functions": self.list_functions(file_path),
            "imports": self.analyze_imports(file_path),
            "call_graph": self.call_graph(file_path),
        }
        for key, value in results.items():
            repo.save_result(task_id, key, value, "static_analysis")
        return results
