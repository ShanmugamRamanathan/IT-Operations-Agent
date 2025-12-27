"""
Orchestrator Agent
Coordinates monitoring, alerting, and healing actions.
"""

# Add project root to Python path
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import time
import argparse
from datetime import datetime
from typing import Dict, Any

# Fixed imports - removed monitoring_agent (not needed)
from agents.alert_manager_agent import send_container_down_alert
from agents.incident_response_agent import (
    get_health_status,
    heal_container,
    heal_all_containers
)

from config.config import MONITORING_INTERVAL_SECONDS


# -------------------------
# Orchestration Logic
# -------------------------

def orchestrate_check_only() -> Dict[str, Any]:
    """
    ONE-TIME health check (no healing, only monitoring + alerting).
    
    Returns:
        Dict with health status and any alerts sent
    """
    print("=" * 80)
    print("🔍 ONE-TIME HEALTH CHECK")
    print("=" * 80)
    print()
    
    # Get current health status
    health = get_health_status()
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("=" * 80)
    print(f"🔍 Monitoring Cycle #1 - {timestamp}")
    print("=" * 80)
    
    running_count = health['running']
    total_count = health['total']
    stopped_count = health['stopped']
    
    print(f"📊 Container Status: {running_count}/{total_count} running")
    
    if stopped_count > 0:
        print(f"⚠️  Found {stopped_count} unhealthy container(s)")
        
        # ALERT ONLY - NO HEALING IN CHECK MODE
        for container in health['stopped_containers']:
            container_name = container['name']
            status = container['status']
            
            print(f"\n🚨 Incident Detected: {container_name} is {status}")
            print(f"⚠️  CHECK MODE: Not healing, only alerting")
            
            # Send alert using your email function
            print(f"📧 Sending alert...")
            
            # Create mock auto_heal_result for alert (no healing in check mode)
            alert_result = send_container_down_alert(
                container_name=container_name,
                auto_heal_result={
                    "success": False,
                    "error": "Check mode - no healing attempted",
                    "old_status": status,
                    "attempts": 0
                }
            )
            
            if alert_result.get('success'):
                print(f"   ✅ Alert sent")
            else:
                print(f"   ⚠️  Alert logged (email may not be sent)")
    else:
        print("✅ All containers healthy")
    
    print()
    print("=" * 80)
    print("✅ Check Complete")
    print("=" * 80)
    
    return health


def orchestrate_heal_once() -> Dict[str, Any]:
    """
    ONE-TIME healing cycle (monitor + heal + alert).
    
    Returns:
        Dict with health status and healing results
    """
    print("=" * 80)
    print("🔧 ONE-TIME AUTO-HEAL")
    print("=" * 80)
    print()
    
    # Get current health status
    health = get_health_status()
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("=" * 80)
    print(f"🔍 Monitoring Cycle #1 - {timestamp}")
    print("=" * 80)
    
    running_count = health['running']
    total_count = health['total']
    stopped_count = health['stopped']
    
    print(f"📊 Container Status: {running_count}/{total_count} running")
    
    if stopped_count > 0:
        print(f"⚠️  Found {stopped_count} unhealthy container(s)")
        
        # HEAL MODE - ATTEMPT HEALING
        for container in health['stopped_containers']:
            container_name = container['name']
            status = container['status']
            
            print(f"\n🚨 Incident Detected: {container_name} is {status}")
            print(f"🔧 HEAL MODE: Attempting auto-heal...")
            
            # Attempt to heal
            heal_result = heal_container(container_name)
            
            if heal_result.get('success'):
                print(f"   ✅ Auto-heal successful! Container restarted.")
            else:
                print(f"   ❌ Auto-heal failed: {heal_result.get('error')}")
            
            # Send alert with heal result
            print(f"📧 Sending alert...")
            alert_result = send_container_down_alert(
                container_name=container_name,
                auto_heal_result=heal_result
            )
            
            if alert_result.get('success'):
                print(f"   ✅ Alert sent")
            else:
                print(f"   ⚠️  Alert logged")
    else:
        print("✅ All containers healthy")
    
    print()
    print("=" * 80)
    print("✅ Heal Complete")
    print("=" * 80)
    
    return health


