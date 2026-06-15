#!/usr/bin/env python3
"""
OpenCyber CTF Agent — CLI 入口

用法:
  python ctf_agent/main.py init                     初始化数据库
  python ctf_agent/main.py import <path>            导入单个样本
  python ctf_agent/main.py import-dir <dir>         批量导入目录
  python ctf_agent/main.py run --sample-id <id>     运行单个任务
  python ctf_agent/main.py eval                     批量评测
  python ctf_agent/main.py report                   生成评测报告
  python ctf_agent/main.py resume                   断点续跑
  python ctf_agent/main.py list                     列出样本
  python ctf_agent/main.py tools                    检查可用工具
"""

import os
import sys
import argparse

# 将项目根目录加入 PATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctf_agent.db.manager import (get_connection, SampleManager, init_database)
from ctf_agent.manager import SampleImporter, TaskRunner
from ctf_agent.eval import BatchEvaluator
from ctf_agent.tools import AnalysisTools

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'db', 'opencyber.db')


def cmd_init(args):
    print("正在初始化数据库...")
    init_database(DB_PATH)
    print("✅ 数据库初始化完成")


def cmd_import(args):
    importer = SampleImporter(DB_PATH)
    result = importer.import_file(args.path, difficulty=args.difficulty, tags=args.tags)
    if 'error' in result:
        print(f"❌ {result['error']}")
    importer.close()


def cmd_import_dir(args):
    importer = SampleImporter(DB_PATH)
    result = importer.import_directory(args.dir)
    if 'error' in result:
        print(f"❌ {result['error']}")
    else:
        print(f"✅ 已导入 {len(result)} 个样本")
    importer.close()


def cmd_run(args):
    runner = TaskRunner(DB_PATH)
    result = runner.create_and_run(args.sample_id)
    if 'error' in result:
        print(f"❌ {result['error']}")
    runner.close()


def cmd_eval(args):
    evaluator = BatchEvaluator(DB_PATH)
    result = evaluator.run_batch(difficulty=args.difficulty, max_samples=args.limit)
    evaluator.close()


def cmd_report(args):
    evaluator = BatchEvaluator(DB_PATH)
    report = evaluator.generate_report(output_path=args.output)
    if not args.output:
        print(report)
    evaluator.close()


def cmd_resume(args):
    runner = TaskRunner(DB_PATH)
    results = runner.resume_unfinished()
    runner.close()


def cmd_list(args):
    conn = get_connection(DB_PATH)
    samples = SampleManager(conn).list_all()
    if not samples:
        print("当前没有样本记录")
    else:
        print(f"\n{'ID':<4} {'名称':<30} {'架构':<10} {'位数':<6} {'难度':<8} {'来源':<10}")
        print(f"{'─'*70}")
        for s in samples:
            print(f"{s['id']:<4} {s['name'][:28]:<30} {s['arch'] or '?':<10} {s['bits'] or '?':<6} {s['difficulty']:<8} {s['source']:<10}")
    conn.close()


def cmd_tools(args):
    tools = AnalysisTools()
    available = tools.get_available()
    print(f"\nWSL 模式: {'✅ 启用' if tools.wsl_mode else '❌ 未检测到'}")
    print(f"可用工具: {', '.join(available) if available else '（无）'}")
    print(f"\n推荐安装 WSL + Ubuntu，然后:")
    print(f"  sudo apt install binutils file gdb python3-pip")
    print(f"  pip3 install pwntools angr z3-solver pyelftools")


def main():
    parser = argparse.ArgumentParser(description='OpenCyber CTF Agent')
    parser.add_argument('command', choices=[
        'init', 'import', 'import-dir', 'run', 'eval',
        'report', 'resume', 'list', 'tools',
    ])
    parser.add_argument('--sample-id', type=int, help='样本 ID')
    parser.add_argument('--difficulty', choices=['basic', 'medium', 'hard'], help='难度过滤')
    parser.add_argument('--tags', help='标签')
    parser.add_argument('--limit', type=int, help='数量限制')
    parser.add_argument('--output', help='输出路径')
    parser.add_argument('path', nargs='?', help='文件/目录路径')
    parser.add_argument('dir', nargs='?', help='目录路径')

    args = parser.parse_args()

    commands = {
        'init': cmd_init,
        'import': cmd_import,
        'import-dir': cmd_import_dir,
        'run': cmd_run,
        'eval': cmd_eval,
        'report': cmd_report,
        'resume': cmd_resume,
        'list': cmd_list,
        'tools': cmd_tools,
    }

    cmd = commands.get(args.command)
    if cmd:
        cmd(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
