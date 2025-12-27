"""
Incident Response Agent
Handles auto-healing with LLM-based decision making.
Can analyze incidents and choose appropriate healing actions.
"""

# Add project root to Python path
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import json
import time
from typing import Any, Dict, List
from datetime import datetime, timezone

import docker
from docker.errors import NotFound, APIError

from langchain_ollama import ChatOllama
from langchain.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage

from config.config import MAX_RESTART_ATTEMPTS, RESTART_TIMEOUT_SECONDS


# -------------------------
# Configuration
# -------------------------

OLLAMA_MODEL = "llama3.2:latest"


# -------------------------
# Docker Client
# -------------------------

def get_docker_client():
    """Get Docker client."""
    try:
        return docker.from_env()
    except Exception as e:
        raise RuntimeError(f"Cannot connect to Docker: {e}")


# -------------------------
# Core Healing Tools (for LLM)
# -------------------------

@tool
def restart_container_with_retry(container_name: str, max_attempts: int = MAX_RESTART_ATTEMPTS) -> Dict[str, Any]:
    """
    Restart a container with retry logic.
    Attempts multiple restarts if the first one fails.
    
    Args:
        container_name: Name of the container to restart
        max_attempts: Maximum number of restart attempts
    """
    client = get_docker_client()
    
    try:
        container = client.containers.get(container_name)
    except NotFound:
        return {
            "success": False,
            "container": container_name,
            "error": "Container not found",
            "attempts": 0
        }
    
    old_status = container.status
    
    for attempt in range(1, max_attempts + 1):
        try:
            container.restart(timeout=RESTART_TIMEOUT_SECONDS)
            container.reload()
            
            if container.status == "running":
                return {
                    "success": True,
                    "container": container_name,
                    "old_status": old_status,
                    "new_status": container.status,
                    "attempts": attempt,
                    "message": f"Successfully restarted after {attempt} attempt(s)"
                }
        except Exception as e:
            if attempt == max_attempts:
                return {
                    "success": False,
                    "container": container_name,
                    "old_status": old_status,
                    "error": str(e),
                    "attempts": attempt,
                    "message": f"Failed after {attempt} attempts"
                }
            time.sleep(2)
    
    return {
        "success": False,
        "container": container_name,
        "error": "Max attempts reached"
    }


@tool
def check_container_health_status() -> Dict[str, Any]:
    """
    Quick health check of containers with 'environment' label.
    Returns summary without taking action.
    """
    client = get_docker_client()
    
    all_containers = client.containers.list(all=True)
    containers = [c for c in all_containers if 'environment' in c.labels]
    
    running = []
    stopped = []
    
    for container in containers:
        info = {
            "name": container.name,
            "status": container.status,
            "image": container.image.tags[0] if container.image.tags else "unknown",
            "environment": container.labels.get("environment", "unknown"),
            "role": container.labels.get("role", "unknown")
        }
        
        if container.status == "running":
            running.append(info)
        else:
            stopped.append(info)
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(containers),
        "running": len(running),
        "stopped": len(stopped),
        "running_containers": running,
        "stopped_containers": stopped,
        "all_healthy": len(stopped) == 0
    }


# -------------------------
# Tool Registry
# -------------------------

TOOLS = [
    restart_container_with_retry,
    check_container_health_status
]

TOOL_MAP = {t.name: t for t in TOOLS}


# -------------------------
# LLM-Based Incident Response Agent
# -------------------------

