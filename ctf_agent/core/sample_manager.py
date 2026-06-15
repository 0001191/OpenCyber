"""Sample manager: import, detect, and manage ELF binary samples."""

import os
import struct
import hashlib
from ..database.repository import Repository


class SampleManager:
    ARCH_MAP = {
        0x00: "unknown", 0x02: "sparc", 0x03: "x86",
        0x08: "mips", 0x14: "powerpc", 0x16: "s390",
        0x28: "arm", 0x2A: "superh", 0x32: "ia64",
        0x3E: "x86_64", 0xB7: "aarch64", 0xF3: "riscv",
    }

    def __init__(self, repo=None):
        self.repo = repo or Repository()

    @staticmethod
    def _detect_arch(file_path):
        try:
            with open(file_path, "rb") as f:
                magic = f.read(4)
                if magic != b"\x7fELF":
                    return (None, None, None)
                ei_class = f.read(1)[0]
                ei_data = f.read(1)[0]
                f.read(12)
                e_machine = int.from_bytes(f.read(2), "little" if ei_data == 1 else "big")
                arch = SampleManager.ARCH_MAP.get(e_machine, f"unknown_0x{e_machine:04x}")
                bits = 64 if ei_class == 2 else 32
                endian = "little" if ei_data == 1 else "big"
                return (arch, bits, endian)
        except Exception:
            return (None, None, None)

    def import_sample(self, file_path, difficulty="unknown"):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Sample not found: {file_path}")
        name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        sha = None
        try:
            sha = hashlib.sha256(open(file_path, "rb").read()).hexdigest()
        except Exception:
            pass

        arch, bits, endian = self._detect_arch(file_path)
        return self.repo.create_sample(
            name, file_path, file_size=file_size, sha256=sha,
            arch=arch, bits=bits, endian=endian, difficulty=difficulty
        )
