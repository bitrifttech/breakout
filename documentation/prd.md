# PRD: AI Discovery — Internet-Enabled MVP (Container-Only Boundary)

## 0) Executive Summary

Build a **minimal but working** experiment where an AI agent (or a human in manual mode) operates **only via a Unix shell inside a Docker container** and attempts to **discover as much meaningful information as possible** about its environment and the public web. The system must:

* Provide a **clear action protocol** (Intent/Command/Expected/OnError → Observation/Inference/Next).
* Supply a **prompt** and **orchestrator** that execute shell commands inside the container and log everything.
* Persist standardized **artifacts**: `MAP.md`, `LOG.md`, `TOOLS.md`, `PLAN.md`.
* Allow full **internet access** from inside the container.
* **No safety controls** beyond the Docker container boundary (explicitly out of scope for this MVP).
* Provide **monitoring & scoring** from run logs (JSONL) to compare runs and models.

The output should be a self-contained repository with Docker/compose, orchestrator code, starter `/world` data, a prompt, and a scorer.

---

## 1) Goals & Non-Goals

### Goals

1. Deliver a runnable repo that:

   * Boots a Debian-based container for the agent with bash + coreutils + Python + curl/wget + git.
   * Mounts a read-only `/world` dataset and a writable home volume.
   * Runs an orchestrator that:

     * Accepts a block in the **Action Protocol** format,
     * Executes the `<Command>` in the container,
     * Returns stdout/stderr/exit code and latency,
     * Captures logs in `runs/<timestamp>/events.jsonl`.
   * Provides a **prompt** instructing the agent to produce artifacts (`MAP.md`, `LOG.md`, `TOOLS.md`, `PLAN.md`) and to build reusable tools under `/home/agent/tools/`.
   * Includes a basic **scorer** that reads logs and outputs coverage/efficiency/latency/tooling metrics.

2. Keep **internet enabled** in the container (no proxy, no allowlists/denylists).

3. Keep **monitoring & scoring** in place for repeatability and comparison.

### Non-Goals (Out of Scope for MVP)

* Any egress proxying, allow/deny lists, robots enforcement, prompt-injection guards, WARC capture, rate limits, key vaults, or other safety controls.
* Browser automation (Playwright) and crawler services.
* Multi-agent orchestration.
* Authentication or secrets handling.

---

## 2) Success Criteria (Acceptance)

* `docker compose up -d --build` starts the agent container with internet access.
* `python3 orchestrator/main.py` runs the loop in **manual mode**.
* A sample run produces:

  * `runs/<timestamp>/events.jsonl` with ≥3 command entries,
  * `MAP.md`, `LOG.md`, `TOOLS.md`, `PLAN.md` created in `/home/agent` inside the container,
  * At least one script created under `/home/agent/tools/` and reused ≥2× (documented in `TOOLS.md`).
* `python3 scoring/scorer.py runs/<timestamp>/` prints a JSON report containing:

  * `coverage_files`, `efficiency_success_rate`, `latency_median_s`, `tools_count`, `steps`.

---

## 3) Users & Scenarios

* **Experimenter / Researcher (you)**: runs the orchestrator, pastes action blocks (or swaps in an LLM), inspects artifacts/logs, and compares runs via the scorer.
* **LLM Agent (future)**: will replace manual mode, emitting the Action Protocol blocks and reading command results to continue.

**Core Scenario**

1. Start container. 2) Start orchestrator. 3) Paste an Action Protocol block (list directories). 4) Orchestrator executes in container and returns results. 5) Paste Observation/Inference/Next. 6) Repeat. 7) Review artifacts and run score.

---

## 4) System Overview

```
Host
├─ docker-compose: launches single "agent" service (Debian) with internet access.
├─ /world (read-only) mounted into the container at /world.
├─ orchestrator/ (Python) runs on host; executes commands inside container via docker exec.
│  ├─ prompt.txt
│  ├─ main.py        (loop + logging)
│  └─ llm_driver.py  (manual mode; pluggable LLM later)
└─ scoring/scorer.py (reads runs/<ts>/events.jsonl and outputs metrics JSON)
```

**Boundary:** Only Docker containerization. No other safety measures.

---

## 5) Functional Requirements

### 5.1 Repository Layout

```
ai-discovery/
  docker-compose.yml
  sandbox/
    Dockerfile.agent
  orchestrator/
    prompt.txt
    main.py
    llm_driver.py
  scoring/
    scorer.py
  world/
    README.md
    data.csv
    puzzles/hidden.txt
  runs/              # generated; artifacts/logs per run
  README.md
```

### 5.2 Docker Compose

* Service `agent`:

  * Base: `debian:stable-slim`
  * Install: `bash`, coreutils, findutils, procps, `grep`, `sed`, `gawk`, `curl`, `wget`, `ca-certificates`, `python3`, `python3-venv`, `python3-pip`, `git`.
  * User: non-root `agent`, `WORKDIR=/home/agent`.
  * Mounts:

    * Named volume `agent_home` → `/home/agent` (rw).
    * `./world` → `/world` (ro).
  * Internet **allowed** (no extra controls).
  * `tty: true`, `stdin_open: true`.
  * Entry: `/bin/bash`.

