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

MODEL = os.getenv("AGENT_MODEL", "llama-3.3-70b-versatile")

SYSTEM_PROMPT = """You are AXON, an autonomous AI agent with direct access to a Linux environment.
You can run bash commands by wrapping them in <cmd>...</cmd> tags.

Rules:
- When the user asks you to do something that requires computation, file operations, or system tasks, use commands.
- After a command runs, you will receive its output in <output>...</output> tags.
- Use that output to inform your response.
- You can chain multiple commands to accomplish complex tasks.
- Always explain what you're doing in plain language before and after commands.
- Keep responses concise and focused on the task.
- You are running in an isolated sandbox. The workspace is /tmp/workspace.

Example interaction:
User: check how much disk space is available
You: I'll check the disk space for you. <cmd>df -h /tmp</cmd>
<output>Filesystem  Size  Used Avail Use%
tmpfs        1.0G   12K  1.0G   1%</output>
You have about 1 GB of available space."""


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY not set — add it in Render → Environment")
        _client = AsyncGroq(api_key=api_key)
    return _client


CMD_RE = re.compile(r"<cmd>(.*?)</cmd>", re.DOTALL)


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

        stream = await client.chat.completions.create(
            model=MODEL,
            max_tokens=2048,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + claude_messages,
            stream=True,
        )

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
            yield {"type": "command", "data": cmd}
            _, output = await exec_fn(cmd)
            output_text = output.strip() if output else "(no output)"
            all_outputs.append(output_text)
            yield {"type": "output", "data": output_text}

        claude_messages.append({"role": "assistant", "content": full_text})
        claude_messages.append({
            "role": "user",
            "content": "\n".join(f"<output>{o}</output>" for o in all_outputs),
        })

    yield {"type": "done"}
