"""
Configuration for IT Operations Multi-Agent System
"""

import os
from dotenv import load_dotenv

load_dotenv()

# -------------------------
# Email Configuration
# -------------------------

# Your Gmail address (the one sending alerts)
EMAIL_FROM = os.getenv("EMAIL_FROM")

# App Password from Gmail (NOT your regular password)
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")

# Where to send alerts (can be same as EMAIL_FROM)
EMAIL_TO = os.getenv("EMAIL_TO")

# Gmail SMTP settings (don't change these)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# -------------------------
# Alert Settings
# -------------------------

ALERT_LEVELS = {
    "INFO": {
        "emoji": "ℹ️",
        "color": "blue",
        "send_email": False  # Don't spam email for INFO
    },
    "WARNING": {
        "emoji": "⚠️",
        "color": "yellow",
        "send_email": True
    },
    "CRITICAL": {
        "emoji": "🔴",
        "color": "red",
        "send_email": True
    },
    "SUCCESS": {
        "emoji": "✅",
        "color": "green",
        "send_email": False  # Optional: set True if you want success emails
    }
}

# -------------------------
# Monitoring Settings
# -------------------------

MONITORING_INTERVAL_SECONDS = 30  # Check every 30 seconds
MAX_RESTART_ATTEMPTS = 3
RESTART_TIMEOUT_SECONDS = 10

# Alert thresholds
CPU_ALERT_THRESHOLD = 80.0  # Alert if CPU > 80%
MEMORY_ALERT_THRESHOLD = 80.0  # Alert if memory > 80%

# Critical services (always send email for these)
CRITICAL_SERVICES = ["prod-web-01", "prod-db-01"]