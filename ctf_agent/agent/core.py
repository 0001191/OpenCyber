"""
Agent 核心 — 主循环和决策引擎

遵循任务书要求：
  任务输入 → 分析决策 → 工具调用 → 结果回填 → 记忆更新 → 停止控制 → 结果输出
"""

import time
import json
import os
import sys
from datetime import datetime

# 将项目根目录加入 PATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from ctf_agent.db.manager import ToolCallRecorder, MemoryManager, ResultManager, get_connection
from ctf_agent.tools import AnalysisTools

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'db', 'opencyber.db')


class AgentCore:
    """
    Agent 主循环

    工作流：
    1. 接收任务（样本路径 + 任务 ID）
    2. 阶段一：信息收集（file, strings, readelf）
    3. 阶段二：环境检查
    4. 阶段三：规划 → 分析执行（调用工具链）
       - 每步结果写回 observation
       - 关键线索写入 agent_memory
       - 失败切换方向
    5. 阶段四：验证并输出 flag
    6. 更新任务状态
    """

    MAX_TURNS = 30         # 最大轮次
    MAX_FAILURES = 5       # 最大失败方向切换次数

    def __init__(self, llm_api_key=None, llm_model='deepseek-chat', llm_base_url='https://api.deepseek.com'):
        self.conn = get_connection(DB_PATH)
        self.tools = AnalysisTools()
        self.tool_recorder = ToolCallRecorder(self.conn)
        self.memory = MemoryManager(self.conn)
        self.results = ResultManager(self.conn)

        # LLM 配置（可选，用于决策增强）
        self.llm_api_key = llm_api_key or os.environ.get('LLM_API_KEY', '')
        self.llm_model = llm_model
        self.llm_base_url = llm_base_url

        # 运行时状态
        self.task_id = None
        self.sample_path = None
        self.sample_id = None
        self.turn_count = 0
        self.fail_count = 0
        self.attempted_directions = []
        self.current_plan = []
        self.plan_index = 0
        self.observations = []
        self.working_memory = []

    def run(self, task_id, sample_path, sample_id=None):
        """Agent 主入口"""
        self.task_id = task_id
        self.sample_path = sample_path
        self.sample_id = sample_id
        self.turn_count = 0
        self.fail_count = 0
        self.attempted_directions = []

        print(f"\n{'='*60}")
        print(f" [Agent] 开始分析任务 #{task_id}")
        print(f" [Agent] 目标文件: {sample_path}")
        print(f"{'='*60}\n")

        # ── 阶段一：信息收集 ──
        self._phase_info_gathering()

        # ── 阶段二：环境检查 ──
        self._phase_env_check()

        # ── 阶段三：规划 → 执行 ──
        result = self._phase_analyze()

        # ── 阶段四：输出结果 ──
        self._phase_output(result)

        return result

    # ────────────────────────────────────────
    # 阶段一：信息收集
    # ────────────────────────────────────────
    def _phase_info_gathering(self):
        print(f"\n{'─'*50}")
        print(" 阶段一：信息收集")
        print(f"{'─'*50}\n")

        results = {}

        # 1. file 类型识别
        result = self._call_tool('file', target_path=self.sample_path)
        if result.success:
            file_type = result.output.strip()
            results['file_type'] = file_type
            print(f"  [FILE]    {file_type}")

        # 2. strings 字符串提取
        result = self._call_tool('strings', target_path=self.sample_path, max_lines=80)
        if result.success:
            strings = result.data.get('preview', [])
            results['strings'] = strings
            # 寻找 flag 相关字符串
            flag_hints = [s for s in strings if any(k in s.lower()
                         for k in ['flag', 'password', 'key', 'secret', 'correct', 'wrong'])]
            if flag_hints:
                print(f"  🔥 发现可疑字符串: {flag_hints[:10]}")

        # 3. readelf
        result = self._call_tool('readelf', target_path=self.sample_path, action='header')
        if result.success:
            results['elf_header'] = result.output

        # 4. 记录观察
        obs_lines = []
        for k, v in results.items():
            if isinstance(v, list):
                obs_lines.append(f"{k}: {len(v)} items")
            elif isinstance(v, str):
                obs_lines.append(f"{k}: {v[:200]}")
        self._add_observation('; '.join(obs_lines), 'info')

        return results

    # ────────────────────────────────────────
    # 阶段二：环境检查
    # ────────────────────────────────────────
    def _phase_env_check(self):
        print(f"\n{'─'*50}")
        print(" 阶段二：环境检查")
        print(f"{'─'*50}\n")

        available = self.tools.get_available()
        print(f"  [TOOLS]   可用工具: {', '.join(available) if available else '无'}")

        if not available:
            print("  ⚠️  警告：没有检测到任何逆向工具！")
            print("     建议通过 WSL 安装：sudo apt install binutils file binutils-aarch64-linux-gnu gdb")

        self._add_observation(f"可用工具: {', '.join(available)}", 'env')
        return available

    # ────────────────────────────────────────
    # 阶段三：规划 → 分析执行
    # ────────────────────────────────────────
    def _phase_analyze(self):
        print(f"\n{'─'*50}")
        print(" 阶段三：分析与执行")
        print(f"{'─'*50}\n")

        # 尝试从记忆库中检索相似样例经验（跨任务读取）
        past_memories = self.memory.read_semantic(limit=5)
        if past_memories:
            print(f"  🧠 从记忆库检索到 {len(past_memories)} 条历史经验（跨任务读取）")

        # 尝试检索失败路径
        past_failures = self.memory.read_failures(limit=3)
        if past_failures:
            print(f"  🧠 检索到 {len(past_failures)} 条历史失败路径，尝试规避")

        # 根据信息收集结果制定计划
        plan = self._make_plan()
        self.current_plan = plan
        self.plan_index = 0

        # 执行计划
        last_result = None
        while self.plan_index < len(plan) and self.turn_count < self.MAX_TURNS:
            step = plan[self.plan_index]
            last_result = self._execute_step(step)
            self.plan_index += 1
            self.turn_count += 1

            # 检查是否已拿到 flag
            if last_result and last_result.get('flag'):
                return last_result

        # 如果计划执行完还没拿到 flag，切换方向重试
        while self.fail_count < self.MAX_FAILURES and self.turn_count < self.MAX_TURNS:
            self.fail_count += 1
            print(f"\n  🔄 方向切换 #{self.fail_count}")

            # 复盘
            self._retrospective()

            # 生成新方向计划
            new_plan = self._make_plan(direction_switch=True)
            self.current_plan = new_plan
            self.plan_index = 0

            while self.plan_index < len(new_plan) and self.turn_count < self.MAX_TURNS:
                step = new_plan[self.plan_index]
                last_result = self._execute_step(step)
                self.plan_index += 1
                self.turn_count += 1
                if last_result and last_result.get('flag'):
                    return last_result

        return last_result or {'success': False, 'reason': 'Max turns/failures reached'}

    def _make_plan(self, direction_switch=False):
        """制定分析计划"""
        if not direction_switch:
            plan = [
                {'type': 'tool', 'tool': 'readelf', 'params': {'action': 'sections'}, 'desc': '查看节区信息'},
                {'type': 'tool', 'tool': 'readelf', 'params': {'action': 'symbols'}, 'desc': '查看符号表'},
                {'type': 'tool', 'tool': 'objdump', 'params': {'mode': 'disasm'}, 'desc': '反汇编分析'},
                {'type': 'tool', 'tool': 'strings', 'params': {'encoding': 'utf16'}, 'desc': '提取 UTF-16 字符串'},
                {'type': 'analyze', 'desc': '综合分析，寻找 flag 验证逻辑'},
            ]
        else:
            # 方向切换后的新策略
            strategies = [
                [{'type': 'tool', 'tool': 'gdb', 'params': {'commands': ['info functions', 'disassemble main']}, 'desc': 'GDB 动态分析'}],
                [{'type': 'analysis', 'sub_type': 'pwntools', 'desc': '用 pwntools 提取 ELF 信息'}],
                [{'type': 'analysis', 'sub_type': 'decompile', 'desc': '尝试反编译核心函数'}],
            ]
            # 轮换策略
            idx = (self.fail_count - 1) % len(strategies)
            plan = strategies[idx]
            plan.append({'type': 'analyze', 'desc': '综合新方向的分析结果'})

        self.attempted_directions.append(plan[0].get('desc', 'unknown'))
        return plan

    def _execute_step(self, step):
        """执行计划中的单个步骤"""
        step_type = step.get('type')
        desc = step.get('desc', '')

        if step_type == 'tool':
            tool_name = step.get('tool')
            params = step.get('params', {})
            params['target_path'] = self.sample_path
            result = self._call_tool(tool_name, **params)
            self._add_observation(f"[{tool_name}] {desc}: {'成功' if result.success else '失败'}", 'tool')
            return {'success': result.success, 'output': result.output}

        elif step_type == 'analysis':
            return self._run_llm_analysis(desc)

        elif step_type == 'analysis' and step.get('sub_type') == 'pwntools':
            tool = self.tools.tools.get('pwntools')
            if tool:
                result = tool.elf_info(self.sample_path)
                if result.success:
                    self._add_observation(f"pwntools ELF info: {json.dumps(result.data)}", 'analysis')
                return {'success': result.success, 'data': result.data}

        return {'success': False, 'reason': 'Unknown step type'}

    def _run_llm_analysis(self, prompt):
        """调用 LLM 进行分析决策（支持 API 和回退模式）"""
        observations_summary = '\n'.join([o['content'][:200] for o in self.observations[-10:]])
        memory_summary = '\n'.join([m['content'][:200] for m in self.working_memory[-5:]])

        print(f"\n  [分析] {prompt}")
        print(f"  当前观察 ({len(self.observations)}条) + 记忆 ({len(self.working_memory)}条)")

        # 构建分析结论（模拟分析，实际接入 LLM API 后可增强）
        analysis = f"已完成{prompt}，等待进一步工具调用确认"
        self._add_observation(analysis, 'analysis')
        self._write_memory(analysis, memory_type='working')

        return {'success': True, 'analysis': analysis}

    # ────────────────────────────────────────
    # 阶段四：结果输出
    # ────────────────────────────────────────
    def _phase_output(self, result):
        print(f"\n{'─'*50}")
        print(" 阶段四：结果输出")
        print(f"{'─'*50}\n")

        if result and result.get('flag'):
            print(f"  🎉 FLAG: {result['flag']}")
            self.results.save(self.task_id, result['flag'],
                            conclusion=result.get('conclusion', ''),
                            evidence=result.get('evidence', ''),
                            confidence=result.get('confidence', 0.8))
            return True
        else:
            reason = result.get('reason', 'Unknown') if result else 'No result'
            print(f"  ❌ 分析未能在限制内找到 flag")
            print(f"     原因: {reason}")
            print(f"     已尝试方向: {', '.join(self.attempted_directions)}")
            return False

    # ────────────────────────────────────────
    # 辅助方法
    # ────────────────────────────────────────
    def _call_tool(self, tool_name, **params):
        """工具调用 + 记录"""
        result = self.tools.call(tool_name, **params)
        self.tool_recorder.record(
            task_id=self.task_id,
            tool_name=tool_name,
            parameters=json.dumps({k: str(v)[:100] for k, v in params.items()}),
            output=result.output[:1000] if result.success else result.error[:500],
            success=1 if result.success else 0,
            duration_ms=result.duration_ms,
        )

        status = '✅' if result.success else '❌'
        duration = f"{result.duration_ms}ms" if result.duration_ms else "?"
        print(f"  {status} [{tool_name}] ({duration})")
        if result.success and result.output:
            lines = result.output.strip().split('\n')
            for line in lines[:5]:
                print(f"    {line.strip()}")
            if len(lines) > 5:
                print(f"    ... ({len(lines) - 5} more lines)")

        return result

    def _add_observation(self, content, category='general'):
        """记录观察结果"""
        self.observations.append({
            'content': content,
            'category': category,
            'turn': self.turn_count,
        })
        # 同时写入数据库 observation 表
        self.conn.execute("""
            INSERT INTO observations (task_id, content, category)
            VALUES (?, ?, ?)
        """, (self.task_id, content, category))
        self.conn.commit()

    def _write_memory(self, content, memory_type='working', is_key=False):
        """写入 Agent 记忆"""
        self.working_memory.append({
            'content': content,
            'memory_type': memory_type,
            'turn': self.turn_count,
        })
        self.memory.write(
            task_id=self.task_id,
            content=content,
            memory_type=memory_type,
            turn_index=self.turn_count,
            is_key_insight=1 if is_key else 0,
        )

    def _retrospective(self):
        """失败复盘"""
        failed_steps = [s for s in self.attempted_directions[-3:]]
        print(f"\n  [RETRO] 复盘 ─── 失败次数: {self.fail_count}")
        print(f"  {'─'*40}")
        print(f"  已尝试方向: {', '.join(failed_steps)}")
        print(f"  失败原因: 当前方向未找到 flag，切换分析策略")
        print(f"  调整方向: {self._next_direction_hint()}")

        # 记录关键失败记忆（用于后续跨任务检索）
        self._write_memory(
            f"方向{failed_steps} 失败，已切换",
            memory_type='episodic',
            is_key=True,
        )

    def _next_direction_hint(self):
        """根据失败次数提示下一步方向"""
        hints = [
            '加强静态分析',
            '尝试动态调试',
            '重新检查文件头，可能遗漏了关键信息',
            '尝试符号执行或约束求解',
            '请手动检查或提供额外提示',
        ]
        idx = min(self.fail_count, len(hints) - 1)
        return hints[idx]

    def close(self):
        self.conn.close()
