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
    """List all Docker containers (running and stopped) with their status."""
    client = get_docker_client()
    containers = client.containers.list(all=True)
    
    result = []
    for c in containers:
        result.append({
            "name": c.name,
            "id": c.short_id,
            "status": c.status,  # running, exited, paused
            "image": c.image.tags[0] if c.image.tags else "unknown",
            "labels": c.labels
        })
    
    return {
        "total": len(result),
        "containers": result
    }


@tool
def get_container_status(container_name: str) -> Dict[str, Any]:
    """Get detailed status and resource usage for a specific container."""
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
        "labels": container.labels,
        "ports": container.attrs['NetworkSettings']['Ports'],
        "health": "healthy" if container.status == "running" else "unhealthy"
    }


@tool
def get_container_logs(container_name: str, lines: int = 20) -> Dict[str, Any]:
    """Get recent logs from a container."""
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
def restart_container(container_name: str) -> Dict[str, Any]:
    """Restart a container. Use this when a container is unhealthy or stopped."""
    client = get_docker_client()
    
    try:
        container = client.containers.get(container_name)
    except NotFound:
        return {"error": f"Container '{container_name}' not found"}
    
    try:
        old_status = container.status
        container.restart(timeout=10)
        # Reload to get new status
        container.reload()
        return {
            "success": True,
            "container": container_name,
            "message": f"Container {container_name} restarted successfully",
            "old_status": old_status,
            "new_status": container.status
        }
    except APIError as e:
        return {
            "success": False,
            "container": container_name,
            "error": str(e)
        }


@tool
def list_running_containers() -> Dict[str, Any]:
    """List only containers that are currently running."""
    client = get_docker_client()
    containers = client.containers.list(filters={"status": "running"})
    
    result = []
    for c in containers:
        result.append({
            "name": c.name,
            "id": c.short_id,
            "status": c.status,
            "image": c.image.tags[0] if c.image.tags else "unknown",
            "labels": c.labels
        })
    
    return {
        "total": len(result),
        "containers": result
    }


# -------------------------
# Tool Registry
# -------------------------

TOOLS = [
    list_all_containers,
    list_running_containers,
    get_container_status,
    get_container_logs,
    restart_container
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
- Suggest actions when containers are unhealthy

CRITICAL RULES:
- Base all answers ONLY on tool results you receive
- Do not invent container names, IDs, or logs
- If a container is down, clearly state this and suggest restarting
- Be concise and actionable
- When asked about "all" containers, use list_all_containers or list_running_containers
"""


# -------------------------
# Agent Function
# -------------------------

def ask_docker_agent(question: str, max_iterations: int = 3) -> str:
    """
    Docker monitoring agent using LangChain tool calling.
    Monitors real Docker containers and can take actions.
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
# Main - Test Cases
# -------------------------

if __name__ == "__main__":
    print("=" * 80)
    print("🐳 DOCKER MONITORING AGENT")
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
        "List all running containers",
        "What is the status of prod-web-01?",
        "Show me logs from prod-db-01",
        "Are there any containers that need attention?",
        "Restart prod-web-01"
    ]
    
    for q in test_questions:
        print("\n" + "=" * 80)
        print(f"Q: {q}")
        print("=" * 80)
        try:
            response = ask_docker_agent(q)
            print(response)
        except Exception as e:
            print(f"Error: {e}")
        print()