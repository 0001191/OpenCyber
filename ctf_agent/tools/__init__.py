"""
CTF Agent 工具层 — 逆向工具封装接口

提供统一的工具调用接口，Agent 通过此层调用各种逆向工具。
每个工具类实现标准接口：run(params) → dict
"""

import subprocess
import os
import re
import json
import time
import tempfile


class ToolResult:
    """工具调用结果"""

    def __init__(self, success=True, output='', error='', data=None, duration_ms=0):
        self.success = success
        self.output = output
        self.error = error
        self.data = data or {}
        self.duration_ms = duration_ms

    def to_dict(self):
        return {
            'success': self.success,
            'output': self.output,
            'error': self.error,
            'data': self.data,
            'duration_ms': self.duration_ms,
        }


class BaseTool:
    """工具基类"""

    name = 'base'

    def __init__(self, wsl_mode=False):
        self.wsl_mode = wsl_mode

    def _resolve_path(self, path):
        """处理 WSL 路径转换"""
        if self.wsl_mode and re.match(r'^[A-Za-z]:\\', path):
            drive = path[0].lower()
            wsl_path = f'/mnt/{drive}/{path[3:].replace("\\", "/")}'
            return wsl_path
        return path

    def _run_cmd(self, cmd, timeout=30):
        """执行命令并计时"""
        start = time.time()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
            duration = int((time.time() - start) * 1000)
            return ToolResult(
                success=(result.returncode == 0),
                output=result.stdout,
                error=result.stderr,
                duration_ms=duration,
            )
        except subprocess.TimeoutExpired:
            duration = int((time.time() - start) * 1000)
            return ToolResult(success=False, error='Timeout', duration_ms=duration)
        except FileNotFoundError as e:
            return ToolResult(success=False, error=f'Tool not found: {e}')
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def run(self, **kwargs):
        raise NotImplementedError


class FileTool(BaseTool):
    """file 命令 — 识别文件类型"""

    name = 'file'

    def run(self, target_path, **kwargs):
        path = self._resolve_path(target_path)
        cmd = ['file', path]
        if self.wsl_mode:
            cmd = ['wsl'] + cmd
        return self._run_cmd(cmd)


class StringsTool(BaseTool):
    """strings 命令 — 提取字符串"""

    name = 'strings'

    def run(self, target_path, encoding='ascii', max_lines=100, **kwargs):
        path = self._resolve_path(target_path)
        if encoding == 'utf16':
            cmd = ['strings', '-e', 'l', path]
        else:
            cmd = ['strings', path]
        if self.wsl_mode:
            cmd = ['wsl'] + cmd

        result = self._run_cmd(cmd)
        if result.success:
            lines = result.output.splitlines()
            result.data['total_lines'] = len(lines)
            result.output = '\n'.join(lines[:max_lines])
            result.data['preview'] = lines[:max_lines]
            result.data['has_more'] = len(lines) > max_lines
        return result


class ReadelfTool(BaseTool):
    """readelf 命令 — ELF 文件分析"""

    name = 'readelf'

    def run(self, target_path, action='all', **kwargs):
        """
        action: all / header / sections / symbols / relocs / notes
        """
        path = self._resolve_path(target_path)
        flag_map = {
            'all': '-a', 'header': '-h', 'sections': '-S',
            'symbols': '-s', 'relocs': '-r', 'notes': '-n'
        }
        flag = flag_map.get(action, '-a')
        cmd = ['readelf', flag, path]
        if self.wsl_mode:
            cmd = ['wsl'] + cmd
        return self._run_cmd(cmd)


class ObjdumpTool(BaseTool):
    """objdump 命令 — 反汇编"""

    name = 'objdump'

    def run(self, target_path, mode='disasm', symbol=None, **kwargs):
        """
        mode: disasm / headers / source / all
        symbol: 指定函数名反汇编
        """
        path = self._resolve_path(target_path)
        if symbol:
            cmd = ['objdump', '-d', f'--disassemble={symbol}', path]
        elif mode == 'headers':
            cmd = ['objdump', '-f', path]
        elif mode == 'source':
            cmd = ['objdump', '-S', path]
        else:
            cmd = ['objdump', '-d', path]
        if self.wsl_mode:
            cmd = ['wsl'] + cmd
        return self._run_cmd(cmd)


