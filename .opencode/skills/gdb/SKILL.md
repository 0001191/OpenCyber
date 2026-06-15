---
name: gdb
description: GNU Debugger (GDB) for binary analysis. Use this skill when the agent needs dynamic analysis - inspecting live process state, stepping through instructions, setting breakpoints, dumping memory, anti-debug bypass, or scripting with batch/MI mode. Works for ELF (via WSL) and PE (local) on Windows.
---

# GDB - GNU Debugger Skill

This skill teaches the binary-analysis agent how to **drive GDB as a first-class information-collection tool**, both interactively and in batch / MI modes. GDB is installed locally at `D:\gcc\w64devkit\bin\gdb.exe` (v16.2, no Python) and inside WSL at `/usr/local/bin/gdb` (v17.2, no Python). Use whichever one matches the target binary's format.

> **Load this skill** whenever the task description mentions GDB, dynamic analysis, debugging, runtime state, anti-debug bypass, breakpoint, trace, register/memory inspection, or when 阶段三 planning requires runtime evidence that static analysis cannot provide.

---

## 0. Pre-flight: Detect & Select GDB

Always run a quick detection before any GDB call. Output the result, then commit to one path for the rest of the session.

### Try-before-build checklist（每次 GDB 会话前过一遍）

```
□ 遇到反调试/抗阻？→ 先查 GDB 是否有原生命令搞定（set follow-fork-mode / catch syscall / return 0）
□ 要写多行脚本？→ 用 Write 工具创建文件，不用 heredoc
□ 这一轮只验证一个假设？→ 是，不要在一轮 GDB 调用里塞 5 个不相关的问题
□ 这段代码解决的是眼前的问题？→ 是，不预判"万一"的场景
```

全部打勾再动手指。

```bash
# ── Local (Windows) ──
which gdb                       # expect: /d/gcc/w64devkit/bin/gdb
gdb --version | head -1        # confirm version
gdb -batch -nx -ex "quit" 2>&1 | head -1     # sanity: it starts

# ── WSL (Linux ELF preferred) ──
wsl which gdb                  # expect: /usr/local/bin/gdb
wsl gdb --version | head -1
```

### Decision matrix

| Target format | Local GDB? | WSL GDB? | Use |
|--------------|-----------|----------|-----|
| Windows PE (.exe/.dll) | ✅ | n/a | **local** |
| Linux ELF x86_64 | ❌  | ✅ | **wsl** (preferred) |
| Linux ELF x86_64 | ✅  | n/a | local works (mingw-built) |
| Linux ELF ARM/MIPS | ❌  | ✅ | **wsl** (multiarch gdb) |
| Mach-O / raw binary | depends | depends | pick one with right `gdb-multiarch` |

### WSL path translation

| Windows path | WSL path |
|---|---|
| `D:\ctf\a.elf` | `/mnt/d/ctf/a.elf` |
| `C:\Users\q\b.exe` | `/mnt/c/Users/q/b.exe` |

Drive letter → lowercase, backslash → forward slash, prepend `/mnt/`. If you need it the other way: `wsl wslpath -w /mnt/d/ctf/a.elf`.

### Avoid quoting hell: Write files, not heredocs

**Never pass multi-line code through shell quoting.** PowerShell mangles `$`, double quotes, and backticks; bash heredocs in nested shells lose context; and debugging quoting errors takes longer than writing a file. The universal rule:

> Needs more than 1 line? → **Write it as a file first.**

Two patterns that always work:

**Pattern A: Write GDB command file with the IDE tool, then execute**

```
Step 1: Use the Write tool to create /tmp/cmds.gdb with content:
  file /mnt/d/ctf/challenge
  set pagination off
  b *0x401234
  r
  info registers
  quit

Step 2: Execute
  wsl gdb -batch -nx -x /tmp/cmds.gdb
```

**Pattern B: Write a standalone script, then execute**

```
Step 1: Use the Write tool to create /tmp/solve.py or /tmp/hook.c
Step 2: Copy to WSL and run
  wsl cp /mnt/d/.../tmp_hook.c /tmp/hook.c
  wsl gcc -shared -fPIC -o /tmp/hook.so /tmp/hook.c
```

**Pattern C (short commands only): Use `-ex` to chain, no heredoc needed**

```bash
wsl gdb -batch -nx \
  -ex "set pagination off" \
  -ex "file /mnt/d/ctf/challenge" \
  -ex "info functions" \
  -ex "disas main" \
  /mnt/d/ctf/challenge
```

