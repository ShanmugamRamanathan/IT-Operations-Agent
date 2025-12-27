"""
Monitoring Agent
Real-time Docker container monitoring with LLM-based analysis.
Uses Docker API to detect container issues and provides intelligent insights.
"""

# Add project root to Python path
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import json
from typing import Any, Dict
from datetime import datetime

import docker
from docker.errors import NotFound, APIError

from langchain_ollama import ChatOllama
from langchain.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage


# -------------------------
# Configuration
# -------------------------

OLLAMA_MODEL = "llama3.2:latest"


# -------------------------
# Docker Client
# -------------------------

def get_docker_client():
    """Get Docker client connected to local Docker daemon."""
    try:
        return docker.from_env()
    except Exception as e:
        raise RuntimeError(f"Cannot connect to Docker. Is Docker Desktop running? Error: {e}")


# -------------------------
# Tools - Real Docker API
# -------------------------

@tool
def list_all_containers() -> Dict[str, Any]:
    """
    List all Docker containers with 'environment' label (managed containers only).
    Returns both running and stopped containers.
    """
    client = get_docker_client()
    all_containers = client.containers.list(all=True)
    
    # Filter: Only containers with 'environment' label
    containers = [c for c in all_containers if 'environment' in c.labels]
    
    result = []
    for c in containers:
        result.append({
            "name": c.name,
            "id": c.short_id,
            "status": c.status,  # running, exited, paused
            "image": c.image.tags[0] if c.image.tags else "unknown",
            "environment": c.labels.get("environment", "unknown"),
            "role": c.labels.get("role", "unknown"),
            "health": "healthy" if c.status == "running" else "unhealthy"
        })
    
    return {
        "total": len(result),
        "containers": result
    }


@tool
def list_running_containers() -> Dict[str, Any]:
    """
    List only containers that are currently running.
    Only monitors containers with 'environment' label.
    """
    client = get_docker_client()
    all_containers = client.containers.list(filters={"status": "running"})
    
    # Filter: Only containers with 'environment' label
    containers = [c for c in all_containers if 'environment' in c.labels]
    
    result = []
    for c in containers:
        result.append({
            "name": c.name,
            "id": c.short_id,
            "status": c.status,
            "image": c.image.tags[0] if c.image.tags else "unknown",
            "environment": c.labels.get("environment", "unknown"),
            "role": c.labels.get("role", "unknown")
        })
    
    return {
        "total": len(result),
        "containers": result
    }


@tool
def get_container_status(container_name: str) -> Dict[str, Any]:
    """
    Get detailed status and resource usage for a specific container.
    Returns health status, uptime, ports, and configuration.
    """
    client = get_docker_client()
    
    try:
        container = client.containers.get(container_name)
    except NotFound:
        return {"error": f"Container '{container_name}' not found"}
    
    # Get basic info without stats (stats can be slow)
    return {
        "name": container.name,
        "id": container.short_id,
        "status": container.status,
        "image": container.image.tags[0] if container.image.tags else "unknown",
        "created": container.attrs['Created'],
        "started_at": container.attrs['State'].get('StartedAt', 'N/A'),
        "finished_at": container.attrs['State'].get('FinishedAt', 'N/A'),
        "exit_code": container.attrs['State'].get('ExitCode', 'N/A'),
        "environment": container.labels.get("environment", "unknown"),
        "role": container.labels.get("role", "unknown"),
        "ports": container.attrs['NetworkSettings']['Ports'],
        "health": "healthy" if container.status == "running" else "unhealthy"
    }


@tool
def get_container_logs(container_name: str, lines: int = 20) -> Dict[str, Any]:
    """
    Get recent logs from a container to diagnose issues.
    Returns last N lines of logs with timestamps.
    """
    client = get_docker_client()
    
    try:
        container = client.containers.get(container_name)
    except NotFound:
        return {"error": f"Container '{container_name}' not found"}
    
    try:
        logs = container.logs(tail=lines, timestamps=True).decode('utf-8').strip()
        log_lines = logs.split('\n') if logs else []
    except Exception as e:
        return {"error": f"Could not retrieve logs: {str(e)}"}
    
    return {
        "container": container_name,
        "log_count": len(log_lines),
        "logs": log_lines[-lines:]  # Last N lines
    }


