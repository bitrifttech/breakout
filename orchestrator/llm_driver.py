#!/usr/bin/env python3
import sys
import os

class LLMDriver:
    def __init__(self, mode="manual"):
        self.mode = mode

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
        else:
            # Stub for future LLM mode
            raise NotImplementedError("LLM mode not implemented yet")

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
        else:
            # Stub for future LLM mode
            raise NotImplementedError("LLM mode not implemented yet")
