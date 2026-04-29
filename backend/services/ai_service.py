"""
AI service: drives the agent using Llama 3.3 70B via Groq (free tier).

The agent loop:
1. User sends a message
2. LLM reasons and optionally emits <cmd>...</cmd> tags
3. Commands execute in the agent's sandbox; output fed back to LLM
4. Repeat until LLM produces a final text response (no more commands)
5. Stream every token and command/output event over the WebSocket
"""

import re
import logging
import os
from typing import AsyncGenerator, Optional
from groq import AsyncGroq

log = logging.getLogger(__name__)

_client: Optional[AsyncGroq] = None

# Primary model and fallback when daily token limit is hit
MODEL_PRIMARY  = os.getenv("AGENT_MODEL", "llama-3.3-70b-versatile")
MODEL_FALLBACK = "llama-3.1-8b-instant"  # 500K TPD vs 100K on primary

SYSTEM_PROMPT = """You are AXON, a concise AI assistant with optional access to a Linux sandbox.

## When to use commands
Only use <cmd>...</cmd> when the task genuinely requires it:
- Running code or scripts
- File operations (read, write, create, delete)
- System info (disk, memory, processes)
- Installing packages or building things
- Anything that requires actual computation

## When NOT to use commands
- Answering questions, giving advice, explaining concepts → just respond in plain text
- NEVER use `echo` or `printf` to display text — write your answer directly
- NEVER use commands just to format or print your response

## Format rules
- Be concise. 2-4 sentences for simple answers, more only when truly needed.
- When using a command, write one short sentence before it explaining what you're doing.
- After command output, summarise the result briefly — do not repeat the raw output.
- No bullet-pointed lists of generic advice unless explicitly asked.

## Command syntax
Wrap each command in <cmd>...</cmd>. You will receive output in <output>...</output>.
You can run multiple commands sequentially.

## Example — command needed
User: how much memory is free?
Assistant: Let me check. <cmd>free -h</cmd>
<output>Mem: 512M used, 1.5G free</output>
You have 1.5 GB of free memory.

## Example — no command needed
User: what is a for loop?
Assistant: A for loop repeats a block of code a fixed number of times, iterating over a sequence. In Python: `for i in range(5): print(i)` prints 0 through 4."""


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY not set — add it in Render → Environment")
        _client = AsyncGroq(api_key=api_key)
    return _client


CMD_RE = re.compile(r"<cmd>(.*?)</cmd>", re.DOTALL)
# echo/printf used just to print a string — not real computation, skip execution
TRIVIAL_ECHO_RE = re.compile(r'^(echo|printf)\s+["\']', re.IGNORECASE)


async def run_agent_turn(
    messages: list[dict],
    exec_fn,
) -> AsyncGenerator[dict, None]:
    """
    Drive one full agent turn, yielding WebSocket events:
      {"type": "token",   "data": str}
      {"type": "command", "data": str}
      {"type": "output",  "data": str}
      {"type": "done"}
    """
    client = _get_client()
    claude_messages = list(messages)
    max_iterations = 8

    for _ in range(max_iterations):
        full_text = ""

        # Try primary model; fall back to faster model on rate-limit (429)
        try:
            stream = await client.chat.completions.create(
                model=MODEL_PRIMARY,
                max_tokens=2048,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + claude_messages,
                stream=True,
            )
        except Exception as e:
            if "rate_limit_exceeded" in str(e) or "429" in str(e):
                log.warning("Primary model rate-limited, falling back to %s", MODEL_FALLBACK)
                yield {"type": "token", "data": f"*(rate limited — using {MODEL_FALLBACK})*\n\n"}
                stream = await client.chat.completions.create(
                    model=MODEL_FALLBACK,
                    max_tokens=2048,
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}] + claude_messages,
                    stream=True,
                )
            else:
                raise

        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                full_text += delta
                yield {"type": "token", "data": delta}

        commands = CMD_RE.findall(full_text)

        if not commands:
            yield {"type": "done"}
            return

        all_outputs = []
        for cmd in commands:
            cmd = cmd.strip()
            if TRIVIAL_ECHO_RE.match(cmd):
                # Model used echo to print text — skip, don't show in UI
                continue
            yield {"type": "command", "data": cmd}
            _, output = await exec_fn(cmd)
            output_text = output.strip() if output else "(no output)"
            all_outputs.append(output_text)
            yield {"type": "output", "data": output_text}

        if not all_outputs:
            # All commands were trivial echoes — treat as plain text response
            yield {"type": "done"}
            return

        claude_messages.append({"role": "assistant", "content": full_text})
        claude_messages.append({
            "role": "user",
            "content": "\n".join(f"<output>{o}</output>" for o in all_outputs),
        })

    yield {"type": "done"}
