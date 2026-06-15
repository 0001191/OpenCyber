#!/usr/bin/env python3
"""数据库初始化脚本"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ctf_agent.db.manager import init_database

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'db', 'opencyber.db')
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

init_database(DB_PATH)
print(f"✅ 数据库已初始化: {DB_PATH}")
print(f"   表: samples, tasks, tool_calls, observations, agent_memory, results, evaluation_stats")
