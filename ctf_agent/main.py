"""Main entry point for CTF Binary Analysis Agent Platform."""

import argparse
import os

def cmd_analyze(args):
    from .core.sample_manager import SampleManager
    from .core.basic_analysis import BasicAnalyzer

    file_path = os.path.abspath(args.path)
    difficulty = args.difficulty or "unknown"
    print(f"\nStarting analysis of: {file_path}")
    print(f"Difficulty: {difficulty}")
    print("-" * 60)

    if args.no_agent:
        sm = SampleManager()
        ba = BasicAnalyzer()
        if not os.path.exists(file_path):
            print(f"Error: File not found: {file_path}")
            return
        print("\n[Step 1] Sample Import & Detection...")
        sample_id = sm.import_sample(file_path, difficulty)
        sample = sm.repo.get_sample(sample_id)
        print(f"  Architecture: {sample.get('arch')} {sample.get('bits')}-bit")
        print(f"  Endian:       {sample.get('endian')}")
        print(f"  SHA256:       {str(sample.get('sha256', 'N/A'))[:32]}...")

        print("\n[Step 2] Protection Mechanisms...")
        prot = ba._run_checksec(file_path)
        if isinstance(prot, dict):
            for k, v in prot.items():
                print(f"  {k}: {v}")

        print("\n[Step 3] Strings Extraction...")
        strings = ba._run_strings(file_path)
        if isinstance(strings, list):
            for s in strings[:15]:
                print(f"  {s[:100]}")

        print("\n[Step 4] ELF Structure...")
        arch_info = ba._run_readelf_header(file_path)
        if isinstance(arch_info, dict):
            print(f"  Machine:  {arch_info.get('machine', 'N/A')}")
            print(f"  Entry:    {arch_info.get('entry', 'N/A')}")
            print(f"  Type:     {arch_info.get('type', 'N/A')}")

        print(f"\n  Analysis Complete (offline mode)!")
        print(f"  Sample ID: {sample_id}")
        return

    from .agent.loop import AgentLoop
    agent = AgentLoop()
    result = agent.analyze_from_path(file_path, difficulty)
    print(f"\nAnalysis Complete!")
    print(f"  Status:    {result['status']}")
    print(f"  Rounds:    {result.get('rounds', 'N/A')}")
    print(f"  Time:      {result.get('elapsed_seconds', 0):.2f}s")
    if result.get("flag"):
        print(f"  Flag:      {result['flag']}")
    if result.get("error"):
        print(f"  Error:     {result['error']}")


def cmd_batch(args):
    from .core.sample_manager import SampleManager
    from .agent.loop import AgentLoop
    directory = os.path.abspath(args.directory)
    sm = SampleManager()
    agent = AgentLoop()
    print(f"\nBatch importing from: {directory}")
    results = []
    for f in os.listdir(directory):
        fp = os.path.join(directory, f)
        if os.path.isfile(fp):
            try:
                r = agent.analyze_from_path(fp, args.difficulty or "unknown")
                results.append(r)
                print(f"  {f}: {r['status']} ({r.get('flag', 'no flag')})")
            except Exception as e:
                print(f"  {f}: ERROR - {e}")
    ok = sum(1 for r in results if r.get("status") == "completed")
    print(f"\nBatch complete: {ok}/{len(results)} successful")


def cmd_evaluate(args):
    from .evaluation.stats import EvaluationStats
    es = EvaluationStats()
    es.evaluate(args.question_set)
    stats = es.repo.get_latest_statistics(args.question_set)
    if stats:
        print(f"\n=== Evaluation: {args.question_set} ===")
        print(f"  Total:   {stats['total_samples']}")
        print(f"  Success: {stats['successful_tasks']}/{stats['total_tasks']} ({stats['success_rate']:.1f}%)")


def cmd_resume(args):
    from .agent.loop import AgentLoop
    agent = AgentLoop()
    task = agent.repo.get_task(args.task_id)
    if not task:
        print(f"Task {args.task_id} not found")
        return
    sample = agent.repo.get_sample(task["sample_id"])
    result = agent.run(args.task_id, sample["file_path"])
    print(f"Resumed task {args.task_id}: {result['status']}")


def cmd_docs(args):
    from .evaluation.docs import DocGenerator
    DocGenerator().generate_all()


def cmd_stats(args):
    print("\n=== OVERALL STATISTICS ===")
    from .database.repository import Repository
    repo = Repository()
    total = repo.get_overall_stats()
    print(f"  Samples: {total['total_samples']}")
    print(f"  Tasks:   {total['total_tasks']}")
    print(f"  Success: {total['successful']}")
    with repo.db.connect() as conn:
        print("\nBy Difficulty:")
        for r in conn.execute("SELECT difficulty, COUNT(*) as c FROM samples GROUP BY difficulty"):
            s = conn.execute("SELECT COUNT(*) FROM tasks t JOIN samples s ON t.sample_id=s.id WHERE s.difficulty=? AND t.status='completed'", (r["difficulty"],)).fetchone()[0]
            print(f"  {r['difficulty']}: {s}/{r['c']}")
        print("\nBy Architecture:")
        for r in conn.execute("SELECT arch, COUNT(*) as c FROM samples GROUP BY arch"):
            s = conn.execute("SELECT COUNT(*) FROM tasks t JOIN samples s ON t.sample_id=s.id WHERE s.arch=? AND t.status='completed'", (r["arch"],)).fetchone()[0]
            print(f"  {r['arch']}: {s}/{r['c']}")


def main():
    parser = argparse.ArgumentParser(description="CTF Binary Analysis Agent Platform")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("analyze")
    p.add_argument("path")
    p.add_argument("--difficulty", choices=["easy","medium","hard","expert"])
    p.add_argument("--no-agent", action="store_true", help="Offline mode: skip AI, run basic analysis only")

    p = sub.add_parser("batch")
    p.add_argument("directory")
    p.add_argument("--difficulty", choices=["easy","medium","hard","expert"])

    p = sub.add_parser("evaluate")
    p.add_argument("question_set")

    sub.add_parser("docs")
    p = sub.add_parser("resume")
    p.add_argument("task_id", type=int)
    sub.add_parser("stats")

    args = parser.parse_args()
    cmds = {"analyze": cmd_analyze, "batch": cmd_batch, "evaluate": cmd_evaluate,
            "docs": cmd_docs, "resume": cmd_resume, "stats": cmd_stats}
    if args.command in cmds:
        cmds[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
