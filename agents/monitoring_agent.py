import json
import re
import requests
from typing import Any, Dict, Optional

from langchain_ollama import ChatOllama
from langchain.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage

MONITORING_API_URL = "http://localhost:8001"

# IMPORTANT: set this to EXACTLY what `ollama list` shows (e.g. "llama3:latest")
OLLAMA_MODEL = "llama3.2:latest"


# -------------------------
# Helpers
# -------------------------

def _extract_hostname(value: str) -> str:
    """Extract a hostname like PRD-APP-01 from messy text such as hostname='PRD-APP-01'."""
    if value is None:
        return ""
    s = str(value).strip()

    # hostname="PRD-APP-01" / hostname = 'PRD-APP-01'
    m = re.search(r"hostname\s*=\s*['\"]?([A-Za-z0-9\-_.]+)['\"]?", s)
    if m:
        return m.group(1)

    # "PRD-APP-01" -> PRD-APP-01
    s = s.strip("\"'")
    m2 = re.search(r"([A-Za-z0-9\-_.]+)", s)
    return m2.group(1) if m2 else s


def _safe_get(url: str, *, params: Optional[dict] = None, timeout: int = 10):
    """HTTP GET wrapper with timeout."""
    return requests.get(url, params=params, timeout=timeout)


# -------------------------
# Tools (docstrings required)
# -------------------------

@tool
def get_server_status(hostname: str) -> Dict[str, Any]:
    """Get server health/status for the given hostname (example: PRD-APP-01)."""
    host = _extract_hostname(hostname)
    r = _safe_get(f"{MONITORING_API_URL}/servers/{host}/status")
    if r.status_code == 404:
        return {"error": f"Server '{host}' not found."}
    r.raise_for_status()
    return r.json()


@tool
def get_server_logs(hostname: str, lines: int = 10) -> Dict[str, Any]:
    """Get recent server logs for the given hostname (default: last 10 lines)."""
    host = _extract_hostname(hostname)
    r = _safe_get(
        f"{MONITORING_API_URL}/servers/{host}/logs",
        params={"lines": int(lines)},
    )
    if r.status_code == 404:
        return {"error": f"Server '{host}' not found."}
    r.raise_for_status()
    return r.json()


@tool
def list_running_servers() -> Dict[str, Any]:
    """List only servers that are currently running."""
    r = _safe_get(f"{MONITORING_API_URL}/servers", params={"status": "running"})
    r.raise_for_status()
    return r.json()


@tool
def get_server_metrics(hostname: str) -> Dict[str, Any]:
    """Get detailed metrics (current/average/peak) for the given hostname."""
    host = _extract_hostname(hostname)
    r = _safe_get(f"{MONITORING_API_URL}/servers/{host}/metrics")
    if r.status_code == 404:
        return {"error": f"Server '{host}' not found."}
    r.raise_for_status()
    return r.json()


TOOLS = [get_server_status, get_server_logs, list_running_servers, get_server_metrics]
TOOL_MAP = {t.name: t for t in TOOLS}


# -------------------------
# Grounded final answer
# -------------------------

FINAL_ANSWER_RULES = """You are an IT operations monitoring assistant.

STRICT RULES:
- Use ONLY the TOOL_RESULT JSON to answer.
- If a field is not present in TOOL_RESULT, say "Not provided by monitoring API" and do not invent it.
- Do not invent IP addresses, timestamps, or log lines.
- Keep the answer short and actionable.
"""


def _final_answer(question: str, tool_name: str, tool_args: dict, tool_out: Any) -> str:
    """Generate a grounded final answer strictly from tool output JSON."""
    llm = ChatOllama(model=OLLAMA_MODEL, temperature=0)

    payload = {
        "tool": tool_name,
        "args": tool_args,
        "result": tool_out,
    }

    prompt = (
        FINAL_ANSWER_RULES
        + "\nUSER_QUESTION:\n"
        + question
        + "\n\nTOOL_RESULT_JSON:\n"
        + json.dumps(payload, indent=2)
        + "\n\nWrite the final answer now:"
    )
    return llm.invoke(prompt).content.strip()


# -------------------------
# Tool-calling loop (max 2)
# -------------------------

def ask_monitoring_agent(question: str, max_tool_calls: int = 2) -> str:
    """
    Uses tool calling (structured tool_calls) with Ollama.
    Key behavior:
    - If a tool is called once, we STOP and produce a grounded final answer from that tool output.
    - No ReAct parsing, no infinite loops.
    """
    llm = ChatOllama(model=OLLAMA_MODEL, temperature=0).bind_tools(TOOLS)
    messages = [HumanMessage(content=question)]

    for iteration in range(max_tool_calls):
        ai = llm.invoke(messages)

        # If no tools requested, return direct answer
        if not getattr(ai, "tool_calls", None):
            return ai.content.strip()

        # Execute all requested tools
        for call in ai.tool_calls:
            tool_name = call["name"]
            tool_args = call.get("args", {}) or {}
            tool_call_id = call.get("id")

            if tool_name not in TOOL_MAP:
                tool_out = {"error": f"Unknown tool: {tool_name}"}
            else:
                try:
                    tool_out = TOOL_MAP[tool_name].invoke(tool_args)
                except Exception as e:
                    tool_out = {"error": str(e)}

            # Send tool result back to LLM
            messages.append(ToolMessage(
                content=json.dumps(tool_out),
                tool_call_id=tool_call_id
            ))

        # Add AI message to maintain conversation structure
        messages.insert(-len(ai.tool_calls), ai)

        # Continue the loop - LLM can call more tools or give final answer

    # If we exit loop without a final answer, ask LLM one more time
    final = llm.invoke(messages)
    return final.content.strip()


# -------------------------
# Main (tests)
# -------------------------

if __name__ == "__main__":
    # Ensure Monitoring API is up
    requests.get(f"{MONITORING_API_URL}/", timeout=5).raise_for_status()
    print("✅ Monitoring API is reachable.\n")

    tests = [
        "Is server PRD-APP-01 healthy?",
        "What is the status of PRD-DB-01 and show me its recent logs.",
        "List all running servers.",
        "Give detailed metrics for PRD-APP-02.",
    ]

    for q in tests:
        print("\n" + "=" * 90)
        print("Q:", q)
        print("=" * 90)
        print(ask_monitoring_agent(q, max_tool_calls=2))