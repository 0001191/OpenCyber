"""
样本与任务管理 CLI
"""

import os
import sys
import json
import subprocess
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from ctf_agent.db.manager import (get_connection, SampleManager, TaskManager,
                                   EvaluationManager, init_database)
from ctf_agent.tools import AnalysisTools


DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'db', 'opencyber.db')


class SampleImporter:
    """样本导入器"""

    def __init__(self, db_path=None):
        self.conn = get_connection(db_path or DB_PATH)
        self.samples = SampleManager(self.conn)
        self.tools = AnalysisTools()

    def import_file(self, file_path, difficulty='basic', tags=''):
        """导入单个样本"""
        if not os.path.exists(file_path):
            return {'error': f'File not found: {file_path}'}

        name = os.path.basename(file_path)
        abs_path = os.path.abspath(file_path)

        # 用 file 命令识别
        info = {'file_type': '', 'arch': '', 'bits': 0, 'endian': '',
                'entry_point': '', 'stripped': 0}

        result = self.tools.call('file', target_path=abs_path)
        if result.success:
            info['file_type'] = result.output.strip()
            # 尝试提取架构信息
            ft = info['file_type'].lower()
            if '64-bit' in ft:
                info['bits'] = 64
            elif '32-bit' in ft:
                info['bits'] = 32
            if 'x86-64' in ft or 'x86_64' in ft:
                info['arch'] = 'x86_64'
            elif 'i386' in ft or 'i686' in ft:
                info['arch'] = 'x86'
            elif 'arm' in ft:
                info['arch'] = 'ARM'
            elif 'mips' in ft:
                info['arch'] = 'MIPS'
            if 'stripped' in ft:
                info['stripped'] = 1

        # 用 readelf 进一步提取（如有）
        if info['bits'] > 0:
            result = self.tools.call('readelf', target_path=abs_path, action='header')
            if result.success:
                for line in result.output.split('\n'):
                    if 'Entry point' in line:
                        info['entry_point'] = line.split(':')[-1].strip()
                    if 'little endian' in line.lower():
                        info['endian'] = 'little'
                    elif 'big endian' in line.lower():
                        info['endian'] = 'big'

        # 保存到数据库
        sample_id = self.samples.create(
            name=name, file_path=abs_path,
            file_type=info['file_type'], arch=info['arch'],
            bits=info['bits'], endian=info['endian'],
            entry_point=info['entry_point'], stripped=info['stripped'],
            difficulty=difficulty, tags=tags,
        )

        print(f"  ✅ 已导入样本 #{sample_id}: {name} ({info['arch']} / {info['bits']}bit)")
        return {'sample_id': sample_id, 'info': info}

    def import_directory(self, dir_path, difficulty_map=None):
        """批量导入目录下的 ELF 文件"""
        if not os.path.isdir(dir_path):
            return {'error': f'Directory not found: {dir_path}'}

        results = []
        for f in sorted(os.listdir(dir_path)):
            fpath = os.path.join(dir_path, f)
            if not os.path.isfile(fpath):
                continue
            # 检查是否为 ELF（粗略判断）
            try:
                with open(fpath, 'rb') as fp:
                    magic = fp.read(4)
                if magic != b'\x7fELF':
                    continue
            except:
                continue

            # 难度映射
            diff = 'basic'
            if difficulty_map:
                for pattern, d in difficulty_map.items():
                    if pattern in f.lower():
                        diff = d
                        break

            result = self.import_file(fpath, difficulty=diff)
            results.append(result)

        print(f"\n  📊 共导入 {len(results)} 个样本")
        return results

    def close(self):
        self.conn.close()


class TaskRunner:
    """任务运行器"""

    def __init__(self, db_path=None):
        self.conn = get_connection(db_path or DB_PATH)
        self.tasks = TaskManager(self.conn)
        self.samples = SampleManager(self.conn)

    def create_and_run(self, sample_id, difficulty=None):
        """创建任务并运行"""
        sample = self.samples.get(sample_id)
        if not sample:
            return {'error': f'Sample #{sample_id} not found'}

        task_id = self.tasks.create(sample_id)
        print(f"\n  🚀 创建任务 #{task_id} → 样本: {sample['name']}")

        # 运行 Agent（延迟导入避免循环）
        from ctf_agent.agent.core import AgentCore
        agent = AgentCore()

        self.tasks.update_status(task_id, 'running')
        try:
            result = agent.run(task_id, sample['file_path'], sample_id)
            agent.close()

            if result and result.get('flag'):
                self.tasks.update_status(task_id, 'success', result='success')
                return {'task_id': task_id, 'status': 'success', 'flag': result['flag']}
            else:
                reason = result.get('reason', 'Analysis incomplete') if result else 'Unknown'
                self.tasks.update_status(task_id, 'failed', result='failed', error_msg=reason)
                return {'task_id': task_id, 'status': 'failed', 'reason': reason}

        except Exception as e:
            self.tasks.update_status(task_id, 'failed', result='failed', error_msg=str(e))
            return {'task_id': task_id, 'status': 'error', 'error': str(e)}

    def resume_unfinished(self):
        """断点续跑：查找并重新运行未完成的任务"""
        unfinished = self.tasks.get_unfinished()
        if not unfinished:
            print("  ✅ 没有未完成的任务")
            return []
        print(f"  🔄 发现 {len(unfinished)} 个未完成任务，准备续跑")
        results = []
        for task in unfinished:
            result = self.create_and_run(task['sample_id'])
            results.append(result)
        return results

    def close(self):
        self.conn.close()
