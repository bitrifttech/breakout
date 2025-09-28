#!/usr/bin/env python3
import os
import sys
import json
import time
import subprocess
import re
from datetime import datetime, timezone
from typing import Optional, Tuple
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

def _load_dotenv_simple(path: str) -> None:
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

def extract_command(pre_exec_block: str) -> str:
    """Extract the shell command from a pre-exec block.

    Robust against common LLM formatting variations:
    - Exact tag on its own line: "<Command>" then next non-empty line is the command
    - Markdown-bold tag: "**<Command>**" (or similar) on its own line
    - Inline notation: "Command: echo hi" or "<Command>: echo hi" or "(Command: echo hi)"
    - Backticked inline command: "Command: `echo hi`"
    - Backticked next-line command after tag

    Behavior for the canonical format is unchanged.
    """
    import re

    text = pre_exec_block or ""
    # Remove any <think> ... </think> sections to avoid capturing narrative mentions
    text = re.sub(r"(?is)<\s*think\s*>.*?</\s*think\s*>", " ", text)

    # 2) Otherwise, find a "<Command>" tag line (possibly with markdown adornments)
    lines = text.splitlines()
    in_command = False
    in_fence = False
    for raw in lines:
        line = raw.strip()
        if not in_command:
            # Normalize common adornments before checking for <Command>
            # Remove leading/trailing markdown chars, quotes, parens, blockquote markers
            md_stripped = re.sub(r"^[\*`_>\s\"'()]+|[\*`_\s\"']+$", "", line)
            # Require the tag to be at the start (after adornments) to avoid narrative mentions
            if re.match(r"(?i)^<\s*Command\s*>", md_stripped):
                # Support same-line command after the tag, e.g. "<Command> echo hi" or "<Command>echo hi</Command>"
                msl = re.search(r"(?i)<\s*Command\s*>\s*`?([^`\n<]+?)`?\s*(?:</\s*Command\s*>)?", line)
                if msl and msl.group(1).strip():
                    candidate = msl.group(1).strip()
                    candidate = candidate.strip('"').strip("'")
                    if candidate:
                        return candidate
                in_command = True
                continue
        else:
            # We are after the command tag
            if not line:
                continue
            # Handle fenced code blocks
            if line.startswith("```"):
                if not in_fence:
                    in_fence = True
                    continue
                else:
                    # closing fence without seeing content; continue looking
                    in_fence = False
                    continue
            if in_fence:
                candidate = line
            else:
                # If next tag appears, stop looking
                md_stripped = re.sub(r"^[\*`_>\s\"'()]+|[\*`_\s\"']+$", "", line)
                if md_stripped.startswith("<"):
                    break
                candidate = line

            # Remove surrounding single backticks if present
            if candidate.startswith("`") and candidate.endswith("`"):
                candidate = candidate[1:-1].strip()
            candidate = candidate.strip('"').strip("'")
            if candidate:
                return candidate

    # If a <Command> tag exists but we failed to extract, do not fall back to inline; surface an error
    if re.search(r"(?i)<\s*Command\s*>", text):
        raise ValueError("No <Command> found in pre-exec block")

    # 3) As a last resort, try to capture inline "Command: ..." on a single line
    inline_pattern = re.compile(
        r"(?mi)^[\s\*\(_\[`>]*<?\s*Command\s*>?\s*[:\-]\s*`?([^`\n]+?)`?\)?\s*$"
    )
    m = inline_pattern.search(text)
    if m:
        cmd = m.group(1).strip()
        cmd = cmd.strip('"').strip("'")
        if cmd:
            return cmd

    raise ValueError("No Command found in pre-exec block")


# ---------------------------
# Helper functions (extracted)
# ---------------------------

def load_env(repo_root: str) -> None:
    """Load environment variables from .env under the repository root."""
    _load_dotenv_simple(os.path.join(repo_root, ".env"))


