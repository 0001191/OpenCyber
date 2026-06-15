# OpenCyber - AI 开发指南

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
