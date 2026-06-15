"""Agent tools: 14 registered tools for binary analysis."""

import json


class ToolRegistry:
    TOOLS = {
        "file_info": {
            "description": "Detect file type and architecture",
            "args": {},
        },
        "check_protections": {
            "description": "Check binary protections (NX, PIE, Canary, RELRO)",
            "args": {},
        },
        "read_strings": {
            "description": "Extract printable strings",
            "args": {"min_length": 4},
        },
        "readelf_headers": {
            "description": "Dump ELF headers",
            "args": {},
        },
        "find_functions": {
            "description": "List all functions in binary",
            "args": {},
        },
        "analyze_imports": {
            "description": "Analyze imported functions",
            "args": {},
        },
        "disassemble": {
            "description": "Disassemble binary section",
            "args": {"section": ".text"},
        },
        "analyze_call_graph": {
            "description": "Analyze function call relationships",
            "args": {},
        },
        "symbolic_execute": {
            "description": "Run symbolic execution via angr",
            "args": {},
        },
        "solve_constraints": {
            "description": "Solve constraints with z3",
            "args": {"constraints": ""},
        },
        "search_pattern": {
            "description": "Search for byte patterns",
            "args": {"pattern": ""},
        },
        "check_dependencies": {
            "description": "Check library dependencies",
            "args": {},
        },
        "trace_execution": {
            "description": "Trace execution with strace",
            "args": {},
        },
        "submit_flag": {
            "description": "Submit found flag",
            "args": {"flag": "", "explanation": ""},
        },
    }

    def get_tools_desc(self):
        lines = ["Available tools:"]
        for name, info in self.TOOLS.items():
            lines.append(f"  {name}: {info['description']}")
        return "\n".join(lines)

    def get_tool_names(self):
        return list(self.TOOLS.keys())