### 5.3 Orchestrator

#### 5.3.1 Prompt (orchestrator/prompt.txt)

* States the **purpose** (discovery), **interface** (shell), **internet allowed**, **artifacts** to maintain, and **Rules**:

  * Explain intent before each command.
  * Use hypothesis + tiny experiments on dead ends.
  * Prefer reusable tools under `/home/agent/tools/` and document them.
* Defines the **Action Protocol** structure (see 6.1).

#### 5.3.2 main.py (Loop)

* Inputs:

  * `AGENT_CONTAINER` env (default `ai_discovery_agent`).
  * `LLM_MODE` env (default `manual`).
* Launch:

  * On start, create `runs/<UTC_ISO_TIMESTAMP>/`.
  * Write `meta.json` with prompt text and metadata.
* Cycle:

  1. Request the “pre-exec” Action Protocol block (from `LLMDriver.decide()`).
  2. Parse `<Command>` (exact single-line command).
  3. `docker exec <container> /bin/bash -lc "<Command>"`.
  4. Record `stdout`, `stderr`, `exit_code`, `latency_s` as JSONL event.
  5. Prompt for “post-exec” block (Observation/Inference/Next), store as JSONL.
  6. Increment step counter; loop until empty input or SIGINT.
* Outputs:

  * `runs/<ts>/events.jsonl` (one JSON per line; see schema below).
  * `runs/<ts>/meta.json` with run metadata.

#### 5.3.3 llm_driver.py

* `mode="manual"` default: stdin for pre-exec block, then stdin for post-exec block.
* Provide stub `LLMDriver.decide()` to be swapped with a real model later.

### 5.4 Logging Schema

**events.jsonl** (each line is a JSON object; union of two types)

* **Command Execution Event**

```json
{
  "t": 1730000000.1234,               // float, epoch seconds
  "plan": "<full pre-exec block text>",
  "command": "ls -la / /world /home/agent",
  "stdout": "…",
  "stderr": "",
  "exit_code": 0,
  "latency_s": 0.2311
}
```

* **Post-Exec Note Event**

```json
{
  "t": 1730000001.5678,
  "post": "<Observation>\n…\n<Inference>\n…\n<Next>\n…"
}
```

**meta.json**

```json
{
  "container": "ai_discovery_agent",
  "mode": "manual",
  "prompt": "<contents of prompt.txt>",
  "started_at": "2025-09-25T00:00:00Z",
  "ended_at": "2025-09-25T00:12:34Z"
}
```

### 5.5 Scoring

`python3 scoring/scorer.py runs/<ts>/` prints JSON like:

```json
{
  "coverage_files": 28,
  "efficiency_success_rate": 0.875,
  "latency_median_s": 0.1123,
  "tools_count": 2,
  "tools": ["/home/agent/tools/parse_csv.sh", "/home/agent/tools/find_text.py"],
  "steps": 8
}
```

**Heuristics (initial):**

* `coverage_files`: count distinct file paths (regex over `stdout`) under `/home/agent` or `/world`.
* `efficiency_success_rate`: ratio of events with `exit_code==0`.
* `latency_median_s`: median `latency_s` across command events.
* `tools_count`: number of distinct paths matching `/home/agent/tools/*` seen in commands or outputs.
* `steps`: number of command events.

> The scorer is intentionally simple; it will evolve.

### 5.6 `/world` Seed

Files (read-only in container):

* `/world/README.md` — describes purpose and hints at hidden content.
* `/world/data.csv` — small CSV (id,value,tag).
* `/world/puzzles/hidden.txt` — “CLUE: Try building a reusable script to parse CSV files faster.”

### 5.7 Artifacts the Agent Must Maintain (inside container)

* `/home/agent/MAP.md`: structured list of discovered entities (filesystem, tools, datasets, commands, external sites) + short interpretations.
* `/home/agent/LOG.md`: chronological “lab notebook” (intent → command → observation → inference), append-only.
* `/home/agent/TOOLS.md`: each tool’s purpose + usage + example invocation; updated when tools evolve.
* `/home/agent/PLAN.md`: current goals, hypotheses, next steps, updated frequently.

---

## 6) Agent Protocols & Content

### 6.1 Action Protocol (required format)

**Pre-exec block** (must include exactly one command):

```
<Intent>
(One concise sentence of what you’re trying to learn or improve.)

<Command>
(ONE shell command exactly as you would type it)

<Expected>
(What you expect to see and how it will inform next steps.)

<OnError>
(A short fallback plan if the command fails.)
```

**Post-exec block** (after the result is returned):

```
<Observation>
(Key details you saw.)

<Inference>
(What changed in your understanding? Any new entities/relationships?)

<Next>
(Next action or micro-experiment, or update to PLAN.md.)
```

### 6.2 Core Prompt Requirements (summary)

