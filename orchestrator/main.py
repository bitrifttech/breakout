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

# Paths
ORCH_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(ORCH_DIR, os.pardir))
PROMPT_PATH = os.path.join(ORCH_DIR, "prompt.txt")

def _load_dotenv_simple(path: str):
    """Minimal .env loader: KEY=VALUE pairs, ignores comments and blanks.
    Quotes around values are stripped. Does not support export or interpolation.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' not in line:
                    continue
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip()
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                os.environ.setdefault(key, val)
    except FileNotFoundError:
        pass

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
    # Auto-load .env from repo root
    _load_dotenv_simple(os.path.join(REPO_ROOT, ".env"))

    # Environment variables (resolved after .env load)
    llm_mode = os.getenv("LLM_MODE", "manual")
    local_container = os.getenv("AGENT_CONTAINER", "breakout_agent")
    print_thoughts = os.getenv("PRINT_THOUGHTS", "1").lower() not in ("0", "false", "no")

    driver = LLMDriver(mode=llm_mode)

    # Create run directory
    timestamp = datetime.now(timezone.utc).isoformat().replace(':', '-').replace('+00:00', 'Z')
    runs_root = os.getenv("RUNS_DIR", os.path.join(REPO_ROOT, "runs"))
    run_dir = os.path.join(runs_root, timestamp)
    os.makedirs(run_dir, exist_ok=True)

    # Set up run context file for LLM API mode to consume
    context_path = os.path.join(run_dir, "context.txt")
    os.environ.setdefault("RUN_CONTEXT", context_path)

    # Write meta.json
    with open(PROMPT_PATH, "r", encoding="utf-8") as pf:
        prompt_text = pf.read()
    meta = {
        "container": local_container,
        "mode": llm_mode,
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
    last_command = None
    repeat_count = 0
    max_repeat = int(os.getenv("MAX_REPEAT", "3"))
    while True:
        step += 1
        print(f"Step {step}")

        # Get pre-exec block
        pre_exec = driver.decide()
        if not pre_exec:
            break
        if print_thoughts and pre_exec.strip():
            print("=== Pre-exec (LLM) ===")
            print(pre_exec)

        # Extract command
        try:
            command = extract_command(pre_exec)
        except ValueError as e:
            print(f"Error: {e}")
            continue

        # Loop guard: stop if the same command repeats too many times
        if command == last_command:
            repeat_count += 1
        else:
            repeat_count = 0
        last_command = command
        if repeat_count >= max_repeat - 1:
            guard_event = {
                "t": time.time(),
                "guard": f"breaking due to repeated command '{command}' seen {repeat_count + 1} times"
            }
            events_file.write(json.dumps(guard_event) + "\n")
            events_file.flush()
            break

        # Execute command
        start_time = time.time()
        try:
            result = subprocess.run(
                ["docker", "exec", local_container, "/bin/bash", "-lc", command],
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

        # Append to run context (trim very long outputs)
        try:
            trimmed_stdout = (stdout or "")
            if len(trimmed_stdout) > 4000:
                trimmed_stdout = trimmed_stdout[:4000] + "\n... [truncated]"
            with open(context_path, "a", encoding="utf-8") as cf:
                cf.write("=== STEP PRE ===\n")
                cf.write(pre_exec + "\n\n")
                cf.write(f"<ExecutedCommand>\n{command}\n\n")
                cf.write(f"<ExitCode>\n{exit_code}\n\n")
                cf.write(f"<Stdout>\n{trimmed_stdout}\n\n")
        except Exception:
            pass

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
            # Append post context including <Next>
            try:
                with open(context_path, "a", encoding="utf-8") as cf:
                    cf.write("=== STEP POST ===\n")
                    cf.write(post_exec + "\n\n")
            except Exception:
                pass
            if print_thoughts and post_exec.strip():
                print("=== Post-exec (LLM) ===")
                print(post_exec)

    # Update meta.json
    meta["ended_at"] = datetime.now(timezone.utc).isoformat().replace(':', '-').replace('+00:00', 'Z')
    with open(f"{run_dir}/meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    events_file.close()
    print(f"Run complete. Logs in {run_dir}")

if __name__ == "__main__":
    main()
