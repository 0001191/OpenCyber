# OpenCyber CTF Agent — 课程设计项目

基于 OpenCyber 二次开发的 Linux CTF 逆向智能体系统。

## 项目定位

本目录是《网络空间安全综合实践》课程设计的核心子系统，实现面向 Linux ELF 逆向题的自动化智能体分析系统。

**系统架构：**

```
ctf_agent/
├── db/              # 数据库层：schema、CRUD 操作
├── tools/           # 工具层：逆向工具封装接口
├── agent/           # Agent 层：主循环、记忆、提示词
├── manager/         # 管理层：样本导入、任务跟踪
├── eval/            # 评测层：批量评测、报告生成
└── main.py          # CLI 入口
```

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python scripts/ctf/init_db.py

# 导入样本
python ctf_agent/main.py import samples/xxx.elf

# 创建并运行分析任务
python ctf_agent/main.py run --sample-id 1

# 批量评测
python ctf_agent/main.py eval --dir ./data/samples/
```

## 数据库表结构

| 表 | 说明 |
|----|------|
| `samples` | 题目元数据（路径、类型、架构、难度等） |
| `tasks` | 分析任务记录（状态、耗时、结果） |
| `tool_calls` | 工具调用记录（工具名、参数、输出） |
| `observations` | 中间分析结果与观察结论 |
| `agent_memory` | Agent 工作记忆与历史线索 |
| `results` | 最终答案与破解结论 |
| `evaluation_stats` | 评测统计数据 |
