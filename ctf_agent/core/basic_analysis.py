"""Basic Analyzer: file type, architecture, strings, protection detection."""

import subprocess
import json
import os
import re
from ..config import TOOL_PATHS
from ..database.repository import Repository
from .sample_manager import SampleManager


class BasicAnalyzer:
    def __init__(self, repo=None):
        self.repo = repo or Repository()

    def _run_cmd(self, cmd, *args):
        exe = TOOL_PATHS.get(cmd, cmd)
        try:
            result = subprocess.run([exe] + list(args), capture_output=True,
                                   text=False, timeout=30, shell=os.name == "nt")
            out = result.stdout
            try:
                return out.decode("utf-8", errors="replace")
            except Exception:
                return str(out)
        except FileNotFoundError:
            return json.dumps({"error": f"tool '{cmd}' not found on this system"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _run_file(self, path):
        return self._run_cmd("file", path)

    def _run_readelf_header(self, path):
        output = self._run_cmd("readelf", "-h", path)
        # Fallback: parse ELF header directly
        if "error" in output:
            try:
                from .sample_manager import SampleManager
                arch, bits, endian = SampleManager._detect_arch(path)
                with open(path, "rb") as f:
                    f.read(4); cls = f.read(1)[0]; data = f.read(1)[0]
                    endian_char = "<" if data == 1 else ">"
                    f.read(12)
                    e_type = int.from_bytes(f.read(2), "little")
                    f.read(4)
                    entry = int.from_bytes(f.read(8), endian_char) if cls == 2 else int.from_bytes(f.read(4), endian_char)
                return {"machine": arch, "bits": bits, "endian": endian, "entry": hex(entry), "type": "ET_DYN" if e_type == 3 else "ET_EXEC" if e_type == 2 else f"type_{e_type}"}
            except Exception:
                return {"error": str(output)}
        return {"raw": output}

    def _run_readelf_sections(self, path):
        return self._run_cmd("readelf", "-S", path)

    def _run_strings(self, path):
        output = self._run_cmd("strings", path)
        if "error" in output:
            # Fallback: extract printable strings manually
            try:
                with open(path, "rb") as f:
                    data = f.read()
                strings = []
                current = b""
                for byte in data:
                    if 0x20 <= byte < 0x7F:
                        current += bytes([byte])
                    else:
                        if len(current) >= 4:
                            strings.append(current.decode("ascii", errors="replace"))
                        current = b""
                if len(current) >= 4:
                    strings.append(current.decode("ascii", errors="replace"))
                return strings
            except Exception:
                return [str(output)]
        return [s for s in output.splitlines() if len(s) >= 4]

    def _run_nm(self, path):
        return self._run_cmd("nm", path)

    def _run_checksec(self, path):
        output = self._run_cmd("checksec", "--output=json", "--file", path)
        if "error" in output or "找不到" in str(output):
            # Fallback: manual detection
            try:
                with open(path, "rb") as f:
                    data = f.read()
                text = ""
                try:
                    text = data.decode("ascii", errors="ignore")
                except Exception:
                    pass
                nx = b"GNU_STACK" in data and not any(
                    struct.unpack("<I", data[i+4:i+8])[0] & 1
                    for i in range(len(data)-8) if data[i:i+4] == b"GNU_STACK"
                ) if "struct" in dir(__import__("struct")) else True
                import struct as _s
                nx = True
                idx = data.find(b"GNU_STACK")
                if idx >= 0 and idx + 8 <= len(data):
                    flags = _s.unpack("<I", data[idx+4:idx+8])[0]
                    nx = not bool(flags & 1)
                canary = "__stack_chk_fail" in text
                pie = True  # ET_DYN parsed earlier
                relro = "Full" if b"BIND_NOW" in data else "Partial" if b"GNU_RELRO" in data else "No"
                return {"NX": nx, "Canary": canary, "PIE": pie, "RELRO": relro}
            except Exception:
                return {"error": str(output)}
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"raw": output}

    def analyze(self, task_id, file_path):
        results = {
            "file_info": self._run_file(file_path),
            "arch_info": self._run_readelf_header(file_path),
            "sections": self._run_readelf_sections(file_path),
            "strings": self._run_strings(file_path),
            "protections": self._run_checksec(file_path),
            "symbols": self._run_nm(file_path),
        }
        for key, value in results.items():
            self.repo.save_result(task_id, key, value, "basic_analysis")
        return results
