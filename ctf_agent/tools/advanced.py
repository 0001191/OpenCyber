"""
Ghidra Headless 分析工具封装
"""

import subprocess
import os
import tempfile
import json

from . import BaseTool, ToolResult


class GhidraTool(BaseTool):
    """Ghidra Headless 分析"""

    name = 'ghidra'

    def __init__(self, ghidra_path=None, wsl_mode=False):
        super().__init__(wsl_mode)
        self.ghidra_path = ghidra_path or os.environ.get('GHIDRA_HOME', '')

    def is_available(self):
        return bool(self.ghidra_path) and os.path.exists(self.ghidra_path)

    def run(self, target_path, script=None, analysis_mode='basic', timeout=120, **kwargs):
        """
        运行 Ghidra Headless 分析
        analysis_mode: basic / full / decompile
        """
        if not self.is_available():
            return ToolResult(success=False, error='Ghidra not configured. Set GHIDRA_HOME')

        path = self._resolve_path(target_path)
        project_dir = tempfile.mkdtemp(prefix='ghidra_')
        project_name = 'ctf_analysis'

        try:
            # Ghidra Headless 命令
            headless = os.path.join(self.ghidra_path, 'support', 'analyzeHeadless' if not os.name == 'nt' else 'analyzeHeadless.bat')
            cmd = [
                headless,
                project_dir, project_name,
                '-import', path,
                '-postscript', script or '',
                '-deleteProject',
            ]

            if self.wsl_mode:
                cmd = ['wsl'] + cmd

            result = self._run_cmd(cmd, timeout=timeout)
            return result

        finally:
            import shutil
            shutil.rmtree(project_dir, ignore_errors=True)


class AngrTool(BaseTool):
    """angr 符号执行"""

    name = 'angr'

    def run(self, target_path, function_addr=None, find_addr=None,
            avoid_addr=None, stdin_mode=True, timeout=60, **kwargs):
        """运行 angr 符号执行"""
        path = self._resolve_path(target_path)
        script = f"""
import angr, claripy, json, sys, time

def analyze():
    proj = angr.Project(r'{path}', auto_load_libs=False)
    info = {{
        'entry': hex(proj.entry),
        'arch': proj.arch.name,
        'bits': proj.arch.bits,
    }}

    find_addr = {find_addr or 'None'}
    avoid_addr = {avoid_addr or 'None'}

    if find_addr:
        start = time.time()
        sm = proj.factory.simulation_manager()
        sm.explore(find=find_addr, avoid=avoid_addr)
        elapsed = time.time() - start

        if sm.found:
            found = sm.found[0]
            info['solved'] = True
            info['solutions'] = []
            for i in range(min(3, len(sm.found))):
                try:
                    sol = sm.found[i].posix.dumps(0)
                    if isinstance(sol, bytes):
                        info['solutions'].append(sol[:256].decode('latin-1'))
                except:
                    pass
            info['found_count'] = len(sm.found)
        else:
            info['solved'] = False

        info['active_count'] = len(sm.active)
        info['deadended_count'] = len(sm.deadended)
        info['elapsed'] = round(elapsed, 2)
    else:
        cfg = proj.analyses.CFGFast()
        info['functions'] = len(cfg.functions)
        info['callsites'] = len(list(cfg.functions.call_sites))

    print(angr.__version__)
    print(json.dumps(info))

analyze()
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(script)
            script_path = f.name

        try:
            cmd = ['python3', script_path]
            result = self._run_cmd(cmd, timeout=timeout)
            if result.success:
                lines = result.output.strip().split('\n')
                if len(lines) >= 1:
                    result.data['angr_version'] = lines[0]
                if len(lines) >= 2:
                    try:
                        result.data['analysis'] = json.loads(lines[1])
                    except json.JSONDecodeError:
                        pass
            return result
        finally:
            os.unlink(script_path)

    def cfg_analysis(self, target_path, timeout=60):
        """CFG 分析（获取函数列表/调用图）"""
        return self.run(target_path, timeout=timeout)


class Z3Tool(BaseTool):
    """Z3 约束求解"""

    name = 'z3'

    def run(self, constraints_code, **kwargs):
        """运行 Z3 求解脚本"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(f"""
from z3 import *
import json
import sys

# 用户约束
{constraints_code}

# 求解
solver = Solver()
solver.set(':timeout', 30000)
result = solver.check()
if result == sat:
    m = solver.model()
    solution = {{str(d): str(m[d]) for d in m.decls()}}
    print(json.dumps({{'sat': True, 'solution': solution}}))
else:
    print(json.dumps({{'sat': False, 'reason': str(result)}}))
""")
            script_path = f.name

        try:
            cmd = ['python3', script_path]
            result = self._run_cmd(cmd, timeout=30)
            if result.success:
                try:
                    result.data = json.loads(result.output.strip())
                except json.JSONDecodeError:
                    pass
            return result
        finally:
            os.unlink(script_path)
