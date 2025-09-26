#!/usr/bin/env python3
import unittest
from unittest.mock import patch

from orchestrator.llm_driver import LLMDriver

class TestLLMDriverManual(unittest.TestCase):
    def test_decide_reads_until_eof(self):
        inputs = [
            "<Intent>",
            "Map things",
            "",
            "<Command>",
            "echo hello",
            "",
            "<Expected>",
        ]
        # Simulate EOF after inputs are exhausted
        with patch('builtins.input', side_effect=inputs + [EOFError()]):
            drv = LLMDriver(mode="manual")
            block = drv.decide()
            self.assertIn("<Command>", block)
            self.assertIn("echo hello", block)

    def test_post_decide_reads_until_eof(self):
        inputs = [
            "<Observation>",
            "It worked",
        ]
        with patch('builtins.input', side_effect=inputs + [EOFError()]):
            drv = LLMDriver(mode="manual")
            block = drv.post_decide()
            self.assertIn("<Observation>", block)
            self.assertIn("It worked", block)

if __name__ == '__main__':
    unittest.main(verbosity=2)
