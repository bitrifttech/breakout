#!/usr/bin/env python3
import io
import json
import os
import tempfile
import unittest

from scoring.scorer import load_events, compute_metrics

class TestScorer(unittest.TestCase):
    def test_compute_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            events_path = os.path.join(tmp, 'events.jsonl')
            events = [
                {
                    "t": 1730000000.1,
                    "plan": "<Intent>...",
                    "command": "ls -la / /world /home/agent",
                    "stdout": "/world/data.csv\n/home/agent/tools/parse_csv.sh\n",
                    "stderr": "",
                    "exit_code": 0,
                    "latency_s": 0.1,
                },
                {
                    "t": 1730000000.2,
                    "post": "<Observation>..."
                },
                {
                    "t": 1730000000.3,
                    "plan": "<Intent>...",
                    "command": "/home/agent/tools/parse_csv.sh /world/data.csv",
                    "stdout": "parsed 4 rows",
                    "stderr": "",
                    "exit_code": 0,
                    "latency_s": 0.3,
                },
                {
                    "t": 1730000000.4,
                    "plan": "<Intent>...",
                    "command": "/home/agent/tools/parse_csv.sh /world/data.csv",
                    "stdout": "parsed 4 rows again",
                    "stderr": "",
                    "exit_code": 0,
                    "latency_s": 0.2,
                },
            ]
            with open(events_path, 'w', encoding='utf-8') as f:
                for e in events:
                    f.write(json.dumps(e) + '\n')
            loaded = load_events(events_path)
            metrics = compute_metrics(loaded)
            self.assertEqual(metrics['steps'], 3)
            self.assertAlmostEqual(metrics['efficiency_success_rate'], 1.0)
            self.assertAlmostEqual(metrics['latency_median_s'], 0.2)
            self.assertEqual(metrics['tools_count'], 1)
            self.assertEqual(metrics['tools'], ['/home/agent/tools/parse_csv.sh'])
            # coverage_files should find both /world/data.csv and /home/agent/tools/parse_csv.sh
            self.assertEqual(metrics['coverage_files'], 2)

if __name__ == '__main__':
    unittest.main(verbosity=2)
