#!/usr/bin/env python3
import os
import sys
import json
import time
import subprocess
import re
from datetime import datetime, timezone
# Support both running as a script and as a module
if __package__:
    from .llm_driver import LLMDriver
else:
    sys.path.append(os.path.dirname(__file__))
    from llm_driver import LLMDriver

# Environment variables
AGENT_CONTAINER = os.getenv("AGENT_CONTAINER", "breakout_agent")
LLM_MODE = os.getenv("LLM_MODE", "manual")
# Paths
ORCH_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(ORCH_DIR, os.pardir))
PROMPT_PATH = os.path.join(ORCH_DIR, "prompt.txt")

def extract_command(pre_exec_block):
    """Extract the command from a pre-exec block.

    PRD format does not use closing tags. We treat the line following the
    '<Command>' tag as the exact single-line command. We skip blank lines
    and stop when we hit the next tag line starting with '<'.
    """
    lines = pre_exec_block.splitlines()
    in_command = False
    for i, raw in enumerate(lines):
        line = raw.strip()
        if not in_command:
            if line == "<Command>":
                in_command = True
        else:
            # We are after <Command>
            if not line:
                # skip empty lines
                continue
            if line.startswith("<"):
                # Hit next tag without seeing a command
                break
            # First non-empty, non-tag line is the command
            return line
    raise ValueError("No <Command> found in pre-exec block")

def main():
    driver = LLMDriver(mode=LLM_MODE)

    # Create run directory
    timestamp = datetime.now(timezone.utc).isoformat().replace(':', '-').replace('+00:00', 'Z')
    runs_root = os.getenv("RUNS_DIR", os.path.join(REPO_ROOT, "runs"))
    run_dir = os.path.join(runs_root, timestamp)
    os.makedirs(run_dir, exist_ok=True)

    # Write meta.json
    with open(PROMPT_PATH, "r", encoding="utf-8") as pf:
        prompt_text = pf.read()
    meta = {
        "container": AGENT_CONTAINER,
        "mode": LLM_MODE,
        "prompt": prompt_text,
        "started_at": timestamp,
        "ended_at": None
    }
    with open(f"{run_dir}/meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    # Open events.jsonl
    events_path = os.path.join(run_dir, "events.jsonl")
    events_file = open(events_path, "a")

    step = 0
    while True:
        step += 1
        print(f"Step {step}")

        # Get pre-exec block
        pre_exec = driver.decide()
        if not pre_exec:
            break

        # Extract command
        try:
            command = extract_command(pre_exec)
        except ValueError as e:
            print(f"Error: {e}")
            continue

        # Execute command
        start_time = time.time()
        try:
            result = subprocess.run(
                ["docker", "exec", AGENT_CONTAINER, "/bin/bash", "-lc", command],
                capture_output=True, text=True, timeout=60
            )
            stdout = result.stdout
            stderr = result.stderr
            exit_code = result.returncode
        except subprocess.TimeoutExpired:
            stdout = ""
            stderr = "Command timed out"
            exit_code = -1
        latency_s = time.time() - start_time

        # Log command event
        event = {
            "t": time.time(),
            "plan": pre_exec,
            "command": command,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "latency_s": latency_s
        }
        events_file.write(json.dumps(event) + "\n")
        events_file.flush()

        # Print result
        print(f"Exit code: {exit_code}")
        print(f"Stdout: {stdout}")
        print(f"Stderr: {stderr}")

        # Get post-exec block
        post_exec = driver.post_decide()
        if post_exec:
            # Log post-exec event
            post_event = {
                "t": time.time(),
                "post": post_exec
            }
            events_file.write(json.dumps(post_event) + "\n")
            events_file.flush()

    # Update meta.json
    meta["ended_at"] = datetime.now(timezone.utc).isoformat().replace(':', '-').replace('+00:00', 'Z')
    with open(f"{run_dir}/meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    events_file.close()
    print(f"Run complete. Logs in {run_dir}")

if __name__ == "__main__":
    main()