* Purpose: discovery of environment and broader world.
* Interface: shell only; **internet allowed**.
* Build & reuse tools under `/home/agent/tools/`; document in `TOOLS.md`.
* Maintain `MAP.md`, `LOG.md`, `PLAN.md`; update frequently.
* Explain intent before commands; when blocked, hypothesize and run tiny experiments.

---

## 7) Implementation Tasks (for the agentic builder)

1. **Repo Bootstrap**

   * Create directories/files as listed in §5.1.
   * Add `README.md` with quick start.

2. **Docker Setup**

   * Implement `sandbox/Dockerfile.agent` per §5.2.
   * Implement `docker-compose.yml` with agent service and volumes.

3. **/world Seed**

   * Add the three seed files with the contents from §5.6.

4. **Orchestrator**

   * `prompt.txt` with the prompt contents described in §5.3.1 & §6.2.
   * `llm_driver.py` with Manual mode as described; stub for future LLM.
   * `main.py` loop as in §5.3.2:

     * Create run dir `runs/<UTC_ISO_TIMESTAMP>/`.
     * Write `meta.json`.
     * Read pre-exec block, extract `<Command>` with a robust regex.
     * `docker exec` the command; capture stdout/stderr/exit and monotonic latency.
     * Append command event JSON to `events.jsonl`.
     * Read post-exec block; append note event JSON to `events.jsonl`.
     * Repeat until blank input.

5. **Scorer**

   * Implement `scoring/scorer.py` per §5.5 with described regexes, metrics, and output JSON.

6. **Smoke Test**

   * Build: `docker compose up -d --build`.
   * Run orchestrator and perform 3+ steps:

     1. List directories including `/world` and `/home/agent`.
     2. Initialize `MAP.md`, `LOG.md`, `PLAN.md`, `TOOLS.md`.
     3. Create `/home/agent/tools/parse_csv.sh`, run it twice on `/world/data.csv`, append to `TOOLS.md`.
   * Verify `events.jsonl` and artifacts exist.
   * Run `python3 scoring/scorer.py runs/<ts>/` and observe JSON metrics.

7. **Quality**

   * Ensure consistent line endings (LF), UTF-8 encoding.
   * Add minimal comments to code explaining extension points (future LLM mode, richer scoring).

8. **License & Metadata**

   * Add `LICENSE` (MIT) and basic `pyproject.toml` or `requirements.txt` if needed (stdlib preferred).

---

## 8) Non-Functional Requirements

* **Reproducibility**: Every run stores `meta.json` and `events.jsonl` under a unique timestamp folder.
* **Simplicity**: No external dependencies beyond Docker and Python 3.10+ on the host.
* **Performance**: Command execution overhead minimal; median latency reported.
* **Portability**: Should run on macOS/Linux hosts with Docker Desktop or Docker Engine.

---

## 9) Example Flow (Happy Path)

1. `docker compose up -d --build`
2. `cd orchestrator && python3 main.py`
3. Paste:

   ```
   <Intent>
   Map top-level directories including /world and /home/agent

   <Command>
   ls -la / /world /home/agent

   <Expected>
   Confirm world (ro) and home (rw)

   <OnError>
   List dirs individually
   ```
4. See stdout; paste post-exec:

   ```
   <Observation>
   /world present; /home/agent writable…

   <Inference>
   I can persist MAP/LOG/TOOLS/PLAN under /home/agent

   <Next>
   Initialize files and scan /world
   ```
5. Paste a command that creates files and a CSV parser in `/home/agent/tools/`, run it twice.
6. End session; view `runs/<ts>/events.jsonl`; run scorer.

---

## 10) Risks & Mitigations (MVP stance)

* **Unrestricted egress** (intentional): No mitigation in MVP other than container boundary.
* **Web variability**: We accept changing web content; logs capture stdout/stderr for post-hoc analysis.
* **LLM variability**: Manual mode ensures the system is usable without an API key; model mode is a future extension.

---

## 11) Future Extensions (explicitly not in MVP scope)

* Proxy + allow/deny lists; request budgets; robots.txt compliance.
* Headless browser service (Playwright) for JS rendering; crawler; WARC capture.
* Prompt-injection detector; canary tokens; redaction.
* Browser/index tools, task packs, CI smoke tests.
* Advanced scoring (citation precision@K, cache hit ratios, dedupe metrics).

---

## 12) Deliverables Checklist

* [ ] Complete repository as per §5.1.
* [ ] Working Docker build and container with internet.
* [ ] Orchestrator loop and prompt implementing the Action Protocol.
* [ ] `/world` seed files.
* [ ] Run artifacts and JSONL logs.
* [ ] Scorer script producing the specified JSON.
* [ ] README with quick start and examples.

---

## 13) Run Commands (Operator Cheatsheet)

```bash
# Start / rebuild container
docker compose up -d --build

# Open a shell in the container (optional)
docker exec -it ai_discovery_agent bash

# Run orchestrator (manual mode)
cd orchestrator
python3 main.py

# Score a run
cd ..
python3 scoring/scorer.py runs/<run-timestamp>
```

This PRD is intentionally precise so an agentic builder can implement the project **exactly** as envisioned: a minimal, internet-enabled, container-only boundary experiment with clean logging and basic scoring.