def read_prompt_text(path: str) -> str:
    """Read and return the full prompt text used to guide the LLM."""
    with open(path, "r", encoding="utf-8") as pf:
        return pf.read()


def read_runtime_config() -> Tuple[str, str, str, int, bool, int]:
    """Return tuple of runtime configuration values.

    Returns:
        (llm_mode, container_name, runs_root, max_repeat, print_thoughts, command_timeout_s)
    """
    llm_mode = os.getenv("LLM_MODE", "manual")
    container_name = os.getenv("AGENT_CONTAINER", "breakout_agent")
    runs_root = os.getenv("RUNS_DIR", os.path.join(REPO_ROOT, "runs"))
    max_repeat = int(os.getenv("MAX_REPEAT", "3"))
    print_thoughts = os.getenv("PRINT_THOUGHTS", "1").lower() not in ("0", "false", "no")
    command_timeout_s = int(os.getenv("COMMAND_TIMEOUT", "60"))
    return llm_mode, container_name, runs_root, max_repeat, print_thoughts, command_timeout_s


def make_run_dir(runs_root: str) -> Tuple[str, str]:
    """Create a timestamped run directory and return (run_dir, run_id)."""
    run_id = datetime.now(timezone.utc).isoformat().replace(':', '-').replace('+00:00', 'Z')
    run_dir = os.path.join(runs_root, run_id)
    os.makedirs(run_dir, exist_ok=True)
    return run_dir, run_id


def write_meta_started(run_dir: str, container_name: str, llm_mode: str, prompt_text: str) -> dict:
    """Write initial meta.json and return the meta object to be updated at the end."""
    meta = {
        "container": container_name,
        "mode": llm_mode,
        "prompt": prompt_text,
        "started_at": os.path.basename(run_dir),
        "ended_at": None,
    }
    with open(f"{run_dir}/meta.json", "w") as f:
        json.dump(meta, f, indent=2)
    return meta


def write_meta_finished(run_dir: str, meta: dict) -> None:
    """Finalize and rewrite meta.json with an ended_at timestamp."""
    meta["ended_at"] = datetime.now(timezone.utc).isoformat().replace(':', '-').replace('+00:00', 'Z')
    with open(f"{run_dir}/meta.json", "w") as f:
        json.dump(meta, f, indent=2)


def open_events_writer(run_dir: str):
    """Open the events.jsonl file in append mode and return the file handle."""
    events_path = os.path.join(run_dir, "events.jsonl")
    return open(events_path, "a")


def print_thoughts_block(kind: str, text: str, enabled: bool) -> None:
    """Optionally print a labeled block of LLM thoughts to the console."""
    if enabled and text.strip():
        print(f"=== {kind} ===")
        print(text)


def log_command_event(events_file, pre_exec: str, command: str, stdout: str, stderr: str, exit_code: int, latency_s: float) -> None:
    event = {
        "t": time.time(),
        "plan": pre_exec,
        "command": command,
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "latency_s": latency_s,
    }
    events_file.write(json.dumps(event) + "\n")
    events_file.flush()


def log_post_event(events_file, post_exec: str) -> None:
    post_event = {
        "t": time.time(),
        "post": post_exec,
    }
    events_file.write(json.dumps(post_event) + "\n")
    events_file.flush()


def log_guard_event(events_file, command: str, repeated: int) -> None:
    guard_event = {
        "t": time.time(),
        "guard": f"breaking due to repeated command '{command}' seen {repeated} times",
    }
    events_file.write(json.dumps(guard_event) + "\n")
    events_file.flush()


def append_pre_context(context_path: str, pre_exec: str, command: str, exit_code: int, stdout: str) -> None:
    """Append pre-exec context including executed command and trimmed stdout."""
    trimmed_stdout = stdout or ""
    if len(trimmed_stdout) > 4000:
        trimmed_stdout = trimmed_stdout[:4000] + "\n... [truncated]"
    with open(context_path, "a", encoding="utf-8") as cf:
        cf.write("=== STEP PRE ===\n")
        cf.write(pre_exec + "\n\n")
        cf.write(f"<ExecutedCommand>\n{command}\n\n")
        cf.write(f"<ExitCode>\n{exit_code}\n\n")
        cf.write(f"<Stdout>\n{trimmed_stdout}\n\n")


