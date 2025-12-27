"""
Orchestrator Agent
Coordinates monitoring, alerting, and healing actions with AI-powered diagnostics.
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

from agents.alert_manager_agent import send_container_down_alert
from agents.incident_response_agent import (
    get_health_status,
    heal_container,
    heal_all_containers
)
# Import LLM-based monitoring for intelligent diagnosis
from agents.docker_monitoring_agent import monitor_containers

from config.config import MONITORING_INTERVAL_SECONDS


# -------------------------
# Orchestration Logic
# -------------------------

def orchestrate_check_only() -> Dict[str, Any]:
    """
    ONE-TIME health check with AI-powered diagnosis.
    No healing - only monitoring, AI analysis, and alerting.
    
    Returns:
        Dict with health status and any alerts sent
    """
    print("=" * 80)
    print("🔍 ONE-TIME HEALTH CHECK (AI-Powered Diagnosis)")
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
            role = container.get('role', 'unknown')
            
            print(f"\n{'=' * 80}")
            print(f"🚨 INCIDENT DETECTED: {container_name}")
            print(f"   Role: {role}")
            print(f"   Status: {status}")
            print(f"   Mode: CHECK ONLY (no auto-healing)")
            print("=" * 80)
            
            # ================================
            # AI DIAGNOSIS - Step 1: Check Status
            # ================================
            print(f"\n🤖 AI Analysis Step 1: Checking container details...")
            print("-" * 80)
            try:
                status_analysis = monitor_containers(
                    f"Get detailed status of {container_name} including when it stopped and exit code"
                )
                print(status_analysis)
            except Exception as e:
                print(f"⚠️  AI analysis failed: {e}")
            print("-" * 80)
            
            # ================================
            # AI DIAGNOSIS - Step 2: Check Logs
            # ================================
            print(f"\n🤖 AI Analysis Step 2: Analyzing recent logs...")
            print("-" * 80)
            try:
                log_analysis = monitor_containers(
                    f"Show me the last 15 lines of logs from {container_name} and identify any errors or warnings"
                )
                print(log_analysis)
            except Exception as e:
                print(f"⚠️  Log analysis failed: {e}")
            print("-" * 80)
            
            # ================================
            # AI DIAGNOSIS - Step 3: Root Cause Analysis
            # ================================
            print(f"\n🤖 AI Analysis Step 3: Root cause diagnosis...")
            print("-" * 80)
            try:
                root_cause = monitor_containers(
                    f"Based on the status and logs of {container_name}, what are the most likely causes for this failure? "
                    f"Consider: configuration issues, resource constraints, dependency failures, or application errors."
                )
                print(root_cause)
            except Exception as e:
                print(f"⚠️  Root cause analysis failed: {e}")
            print("-" * 80)
            
            # Send alert with diagnosis summary
            print(f"\n📧 Sending alert to operations team...")
            alert_result = send_container_down_alert(
                container_name=container_name,
                auto_heal_result={
                    "success": False,
                    "error": "Check mode - no healing attempted (awaiting manual intervention)",
                    "old_status": status,
                    "attempts": 0
                }
            )
            
            if alert_result.get('success'):
                print(f"   ✅ Alert sent successfully")
            else:
                print(f"   ⚠️  Alert logged to file")
            
            print(f"\n{'=' * 80}\n")
    else:
        print("\n✅ All containers healthy")
        
        # Optional: Get AI health summary even when all is well
        print(f"\n🤖 AI Health Summary:")
        print("-" * 80)
        try:
            summary = monitor_containers(
                "All containers are running. Provide a brief health summary and any recommendations."
            )
            print(summary)
        except Exception as e:
            print(f"⚠️  Summary generation failed: {e}")
        print("-" * 80)
    
    print()
    print("=" * 80)
    print("✅ Check Complete")
    print("=" * 80)
    
    return health


def orchestrate_heal_once() -> Dict[str, Any]:
    """
    ONE-TIME healing cycle with AI-powered diagnosis.
    Monitor + AI diagnosis + auto-heal + alert.
    
    Returns:
        Dict with health status and healing results
    """
    print("=" * 80)
    print("🔧 ONE-TIME AUTO-HEAL (AI-Powered Diagnosis)")
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
        
        # HEAL MODE - AI DIAGNOSIS + AUTO-HEALING
        for container in health['stopped_containers']:
            container_name = container['name']
            status = container['status']
            role = container.get('role', 'unknown')
            
            print(f"\n{'=' * 80}")
            print(f"🚨 INCIDENT DETECTED: {container_name}")
            print(f"   Role: {role}")
            print(f"   Status: {status}")
            print(f"   Mode: HEAL (AI diagnosis + auto-restart)")
            print("=" * 80)
            
            # ================================
            # AI DIAGNOSIS - Before Healing
            # ================================
            print(f"\n🤖 Pre-Healing AI Diagnosis:")
            print("-" * 80)
            
            # Step 1: Check what went wrong
            print("\n📋 Analyzing failure reason...")
            try:
                failure_analysis = monitor_containers(
                    f"Container {container_name} is {status}. Check its logs for the last 20 lines "
                    f"and tell me what caused it to fail. Look for error messages, exit codes, or crash logs."
                )
                print(failure_analysis)
            except Exception as e:
                print(f"⚠️  Analysis failed: {e}")
            
            # Step 2: Check if restart is safe
            print(f"\n🔍 Checking if restart is safe...")
            try:
                restart_safety = monitor_containers(
                    f"Based on the failure of {container_name}, is it safe to restart? "
                    f"Are there any configuration issues or dependencies that need fixing first?"
                )
                print(restart_safety)
            except Exception as e:
                print(f"⚠️  Safety check failed: {e}")
            
            print("-" * 80)
            
            # ================================
            # HEALING ACTION
            # ================================
            print(f"\n🔧 Attempting auto-heal...")
            heal_result = heal_container(container_name)
            
            if heal_result.get('success'):
                print(f"   ✅ Auto-heal successful! Container restarted.")
                print(f"   📊 Restart attempts: {heal_result.get('attempts', 1)}")
                print(f"   📊 Old status: {heal_result.get('old_status')}")
                print(f"   📊 New status: {heal_result.get('new_status')}")
                
                # ================================
                # AI DIAGNOSIS - Post-Healing Verification
                # ================================
                print(f"\n🤖 Post-Healing AI Verification:")
                print("-" * 80)
                
                # Wait a moment for container to stabilize
                print("⏳ Waiting 3 seconds for container to stabilize...")
                time.sleep(3)
                
                try:
                    verification = monitor_containers(
                        f"Container {container_name} was just restarted. Check its current status and recent logs "
                        f"to verify it's running properly without errors."
                    )
                    print(verification)
                except Exception as e:
                    print(f"⚠️  Verification failed: {e}")
                
                print("-" * 80)
                
            else:
                print(f"   ❌ Auto-heal FAILED: {heal_result.get('error')}")
                print(f"   📊 Attempts made: {heal_result.get('attempts', 0)}")
                
                # ================================
                # AI DIAGNOSIS - Why Healing Failed
                # ================================
                print(f"\n🤖 AI Analysis - Why Healing Failed:")
                print("-" * 80)
                try:
                    failure_reason = monitor_containers(
                        f"Container {container_name} failed to restart after {heal_result.get('attempts', 0)} attempts. "
                        f"Check logs and status to determine why the restart failed. What manual intervention is needed?"
                    )
                    print(failure_reason)
                except Exception as e:
                    print(f"⚠️  Failure analysis unavailable: {e}")
                print("-" * 80)
            
            # Send alert with full diagnosis
            print(f"\n📧 Sending detailed alert...")
            alert_result = send_container_down_alert(
                container_name=container_name,
                auto_heal_result=heal_result
            )
            
            if alert_result.get('success'):
                print(f"   ✅ Alert sent successfully")
            else:
                print(f"   ⚠️  Alert logged to file")
            
            print(f"\n{'=' * 80}\n")
    else:
        print("\n✅ All containers healthy")
    
    print()
    print("=" * 80)
    print("✅ Heal Complete")
    print("=" * 80)
    
    return health


def orchestrate_continuous(mode: str = "check"):
    """
    CONTINUOUS monitoring loop with AI-powered diagnostics.
    Runs until interrupted (Ctrl+C).
    
    Args:
        mode: "check" (monitor + AI diagnosis only) or "heal" (monitor + AI diagnosis + heal)
    """
    mode_label = "CHECK MODE (AI diagnosis, no healing)" if mode == "check" else "HEAL MODE (AI diagnosis + auto-healing)"
    
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
                    
                    # ================================
                    # AI QUICK DIAGNOSIS (Continuous mode - lighter analysis)
                    # ================================
                    print(f"\n🤖 AI Quick Diagnosis:")
                    print("-" * 60)
                    try:
                        quick_diagnosis = monitor_containers(
                            f"Container {container_name} is {status}. Quick diagnosis: "
                            f"check last 10 log lines and identify the issue."
                        )
                        print(quick_diagnosis)
                    except Exception as e:
                        print(f"⚠️  Diagnosis unavailable: {e}")
                    print("-" * 60)
                    
                    if mode == "heal":
                        # HEAL MODE - Attempt healing
                        print(f"\n🔧 HEAL MODE: Attempting auto-heal...")
                        
                        heal_result = heal_container(container_name)
                        
                        if heal_result.get('success'):
                            print(f"   ✅ Auto-heal successful!")
                            
                            # Quick verification
                            time.sleep(2)
                            try:
                                verify = monitor_containers(
                                    f"Verify {container_name} is now running properly"
                                )
                                print(f"\n🤖 Verification: {verify}")
                            except:
                                pass
                        else:
                            print(f"   ❌ Auto-heal failed: {heal_result.get('error')}")
                        
                        # Send alert
                        send_container_down_alert(container_name, heal_result)
                    else:
                        # CHECK MODE - Alert only
                        print(f"\n⚠️  CHECK MODE: Not healing, only alerting")
                        
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
                print("\n✅ All containers healthy")
            
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
        description="IT Operations Orchestrator - AI-Powered Container Monitoring & Healing",
        epilog="""
Examples:
  # One-time check with AI diagnosis (no healing)
  python orchestrator.py --mode check
  
  # One-time heal with full AI analysis
  python orchestrator.py --mode heal
  
  # Continuous monitoring with AI quick diagnosis
  python orchestrator.py --mode check --continuous
  
  # Continuous auto-healing with AI verification
  python orchestrator.py --mode heal --continuous
        """
    )
    
    parser.add_argument(
        "--mode",
        choices=["check", "heal"],
        default="check",
        help="Operating mode: 'check' (AI diagnosis only) or 'heal' (AI diagnosis + auto-heal)"
    )
    
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuously (loop every N seconds). Without this flag, runs once and exits."
    )
    
    args = parser.parse_args()
    
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  🤖 AI-POWERED IT OPERATIONS ORCHESTRATOR  ".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "═" * 78 + "╝")
    print()
    
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