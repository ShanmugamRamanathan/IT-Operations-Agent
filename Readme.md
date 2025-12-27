# AI-Powered IT Operations Agent

An AI-driven, multi-agent system for **monitoring**, **diagnosing**, and **auto-healing** Docker-based production environments. It uses LLMs for root-cause analysis and traditional automation for fast, reliable healing.

---

## Features

- **Real-time Docker monitoring**
- **AI-powered diagnosis** of container failures (status + logs + root cause)
- **Automated healing** with retry logic
- **Email alerts** via Gmail SMTP (HTML formatted)
- **Label-based filtering** (only manage production containers)
- **Check vs Heal modes**:
  - Check: Diagnose + alert, no changes
  - Heal: Diagnose + auto-restart + verify
- **Continuous or one-shot operation**

---

## Architecture

```
                          ┌───────────────────────────┐
                          │        Orchestrator       │
                          │  (orchestrator.py)        │
                          └───────────┬───────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        │                             │                             │
┌───────────────┐            ┌────────────────┐           ┌────────────────────┐
│ Monitoring    │            │ Incident       │           │ Alert Manager       │
│ Agent         │            │ Response Agent │           │ Agent               │
│ (docker_      │            │ (incident_     │           │ (alert_manager_     │
│ monitoring_   │            │ response_      │           │ agent.py)           │
│ agent.py)     │            │ agent.py)      │           └────────────────────┘
└───────────────┘            └────────────────┘
   ▲   LLM (LLM-based)            ▲  Direct + LLM
   │                              │
 Docker API & Logs           Docker API (health, restart)
```

---

## Components Overview

- `config/config.py`  
  Central configuration: email, alert levels, monitoring interval, restart settings.

- `agents/docker_monitoring_agent.py`  
  LLM-based monitoring & diagnosis:
  - Lists containers
  - Fetches status & logs
  - Answers natural language questions about health/issues

- `agents/incident_response_agent.py`  
  Healing & status:
  - `get_health_status()` – direct health check for orchestrator
  - `heal_container(name)` – restart with retry logic
  - `heal_all_containers()` – heal all unhealthy containers
  - `incident_response_agent()` – optional LLM-based decision agent

- `agents/alert_manager_agent.py`  
  Email alerting via Gmail:
  - HTML emails with severity levels
  - Test alert sender
  - Container-down and summary alerts

- `agents/orchestrator.py`  
  Main entrypoint:
  - Coordinates monitoring, AI diagnosis, healing, and alerts
  - Modes: `check` (no healing), `heal` (auto-heal)
  - One-time or continuous operation

- `docker-compose.yml`  
  Example production stack:
  - `prod-web-01` (nginx)
  - `prod-app-01` (python app)
  - `prod-db-01` (postgres)
  - `prod-cache-01` (redis)  
  All labeled with `environment=production` so the agents only manage these.

---

## Prerequisites

- Python 3.11+
- Docker & Docker Compose installed and running
- Ollama installed and a model like `llama3.2` pulled
- Gmail account with:
  - 2FA enabled
  - App password generated (16-character)

---

## Setup

### 1. Clone the Repository

```
git clone <your-repo-url> IT-Operations-Agent
cd IT-Operations-Agent
```

### 2. Create and Activate Virtual Environment (Optional but Recommended)

```
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```
pip install -r requirements.txt
```

*(Create `requirements.txt` if not present, e.g. using your current environment.)*

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```
cp .env.example .env
```

Edit `.env`:

```
EMAIL_FROM=your-email@gmail.com
EMAIL_APP_PASSWORD=your-16-char-google-app-password
EMAIL_TO=your-alerts-recipient@gmail.com
```

### 5. Configure `config/config.py`

Ensure at least:

```
MONITORING_INTERVAL_SECONDS = 30
MAX_RESTART_ATTEMPTS = 3
RESTART_TIMEOUT_SECONDS = 10

