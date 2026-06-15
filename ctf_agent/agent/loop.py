"""Agent main loop: GLM-powered decision cycle with tool orchestration."""

import json
import time
from ..core.sample_manager import SampleManager
from ..core.basic_analysis import BasicAnalyzer
from ..core.static_analysis import StaticAnalyzer
from ..core.dynamic_analysis import DynamicAnalyzer
from ..database.repository import Repository
from .memory import AgentMemory
from .tools import ToolRegistry
from ..config import GLM_API_KEY, GLM_MODEL, MAX_ANALYSIS_ROUNDS


class AgentLoop:
    def __init__(self, repo=None):
        self.repo = repo or Repository()
        self.sm = SampleManager(self.repo)
        self.ba = BasicAnalyzer(self.repo)
        self.sa = StaticAnalyzer()
        self.da = DynamicAnalyzer()
        self.memory = AgentMemory(self.repo)
        self.tools = ToolRegistry()
        self._current_task = None
        self._current_path = None

    def _call_llm(self, messages):
        if not GLM_API_KEY:
            return json.dumps({"tool": "submit_flag", "arguments": {}, "flag": "", "explanation": "No API key configured"})
        try:
            from zhipuai import ZhipuAI
            client = ZhipuAI(api_key=GLM_API_KEY)
            response = client.chat.completions.create(
                model=GLM_MODEL, messages=messages, temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            return json.dumps({"tool": "submit_flag", "arguments": {}, "flag": "", "explanation": f"LLM error: {e}"})

    def _build_prompt(self, round_num):
        tool_list = self.tools.get_tools_desc()
        past = self.memory.get_context_for_llm()
        cross = ""
        if self._current_task:
            cross_results = self.repo.cross_task_read(self._current_task["id"], limit=10)
            if cross_results:
                cross = "\n## CROSS-TASK KNOWLEDGE\n" + "\n".join(
                    f"- [{r['result_type']}] {str(r['data'])[:150]}" for r in cross_results[:3]
                )
        return f"""You are a CTF binary analysis expert. Analyze the given ELF binary step by step.

## AVAILABLE TOOLS
{tool_list}

## CURRENT STATE
Round: {round_num}/{MAX_ANALYSIS_ROUNDS}
File: {self._current_path}
{past}
{cross}

## OUTPUT FORMAT
Respond in JSON: {{"tool": "TOOL_NAME", "arguments": {{...}}, "reasoning": "why"}}

If you found the flag: {{"tool": "submit_flag", "arguments": {{"flag": "FLAG_HERE"}}, "explanation": "how you found it"}}

If exhausted: {{"tool": "submit_flag", "arguments": {{"flag": ""}}, "explanation": "reason"}}
"""

    def _execute_tool(self, tool_name, args, round_num):
        task_id = self._current_task["id"]
        path = self._current_path
        try:
            if tool_name == "file_info":
                result = self.ba._run_file(path)
            elif tool_name == "check_protections":
                result = self.ba._run_checksec(path)
            elif tool_name == "read_strings":
                result = self.ba._run_strings(path)
            elif tool_name == "readelf_headers":
                result = self.ba._run_readelf_header(path)
            elif tool_name == "find_functions":
                result = self.sa.list_functions(path)
            elif tool_name == "analyze_imports":
                result = self.sa.analyze_imports(path)
            elif tool_name == "disassemble":
                result = self.sa.disassemble(path, args.get("section", ".text"))
            elif tool_name == "analyze_call_graph":
                result = self.sa.call_graph(path)
            elif tool_name == "symbolic_execute":
                result = self.da.symbolic_execute(path)
            elif tool_name == "solve_constraints":
                result = self.da.solve_constraints(args.get("constraints", ""))
            elif tool_name == "submit_flag":
                return {"flag": args.get("flag", ""), "_stop": True}
            else:
                result = json.dumps({"error": f"Unknown tool: {tool_name}"})
            self.repo.record_tool_call(task_id, round_num, tool_name, args, result)
            return {"result": result}
        except Exception as e:
            err = json.dumps({"error": str(e)})
            self.repo.record_tool_call(task_id, round_num, tool_name, args, err, success=False)
            return {"result": err}

    def run(self, task_id, file_path):
        self._current_task = self.repo.get_task(task_id)
        self._current_path = file_path
        self.memory.set_task(task_id)
        self.repo.start_task(task_id)

        messages = [{"role": "system", "content": "You are a CTF binary analysis expert. Respond in JSON."}]
        final_flag = ""
        final_explanation = ""
        ok = False
        t0 = time.time()

        for rnd in range(1, MAX_ANALYSIS_ROUNDS + 1):
            prompt = self._build_prompt(rnd)
            messages.append({"role": "user", "content": prompt})
            self.memory.record(rnd, "observation", f"Analyzing binary: {file_path}\nRound: {rnd}/{MAX_ANALYSIS_ROUNDS}")

            response = self._call_llm(messages[-5:])
            self.memory.record(rnd, "thought", f"Round {rnd} response: {response[:500]}")

            try:
                decision = json.loads(response) if isinstance(response, str) else response
            except json.JSONDecodeError:
                # Try to extract JSON from response
                import re
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if match:
                    try:
                        decision = json.loads(match.group())
                    except json.JSONDecodeError:
                        decision = {"tool": "submit_flag", "arguments": {}, "flag": "", "explanation": "Could not parse LLM response"}
                else:
                    decision = {"tool": "submit_flag", "arguments": {}, "flag": "", "explanation": "Could not parse LLM response"}

            tool = decision.get("tool", "submit_flag")
            args = decision.get("arguments", {})
            self.memory.record(rnd, "decision", json.dumps(decision))

            result = self._execute_tool(tool, args, rnd)
            if result and result.get("_stop"):
                final_flag = result.get("flag", "")
                final_explanation = decision.get("explanation", "")
                ok = True
                break

        elapsed = time.time() - t0
        self.repo.complete_task(task_id, ok, flag=final_flag, elapsed=elapsed,
                               error=None if ok else "Max rounds reached")
        if final_flag:
            self.repo.save_answer(task_id, final_flag, final_explanation, confidence=0.8)
        return {
            "task_id": task_id, "status": "completed" if ok else "error",
            "rounds": rnd if ok else MAX_ANALYSIS_ROUNDS,
            "elapsed_seconds": elapsed, "flag": final_flag,
        }

    def analyze_from_path(self, file_path, difficulty="unknown"):
        sample_id = self.sm.import_sample(file_path, difficulty)
        task_id = self.repo.create_task(sample_id)
        return self.run(task_id, file_path)