> `-batch -nx -ex "set pagination off"` starts every session. `-batch` exits when commands finish; `-nx` skips `~/.gdbinit` (avoids the user's pwndbg/gef TUI hijacking the session); `set pagination off` prevents `--More--` blocks.

---

## 1. 4 Modes of Using GDB

| Mode | Flag | When to use |
|------|------|------------|
| **Batch** | `-batch -x file.gdb` | CI / automation / one-shot analysis |
| **Interactive TUI** | `-tui` | Human-driven exploration |
| **MI (Machine Interface)** | `--interpreter=mi2` | Tool integration (lldb-vscode, VSCode, scripts) |
| **Python scripting** | `-ex "py ..."` | When GDB has Python embedded (most distros do, w64devkit does NOT) |

For this agent, **batch mode is the default**. TUI/MI are documented below for completeness.

### MI (Machine Interface) — for scripts that need to react to events

```bash
# Stream MI events; parse with awk/grep
gdb --interpreter=mi2 -batch -nx \
  -ex "set pagination off" \
  -ex "file ./challenge" \
  -ex "b main" \
  -ex "exec-run" \
  -ex "data-evaluate-expression \$rax"
```

Each `-ex` in MI mode produces `^done` / `*stopped` records. Easier to consume than human-readable text.

---

## 2. Core Command Reference (the 30 commands you actually need)

### Lifecycle

```
file <path>            load a binary (no execution)
exec-file <path>       set binary to debug (no symbols)
core <path>            load a core dump
attach <pid>           attach to a running process
detach                 release the process
run [args...]          r / r < input    start the program
start                  run + break at main
quit                    q               exit GDB
```

### Breakpoints

```
b main                  by symbol
b *0x401234            by absolute address
b *main+0x42            by symbol+offset
b file.c:42             by source line
b foo if $rax==0x1337   conditional
tb foo                  temporary (auto-delete after hit)
hb HardwareWatchpoint   hbreak (requires hw support, bypasses some anti-debug)
watch $rax == 0x1337    data watchpoint (trigger on memory/register change)
rwatch, awatch          read / access watchpoint
info breakpoints         i b             list all
delete <n>               d N             remove one
delete                   d               remove all
disable <n> / enable <n>                toggle without losing
save breakpoints file.gdb               export bp list
source file.gdb                          restore bp list
```

### Stepping

```
n / next               step over calls
s / step               step into calls
ni / nexti             step one instruction (skip calls)
si / stepi             step one instruction (enter calls)
c / continue           resume
finish                 run until current function returns
until <line>           run to source line
```

### Inspection

```
info registers         i r          all registers
info registers rax     i r rax      one register
info frame             i f          current frame (caller, ret addr, saved regs)
info locals                       local vars
info args                         args of current fn
x/10gx $rsp            raw 8-byte hex dump, 10 units, giant format
x/20i $pc              20 instructions at PC
x/s $rdi               as C string
x/4wx $rsp+8           4 32-bit words
x/64bx 0x404000        64 bytes from absolute addr
p $rax                 print register
p/d $rax               decimal
p/x $rax               hex
p/t $rax               binary
p (char*)$rdi          cast to string
p *((int*)$rsp)        deref pointer
disas                  disassemble current function
disas main              disassemble a function
disas 0x401000,0x401200 disassemble a range
set $rax = 0            modify register
set {int}0x404000 = 0   write memory
```

### Memory mapping

```
info proc mappings     i proc m      regions with perms (rwx)
info files                          sections
info sharedlibrary                 loaded shared libs
maintenance info sections q          all sections with flags
```

### Reverse debugging (when recorded)

```
record                  start recording
reverse-step            rs
reverse-continue        rc
```

### Misc

```
generate-core-file     dump core
shell ls                run shell command
python print(1+1)       Python REPL (if compiled with python)
```

### GDB 最小行动法则（防过度设计）

```
  遇到问题
     │
     ▼
  GDB 有内置命令吗？  ──有──→ 一行 -ex 搞定，不写脚本
     │ 没有
     ▼
  写 GDB 命令文件 (< 10 行)  ──行──→ Write → -x 执行
     │ 不够
     ▼
  写 Python/C 脚本 (LD_PRELOAD)  ← 最后手段
```

- **3 条 GDB 命令以内**：直接 `-ex` 串联，不另建文件
- **3-10 条命令**：Write 写 `.gdb` 文件，`-x` 执行
- **超过 10 条或需要条件逻辑**：用 Python/pwntools 写独立脚本

---

## 3. CTF Playbooks (the 5 patterns that solve 80% of problems)

### Playbook A: Find & dump a hidden flag string in memory

```bash
# Step 1: locate candidate functions
gdb -batch -nx -ex "set pagination off" \
  -ex "file ./challenge" \
  -ex "info functions" \
  -ex "disas main" \
  ./challenge > /tmp/initial.txt

# Step 2: pick the suspicious function (e.g. decrypt_flag at 0x4012a0)
# Step 3: run, break at the function exit, dump its stack/heap
gdb -batch -nx -ex "set pagination off" \
  -ex "file ./challenge" \
  -ex "b *0x4012a0" \
  -ex "r" \
  -ex "ni" -ex "ni" -ex "ni" \
  -ex "x/s $rdi" \
  -ex "x/s $rsi" \
  -ex "x/64s $rsp" \
  ./challenge
```

### Playbook B: Bypass a `strcmp`-style check

```bash
# Hook the comparison: return 0 (equal) at the call site
gdb -batch -nx -ex "set pagination off" \
  -ex "file ./challenge" \
  -ex "b strcmp" \
  -ex "r AAAA" \
  -ex "p (char*)\$rdi" \
  -ex "p (char*)\$rsi" \
  -ex "set \$rax = 0" \
  -ex "c" \
  ./challenge
```

### Playbook C: Patch memory to skip a check

```bash
# Skip a "if (input[i] != expected[i]) return 0;" branch
# Find the JNE instruction, overwrite with NOPs or unconditional JMP
gdb -batch -nx -ex "set pagination off" \
  -ex "file ./challenge" \
  -ex "b *0x401345" \
  -ex "r" \
  -ex "x/4i \$pc" \
  -ex "set {char}(\$pc+2) = 0x90" \
  -ex "set {char}(\$pc+3) = 0x90" \
  -ex "c" \
  ./challenge
```

### Playbook D: Follow a fork/anti-debug

```bash
# ptrace anti-debug: usually PTRACE_TRACEME self-trace
# Common bypass: catch the syscall and return 0
gdb -batch -nx -ex "set pagination off" \
  -ex "file ./challenge" \
  -ex "catch syscall ptrace" \
  -ex "r" \
  -ex "return 0" \
  -ex "c" \
  ./challenge

# Or: detach-on-fork to follow the child
gdb -batch -nx -ex "set pagination off" \
  -ex "file ./challenge" \
  -ex "set follow-fork-mode child" \
  -ex "set detach-on-fork on" \
  -ex "r" \
  -ex "info registers" \
  ./challenge
```

### Playbook E: Dump everything at OEP after manual unpack

```bash
# When you've reached the OEP (e.g. after UPX unpack or manual tracing)
gdb -batch -nx -ex "set pagination off" \
  -ex "file ./challenge" \
  -ex "b *0x401000" \
  -ex "r" \
  -ex "info proc mappings" \
  -ex "dump binary memory /tmp/clean.bin 0x400000 0x410000" \
  -ex "info files" \
  ./challenge
# Now `file /tmp/clean.bin` shows the unpacked binary.
```

---

## 4. ELF-specific tips (via WSL)

- **PIE binaries**: addresses shown by `readelf` are offsets. Once loaded, add the runtime base. Use `info proc mappings` to get the actual base, then `b *BASE+OFFSET`.
- **Stripped symbols**: use `nm -D` (dynamic symbols) or rely on `info functions` (GDB can read DWARF even in stripped binaries if `-readnow` is used; else fall back to objdump).
- **GOT/PLT**: `info functions` lists PLT entries; `x/4i PLT_ENTRY` shows the resolver stub.
- **Stack canary**: presence of `%fs:0x28` access in a function is a canary check. Patch with `set $fs_base = 0` after `b __stack_chk_fail`.
- **libc 2.31+**: `set environment LD_PRELOAD=...` lets you hook without recompiling.

## 5. PE-specific tips (local GDB on Windows)

- Local GDB (`w64devkit`) doesn't have Python; batch mode only.
- `info functions` works for MSVC PDB symbols if loaded: `file foo.exe` triggers symbol auto-load.
- WOW64 binaries (32-bit on 64-bit) work; use `set architecture i386` if auto-detect fails.
- For anti-debug checks like `IsDebuggerPresent`, `b kernel32!IsDebuggerPresent` → modify return to 0 in the MI-style way (or patch the IAT).

## 6. Anti-anti-debug (GDB built-ins FIRST, LD_PRELOAD last)

遇到反调试时，按以下顺序尝试，**不要跳过前两步直接写 hook**：

### 第 0 步：确认问题（1 条 GDB 命令就能验证）

```bash
# fork 问题——只跑一次就知道
gdb -batch -nx -ex "set pagination off" \
    -ex "file ./challenge" \
    -ex "set follow-fork-mode parent" \
    -ex "r" ./challenge

# ptrace 反调试——catch 到了就是它
gdb -batch -nx -ex "set pagination off" \
    -ex "file ./challenge" \
    -ex "catch syscall ptrace" \
    -ex "r" ./challenge
```

如果上面跑通了，**不要写 hook**，直接用这个方案继续分析。

### 第 1 步：GDB 内置绕过（一行命令，不写代码）

| Trick | GDB 解决方案 |
|-------|-------------|
| `fork()` 后父进程无法 attach 子进程 | `set follow-fork-mode parent`（跟踪父进程）/ `set follow-fork-mode child`（跟踪子进程） |
| `ptrace(PTRACE_TRACEME, ...)` | `catch syscall ptrace` → 命中后 `return 0` |
| `IsDebuggerPresent` | `b IsDebuggerPresent` → `set $rax = 0` |
| `CheckRemoteDebuggerPresent` | 同上模式 |
| `NtQueryInformationProcess(ProcessDebugPort)` | `catch syscall` → nop 检查条件跳转 |
| Timing checks (`rdtsc` diff) | patch the JCC after the cmp |
| `INT 2D` / `INT 3` traps | `b *AFTER_TRAP` 跳过；或 `set $pc += 1` 绕过 |
| `IsProcessorFeaturePresent(PF_FASTFAIL)` / `__fastfail` | 同 INT 3 处理 |

### 第 2 步：GDB 命令行文件（超过 3 条命令时用）

```bash
# Write 工具创建 /tmp/anti.gdb
#   file ./challenge
#   set pagination off
#   set follow-fork-mode parent
#   catch syscall ptrace
#   r
#   info registers
#   quit

gdb -batch -nx -x /tmp/anti.gdb ./challenge
```

### 第 3 步：LD_PRELOAD / 自定义 hook（最后手段）

如果 GDB 内置方案全部失败（例如壳在内存中 patched GOT entry，或使用了 `PTRACE_PEEKUSER` 等非常规 ptrace 请求），才退到 LD_PRELOAD。**写 LD_PRELOAD 时也只解决眼前问题，不要预判"以防万一"的各种场景。**

## 7. Output hygiene

When pasting GDB output into the agent transcript:

```
══════════════════════════════════════════
GDB Session: <topic>
══════════════════════════════════════════
[gdb] file ./challenge
[gdb] b *0x401234
[gdb] r
Breakpoint 1, 0x0000000000401234 in main ()
[gdb] info registers
rax            0x0                 0
rbx            0x7fffffffe4a0      140737488348320
…
──────────────────────────────────────────
  → finding: rax=0, rdi=0x7ffff7fc4c80 → "AAAA"
  → next: x/64s $rsi to see expected string
```

Always end with a one-line "finding" + "next" pair. The agent uses those for the 阶段三 feedback loop.

## 8. Failure handling

| Symptom | Likely cause | Recovery |
|---------|--------------|----------|
| `Reading symbols from ...(no debugging symbols found)` | Stripped | use `objdump -d` + addr math; don't rely on symbol names |
| `Cannot access memory at address 0x...` | Wrong arch / PIE base | `info proc mappings` → recalc |
| `Program received signal SIGSEGV` | Wrong breakpoint, packed, or wrong base | `bt` then `info registers` |
| `Single stepping until exit from function ...` infinite | loop in `__libc_start_main` | `finish` or `until` |
| `Couldn't get registers: No such process` | inferior exited | check stdin/args, `r < input` |
| `Hang after -batch` | paging in TUI mode | always `-ex "set pagination off"` |

If after 3 distinct GDB attempts the analysis is still stuck, switch to **scripted analysis** (`objdump -d` + Python reimplementation of the algorithm) — that is explicitly allowed by the agent's 方向切换策略.

## 9. Quick-look: GDB frontends to consider (NOT required, just for awareness)

- **pwndbg / GEF / Peda** — Python-based enhancement, not in this GDB build. If installed in the user's WSL, can be loaded via `source /path/pwndbg/gdbinit.py` *after* `-nx` reset.
- **gdb-dashboard** — single-file TUI improvement, easier to install.
- **Voltron** — split-window UI.
- For this agent's purposes, **plain GDB in batch mode is enough**; reach for these only if the user asks.

## 10. Decision tree: do I actually need GDB right now?

```
[Stage-1: file/strings/readelf]
   ├── flag found? → DONE, exit
   └── no flag
[Stage-2: objdump -d / disassembly]
   ├── algorithm is trivial (XOR, compare, base64) → reimplement in Python, exit
   ├── algorithm is complex (crypto, virtualization) → continue
   └── can't make sense of static output
[Stage-3: GDB dynamic]
   ├── binary won't run (missing libc, segfault) → 静态+patch only, exit
   ├── binary has anti-debug → handle, then continue
   ├── set 1-3 breakpoints at interesting points → dump state
   └── confirm flag → DONE
[Stage-4: GDB patch]
   └── if breakpoint dump isn't enough, patch memory to skip checks
```

Use GDB only when static + Python reimpl is insufficient. This matches the agent's "先易后难" priority.

---

## 11. Session templates (copy-paste ready)

### T1: List functions + main disasm (always start here)

```bash
gdb -batch -nx -ex "set pagination off" \
    -ex "file ./CHALLENGE" \
    -ex "set width 0" \
    -ex "info functions" \
    -ex "disas main" \
    ./CHALLENGE
```

### T2: Run with input, dump state at suspicious address

```bash
gdb -batch -nx -ex "set pagination off" \
    -ex "file ./CHALLENGE" \
    -ex "b *0xADDR" \
    -ex "r INPUT" \
    -ex "info registers" \
    -ex "x/32gx \$rsp" \
    -ex "x/4i  \$pc" \
    ./CHALLENGE
```

### T3: WSL ELF (write GDB script file first)

```bash
# Step 1: Write /tmp/explore.gdb with:
#   file /mnt/d/ctf/CHALLENGE
#   set pagination off
#   info functions
#   disas main
#   quit

# Step 2: Execute
wsl gdb -batch -nx -x /mnt/d/ctf/tmp/explore.gdb
```

### T4: WSL gdb command file (for multi-step analysis)

```bash
# Step 1: Write /tmp/step.gdb
#   file /mnt/d/ctf/CHALLENGE
#   set pagination off
#   b *0x401234
#   r
#   info registers rax rdi rsi
#   x/32gx $rsp
#   quit

# Step 2: Execute
wsl gdb -batch -nx -x /mnt/d/ctf/tmp/step.gdb
```

### T5: Python standalone script (for complex logic)

```bash
# Step 1: Write /tmp/solve.py with the pwntools/GDB logic
# Step 2: Copy to WSL and run
wsl python3 /mnt/d/path/to/solve.py
```

---

## 12. Sanity commands (run on every GDB install to confirm capability)

```bash
# 1. starts
gdb --version
# 2. can run -batch
echo 'quit' | gdb -batch -nx
# 3. can attach to a self
gdb -batch -nx -ex "attach $$" -ex "detach" -ex "quit" 2>&1 | head
# 4. python (if present)
gdb -batch -nx -ex "python print('py ok')" 2>&1 | head
# 5. tui (interactive only)
gdb -tui -batch -nx -ex "help" 2>&1 | head -3
```

If any fails, the agent must fall back to static analysis or shell into WSL.

---

## 13. Remember

- **Always start with `gdb -batch -nx -ex "set pagination off"`.** These three options remove 95% of GDB foot-guns.
- **One GDB invocation per question.** Don't `run` twice without `file` reload; GDB remembers state.
- **Save transcripts to /tmp**, not the workspace. They're bulky and may contain the flag (sensitive).
- **Use WSL for ELF** unless you have a strong reason. mingw GDB is fine for PE.
- **Don't run untrusted binaries with the network up.** CTF binaries can be live malware; use a sandbox VM or `unshare -n` if available.
- **Write files, not heredocs.** Multi-line scripts → Write tool first, execute second.
- **GDB built-ins before LD_PRELOAD.** One `-ex` flag beats 30 lines of C hook.
- **3-command rule.** If 3 GDB invocations on the same direction produce nothing, switch direction. Don't escalate complexity.
