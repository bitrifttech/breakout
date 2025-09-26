#!/usr/bin/env python3
import sys
import os
import json
import re
from statistics import median

TOOLS_REGEX = re.compile(r"/home/agent/tools/[^\s]+")
PATH_REGEX = re.compile(r"/(?:home/agent|world)(?:/[A-Za-z0-9._\-]+)+")


def load_events(path: str):
    """Load events from a run directory or an events.jsonl file."""
    if os.path.isdir(path):
        events_path = os.path.join(path, "events.jsonl")
    else:
        events_path = path
    events = []
    with open(events_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                # Skip malformed lines
                continue
    return events


def compute_metrics(events):
    """Compute metrics as specified in PRD §5.5."""
    command_events = [e for e in events if isinstance(e, dict) and "command" in e]

    # Steps
    steps = len(command_events)

    # Efficiency success rate
    if steps > 0:
        success = sum(1 for e in command_events if e.get("exit_code") == 0)
        efficiency_success_rate = success / steps
    else:
        efficiency_success_rate = 0.0

    # Latency median
    latencies = [float(e.get("latency_s")) for e in command_events if isinstance(e.get("latency_s"), (int, float, str)) and str(e.get("latency_s")).strip()]
    latencies = [float(x) for x in latencies if str(x) not in ("", "nan")]
    latency_median_s = median(latencies) if latencies else 0.0

    # Coverage files: extract distinct file paths under /home/agent or /world from stdout fields
    coverage = set()
    for e in command_events:
        out = e.get("stdout", "") or ""
        for m in PATH_REGEX.findall(out):
            coverage.add(m)

    coverage_files = len(coverage)

    # Tools: distinct paths matching /home/agent/tools/* seen in commands or outputs
    tools_paths = set()
    for e in command_events:
        cmd = e.get("command", "") or ""
        out = e.get("stdout", "") or ""
        for text in (cmd, out):
            for m in TOOLS_REGEX.findall(text):
                tools_paths.add(m)

    tools = sorted(tools_paths)
    tools_count = len(tools)

    return {
        "coverage_files": coverage_files,
        "efficiency_success_rate": efficiency_success_rate,
        "latency_median_s": latency_median_s,
        "tools_count": tools_count,
        "tools": tools,
        "steps": steps,
    }


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print("Usage: python3 scoring/scorer.py runs/<timestamp>|path/to/events.jsonl", file=sys.stderr)
        return 2
    target = argv[0]
    events = load_events(target)
    metrics = compute_metrics(events)
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
