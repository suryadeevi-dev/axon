"""
AI service: drives the agent using Claude.

The agent loop:
1. User sends a message
2. Claude reasons about it and decides whether to run a command
3. If a command: execute it in the agent's container, feed output back to Claude
4. Repeat until Claude produces a final text response
5. Stream every token and every command/output event over the WebSocket
"""

import re
import logging
import os
from typing import AsyncGenerator, Optional
from anthropic import AsyncAnthropic

log = logging.getLogger(__name__)

_client: Optional[AsyncAnthropic] = None

SYSTEM_PROMPT = """You are AXON, an autonomous AI agent with direct access to a Linux environment.
You can run bash commands by wrapping them in <cmd>...</cmd> tags.

Rules:
- When the user asks you to do something that requires computation, file operations, or system tasks, use commands.
- After a command runs, you will receive its output in <output>...</output> tags.
- Use that output to inform your response.
- You can chain multiple commands to accomplish complex tasks.
- Always explain what you're doing in plain language before and after commands.
- Keep responses concise and focused on the task.
- You are running as a non-root user in an isolated container. The workspace is /home/axon/workspace.

Example interaction:
User: check how much disk space is available
You: I'll check the disk space for you. <cmd>df -h /home/axon/workspace</cmd>
<output>Filesystem  Size  Used Avail Use%
/dev/sda1    20G  1.2G  18G   7%</output>
You have about 18 GB of available disk space."""


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        _client = AsyncAnthropic(api_key=api_key)
    return _client


CMD_RE = re.compile(r"<cmd>(.*?)</cmd>", re.DOTALL)


async def run_agent_turn(
    messages: list[dict],
    exec_fn,  # Callable[[str], tuple[int, str]]
) -> AsyncGenerator[dict, None]:
    """
    Drive one full turn of the agent:
    - streams tokens as {"type": "token", "data": str}
    - emits commands as {"type": "command", "data": str}
    - emits outputs as {"type": "output", "data": str}
    - emits {"type": "done"} when complete
    """
    client = _get_client()

    claude_messages = list(messages)
    max_iterations = 8

    for _ in range(max_iterations):
        full_text = ""

        # Stream from Claude
        async with client.messages.stream(
            model="claude-3-5-haiku-20241022",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=claude_messages,
        ) as stream:
            async for text in stream.text_stream:
                full_text += text
                yield {"type": "token", "data": text}

        # Check if there are commands in the response
        commands = CMD_RE.findall(full_text)

        if not commands:
            # Pure text response — we're done
            yield {"type": "done"}
            return

        # Execute each command and collect outputs
        all_outputs = []
        for cmd in commands:
            cmd = cmd.strip()
            yield {"type": "command", "data": cmd}

            exit_code, output = await exec_fn(cmd)
            output_text = output.strip() if output else "(no output)"
            all_outputs.append(f"<output>{output_text}</output>")
            yield {"type": "output", "data": output_text}

        # Feed results back to Claude as an assistant + tool-result turn
        claude_messages.append({"role": "assistant", "content": full_text})
        claude_messages.append({"role": "user", "content": "\n".join(all_outputs)})

    yield {"type": "done"}