def incident_response_agent(issue_description: str) -> Dict[str, Any]:
    """
    LLM-based Incident Response Agent.
    Analyzes incidents and decides what action to take.
    
    Args:
        issue_description: Natural language description of the incident
            Examples:
            - "prod-web-01 is down"
            - "Check all container health"
            - "Database container crashed"
    
    Returns:
        Dict with action taken and results
    """
    llm = ChatOllama(model=OLLAMA_MODEL, temperature=0).bind_tools(TOOLS)
    
    system_prompt = """You are an Incident Response Agent for Docker infrastructure.

Your job:
- Analyze incidents reported by monitoring
- Choose appropriate healing actions
- Use restart_container_with_retry for specific containers
- Use check_container_health_status to assess the situation
- Return clear status reports

Guidelines:
- If a specific container is mentioned, restart it
- If asked to check health, use check_container_health_status
- Always provide clear reasoning for your actions
"""
    
    messages = [HumanMessage(content=system_prompt + "\n\nIncident: " + issue_description)]
    
    # Let LLM decide what to do
    ai = llm.invoke(messages)
    
    if not getattr(ai, "tool_calls", None):
        return {
            "action": "no_action",
            "reasoning": ai.content.strip(),
            "llm_used": True
        }
    
    # Execute the tool the LLM chose
    call = ai.tool_calls[0]
    tool_name = call["name"]
    tool_args = call.get("args", {}) or {}
    
    if tool_name in TOOL_MAP:
        result = TOOL_MAP[tool_name].invoke(tool_args)
        return {
            "action": tool_name,
            "result": result,
            "llm_used": True,
            "reasoning": f"LLM decided to use {tool_name}"
        }
    
    return {"action": "unknown", "error": "Tool not found", "llm_used": True}


# -------------------------
# Direct Functions (for Orchestrator)
# -------------------------

def get_health_status() -> Dict[str, Any]:
    """
    Direct health check (no LLM).
    Fast path for orchestrator.
    """
    return check_container_health_status.invoke({})


def heal_container(container_name: str) -> Dict[str, Any]:
    """
    Direct container healing (no LLM).
    Fast path for orchestrator when action is already determined.
    """
    return restart_container_with_retry.invoke({"container_name": container_name})


def heal_all_containers() -> Dict[str, Any]:
    """
    Heal all unhealthy containers (no LLM).
    Scans and heals - fast deterministic path.
    """
    client = get_docker_client()
    
    all_containers = client.containers.list(all=True)
    containers = [c for c in all_containers if 'environment' in c.labels]
    
    healed = []
    already_healthy = []
    failed_healing = []
    
    for container in containers:
        if container.status == "running":
            already_healthy.append({"name": container.name, "status": "running"})
        else:
            result = restart_container_with_retry.invoke({"container_name": container.name})
            if result.get("success"):
                healed.append(result)
            else:
                failed_healing.append(result)
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_containers": len(containers),
        "healthy_count": len(already_healthy),
        "healed_count": len(healed),
        "failed_count": len(failed_healing),
        "healed_containers": healed,
        "failed_containers": failed_healing,
        "healthy_containers": [c["name"] for c in already_healthy],
        "requires_human_intervention": len(failed_healing) > 0
    }


# -------------------------
# Testing
# -------------------------

if __name__ == "__main__":
    print("=" * 80)
    print("🚨 INCIDENT RESPONSE AGENT TEST")
    print("=" * 80)
    
    # Test 1: Direct health check (no LLM)
    print("\n[TEST 1] Direct Health Check (no LLM)...")
    health = get_health_status()
    print(json.dumps(health, indent=2))
    
    # Test 2: LLM-based incident response
    print("\n[TEST 2] LLM-Based Incident Analysis...")
    if health['stopped'] > 0:
        container_name = health['stopped_containers'][0]['name']
        result = incident_response_agent(f"{container_name} is down, please fix it")
        print(json.dumps(result, indent=2))
    else:
        result = incident_response_agent("Check all container health status")
        print(json.dumps(result, indent=2))
    
    # Test 3: Direct heal all (no LLM)
    if health['stopped'] > 0:
        print("\n[TEST 3] Direct Heal All (no LLM)...")
        result = heal_all_containers()
        print(json.dumps(result, indent=2))
    
    print("\n" + "=" * 80)
    print("✅ Tests Complete")
    print("=" * 80)