def append_post_context(context_path: str, post_exec: str) -> None:
    with open(context_path, "a", encoding="utf-8") as cf:
        cf.write("=== STEP POST ===\n")
        cf.write(post_exec + "\n\n")


def execute_in_container(container_name: str, command: str, timeout_s: int) -> Tuple[str, str, int, float]:
    """Execute a shell command inside the Docker container and return (stdout, stderr, exit_code, latency_s)."""
    start_time = time.time()
    try:
        result = subprocess.run(
            ["docker", "exec", container_name, "/bin/bash", "-lc", command],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        stdout = ""
        stderr = "Command timed out"
        exit_code = -1
    latency_s = time.time() - start_time
    return stdout, stderr, exit_code, latency_s


def update_repeat_guard(last_command: Optional[str], current_command: str, repeat_count: int, max_repeat: int) -> Tuple[int, bool]:
    """Update repetition counters and decide whether to break due to repeats."""
    if current_command == last_command:
        repeat_count += 1
    else:
        repeat_count = 0
    should_break = repeat_count >= max_repeat - 1
    return repeat_count, should_break

def main() -> None:
    # 1) Load environment and runtime config
    load_env(REPO_ROOT)
    llm_mode, container_name, runs_root, max_repeat, print_thoughts, command_timeout_s = read_runtime_config()

    # 2) Initialize driver, run directory, meta, events, and context
    driver = LLMDriver(mode=llm_mode)
    prompt_text = read_prompt_text(PROMPT_PATH)
    run_dir, _run_id = make_run_dir(runs_root)
    context_path = os.path.join(run_dir, "context.txt")
    os.environ.setdefault("RUN_CONTEXT", context_path)
    meta = write_meta_started(run_dir, container_name, llm_mode, prompt_text)
    events_file = open_events_writer(run_dir)

    # 3) Main loop
    step = 0
    last_command: Optional[str] = None
    repeat_count = 0
    try:
        while True:
            step += 1
            print(f"Step {step}")

            # Decide pre-exec
            pre_exec = driver.decide()
            if not pre_exec:
                break
            print_thoughts_block("Pre-exec (LLM)", pre_exec, print_thoughts)

            # Extract and guard repetition
            try:
                command = extract_command(pre_exec)
            except ValueError as e:
                print(f"Error: {e}")
                continue

            repeat_count, should_break = update_repeat_guard(last_command, command, repeat_count, max_repeat)
            last_command = command
            if should_break:
                log_guard_event(events_file, command, repeat_count + 1)
                break

            # Execute inside container
            print(f"$ {command}")
            stdout, stderr, exit_code, latency_s = execute_in_container(container_name, command, command_timeout_s)

            # Log command event and update context
            log_command_event(events_file, pre_exec, command, stdout, stderr, exit_code, latency_s)
            try:
                append_pre_context(context_path, pre_exec, command, exit_code, stdout)
            except Exception:
                pass

            # Print command result to console
            print(f"Exit code: {exit_code}")
            print(f"Stdout: {stdout}")
            print(f"Stderr: {stderr}")

            # Post-decision
            post_exec = driver.post_decide()
            if post_exec:
                log_post_event(events_file, post_exec)
                try:
                    append_post_context(context_path, post_exec)
                except Exception:
                    pass
                print_thoughts_block("Post-exec (LLM)", post_exec, print_thoughts)
    finally:
        # 4) Finalize meta and close files
        write_meta_finished(run_dir, meta)
        events_file.close()
        print(f"Run complete. Logs in {run_dir}")

if __name__ == "__main__":
    main()
