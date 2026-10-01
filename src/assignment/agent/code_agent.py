"""The Part 1 coding agent: fix a software issue and submit a git patch."""

from __future__ import annotations

import json
from typing import Any

from assignment.agent.base import (
    DEFAULT_COMPACTION_KEEP_RECENT_STEPS,
    DEFAULT_COMPACTION_MAX_TOKENS,
    Agent,
    format_tool_output
)
from assignment.agent.tools import EXECUTE_TOOL, SEND_MESSAGE_TOOL
from assignment.env import Environment

class CodeAgent(Agent):
    """An agent that fixes a software issue and submits a git patch."""

    def __init__(
        self,
        task: str,
        environment: Environment,
        model: str | None = None,
        logs_save_path: str | None = None,
        step_limit: int = 100,
        skills_path: str | None = None,
        auto_stop_environment: bool = True,
        compact_threshold_tokens: int | None = None,
        compaction_keep_recent_steps: int = DEFAULT_COMPACTION_KEEP_RECENT_STEPS,
        compaction_max_tokens: int = DEFAULT_COMPACTION_MAX_TOKENS,
    ):
        super().__init__( 
            environment=environment,
            model=model,
            logs_save_path=logs_save_path,
            step_limit=step_limit,
            skills_path=skills_path,
            auto_stop_environment=auto_stop_environment,
            compact_threshold_tokens=compact_threshold_tokens,
            compaction_keep_recent_steps=compaction_keep_recent_steps,
            compaction_max_tokens=compaction_max_tokens,
        )
        self.task = task
        self.submitted_patch = ""

        # TODO(Part 1.3): Make the `execute` and `send_message` tools available
        # to the agent.
        self.tools.extend([EXECUTE_TOOL, SEND_MESSAGE_TOOL])

        # TODO(1.1.b): Construct the system prompt and task_prompt. These
        # should be usable by the `Agent.build_prompt` method.
        self.system_prompt = f"""You are an autonomous coding agent working in a terminal environment.

            Inspect the repository, reproduce the reported problem, make the necessary
            source changes, and run relevant tests to verify the solution. Use the
            available tools to perform work in the environment rather than only describing
            what should be done.

            The default working directory is {self.env.cwd}.

            <system_information>
            {{
            "machine": {json.dumps(self.env.machine)},
            "release": {json.dumps(self.env.release)},
            "system": {json.dumps(self.env.system)},
            "version": {json.dumps(self.env.version)}
            }}
            </system_information>
        """

        self.task_prompt = f"""Fix the following software issue.
                        
        <task>
            {self.task}
        </task>
        """
        # TODO(1.4): If any skills are available to the agent, make their
        # descriptions/metadata available to the agent in the prompt.
        if self.skills:
            skills_prompt = "\nAvailable skills:"
            for name, skill in self.skills.items():
                 metadata = skill.get("metadata")
                 skills_prompt += f"\n<skill>{metadata}</skill>"

            self.system_prompt += skills_prompt

    def execute_tool_calls(
        self, tool_calls: list[dict[str, Any]]
    ) -> list[dict[str, str]]:
        """Execute ``execute`` and ``send_message`` calls in the code sandbox."""

        # TODO(Part 1.3): Parse each call, execute recognized tools, and return
        # one message per call (there may be multiple tool calls in one agent
        # response!). Malformed JSON and unknown tools must become recoverable
        # observations relayed to the agent instead of exceptions.
        
        tool_messages = []

        for tool_call in tool_calls:

            if not isinstance(tool_call, dict):
                            tool_messages.append({
                                "role": "tool",
                                "tool_call_id": "unknown",
                                "content": f"<tool_error>tool_call should be a dict.</tool_error>"
                            })
                            continue
            
            tool_call_id = tool_call.get("id", "unknown")
            if tool_call_id == "unknown":
                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": f"<tool_error>Unknown tool.</tool_error>"
                })
                continue

            if self.finished:
                 tool_messages.append({
                      "role": "tool",
                      "tool_call_id":tool_call_id,
                      "content": "omitted because task already finished."
                 })
                 continue
            
            function = tool_call.get("function")
            if not isinstance(function, dict):
                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": f"<tool_error>function should be a dict.</tool_error>"
                })
                continue


            tool_name = function.get("name", "unknown")
            raw_arguments = function.get("arguments")

            try:
                arguments = json.loads(raw_arguments)
                if not isinstance(arguments, dict):
                    raise Exception
            except Exception:
                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": f"<tool_error>{tool_name}: Invalid json arguments.</tool_error>"
                })
                continue

            if tool_name == "execute":
                commands = arguments.get("command")
                if not commands :
                    tool_messages.append({
                                        "role": "tool",
                                        "tool_call_id": tool_call_id,
                                        "content": f"<tool_error>{tool_name}: Execution requires command.</tool_error>"
                                    })
                    continue

                elif not isinstance(commands, str) and not (isinstance(commands, list) and all(isinstance(command, str) for command in commands)):
                    tool_messages.append({
                                        "role": "tool",
                                        "tool_call_id": tool_call_id,
                                        "content": f"<tool_error>{tool_name}: Execution commands should be str or list[str].</tool_error>"
                                    })
                    continue
                    
                shell = arguments.get("shell")
                cwd = arguments.get("cwd")
                timeout = arguments.get("timeout")
                env = arguments.get("env")

                tool_call_result = format_tool_output(self.env.execute(
                    command=commands,
                    shell=shell,
                    cwd=cwd,               
                    timeout=timeout,
                    env=env))
                
                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content":  tool_call_result
                })

            elif tool_name == "send_message":
                summary = arguments.get("summary")
                if not isinstance(summary, str):
                    tool_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": f"<tool_error>{tool_name} summary should be a str.</tool_error>"
                    })
                    continue

                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": summary
                })
                self.finished = True
                continue

            elif tool_name == "invoke_skill":
                name = arguments.get("name")
                if not isinstance(name, str):
                    tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": f"<tool_error>{tool_name}: name should be a str.</tool_error>"
                })
                    continue
                if not self.skills.get(name):
                    tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": f"<tool_error>{tool_name}: No skill named `{name}`.</tool_error>"
                })
                    continue

                tool_messages.append({
                     "role": "tool",
                     "tool_call_id": tool_call_id,
                     "content": self.skills.get(name).get("content")
                })

            else:
                tool_messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call_id,
                                    "content": f"<tool_error>Unknown tool:{tool_name}</tool_error>"
                                })

        return tool_messages