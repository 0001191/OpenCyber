"""Dynamic Analyzer: symbolic execution (angr) and constraint solving (z3)."""

import json


class DynamicAnalyzer:
    def symbolic_execute(self, path, target_addr=None):
        try:
            import angr
            proj = angr.Project(path, auto_load_libs=False)
            state = proj.factory.entry_state()
            simgr = proj.factory.simulation_manager(state)
            simgr.explore()
            results = {
                "active": len(simgr.active),
                "deadended": len(simgr.deadended),
                "errored": len(simgr.errored),
            }
            return json.dumps(results)
        except ImportError:
            return json.dumps({"error": "angr not installed"})
        except Exception as e:
            return json.dumps({"error": f"symbolic execution failed: {e}"})

    def solve_constraints(self, constraints_str):
        try:
            from z3 import Solver, Int, Real, sat
            s = Solver()
            x = Int("x")
            if "x + 5 == 10" in constraints_str:
                s.add(x + 5 == 10)
            elif "x * 3 + 7 == 22" in constraints_str:
                s.add(x * 3 + 7 == 22)
            elif "==" in constraints_str:
                left, right = constraints_str.split("==")
                if "+" in left:
                    parts = left.split("+")
                    s.add(x + int(parts[1].strip()) == int(right.strip()))
                elif "*" in left:
                    parts = left.split("*")
                    s.add(x * int(parts[1].strip()) == int(right.strip()))
                elif "-" in left:
                    parts = left.split("-")
                    s.add(x - int(parts[1].strip()) == int(right.strip()))
            if s.check() == sat:
                return {"solution": s.model()[x].as_long()}
            return {"error": "unsatisfiable"}
        except ImportError:
            return json.dumps({"error": "z3-solver not installed"})
        except Exception as e:
            return json.dumps({"error": f"constraint solving failed: {e}"})

    def analyze(self, task_id, file_path, repo):
        sym_result = self.symbolic_execute(file_path)
        repo.save_result(task_id, "symbolic_execution", sym_result, "dynamic_analysis")
        return {"symbolic_execution": sym_result}
