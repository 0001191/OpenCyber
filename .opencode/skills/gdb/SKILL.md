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

### Avoid quoting hell

PowerShell mangles `$`, double quotes, and backticks when calling `wsl gdb -ex "..."`. Three escape patterns that always work:

```bash
# Pattern A: heredoc to wsl bash
wsl bash << 'GDB_SCRIPT'
cd /mnt/d/ctf
gdb -batch -nx \
  -ex "file ./challenge" \
  -ex "set pagination off" \
  -ex "info functions" \
  -ex "disas main" \
  ./challenge
GDB_SCRIPT

# Pattern B: GDB command file (-x)
cat > /tmp/cmds.gdb << 'EOF'
file /mnt/d/ctf/challenge
set pagination off
b *0x401234
r
info registers
x/8gx $rsp
quit
EOF
wsl gdb -batch -nx -x /tmp/cmds.gdb /mnt/d/ctf/challenge

# Pattern C: pwntools (when installed in WSL)
wsl python3 - << 'PY'
from pwn import *
context.log_level = 'info'
p = process('/mnt/d/ctf/challenge')
gdb.attach(p, '''
  b *0x401234
  c
''')
p.interactive()
PY
```

> **Always use `-batch -nx -ex "set pagination off"`** for non-interactive runs. `-batch` exits when commands finish; `-nx` skips `~/.gdbinit` (avoids the user's pwndbg/gef TUI hijacking the session); `set pagination off` prevents `--More--` blocks.

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

## 6. Anti-anti-debug (in priority order)

| Trick | Symptom | Fix |
|-------|---------|-----|
| `ptrace(PTRACE_TRACEME, ...)` | tracee attaches to parent, refuses to run under debugger | catch syscall ptrace; `return 0` |
| `IsDebuggerPresent` | returns 1 → program branches to dead code | b `IsDebuggerPresent`; `set $rax = 0` |
| `CheckRemoteDebuggerPresent` | same | same pattern |
| `NtQueryInformationProcess(ProcessDebugPort)` | same | catch syscall; nop the check |
| Timing checks (`rdtsc` diff) | time delta too small → exit | patch the JCC after the cmp |
| `INT 2D` / `INT 3` traps | debugger swallows, normal flow continues | `b *AFTER_TRAP`; or pass through with `set $pc += 1` |
| `IsProcessorFeaturePresent(PF_FASTFAIL)` / `__fastfail` | crashes on debug | same as INT 2D |

Always **try the cheapest countermeasure first** (single breakpoint + register poke). Only escalate to full LD_PRELOAD hooks if 3+ pokes fail.

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

### T3: WSL ELFGDB (when target is Linux ELF)

```bash
wsl bash << 'GDB'
gdb -batch -nx -ex "set pagination off" \
    -ex "file /mnt/d/ctf/CHALLENGE" \
    -ex "info functions" \
    -ex "disas main" \
    /mnt/d/ctf/CHALLENGE
GDB
```

### T4: WSL GDB + Python script (for complex checks)

```bash
wsl bash << 'GDB'
python3 - << 'PY'
import gdb  # works only if GDB built with python
gdb.execute("set pagination off")
gdb.execute("file /mnt/d/ctf/CHALLENGE")
gdb.execute("info functions")
PY
gdb -batch -nx /mnt/d/ctf/CHALLENGE
GDB
```

### T5: pwntools + GDB attach (interactive exploitation)

```bash
wsl python3 - << 'PY'
from pwn import *
context.binary = '/mnt/d/ctf/CHALLENGE'
p = process(context.binary.path)
# gdb.attach(p, 'b *main\nc')  # manual; only with display
print(p.recvline())
p.close()
PY
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