CRITICAL_SERVICES = ["prod-web-01", "prod-db-01"]
```

Alert levels and SMTP settings are already wired to the environment variables.

---

## Start Sample Production Stack

```
docker-compose up -d
```

Verify:

```
docker ps
# You should see:
# prod-web-01, prod-app-01, prod-db-01, prod-cache-01
```

---

## Testing Individual Agents

### 1. Test Alert Manager

```
python agents/alert_manager_agent.py
```

- Sends a test email using the configured Gmail account.
- Check your inbox (and spam) for confirmation.

### 2. Test Incident Response Agent

Healthy scenario:

```
python agents/incident_response_agent.py
```

You should see a health report and a message that all containers are healthy.

Failure scenario:

```
docker stop prod-web-01
python agents/incident_response_agent.py
```

Expected:
- Detects `prod-web-01` as exited
- Attempts auto-heal (restart)
- Shows success/failure details

### 3. Test LLM Monitoring Agent

```
python agents/docker_monitoring_agent.py
```

It will run several test questions like:

- “Are all containers healthy?”
- “What is the status of prod-web-01?”
- “Which containers need attention?”

---

## Orchestrator Usage (Main Entry)

### 1. One-Time Check (AI Diagnosis Only, No Healing)

```
python agents/orchestrator.py --mode check
```

- Runs a single health check.
- For any failed container:
  - AI performs multi-step diagnosis:
    - Status & exit code analysis
    - Recent logs analysis
    - Root cause & recommendation
  - Sends an email alert.
- Does **not** restart containers.

### 2. One-Time Heal (AI Diagnosis + Auto-Heal)

```
python agents/orchestrator.py --mode heal
```

For each unhealthy container:

1. **Pre-healing AI diagnosis**
   - Analyze logs & status
   - Check if restart is safe
2. **Healing**
   - Attempts restart with retry logic
3. **Post-healing AI verification**
   - Confirms container is healthy
4. **Alert**
   - Sends detailed email (success or failure)

### 3. Continuous Monitoring (Every N Seconds)

**Check-only mode:**

```
python agents/orchestrator.py --mode check --continuous
```

**Heal mode:**

```
python agents/orchestrator.py --mode heal --continuous
```

Behavior:
- Every `MONITORING_INTERVAL_SECONDS`:
  - Check status of all labeled containers.
  - If failures:
    - In `check` mode: AI diagnosis + alert (no restart).
    - In `heal` mode: AI diagnosis + auto-heal + verification + alert.

Stop with `Ctrl + C`.

---

## How AI Diagnosis Works

The LLM-powered monitoring is used to:

1. **Inspect container status**
   - Exit code
   - Timestamps (start/stop)
   - Image, role, labels

2. **Parse logs**
   - Last N lines
   - Identify errors/warnings/failure patterns

3. **Perform root-cause analysis**
   - Distinguish:
     - Configuration issues
     - Resource constraints
     - Dependency issues
     - Application crashes
   - Recommend:
     - Whether restart is safe
     - What manual actions may be needed

The orchestrator uses this AI diagnosis both **before** healing (safety + insight) and **after** healing (verification).

---

## Design Choices

- **Direct functions for actions**, LLMs for *diagnosis/explanation*:
  - Healing runs via deterministic logic for speed and reliability.
  - The LLM never directly executes restarts; it advises.

- **Label-based filtering**:
  - Only containers with an `environment` label (e.g., `production`) are managed.
  - Prevents interfering with random/local containers.

- **Config-driven behavior**:
  - All critical thresholds and email settings are in `config/config.py` + `.env`.

- **Modes (check vs heal)**:
  - Check mode is safe for staging / observability-only setups.
  - Heal mode is for production automation.

---

## Folder Structure (Example)

```
IT-Operations-Agent/
├── agents/
│   ├── docker_monitoring_agent.py
│   ├── incident_response_agent.py
│   ├── alert_manager_agent.py
│   └── orchestrator.py
├── config/
│   └── config.py
├── docker-compose.yml
├── logs/
│   └── alerts.log
├── .env
├── .env.example
├── requirements.txt
└── README.md
```

---

## Demo Scenario (For Interviews)

1. Start stack:

   ```
   docker-compose up -d
   ```

2. Show containers:

   ```
   docker ps
   ```

3. Simulate incident:

   ```
   docker stop prod-web-01
   ```

4. Run **check mode**:

   ```
   python agents/orchestrator.py --mode check
   ```

   - Show AI diagnosis for `prod-web-01`.
   - Explain the root-cause analysis.

5. Run **heal mode**:

   ```
   python agents/orchestrator.py --mode heal
   ```

   - Show AI pre-healing analysis.
   - Show successful restart & AI verification.

6. Show alerts log:

   ```
   tail -20 logs/alerts.log
   ```

7. Show alert email in inbox.

---

## Possible Extensions

- Slack or Teams integration for alerts
- Web dashboard (Flask/FastAPI) for status & history
- Metrics export (Prometheus/Grafana)
- Kubernetes support via the Kubernetes Python client
- Noise reduction (alert aggregation, incident correlation)

---

Developer
Shanmugam Ramanathan