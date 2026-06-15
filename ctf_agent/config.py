"""Global configuration for CTF Binary Analysis Agent Platform."""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "ctf_agent.db")
SAMPLES_DIR = os.path.join(BASE_DIR, "data", "samples")
RESULTS_DIR = os.path.join(BASE_DIR, "data", "results")
LOGS_DIR = os.path.join(BASE_DIR, "data", "logs")

for d in [os.path.dirname(DB_PATH), SAMPLES_DIR, RESULTS_DIR, LOGS_DIR]:
    os.makedirs(d, exist_ok=True)

GLM_API_KEY = os.environ.get("ZHIPUAI_API_KEY", "")
GLM_MODEL = os.environ.get("GLM_MODEL", "glm-4-flash")

MAX_ANALYSIS_ROUNDS = 20
AGENT_TIMEOUT_SECONDS = 600

TOOL_PATHS = {
    "file": "file", "readelf": "readelf", "objdump": "objdump",
    "strings": "strings", "checksec": "checksec", "gdb": "gdb",
    "nm": "nm", "ldd": "ldd", "strace": "strace", "ltrace": "ltrace",
}
