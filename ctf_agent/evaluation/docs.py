"""Documentation generator: auto-generate project docs."""

import os
from ..config import BASE_DIR


class DocGenerator:
    def generate_all(self):
        docs_dir = os.path.join(BASE_DIR, "docs")
        os.makedirs(docs_dir, exist_ok=True)

        design = os.path.join(docs_dir, "DESIGN.md")
        with open(design, "w", encoding="utf-8") as f:
            f.write("""# CTF Binary Analysis Agent - Design Document

## Architecture
```
ctf_agent/
├── database/     SQLite storage (schema.py + repository.py)
├── core/         Sample mgmt, basic/static/dynamic analysis
├── agent/        GLM-powered decision loop with 14 tools
├── evaluation/   Statistics and doc generation
└── main.py       CLI entry point
```

## Data Flow
1. User provides ELF binary -> SampleManager imports to database
2. AgentLoop queries GLM for next action -> executes tool -> records result
3. Cross-task knowledge reuse via intermediate_results table
4. Statistics computed from tasks/samples/answers tables

## Database Schema
7 tables: samples, tasks, tool_calls, intermediate_results, agent_memory, answers, statistics

## External Dependencies
- zhipuai: GLM API client
- pyelftools: ELF parsing (optional)
- angr: Symbolic execution (optional, Linux/WSL)
- z3-solver: Constraint solving (optional, Linux/WSL)
""")
        print(f"Generated: {design}")

        er_diagram = os.path.join(docs_dir, "ER_DIAGRAM.md")
        with open(er_diagram, "w", encoding="utf-8") as f:
            f.write("""# ER Diagram

```
samples ──1:N──> tasks ──1:N──> tool_calls
                        ├──1:N──> intermediate_results
                        ├──1:N──> agent_memory
                        └──1:N──> answers

statistics (aggregated from samples + tasks)
```
""")
        print(f"Generated: {er_diagram}")

        print(f"\nDocumentation generated in: {docs_dir}")
