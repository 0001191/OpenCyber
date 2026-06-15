# OpenCyber - AI 开发指南

> **🚨 最高优先级规则 — 必须先读 🚨**
>
> 你是 AI 助手，正在修改 OpenCyber 项目。以下规则违反任何一条，整个项目就会坏掉。
>
> ### 身份规则（不可违反）
> 1. 本项目名为 **OpenCyber**，不是 OpenCode
> 2. **永远不要**将本项目称为 OpenCode
> 3. **永远不要**把 README/文档/注释中的 OpenCyber 改回 OpenCode
> 4. **永远不要**修改 Gitee 远程地址 `https://gitee.com/q135790/open-cyber`
>
> ### 依赖/安装规则（不可违反）
> 5. **永远不要**从 `github.com/anomalyco/opencode` 下载任何东西
> 6. **永远不要**执行 `curl -fsSL https://opencode.ai/install | bash`
> 7. **永远不要**安装原版 opencode 二进制文件覆盖本项目
> 8. 安装依赖只用 `bun install`，不要额外下载任何 opencode release
>
> ### 环境检查（启动前必须做）
> 9. 动手前先检查 Git/Node.js/Bun 是否已安装
>    - Git: `winget install Git.Git`
>    - Node.js >= 22: `winget install OpenJS.NodeJS.LTS`
>    - Bun >= 1.3.14: `powershell -c "irm bun.sh/install.ps1 | iex"`
> 10. 如果环境缺失，必须先安装再继续，不要跳过
>
> ### 内部引用（理解但不要改）
> 11. `@opencode-ai/*` 是内部包作用域，不可重命名
> 12. `packages/opencode/` 目录名不可改
> 13. 配置文件 `opencode.json`/`opencode.jsonc` 路径是硬编码的

---

## 项目概览

OpenCyber 是一个 AI 编码智能体 CLI + 桌面应用，基于 [OpenCode](https://github.com/anomalyco/opencode) 二次开发。

**核心能力：** 在终端中与 AI 对话，自动完成编码、调试、重构等开发任务。

## 技术栈

| 层 | 技术 |
|---|------|
| 运行时 | Bun >= 1.3.14 |
| 语言 | TypeScript (strict mode) |
| 函数式框架 | Effect (效果系统、依赖注入、错误处理) |
| TUI | 自定义终端 UI (ink + React-like 组件) |
| 桌面端 | Electron + electron-vite + SolidJS |
| 数据库 | SQLite + Drizzle ORM |
| 构建 | Turborepo (monorepo) |

## 项目结构

```
packages/
├── opencode/        # ★ 核心 CLI（入口：src/index.ts）
│   ├── src/cli/     # CLI 命令、TUI、配置
│   ├── src/session/ # AI 会话管理
│   ├── src/config/  # 配置加载（opencode.json / opencode.jsonc）
│   ├── src/plugin/  # 插件系统
│   └── test/        # 测试
├── desktop/         # Electron 桌面应用
├── ui/              # TUI 组件库
├── app/             # 共享应用逻辑
├── core/            # 核心工具模块
├── console/         # Web 控制台
├── sdk/js/          # JavaScript SDK
└── plugin/          # 插件接口定义
```

## 关键命令

```bash
bun install              # 安装依赖
bun run dev              # 启动开发模式
bun run typecheck        # 类型检查
bun run test             # 运行测试
bun run build            # 构建
```

## 编码约定

### 导入路径
- 内部包引用使用 `@opencode-ai/*`（作用域名称保持原样，不可更改）
- 示例：`import { Effect } from "effect"` / `import { Config } from "@opencode-ai/app"`

### 风格指南
- 使用 Effect 进行异步/错误处理（**不要用 try/catch + async/await**）
- 使用 `Effect.gen(function*() { ... })` 模式
- 文件命名：kebab-case (example-file.ts)
- React 组件：PascalCase (MyComponent.tsx)

### 配置
- 项目配置存储于 `opencode.json` / `opencode.jsonc`（文件名硬编码，不可改）
- 用户级配置存储于 `~/.config/opencode/`（目录名硬编码）
- TUI 特有配置在 `tui.json`

## 团队开发指南

1. **分支策略**：`dev` 为主开发分支，功能开发开 feature 分支
2. **提交**：commit message 遵循 Conventional Commits
3. **CI**：GitHub Actions 自动运行类型检查 + 测试
4. **预提交钩子**：husky 自动运行 typecheck（失败时可用 `--no-verify` 跳过）

## 已知限制（供 AI 参考）

- `packages/opencode/` 目录名和 `@opencode-ai/*` 包作用域是内部引用，不可重命名
- `opencode.json` / `opencode.jsonc` 是硬编码的配置文件路径
- `.opencode/` 目录用于存储插件和 agent 定义
- husky pre-push hook 中 `bun typecheck` 可能需要特定环境