def orchestrate_continuous(mode: str = "check"):
    """
    CONTINUOUS monitoring loop.
    Runs until interrupted (Ctrl+C).
    
    Args:
        mode: "check" (monitor only) or "heal" (monitor + heal)
    """
    mode_label = "CHECK MODE (monitor + alert only)" if mode == "check" else "HEAL MODE (monitor + heal + alert)"
    
    print("=" * 80)
    print(f"🔄 CONTINUOUS MONITORING - {mode_label}")
    print(f"⏱️  Interval: {MONITORING_INTERVAL_SECONDS} seconds")
    print("   Press Ctrl+C to stop")
    print("=" * 80)
    print()
    
    cycle_count = 0
    
    try:
        while True:
            cycle_count += 1
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print("=" * 80)
            print(f"🔍 Monitoring Cycle #{cycle_count} - {timestamp}")
            print("=" * 80)
            
            # Get current health status
            health = get_health_status()
            
            running_count = health['running']
            total_count = health['total']
            stopped_count = health['stopped']
            
            print(f"📊 Container Status: {running_count}/{total_count} running")
            
            if stopped_count > 0:
                print(f"⚠️  Found {stopped_count} unhealthy container(s)")
                
                for container in health['stopped_containers']:
                    container_name = container['name']
                    status = container['status']
                    
                    print(f"\n🚨 Incident Detected: {container_name} is {status}")
                    
                    if mode == "heal":
                        # HEAL MODE - Attempt healing
                        print(f"🔧 HEAL MODE: Attempting auto-heal...")
                        
                        heal_result = heal_container(container_name)
                        
                        if heal_result.get('success'):
                            print(f"   ✅ Auto-heal successful!")
                        else:
                            print(f"   ❌ Auto-heal failed: {heal_result.get('error')}")
                        
                        # Send alert with heal result
                        send_container_down_alert(container_name, heal_result)
                    else:
                        # CHECK MODE - Alert only (no healing)
                        print(f"⚠️  CHECK MODE: Not healing, only alerting")
                        
                        # Send alert without healing
                        send_container_down_alert(
                            container_name=container_name,
                            auto_heal_result={
                                "success": False,
                                "error": "Check mode - no healing attempted",
                                "old_status": status,
                                "attempts": 0
                            }
                        )
                        print(f"   ✅ Alert sent")
            else:
                print("✅ All containers healthy")
            
            print(f"\n⏳ Next check in {MONITORING_INTERVAL_SECONDS} seconds...")
            print()
            
            time.sleep(MONITORING_INTERVAL_SECONDS)
    
    except KeyboardInterrupt:
        print()
        print("=" * 80)
        print("🛑 Monitoring stopped by user")
        print(f"📊 Total cycles completed: {cycle_count}")
        print("=" * 80)


# -------------------------
# CLI
# -------------------------

def main():
    parser = argparse.ArgumentParser(
        description="IT Operations Orchestrator - Coordinates monitoring, alerting, and healing"
    )
    
    parser.add_argument(
        "--mode",
        choices=["check", "heal"],
        default="check",
        help="Operating mode: 'check' (monitor + alert only) or 'heal' (monitor + heal + alert)"
    )
    
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuously (loop every N seconds). Without this flag, runs once and exits."
    )
    
    args = parser.parse_args()
    
    if args.continuous:
        # Continuous monitoring loop
        orchestrate_continuous(mode=args.mode)
    else:
        # One-time execution
        if args.mode == "check":
            orchestrate_check_only()
        else:
            orchestrate_heal_once()


if __name__ == "__main__":
    main()