#!/usr/bin/env python3
import io
import json
import os
import unittest
import tempfile
from unittest.mock import patch

from orchestrator import main as orchestrator_main
from types import SimpleNamespace

PRE_EXEC = """
<Intent>
Map top-level directories including /world and /home/agent

<Command>
ls -la / /world /home/agent

<Expected>
Confirm world (ro) and home (rw)

<OnError>
List dirs individually
""".strip()

POST_EXEC = """
<Observation>
...

<Inference>
...

<Next>
Initialize files and scan /world
""".strip()

class FakeDriver:
    def __init__(self):
        self._calls = 0
    def decide(self):
        # First call returns the block, second call returns empty to end loop
        if self._calls == 0:
            self._calls += 1
            return PRE_EXEC
        else:
            return ""
    def post_decide(self):
        return POST_EXEC

class OrchestratorFlowTests(unittest.TestCase):
    @patch.dict(os.environ, {"AGENT_CONTAINER": "breakout_agent"}, clear=False)
    def test_single_step_generates_logs(self):
        with tempfile.TemporaryDirectory() as tmp_runs:
            with patch.dict(os.environ, {"RUNS_DIR": tmp_runs}, clear=False):
                # Mock docker exec
                with patch.object(orchestrator_main, 'subprocess') as mock_sub:
                    # Return a simple object with stdout/stderr/returncode
                    mock_sub.run.return_value = SimpleNamespace(stdout='OK', stderr='', returncode=0)
                    # Inject fake driver
                    with patch.object(orchestrator_main, 'LLMDriver', return_value=FakeDriver()):
                        orchestrator_main.main()
                # Verify run directory created with meta and events
                run_dirs = [d for d in os.listdir(tmp_runs) if os.path.isdir(os.path.join(tmp_runs, d))]
                self.assertEqual(len(run_dirs), 1, f"Expected 1 run dir, found {run_dirs}")
                run_dir = os.path.join(tmp_runs, run_dirs[0])
                meta_path = os.path.join(run_dir, 'meta.json')
                events_path = os.path.join(run_dir, 'events.jsonl')
                self.assertTrue(os.path.exists(meta_path))
                self.assertTrue(os.path.exists(events_path))
                # Validate events
                with open(events_path, 'r') as f:
                    lines = [json.loads(line) for line in f.read().splitlines()]
                self.assertEqual(len(lines), 2)
                cmd_event = lines[0]
                post_event = lines[1]
                self.assertIn('command', cmd_event)
                self.assertEqual(cmd_event['command'], 'ls -la / /world /home/agent')
                self.assertEqual(cmd_event['exit_code'], 0)
                self.assertIn('post', post_event)

if __name__ == '__main__':
    unittest.main(verbosity=2)
