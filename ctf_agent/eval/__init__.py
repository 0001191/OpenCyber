"""
评测模块 — 批量评测、统计分析和报告生成
"""

import os
import sys
import json
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from ctf_agent.db.manager import (get_connection, SampleManager, TaskManager,
                                   EvaluationManager, ResultManager, init_database)


DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'db', 'opencyber.db')


class BatchEvaluator:
    """批量评测器"""

    def __init__(self, db_path=None):
        self.conn = get_connection(db_path or DB_PATH)
        self.samples = SampleManager(self.conn)
        self.tasks = TaskManager(self.conn)
        self.eval_mgr = EvaluationManager(self.conn)
        self.results_mgr = ResultManager(self.conn)

    def run_batch(self, difficulty=None, parallel=False, max_samples=None):
        """批量运行评测"""
        sample_list = self.samples.list_all(difficulty)
        if max_samples:
            sample_list = sample_list[:max_samples]

        print(f"\n{'='*60}")
        print(f" 批量评测: {len(sample_list)} 个样本 (难度: {difficulty or '全部'})")
        print(f"{'='*60}\n")

        from ctf_agent.agent.core import AgentCore
        stats = {'total': 0, 'success': 0, 'failed': 0, 'errors': 0}
        details = []

        for sample in sample_list:
            stats['total'] += 1
            print(f"\n─── [{stats['total']}/{len(sample_list)}] {sample['name']} ───")

            task_id = self.tasks.create(sample['id'])
            self.tasks.update_status(task_id, 'running')

            agent = AgentCore()
            try:
                result = agent.run(task_id, sample['file_path'], sample['id'])
                agent.close()

                if result and result.get('flag'):
                    stats['success'] += 1
                    self.tasks.update_status(task_id, 'success', result='success')
                    self.results_mgr.save(task_id, result['flag'])
                    details.append({'name': sample['name'], 'status': 'success', 'flag': result['flag']})
                    print(f"  🎉 成功: {result['flag']}")
                else:
                    stats['failed'] += 1
                    reason = result.get('reason', 'Failed') if result else 'No result'
                    self.tasks.update_status(task_id, 'failed', result='failed', error_msg=reason)
                    details.append({'name': sample['name'], 'status': 'failed', 'reason': reason})
                    print(f"  ❌ 失败: {reason}")

            except Exception as e:
                stats['errors'] += 1
                self.tasks.update_status(task_id, 'failed', result='failed', error_msg=str(e))
                details.append({'name': sample['name'], 'status': 'error', 'error': str(e)})
                print(f"  ⚠️ 异常: {e}")

        # 保存评测快照
        self.eval_mgr.save_snapshot()

        # 输出汇总
        rate = round(stats['success'] / stats['total'] * 100, 2) if stats['total'] > 0 else 0
        print(f"\n{'='*60}")
        print(f" 评测结果汇总:")
        print(f"   总样本: {stats['total']}")
        print(f"   成功:   {stats['success']} ({rate}%)")
        print(f"   失败:   {stats['failed']}")
        print(f"   异常:   {stats['errors']}")
        print(f"{'='*60}")

        return {'stats': stats, 'rate': rate, 'details': details}

    def generate_report(self, output_path=None):
        """生成评测报告 Markdown"""
        report = []
        report.append("# 评测报告\n")
        report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # 各难度统计
        report.append("## 难度覆盖率统计\n")
        report.append("| 难度 | 总样本 | 解出 | 失败 | 成功率 |")
        report.append("|------|--------|------|------|--------|")
        for diff in ['basic', 'medium', 'hard']:
            stats = self.eval_mgr.compute_stats(diff)
            if stats and stats['total'] > 0:
                rate = round(stats['solved'] / stats['total'] * 100, 2)
                report.append(f"| {diff} | {stats['total']} | {stats['solved']} | {stats['failed']} | {rate}% |")

        # 总体统计
        total = self.eval_mgr.compute_stats()
        if total and total['total'] > 0:
            rate = round(total['solved'] / total['total'] * 100, 2)
            report.append(f"| **总计** | {total['total']} | {total['solved']} | {total['failed']} | **{rate}%** |")

        # 失败样例分析
        report.append("\n## 典型失败样例\n")
        failures = self.eval_mgr.get_failure_examples(10)
        if failures:
            report.append("| 样本 | 难度 | 失败原因 | 耗时(ms) |")
            report.append("|------|------|----------|---------|")
            for f in failures:
                report.append(f"| {f['name']} | {f['difficulty']} | {f['error_msg'] or 'N/A'} | {f['duration_ms'] or 'N/A'} |")

        report.append("\n## 改进分析\n")
        report.append("1. 成功率较低的方向，需要优化 Agent 决策策略")
        report.append("2. 失败样例中频繁出现的模式，需补充针对性分析能力")
        report.append("3. 建议增加方向切换和记忆复用机制以提升泛化能力\n")

        content = '\n'.join(report)

        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  📝 报告已保存: {output_path}")

        return content

    def close(self):
        self.conn.close()
