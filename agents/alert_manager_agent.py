"""
Alert Manager Agent
Handles notifications via email when incidents occur.
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, Any, Optional

from config.config import (
    EMAIL_FROM,
    EMAIL_APP_PASSWORD,
    EMAIL_TO,
    SMTP_SERVER,
    SMTP_PORT,
    ALERT_LEVELS,
    CRITICAL_SERVICES
)


# -------------------------
# Email Sending Functions
# -------------------------

def send_email_alert(
    subject: str,
    body: str,
    alert_level: str = "INFO",
    to_email: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send an email alert using Gmail SMTP.
    
    Args:
        subject: Email subject line
        body: Email body (plain text or HTML)
        alert_level: INFO, WARNING, or CRITICAL
        to_email: Override recipient (default from config)
    
    Returns:
        Result dictionary with success status
    """
    try:
        # Get alert emoji
        emoji = ALERT_LEVELS.get(alert_level, {}).get("emoji", "📧")
        subject_with_emoji = f"{emoji} {subject}"
        
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject_with_emoji
        msg["From"] = EMAIL_FROM
        msg["To"] = to_email or EMAIL_TO
        
        # Add body
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <div style="padding: 20px; background-color: #f5f5f5;">
                    <h2 style="color: {'#d32f2f' if alert_level == 'CRITICAL' else '#f57c00' if alert_level == 'WARNING' else '#1976d2'};">
                        {emoji} {alert_level} Alert
                    </h2>
                    <div style="background-color: white; padding: 15px; border-radius: 5px; margin-top: 10px;">
                        <pre style="white-space: pre-wrap; font-family: monospace;">{body}</pre>
                    </div>
                    <p style="color: #666; font-size: 12px; margin-top: 20px;">
                        Sent by IT Operations Agent at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
                    </p>
                </div>
            </body>
        </html>
        """
        
        msg.attach(MIMEText(html_body, "html"))
        
        # Connect to Gmail SMTP
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Secure connection
            server.login(EMAIL_FROM, EMAIL_APP_PASSWORD)
            server.send_message(msg)
        
        return {
            "success": True,
            "message": f"Email sent to {to_email or EMAIL_TO}",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


# -------------------------
# Alert Functions
# -------------------------

def send_container_down_alert(container_name: str, auto_heal_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send alert when a container goes down.
    
    Args:
        container_name: Name of the failed container
        auto_heal_result: Result from incident response agent
    """
    is_critical = container_name in CRITICAL_SERVICES
    alert_level = "CRITICAL" if is_critical else "WARNING"
    
    if auto_heal_result.get("success"):
        # Auto-heal succeeded
        subject = f"Container {container_name} - Auto-Healed Successfully"
        body = f"""
Container Alert: {container_name}

Status: Container was DOWN but has been AUTO-RESTARTED
Severity: {'CRITICAL' if is_critical else 'WARNING'}
Action Taken: Automatic restart
Result: ✅ SUCCESS

Details:
- Old Status: {auto_heal_result.get('old_status', 'unknown')}
- New Status: {auto_heal_result.get('new_status', 'running')}
- Restart Attempts: {auto_heal_result.get('attempts', 1)}
- Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

No further action required. System is operational.
"""
        # For successful auto-heal, send as INFO/SUCCESS (won't spam)
        alert_level = "SUCCESS"
    else:
        # Auto-heal failed - CRITICAL
        subject = f"URGENT: Container {container_name} DOWN - Auto-Heal FAILED"
        body = f"""
🚨 CRITICAL INCIDENT 🚨

Container: {container_name}
Status: DOWN
Severity: CRITICAL

Auto-Healing Result: ❌ FAILED
Error: {auto_heal_result.get('error', 'Unknown error')}
Attempts: {auto_heal_result.get('attempts', 0)}

ACTION REQUIRED:
This container requires immediate manual intervention.

Suggested Actions:
1. Check container logs: docker logs {container_name}
2. Inspect container: docker inspect {container_name}
3. Check host resources: disk space, memory
4. Review application logs for errors

Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
"""
        alert_level = "CRITICAL"
    
    # Check if we should send email for this alert level
    if ALERT_LEVELS.get(alert_level, {}).get("send_email", True):
        return send_email_alert(subject, body, alert_level)
    else:
        # Log only, don't send email
        return {
            "success": True,
            "message": f"Alert logged (level {alert_level}, email not sent)",
            "alert_level": alert_level
        }


def send_monitoring_summary(health_status: Dict[str, Any], healed_containers: list) -> Dict[str, Any]:
    """
    Send periodic monitoring summary email.
    """
    subject = "IT Ops Agent - Monitoring Summary"
    
    body = f"""
Monitoring Summary Report

Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

Container Status:
- Total Containers: {health_status.get('total', 0)}
- Running: {health_status.get('running', 0)}
- Stopped: {health_status.get('stopped', 0)}

Auto-Healing Actions:
- Containers Healed: {len(healed_containers)}
"""
    
    if healed_containers:
        body += "\nHealed Containers:\n"
        for container in healed_containers:
            body += f"  - {container.get('container', 'unknown')} (attempts: {container.get('attempts', 1)})\n"
    
    body += "\nAll systems operational.\n"
    
    return send_email_alert(subject, body, alert_level="INFO")


def send_test_alert() -> Dict[str, Any]:
    """Send a test alert to verify email configuration."""
    subject = "Test Alert - IT Operations Agent"
    body = """
This is a test alert from your IT Operations Multi-Agent System.

If you received this email, your alert configuration is working correctly!

Container monitoring and auto-healing is active.
"""
    return send_email_alert(subject, body, alert_level="INFO")


# -------------------------
# Testing
# -------------------------

if __name__ == "__main__":
    print("=" * 80)
    print("📧 ALERT MANAGER TEST")
    print("=" * 80)
    
    print("\n[TEST] Sending test email...")
    result = send_test_alert()
    
    if result.get("success"):
        print(f"✅ Email sent successfully to {EMAIL_TO}")
        print("Check your inbox!")
    else:
        print(f"❌ Failed to send email: {result.get('error')}")
        print("\nTroubleshooting:")
        print("1. Check EMAIL_FROM in config.py")
        print("2. Check EMAIL_APP_PASSWORD (should be 16 chars from Google)")
        print("3. Make sure 2-Step Verification is enabled on Gmail")