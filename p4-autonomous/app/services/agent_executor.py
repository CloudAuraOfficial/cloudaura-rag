"""Agentic RAG — plan-then-execute with tool orchestration."""

import json

import httpx
import structlog

from app.models.schemas import AgentStep, ToolCall
from app.services.tool_registry import TOOL_DESCRIPTIONS, ToolRegistry

logger = structlog.get_logger()

PLANNING_PROMPT = """You are an AI agent that answers questions by using tools. Available tools:

{tools}

Given the question, decide which tools to use and in what order. Think step by step.

For each step, output JSON on its own line:
{{"thought": "why this step", "tool": "tool_name", "args": {{...}}}}

When you have enough information, use the "answer" tool to give the final answer.
Output at most {max_steps} steps.

Question: {question}

Steps (one JSON per line):"""


class AgentExecutor:
    def __init__(
        self,
        tool_registry: ToolRegistry,
        ollama_base_url: str,
        model: str,
        max_steps: int = 5,
    ) -> None:
        self._tools = tool_registry
        self._client = httpx.AsyncClient(
            base_url=ollama_base_url.rstrip("/"),
            timeout=httpx.Timeout(180.0),
        )
        self._model = model
        self._max_steps = max_steps

    async def close(self) -> None:
        await self._client.aclose()

    async def run(self, question: str) -> tuple[str, list[AgentStep]]:
        """Execute agentic RAG pipeline.

        Returns:
            (final_answer, steps)
        """
        self._tools.reset()
        plan = await self._create_plan(question)
        steps: list[AgentStep] = []
        final_answer = ""

        for i, step_data in enumerate(plan[:self._max_steps]):
            thought = step_data.get("thought", "")
            tool_name = step_data.get("tool", "")
            tool_args = step_data.get("args", {})

            if not tool_name:
                continue

            # Execute tool
            result = await self._tools.execute(tool_name, tool_args)

            step = AgentStep(
                step=i + 1,
                thought=thought,
                tool_call=ToolCall(tool=tool_name, args=tool_args, result=result[:500]),
                observation=result[:500],
            )
            steps.append(step)

            logger.info(
                "agent_step",
                step=i + 1,
                tool=tool_name,
                observation_length=len(result),
            )

            # If final answer tool, we're done
            if tool_name == "answer":
                final_answer = result
                break

        # If no explicit answer step, synthesize from observations
        if not final_answer:
            final_answer = await self._synthesize(question, steps)

        return final_answer, steps

    async def _create_plan(self, question: str) -> list[dict]:
        tools_desc = "\n".join(
            f"- {name}: {desc}" for name, desc in TOOL_DESCRIPTIONS.items()
        )
        prompt = PLANNING_PROMPT.format(
            tools=tools_desc,
            max_steps=self._max_steps,
            question=question,
        )

        try:
            resp = await self._client.post(
                "/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 1024},
                },
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "")
            return self._parse_plan(raw)
        except Exception:
            logger.warning("planning_failed")
            # Fallback: just retrieve and answer
            return [
                {"thought": "Retrieve relevant information", "tool": "retrieve", "args": {"query": question}},
                {"thought": "Provide answer based on retrieved context", "tool": "answer", "args": {"answer": ""}},
            ]

    def _parse_plan(self, raw: str) -> list[dict]:
        steps = []
        # Try line-by-line JSON parsing
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Strip leading numbering like "1." or "- "
            line = line.lstrip("0123456789.-) ").strip()
            idx = line.find("{")
            if idx >= 0:
                end = line.rfind("}") + 1
                if end > idx:
                    try:
                        data = json.loads(line[idx:end])
                        if "tool" in data:
                            steps.append(data)
                    except json.JSONDecodeError:
                        continue

        if not steps:
            # Fallback: try parsing entire response as JSON array
            try:
                text = raw.strip()
                if text.startswith("["):
                    steps = json.loads(text)
            except json.JSONDecodeError:
                pass

        if not steps:
            # Last resort: simple retrieve + answer
            steps = [
                {"thought": "Search for relevant information", "tool": "retrieve", "args": {"query": raw[:200] if raw else "information"}},
            ]

        return steps

    async def _synthesize(self, question: str, steps: list[AgentStep]) -> str:
        observations = "\n\n".join(
            f"Step {s.step} ({s.tool_call.tool if s.tool_call else 'unknown'}): {s.observation or ''}"
            for s in steps
        )

        try:
            resp = await self._client.post(
                "/api/generate",
                json={
                    "model": self._model,
                    "prompt": (
                        f"Based on the following information gathered by an AI agent, "
                        f"provide a comprehensive answer to the question.\n\n"
                        f"Question: {question}\n\n"
                        f"Gathered information:\n{observations[:3000]}\n\n"
                        f"Answer (cite sources where available):"
                    ),
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 1024},
                },
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except Exception:
            logger.warning("synthesis_failed")
            # Combine observations as answer
            return "\n".join(s.observation or "" for s in steps if s.observation)
