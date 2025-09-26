#!/usr/bin/env python3
import sys
import os

class LLMDriver:
    def __init__(self, mode="manual"):
        self.mode = mode
        self.block_delim = os.getenv("BLOCK_DELIM", "---")
        self._loaded = False
        self._segments = []
        self._idx = 0

    def _load_stream(self):
        # Read entire stdin once and split into segments on a line that equals the delimiter
        data = sys.stdin.read()
        import re
        parts = re.split(rf"(?m)^\s*{re.escape(self.block_delim)}\s*$", data)
        self._segments = [p.strip() for p in parts if p.strip()]
        self._loaded = True

    def decide(self):
        if self.mode == "manual":
            # Read pre-exec block from stdin, line by line
            print("Enter pre-exec Action Protocol block (Intent/Command/Expected/OnError). Press Ctrl+D when done:")
            lines = []
            try:
                while True:
                    line = input()
                    lines.append(line)
            except EOFError:
                pass
            pre_exec = '\n'.join(lines).strip()
            return pre_exec
        elif self.mode == "delimited":
            if not self._loaded:
                self._load_stream()
            if self._idx >= len(self._segments):
                return ""
            seg = self._segments[self._idx]
            self._idx += 1
            return seg
        else:
            raise NotImplementedError(f"LLM mode '{self.mode}' not implemented")

    def post_decide(self):
        if self.mode == "manual":
            # Read post-exec block from stdin, line by line
            print("Enter post-exec Action Protocol block (Observation/Inference/Next). Press Ctrl+D when done:")
            lines = []
            try:
                while True:
                    line = input()
                    lines.append(line)
            except EOFError:
                pass
            post_exec = '\n'.join(lines).strip()
            return post_exec
        elif self.mode == "delimited":
            if not self._loaded:
                self._load_stream()
            if self._idx >= len(self._segments):
                return ""
            seg = self._segments[self._idx]
            self._idx += 1
            return seg
        else:
            raise NotImplementedError(f"LLM mode '{self.mode}' not implemented")
