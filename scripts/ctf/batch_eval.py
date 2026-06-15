#!/usr/bin/env python3
"""批量评测入口"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ctf_agent.eval import BatchEvaluator

evaluator = BatchEvaluator()
result = evaluator.run_batch()
evaluator.generate_report(output_path='evaluation_report.md')
evaluator.close()
