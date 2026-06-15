#!/usr/bin/env bash
#
# OpenCyber CTF Agent — 数据库初始化脚本
#
# 用法：
#   chmod +x scripts/init-db.sh
#   ./scripts/init-db.sh                    # 在当前目录创建 opencyber.db
#   ./scripts/init-db.sh /path/to/dir       # 在指定目录创建
#
# 依赖：sqlite3（Linux / WSL / macOS 自带，Windows 需安装）

set -e

DB_DIR="${1:-.}"
DB_PATH="$DB_DIR/opencyber.db"
SCHEMA_DIR="$(cd "$(dirname "$0")/.." && pwd)/db"

echo "============================================"
echo " OpenCyber CTF Agent — 数据库初始化"
echo "============================================"
echo ""

# 检查 sqlite3
if ! command -v sqlite3 &>/dev/null; then
    echo "[!] 未找到 sqlite3，正在安装..."
    if command -v apt &>/dev/null; then
        sudo apt install -y sqlite3
    elif command -v brew &>/dev/null; then
        brew install sqlite3
    else
        echo "[!] 请手动安装 sqlite3 后重试"
        exit 1
    fi
fi

echo "[1/3] 创建数据库文件: $DB_PATH"
mkdir -p "$DB_DIR"

echo "[2/3] 执行建表脚本..."
sqlite3 "$DB_PATH" < "$SCHEMA_DIR/schema.sql"

echo "[3/3] 验证表结构..."
sqlite3 "$DB_PATH" ".tables"
echo ""

echo "============================================"
echo " ✅ 数据库初始化完成"
echo "    路径: $DB_PATH"
echo "    表: samples, tasks, tool_calls, observations"
echo "         agent_memory, results, evaluation_stats"
echo "    视图: v_evaluation_summary"
echo "============================================"
echo ""
echo "快速验证: sqlite3 $DB_PATH \"SELECT * FROM v_evaluation_summary;\""
