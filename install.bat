@echo off
chcp 65001 >nul
title OpenCyber 一键安装程序
setlocal enabledelayedexpansion

:: ============================================================
::  OpenCyber Windows 一键安装脚本
::  版本: 1.0
::  适用: Windows 10/11
::  双击运行即可自动安装所有依赖和项目
:: ============================================================

echo.
echo   ╔══════════════════════════════════════════════════╗
echo   ║          OpenCyber AI 编程助手 - 安装程序          ║
echo   ╚══════════════════════════════════════════════════╝
echo.
echo   本程序将自动安装以下内容：
echo     [1] Git (版本管理)
echo     [2] Node.js LTS (JavaScript 运行时)
echo     [3] Bun (高性能 JS 运行时)
echo     [4] OpenCyber 项目 (AI 编程助手)
echo.
echo   整个过程大约需要 5-15 分钟，请耐心等待。
echo.
echo   ────────────────────────────────────────────────
echo.

:: ---------- 步骤 0: 检查管理员权限 ----------
echo   [检查] 管理员权限...
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo   [提示] 建议以管理员身份运行，某些安装可能需要权限
    echo   [提示] 如果安装失败，请右键此文件 → "以管理员身份运行"
    echo.
)

:: ---------- 步骤 1: 检查/安装 Git ----------
echo   [1/4] 检查 Git...
where git >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('git --version') do echo         已安装: %%i
) else (
    echo         未检测到 Git，正在安装...
    winget install --id Git.Git -e --source winget --accept-source-agreements --accept-package-agreements >nul 2>&1
    if %errorlevel% equ 0 (
        echo         Git 安装完成！请重新运行此脚本。
        echo.
        echo   ⚠ 刚刚安装了 Git，需要刷新环境变量。
        echo     请关闭此窗口，重新双击 install.bat。
        pause
        exit /b 0
    ) else (
        echo         winget 安装失败，请手动安装 Git:
        echo         https://git-scm.com/download/win
        echo         安装后重新运行此脚本。
        pause
        exit /b 1
    )
)

:: ---------- 步骤 2: 检查/安装 Node.js ----------
echo   [2/4] 检查 Node.js...
where node >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('node --version') do echo         已安装: %%i
) else (
    echo         未检测到 Node.js，正在安装...
    winget install --id OpenJS.NodeJS.LTS -e --source winget --accept-source-agreements --accept-package-agreements >nul 2>&1
    if %errorlevel% equ 0 (
        echo         Node.js 安装完成！请重新运行此脚本。
        echo.
        echo   ⚠ 刚刚安装了 Node.js，需要刷新环境变量。
        echo     请关闭此窗口，重新双击 install.bat。
        pause
        exit /b 0
    ) else (
        echo         winget 安装失败，请手动安装 Node.js:
        echo         https://nodejs.org/ (选择 LTS 版本)
        echo         安装后重新运行此脚本。
        pause
        exit /b 1
    )
)

:: ---------- 步骤 3: 检查/安装 Bun ----------
echo   [3/4] 检查 Bun...
where bun >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('bun --version') do echo         已安装: %%i
) else (
    echo         未检测到 Bun，正在安装...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm bun.sh/install.ps1 | iex" >nul 2>&1
    if %errorlevel% equ 0 (
        echo         Bun 安装完成！
    ) else (
        echo         自动安装失败，请手动安装:
        echo         1. 打开 PowerShell (Win+R → 输入 powershell)
        echo         2. 粘贴运行: powershell -c "irm bun.sh/install.ps1 | iex"
        echo         3. 安装完成后，重新双击 install.bat
        pause
        exit /b 1
    )
    :: 刷新环境变量
    set "PATH=%USERPROFILE%\.bun\bin;%PATH%"
    where bun >nul 2>&1
    if %errorlevel% neq 0 (
        echo         Bun 已安装但未生效，请重新运行此脚本。
        pause
        exit /b 1
    )
    echo         Bun 安装完成！
)

echo.
echo   ────────────────────────────────────────────────
echo   ✓ 所有运行环境已就绪！
echo   ────────────────────────────────────────────────
echo.

:: ---------- 步骤 4: 克隆/更新 OpenCyber 项目 ----------
echo   [4/4] 安装 OpenCyber 项目...

set "INSTALL_DIR=%USERPROFILE%\OpenCyber"

if exist "%INSTALL_DIR%\.git" (
    echo         检测到已有项目，正在更新到最新版本...
    cd /d "%INSTALL_DIR%"
    git pull --no-verify >nul 2>&1
    if %errorlevel% equ 0 (
        echo         更新完成！
    ) else (
        echo         更新失败，尝试重新克隆...
        cd /d "%USERPROFILE%"
        rmdir /s /q "%INSTALL_DIR%" >nul 2>&1
        goto :clone_fresh
    )
) else (
    :clone_fresh
    if exist "%INSTALL_DIR%" (
        echo         目录已存在，正在清理...
        rmdir /s /q "%INSTALL_DIR%" >nul 2>&1
    )
    echo         正在从 Gitee 下载项目...
    git clone https://gitee.com/q135790/open-cyber.git "%INSTALL_DIR%" >nul 2>&1
    if %errorlevel% neq 0 (
        echo         克隆失败！请检查网络连接。
        echo         手动下载: https://gitee.com/q135790/open-cyber
        pause
        exit /b 1
    )
    echo         项目下载完成！
)

:: ---------- 安装项目依赖 ----------
cd /d "%INSTALL_DIR%"
echo.
echo         正在安装项目依赖（这可能需要几分钟）...
call bun install >nul 2>&1
if %errorlevel% neq 0 (
    echo         依赖安装失败，正在重试...
    call bun install
    if %errorlevel% neq 0 (
        echo         安装失败，请检查错误信息。
        pause
        exit /b 1
    )
)

echo         依赖安装完成！
echo.

:: ---------- 验证 ----------
echo   ────────────────────────────────────────────────
echo   [验证] 检查安装...
echo.

set "ALL_OK=1"

where git >nul 2>&1 || (echo   ✗ Git 未找到 && set "ALL_OK=0")
where node >nul 2>&1 || (echo   ✗ Node.js 未找到 && set "ALL_OK=0")
where bun >nul 2>&1 || (echo   ✗ Bun 未找到 && set "ALL_OK=0")

if exist "%INSTALL_DIR%\package.json" (
    echo   ✓ OpenCyber 项目已安装
) else (
    echo   ✗ OpenCyber 项目未找到
    set "ALL_OK=0"
)

echo.

if %ALL_OK% equ 0 (
    echo   ⚠ 部分组件缺失，请检查上述错误。
    pause
    exit /b 1
)

echo   ╔══════════════════════════════════════════════════╗
echo   ║            🎉 安装完成！欢迎使用 OpenCyber           ║
echo   ╚══════════════════════════════════════════════════╝
echo.
echo   项目路径: %INSTALL_DIR%
echo.
echo   ❯ 如何启动开发模式：
echo       cd %INSTALL_DIR%
echo       bun run dev
echo.
echo   ❯ 如何启动桌面应用：
echo       cd %INSTALL_DIR%
echo       bun run dev:desktop
echo.
echo   ❯ 如需使用 AI 助手修改项目，请阅读 README.md
echo      (已包含给 AI 的提示词)
echo.
echo   建议将此窗口保存以备后续参考。
echo   ────────────────────────────────────────────────
pause
