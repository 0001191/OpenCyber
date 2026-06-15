<p align="center">
  <br/>
  <img src="https://github.com/0001191/OpenCyber/raw/dev/packages/console/app/src/asset/logo-ornate-light.svg" alt="OpenCyber logo" width="420">
  <br/>
</p>

<p align="center">
  <strong>下一代 AI 编码智能体 · 开源 · 可定制</strong>
</p>

<p align="center">
  <a href="https://github.com/0001191/OpenCyber/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/0001191/OpenCyber?style=flat-square" /></a>
  <a href="https://github.com/0001191/OpenCyber/actions"><img alt="Build" src="https://img.shields.io/github/actions/workflow/status/0001191/OpenCyber/publish.yml?style=flat-square&branch=dev" /></a>
</p>

---

## 快速开始

```bash
git clone https://github.com/0001191/OpenCyber.git
cd OpenCyber
bun install
bun link               # 全局注册 opencyber 命令
bun run dev            # 启动开发模式
opencyber              # 终端中启动 AI 编码智能体
```

### 环境要求

| 工具 | 版本 |
|------|------|
| [Bun](https://bun.sh) | >= 1.3.14 |
| Node.js | >= 22 |
| Git | - |

---

## 团队 AI 开发

OpenCyber 附带 `AGENT.md`，打开项目后 AI 编码工具（Cursor / Claude Code / Windsurf / GitHub Copilot 等）会自动读取，开箱即用。

```bash
# 团队成员直接：
git clone https://github.com/0001191/OpenCyber.git
cd OpenCyber
bun install
opencyber
```

AI 工具会自动获得：
- 项目结构概览
- 技术栈细节（Bun + Effect + SolidJS + Electron）
- 编码约定（Effect 模式、导入路径等）
- 关键命令和构建方式

---

## 桌面应用

从 [Releases](https://github.com/0001191/OpenCyber/releases) 下载桌面版。

| 平台 | 下载 |
|------|------|
| macOS (Apple Silicon) | `opencyber-desktop-mac-arm64.dmg` |
| macOS (Intel) | `opencyber-desktop-mac-x64.dmg` |
| Windows | `opencyber-desktop-windows-x64.exe` |
| Linux | `.deb` / `.rpm` / `.AppImage` |

---

## 智能体

OpenCyber 内置两种智能体，`Tab` 键切换：

- **build** — 全权限开发智能体
- **plan** — 只读分析/代码探索智能体（禁止文件编辑，运行命令前会请求确认）

另有 **general** 子智能体，通过 `@general` 调用。

---

## 项目结构

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

## 贡献

欢迎提交 PR。请先阅读 [CONTRIBUTING.md](./CONTRIBUTING.md)。

---

**基于 [OpenCode](https://github.com/anomalyco/opencode) · 独立维护 · OpenCyber 团队**