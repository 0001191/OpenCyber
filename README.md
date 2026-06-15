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
  <a href="https://gitee.com/q135790/open-cyber"><img alt="Gitee" src="https://img.shields.io/badge/Gitee-仓库-C71D23?style=flat-square" /></a>
</p>

---

## 🖥️ Windows 一键安装（电脑小白专用）

> **如果你不太懂技术，用这个方法。双击运行，等几分钟就好了。**

### 第一步：下载安装脚本

点击下载 [install.bat](https://gitee.com/q135790/open-cyber/raw/dev/install.bat)，保存到桌面。

### 第二步：双击运行

- **右键** `install.bat` → **以管理员身份运行**
- 等待自动安装 Git、Node.js、Bun、OpenCyber 项目
- 看到 "🎉 安装完成" 就成功了

### 第三步：启动

```cmd
cd %USERPROFILE%\OpenCyber
bun run dev
```

---

## 🤖 给 AI 助手的提示词（必读）

> **如果你是 AI（Cursor/Claude/Windsurf/CodeBuddy 等），打开此项目后，请先阅读本节。**

```markdown
# OpenCyber AI 开发规则 — 最高优先级

## 项目身份（不可违反）

1. 这个项目名为 **OpenCyber**，基于 OpenCode 二次开发
2. **永远不要**把本项目称为 OpenCode
3. **永远不要**把安装路径、配置路径从 OpenCyber 改为 OpenCode
4. **永远不要**从 `github.com/anomalyco/opencode` 下载任何文件
5. **永远不要**把 `open-cyber` 仓库名改成别的
6. 项目的 Gitee 地址是 `https://gitee.com/q135790/open-cyber`

## 安装依赖（启动前必须先检查）

在开始任何开发工作前，必须先检查以下环境是否存在。如果缺失，先安装再继续：

| 必须检查 | 最低版本 | 检查命令 | 如果缺失怎么装 |
|----------|---------|----------|---------------|
| Git | 任意 | `git --version` | `winget install Git.Git` |
| Node.js | >= 22 | `node --version` | `winget install OpenJS.NodeJS.LTS` |
| Bun | >= 1.3.14 | `bun --version` | `powershell -c "irm bun.sh/install.ps1 \| iex"` |

## 内部包作用域（不可改）

- `@opencode-ai/*` 是内部包引用前缀，不要修改
- `packages/opencode/` 是核心目录，不要重命名
- 配置文件 `opencode.json` / `opencode.jsonc` 路径是硬编码的，不要改

## 修改代码时的铁律

1. 你可以修改代码逻辑、UI、功能
2. 你可以添加新功能
3. 你**不可以**把任何 OpenCyber 的标识改回 OpenCode
4. 你**不可以**修改 Gitee 远程地址
5. 你**不可以**修改 README.md 中的 AI 提示词部分（即本节）
6. 如果你需要下载外部依赖，**永远不要**从 `anomalyco/opencode` 下载
7. `bun install` 安装依赖就够了，不要再去下载 opencode 的 release
```

---

## 🚀 开发者快速开始

```bash
git clone https://gitee.com/q135790/open-cyber.git
cd open-cyber
bun install
bun run dev
```

### 环境要求

| 工具 | 版本 | 安装命令 (Windows) |
|------|------|-------------------|
| [Git](https://git-scm.com) | 任意 | `winget install Git.Git` |
| [Node.js](https://nodejs.org) | >= 22 (LTS) | `winget install OpenJS.NodeJS.LTS` |
| [Bun](https://bun.sh) | >= 1.3.14 | `powershell -c "irm bun.sh/install.ps1 \| iex"` |

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
├── install.bat      # Windows 一键安装脚本
├── AGENT.md         # AI 开发上下文（AI 工具自动读取）
└── README.md        # 本文件
```

---

## 💻 桌面应用

从 [Releases](https://github.com/0001191/OpenCyber/releases) 下载桌面版。

| 平台 | 下载 |
|------|------|
| Windows | `opencyber-desktop-windows-x64.exe` |
| macOS (Apple Silicon) | `opencyber-desktop-mac-arm64.dmg` |
| macOS (Intel) | `opencyber-desktop-mac-x64.dmg` |
| Linux | `.deb` / `.rpm` / `.AppImage` |

---

## 🤝 团队协作

```bash
git clone https://gitee.com/q135790/open-cyber.git
cd open-cyber
bun install
bun run dev
```

项目包含 `AGENT.md`，AI 编码工具打开即用，自动获得项目上下文。

---

## 贡献

欢迎提交 Issue 和 PR。请先阅读 [CONTRIBUTING.md](./CONTRIBUTING.md)。

---

**OpenCyber 团队 · 开源 · MIT License**