class GDBTool(BaseTool):
    """GDB 自动化调试"""

    name = 'gdb'

    def run(self, target_path, commands=None, script=None, **kwargs):
        """
        commands: GDB 命令列表
        script: GDB 脚本路径
        """
        path = self._resolve_path(target_path)
        gdb_cmd = ['gdb', '-batch', '-nx', path]

        if script:
            gdb_cmd += ['-x', self._resolve_path(script)]
        if commands:
            for cmd in commands:
                gdb_cmd += ['-ex', cmd]

        if self.wsl_mode:
            gdb_cmd = ['wsl'] + gdb_cmd
        return self._run_cmd(gdb_cmd, timeout=60)

    def checksec(self, target_path):
        """检查二进制保护"""
        path = self._resolve_path(target_path)
        # 用 GDB 的 checksec 或 readelf 检查
        result = self.run(path, commands=['info files'])
        data = {}
        if result.success:
            output = result.output
            data['nx'] = 'NX enabled' in output or 'stack_exec' not in output
            data['pie'] = 'Position Independent' in output or 'Type: DYN' in output
            data['relro'] = 'RELRO' in output
            data['canary'] = '__stack_chk_fail' in output
        result.data = data
        return result


class PwntoolsTool(BaseTool):
    """Python pwntools 封装"""

    name = 'pwntools'

    def run(self, script_code, **kwargs):
        """执行 pwntools Python 脚本"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(script_code)
            script_path = f.name

        try:
            cmd = ['python3', script_path]
            result = self._run_cmd(cmd, timeout=60)
            return result
        finally:
            os.unlink(script_path)

    def elf_info(self, target_path):
        """获取 ELF 关键信息"""
        path = self._resolve_path(target_path)
        # 使用 Windows 路径（pwntools 运行在 WSL 中需要处理）
        python_code = f"""
from pwn import *
import json
try:
    elf = ELF('''{path}''')
    info = {{
        'arch': elf.arch,
        'bits': elf.bits,
        'entry': hex(elf.entry),
        'pie': elf.pie,
        'nx': elf.execstack,
        'canary': elf.canary,
        'relro': elf.relro,
        'plt': list(elf.plt.keys()),
        'got': list(elf.got.keys()),
    }}
    print(json.dumps(info))
except Exception as e:
    print(f'ERROR: {{e}}')
"""
        result = self.run(python_code)
        if result.success:
            try:
                result.data = json.loads(result.output.strip())
            except json.JSONDecodeError:
                pass
        return result


class AnalysisTools:
    """工具集合 — 统一调用的门面类"""

    def __init__(self, wsl_mode=None):
        # 自动检测 WSL 环境
        if wsl_mode is None:
            try:
                result = subprocess.run(['where', 'wsl'], capture_output=True, text=True)
                wsl_mode = result.returncode == 0 and not os.name == 'posix'
            except FileNotFoundError:
                wsl_mode = False
        self.wsl_mode = wsl_mode
        self.tools = {
            'file': FileTool(wsl_mode),
            'strings': StringsTool(wsl_mode),
            'readelf': ReadelfTool(wsl_mode),
            'objdump': ObjdumpTool(wsl_mode),
            'gdb': GDBTool(wsl_mode),
            'pwntools': PwntoolsTool(wsl_mode),
        }

    def get_available(self):
        """返回当前可用的工具列表"""
        available = []
        for name, tool in self.tools.items():
            try:
                result = tool._run_cmd(['which' if not self.wsl_mode else 'wsl', name] + [name] * (1 if not self.wsl_mode else 0))
                if result.success:
                    available.append(name)
            except Exception:
                pass
        return available

    def call(self, tool_name, **params):
        """统一工具调用入口"""
        tool = self.tools.get(tool_name)
        if not tool:
            return ToolResult(success=False, error=f'Unknown tool: {tool_name}')
        return tool.run(**params)
