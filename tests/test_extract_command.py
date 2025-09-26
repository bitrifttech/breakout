#!/usr/bin/env python3
import unittest

from orchestrator.main import extract_command

SAMPLE_BLOCK = """
<Intent>
Map top-level directories including /world and /home/agent

<Command>
ls -la / /world /home/agent

<Expected>
Confirm world (ro) and home (rw)

<OnError>
List dirs individually
""".strip()

class TestExtractCommand(unittest.TestCase):
    def test_extract_basic(self):
        cmd = extract_command(SAMPLE_BLOCK)
        self.assertEqual(cmd, "ls -la / /world /home/agent")

    def test_extract_with_leading_blank_line(self):
        block = """
<Intent>
...

<Command>

   ls -la /tmp

<Expected>
...
<OnError>
...
""".strip()
        cmd = extract_command(block)
        self.assertEqual(cmd, "ls -la /tmp")

    def test_missing_command_line_raises(self):
        block = """
<Intent>
...

<Command>

<Expected>
...
<OnError>
...
""".strip()
        with self.assertRaises(ValueError):
            extract_command(block)

    def test_command_stops_at_next_tag(self):
        block = """
<Intent>
...

<Command>
ls -la
<Expected>
foo
<OnError>
bar
""".strip()
        cmd = extract_command(block)
        self.assertEqual(cmd, "ls -la")

if __name__ == "__main__":
    unittest.main()
