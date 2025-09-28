#!/usr/bin/env python3
import sys
import os
import json
import time
from urllib import request, error

class LLMDriver:
    def __init__(self, mode="manual"):
        self.mode = mode
        self.block_delim = os.getenv("BLOCK_DELIM", "---")
        self._loaded = False
        self._segments = []
        self._idx = 0
        # API config
        self.provider = os.getenv("LLM_PROVIDER", "openai")
        self.model = os.getenv("LLM_MODEL", os.getenv("OPENAI_MODEL", "gpt-5"))
        # HTTP timeout (seconds) for API calls
        self.http_timeout = int(os.getenv("LLM_HTTP_TIMEOUT", os.getenv("LLM_TIMEOUT", "300")))
        # Base URL for OpenAI-compatible endpoints (LM Studio, custom proxies)
        # Defaults: OpenAI -> https://api.openai.com/v1, LM Studio -> http://localhost:1234/v1
        default_base = (
            "https://api.openai.com/v1" if self.provider == "openai" else "http://localhost:1234/v1"
        )
        self.base_url = os.getenv("LLM_BASE_URL", default_base)
        self._orch_dir = os.path.dirname(__file__)
        self._prompt_path = os.path.join(self._orch_dir, "prompt.txt")

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
        elif self.mode == "api":
            prompt = self._read_prompt()
            ctx = self._read_context()
            content = (
                f"{prompt}\n\n"
                f"Recent context (latest first):\n{ctx}\n\n"
                "You are the Orchestrator. Use the most recent <Next> from the post-exec block to drive your "
                "next action. Do NOT repeat the same <Command> as the previous step. Produce ONLY the pre-exec "
                "Action Protocol block with tags <Intent>, <Command>, <Expected>, <OnError>. No extra commentary."
            )
            return self._invoke_llm(content)
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
        elif self.mode == "api":
            prompt = self._read_prompt()
            ctx = self._read_context()
            content = (
                f"{prompt}\n\n"
                f"Recent context (latest first):\n{ctx}\n\n"
                "You are the Orchestrator. Reflect concisely on the just-executed command and outcome. "
                "Produce ONLY the post-exec Action Protocol block with tags <Observation>, <Inference>, <Next>. "
                "No extra commentary."
            )
            return self._invoke_llm(content)
        else:
            raise NotImplementedError(f"LLM mode '{self.mode}' not implemented")

    # Helpers for API mode
    def _read_prompt(self) -> str:
        try:
            with open(self._prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def _read_context(self) -> str:
        path = os.getenv("RUN_CONTEXT")
        if not path:
            return ""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def _invoke_llm(self, content: str) -> str:
        provider = self.provider
        base = (self.base_url or "").rstrip("/")
        if provider in ("openai", "lmstudio", "openai_compatible"):
            # Build OpenAI-compatible Chat Completions request
            url = f"{base}/chat/completions"
            body = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": content},
                ],
                # "temperature": float(os.getenv("LLM_TEMPERATURE", "0")),
                # "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "512")),
            }
            data = json.dumps(body).encode("utf-8")
            req = request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            # Authorization header only for OpenAI or if user provides a key explicitly
            api_key = os.getenv("OPENAI_API_KEY")
            if provider == "openai":
                if not api_key:
                    raise RuntimeError("OPENAI_API_KEY not set")
                req.add_header("Authorization", f"Bearer {api_key}")
            elif api_key:
                # Optional: allow sending auth to compatible proxies if provided
                req.add_header("Authorization", f"Bearer {api_key}")

            try:
                with request.urlopen(req, timeout=self.http_timeout) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
            except error.HTTPError as e:
                raise RuntimeError(f"OpenAI HTTPError: {e.code} {e.read().decode('utf-8', 'ignore')}")
            except error.URLError as e:
                raise RuntimeError(f"OpenAI URLError: {e.reason}")
            # Extract content
            try:
                return payload["choices"][0]["message"]["content"].strip()
            except Exception as e:
                raise RuntimeError(f"Unexpected OpenAI response shape: {e} :: {payload}")
        else:
            raise NotImplementedError(f"LLM provider '{provider}' not implemented")
