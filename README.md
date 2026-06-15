<p align="center">
  <br/>
  <img src="./packages/console/app/src/asset/logo-ornate-light.svg" alt="OpenCyber logo" width="420">
  <br/>
</p>

<p align="center">
  <strong>AI 编码智能体 · 终端内智能编程 · 开源</strong>
</p>

<p align="center">
  <a href="https://github.com/0001191/OpenCyber/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/0001191/OpenCyber?style=flat-square" /></a>
  <a href="https://github.com/0001191/OpenCyber/actions"><img alt="Build" src="https://img.shields.io/github/actions/workflow/status/0001191/OpenCyber/publish.yml?style=flat-square&branch=dev" /></a>
  <a href="https://gitee.com/q135790/open-cyber"><img alt="Gitee" src="https://img.shields.io/badge/Gitee-镜像-C71D23?style=flat-square" /></a>
</p>

---

## 🚀 快速开始

```bash
git clone https://github.com/0001191/OpenCyber.git
cd OpenCyber
bun install
bun link
bun run dev          # 启动开发模式
opencyber            # 在终端中启动 AI 编码智能体
```

### 环境要求

| 工具 | 版本 |
|------|------|
| [Bun](https://bun.sh) | >= 1.3.14 |
| Node.js | >= 22 |
| Git | - |

---

## 🤖 智能体

OpenCyber 内置两种智能体，按 `Tab` 键切换：

| 模式 | 说明 |
|------|------|
| **build** | 全权限开发智能体，可读写文件、执行命令 |
| **plan** | 只读分析模式，探索代码、提供建议，执行命令前需确认 |

---

## 📁 项目结构

```
OpenCyber/
├── packages/
│   ├── opencode/    # 核心 CLI（TUI + AI 会话 + 配置 + 插件）
│   ├── desktop/     # Electron 桌面应用
│   ├── ui/          # TUI 组件库
│   ├── app/         # 共享应用逻辑
│   ├── core/        # 核心工具模块
│   ├── console/     # Web 控制台
│   └── ...
├── AGENT.md         # AI 开发上下文（AI 工具自动读取）
└── bun.lock
```

---

## 💻 桌面应用

从 [Releases](https://github.com/0001191/OpenCyber/releases) 下载桌面版。

| 平台 | 下载 |
|------|------|
| macOS (Apple Silicon) | `opencyber-desktop-mac-arm64.dmg` |
| macOS (Intel) | `opencyber-desktop-mac-x64.dmg` |
| Windows | `opencyber-desktop-windows-x64.exe` |
| Linux | `.deb` / `.rpm` / `.AppImage` |

---

## 🤝 团队协作

1. 将你的 Gitee 用户名告诉项目管理员
2. 生成个人访问令牌：[设置 → 私人令牌](https://gitee.com/profile/personal_access_tokens)
3. 克隆仓库并开始开发：

```bash
git clone https://gitee.com/q135790/open-cyber.git
cd open-cyber
bun install
bun run dev
```

项目包含 `AGENT.md`，AI 编码工具（Cursor / Claude Code / Windsurf 等）打开即用，自动获得项目上下文。

---

## 贡献

欢迎提交 Issue 和 PR。请先阅读 [CONTRIBUTING.md](./CONTRIBUTING.md)。

---

**OpenCyber 团队 · 开源 · MIT License**
