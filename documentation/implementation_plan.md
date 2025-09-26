# Implementation Plan for AI Discovery Project

This document outlines the step-by-step implementation plan for the AI Discovery project, based on the Product Requirements Document (PRD). Each step is designed to be a full, testable feature. We'll implement one step at a time, test it, commit if working, and then proceed to the next.

## Key Principles
- **Reference to PRD**: Each step cites the relevant section(s) for exact requirements.
- **Testing Approach**: Focus on manual or simple automated checks to validate without overcomplicating the MVP.
- **Assumptions**: Working in `/Users/matthew/bitrift/breakout` (repo root), with Docker and Python 3.10+ available.
- **Version Control**: After each successful test, run `git add . && git commit -m "<descriptive message>"`.
- **Dependencies**: Stick to standard libraries to avoid external deps per the PRD.

## Step-by-Step Plan

### Step 1: Bootstrap Repository Structure
- **Description**: Create all required directories and placeholder files as per PRD §5.1. This sets up the basic layout without any logic.
- **Implementation Details**:
  - Create directories: `sandbox/`, `orchestrator/`, `scoring/`, `world/`, `runs/`.
  - Add placeholder files: `sandbox/Dockerfile.agent` (empty), `orchestrator/prompt.txt` (empty), `orchestrator/main.py` (stub with shebang), `orchestrator/llm_driver.py` (stub), `scoring/scorer.py` (stub), `world/README.md` (stub), `world/data.csv` (stub), `world/puzzles/hidden.txt` (stub), and root `README.md` (stub).
- **Testing Criteria**:
  - Run `ls -la` to verify all directories and files exist.
  - Check that the structure matches PRD §5.1.
- **Expected Outcome**: Basic file structure is in place.
- **Commit Message**: "Bootstrap repository structure per PRD §5.1"

### Step 2: Implement Docker Setup
- **Description**: Create `sandbox/Dockerfile.agent` and `docker-compose.yml` per PRD §5.2. Test by building and starting the container with internet access.
- **Implementation Details**:
  - Fill `sandbox/Dockerfile.agent` with Debian base, package installs, user setup, mounts, and entrypoint.
  - Create `docker-compose.yml` with the `agent` service, volumes, and internet access.
- **Testing Criteria**:
  - Run `docker compose up -d --build` and check for success.
  - Run `docker exec -it breakout_agent bash -c "whoami && ls -la /world /home/agent"` to verify user, mounts, and internet.
  - Stop with `docker compose down`.
- **Expected Outcome**: Container builds and runs with internet.
- **Commit Message**: "Implement Docker setup with internet-enabled container per PRD §5.2"

### Step 3: Add /world Seed Files
- **Description**: Create `world/README.md`, `world/data.csv`, and `world/puzzles/hidden.txt` with exact contents from PRD §5.6. Test by inspecting files and mounting in container.
- **Implementation Details**:
  - Populate `world/README.md` with purpose and hints.
  - Add `world/data.csv` with sample CSV data.
  - Add `world/puzzles/hidden.txt` with the exact clue.
- **Testing Criteria**:
  - Inspect files: `cat world/README.md` should show the description; `head world/data.csv` should show CSV; `cat world/puzzles/hidden.txt` should show the clue.
  - Start the container and verify files are read-only.
- **Expected Outcome**: Seed files are in place and accessible.
- **Commit Message**: "Add /world seed files per PRD §5.6"

### Step 4: Implement Orchestrator Components
- **Description**: Create `orchestrator/prompt.txt`, `orchestrator/llm_driver.py` (manual mode), and `orchestrator/main.py` per PRD §5.3. Test by running the orchestrator loop with sample input.
- **Implementation Details**:
  - Fill `orchestrator/prompt.txt` with the full prompt text.
  - Implement `orchestrator/llm_driver.py` with manual mode and a stub for `decide()`.
  - Implement `orchestrator/main.py` with the full loop: env vars, run dir creation, meta.json, command parsing, `docker exec`, logging to events.jsonl.
- **Testing Criteria**:
  - Start the container: `docker compose up -d`.
  - Run `cd orchestrator && python3 main.py` with sample input.
  - Verify: `runs/<timestamp>/events.jsonl` has at least one entry; `runs/<timestamp>/meta.json` exists.
- **Expected Outcome**: Orchestrator runs the loop and logs correctly.
- **Commit Message**: "Implement orchestrator with Action Protocol and logging per PRD §5.3"

### Step 5: Implement Scorer
- **Description**: Create `scoring/scorer.py` per PRD §5.5. Test by running it on a sample events.jsonl file.
- **Implementation Details**:
  - Fill `scoring/scorer.py` with logic to read `events.jsonl`, compute metrics, and output JSON.
- **Testing Criteria**:
  - Create a sample `runs/test/events.jsonl` with mock data.
  - Run `python3 scoring/scorer.py runs/test/` and verify JSON output.
- **Expected Outcome**: Scorer produces valid JSON metrics.
- **Commit Message**: "Implement scorer with metrics calculation per PRD §5.5"

### Step 6: Run Smoke Test
- **Description**: Perform the exact smoke test from PRD §7.6, including building, running orchestrator for 3+ steps, and verifying artifacts/logs. Test full integration.
- **Implementation Details**: No new code—just execute the test.
- **Testing Criteria**:
  - Build and start: `docker compose up -d --build`.
  - Run orchestrator with 3+ steps: list directories, initialize artifacts, create and reuse a tool.
  - Verify: `runs/<timestamp>/events.jsonl` has ≥3 entries; artifacts exist; scorer outputs JSON.
- **Expected Outcome**: Full integration works per acceptance criteria.
- **Commit Message**: "Pass smoke test per PRD §7.6"

### Step 7: Add Quality and Metadata
- **Description**: Ensure consistent formatting, add comments, create root README.md, and add LICENSE/pyproject.toml per PRD §7.7 and §7.8. Test by checking encoding and running a quick validation.
- **Implementation Details**:
  - Ensure LF line endings, UTF-8 encoding.
  - Add comments to code.
  - Fill root `README.md` with quick start.
  - Add `LICENSE` (MIT) and `pyproject.toml`.
- **Testing Criteria**:
  - Run `file *.md *.py` to confirm encoding.
  - Manually review `README.md`.
  - Quick validation: Ensure no syntax errors.
- **Expected Outcome**: Code is polished and documented.
- **Commit Message**: "Add quality checks, README, and metadata per PRD §7.7 and §7.8"

## Next Steps
- Start with Step 1 and proceed sequentially.
- If any step fails, debug and iterate before committing.
- This plan ensures a reproducible, MVP-aligned implementation.