@tool
def check_unhealthy_containers() -> Dict[str, Any]:
    """
    Quick check to find all unhealthy (stopped/exited) containers.
    Returns list of containers that need attention.
    """
    client = get_docker_client()
    all_containers = client.containers.list(all=True)
    
    # Filter: Only containers with 'environment' label
    containers = [c for c in all_containers if 'environment' in c.labels]
    
    unhealthy = []
    for c in containers:
        if c.status != "running":
            unhealthy.append({
                "name": c.name,
                "status": c.status,
                "image": c.image.tags[0] if c.image.tags else "unknown",
                "environment": c.labels.get("environment", "unknown"),
                "role": c.labels.get("role", "unknown"),
                "exit_code": c.attrs['State'].get('ExitCode', 'N/A')
            })
    
    return {
        "total_checked": len(containers),
        "unhealthy_count": len(unhealthy),
        "unhealthy_containers": unhealthy,
        "all_healthy": len(unhealthy) == 0
    }


# -------------------------
# Tool Registry
# -------------------------

TOOLS = [
    list_all_containers,
    list_running_containers,
    get_container_status,
    get_container_logs,
    check_unhealthy_containers
]

TOOL_MAP = {t.name: t for t in TOOLS}


# -------------------------
# System Prompt
# -------------------------

SYSTEM_PROMPT = """You are a Docker infrastructure monitoring assistant.

Your role:
- Monitor Docker containers (web servers, databases, caches, applications)
- Report on container health and status
- Help diagnose issues by checking logs
- Identify containers that need attention

CRITICAL RULES:
- Base all answers ONLY on tool results you receive
- Do not invent container names, IDs, or logs
- If a container is down, clearly state this and recommend notifying the incident response team
- Be concise and actionable
- When asked about "all" containers, use list_all_containers or check_unhealthy_containers
- You ONLY monitor and report - you do NOT restart containers (that's the incident response agent's job)

Available tools:
- list_all_containers: See all managed containers
- list_running_containers: See only running containers
- get_container_status: Get details about a specific container
- get_container_logs: Read recent logs from a container
- check_unhealthy_containers: Find all containers that are down or unhealthy
"""


# -------------------------
# Agent Function
# -------------------------

def monitor_containers(question: str, max_iterations: int = 3) -> str:
    """
    Docker monitoring agent using LLM-based analysis.
    Monitors real Docker containers and provides intelligent insights.
    
    Args:
        question: Natural language question about container status
        max_iterations: Maximum tool calling iterations
    
    Returns:
        Natural language response with monitoring insights
    
    Examples:
        - "Are all containers healthy?"
        - "What's wrong with prod-web-01?"
        - "Show me logs from the database"
        - "List all running containers"
    """
    llm = ChatOllama(model=OLLAMA_MODEL, temperature=0).bind_tools(TOOLS)
    messages = [HumanMessage(content=SYSTEM_PROMPT + "\n\nUser question: " + question)]
    
    for iteration in range(max_iterations):
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
    
    # If max iterations reached, ask LLM for final answer
    final = llm.invoke(messages)
    return final.content.strip()


# -------------------------
# Direct Functions (for orchestrator if needed)
# -------------------------

def get_all_containers() -> Dict[str, Any]:
    """Direct function to get all containers (no LLM)."""
    return list_all_containers.invoke({})


def get_unhealthy_containers() -> Dict[str, Any]:
    """Direct function to check unhealthy containers (no LLM)."""
    return check_unhealthy_containers.invoke({})


# -------------------------
# Testing
# -------------------------

if __name__ == "__main__":
    print("=" * 80)
    print("🐳 DOCKER MONITORING AGENT TEST")
    print("=" * 80)
    
    # Check Docker is accessible
    try:
        client = get_docker_client()
        version = client.version()['Version']
        print(f"✅ Connected to Docker Engine (version {version})\n")
    except Exception as e:
        print(f"❌ Cannot connect to Docker: {e}")
        print("Make sure Docker Desktop is running!")
        exit(1)
    
    # Test questions
    test_questions = [
        "Are all containers healthy?",
        "List all running containers",
        "What is the status of prod-web-01?",
        "Show me the last 10 logs from prod-db-01",
        "Which containers need attention?"
    ]
    
    for i, q in enumerate(test_questions, 1):
        print("\n" + "=" * 80)
        print(f"[TEST {i}] {q}")
        print("=" * 80)
        try:
            response = monitor_containers(q)
            print(response)
        except Exception as e:
            print(f"❌ Error: {e}")
        print()
    
    print("=" * 80)
    print("✅ Tests Complete")
    print("=" * 80)