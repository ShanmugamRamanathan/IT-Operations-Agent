from fastapi import FastAPI, HTTPException
from datetime import datetime
import json
import random
from pathlib import Path

app = FastAPI(title="Mock Monitoring API", version="1.0")

# Load fake server data
DATA_FILE = Path(__file__).parent / "data" / "servers.json"
with open(DATA_FILE, 'r') as f:
    data = json.load(f)
    SERVERS = {server['hostname']: server for server in data['servers']}

# Fake log templates
LOG_TEMPLATES = [
    "[INFO] Application started successfully",
    "[INFO] Backup completed at {time}",
    "[WARNING] High memory usage detected: {memory}%",
    "[WARNING] Disk space low on C: drive",
    "[ERROR] Connection timeout to database at {time}",
    "[ERROR] Failed to start service: HealthService",
    "[INFO] User login: admin from 10.0.0.5",
    "[INFO] Scheduled task completed: DailyBackup"
]

@app.get("/")
def root():
    return {
        "service": "Mock Monitoring API",
        "version": "1.0",
        "endpoints": [
            "/servers - List all servers",
            "/servers/{hostname}/status - Get server status",
            "/servers/{hostname}/logs - Get server logs",
            "/servers/{hostname}/metrics - Get detailed metrics"
        ]
    }

@app.get("/servers")
def list_servers(status: str = None):
    """List all servers, optionally filter by status"""
    servers_list = list(SERVERS.values())
    
    if status:
        servers_list = [s for s in servers_list if s['status'] == status]
    
    return {
        "total": len(servers_list),
        "servers": servers_list
    }

@app.get("/servers/{hostname}/status")
def get_server_status(hostname: str):
    """Get current status of a specific server"""
    if hostname not in SERVERS:
        raise HTTPException(status_code=404, detail=f"Server {hostname} not found")
    
    server = SERVERS[hostname].copy()
    
    # Add some randomness to simulate live metrics
    if server['status'] == 'running':
        server['cpu_percent'] = round(server['cpu_percent'] + random.uniform(-5, 5), 1)
        server['memory_percent'] = round(server['memory_percent'] + random.uniform(-3, 3), 1)
        server['cpu_percent'] = max(0, min(100, server['cpu_percent']))  # Clamp to 0-100
        server['memory_percent'] = max(0, min(100, server['memory_percent']))
    
    server['last_checked'] = datetime.now().isoformat()
    
    return server

@app.get("/servers/{hostname}/logs")
def get_server_logs(hostname: str, lines: int = 10):
    """Get recent logs from a server"""
    if hostname not in SERVERS:
        raise HTTPException(status_code=404, detail=f"Server {hostname} not found")
    
    server = SERVERS[hostname]
    
    # Generate fake logs
    logs = []
    for i in range(min(lines, 20)):  # Max 20 logs
        template = random.choice(LOG_TEMPLATES)
        log_entry = template.format(
            time=datetime.now().strftime("%H:%M:%S"),
            memory=random.randint(60, 95)
        )
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logs.append(f"[{timestamp}] {log_entry}")
    
    # If server is down, add error logs
    if server['status'] == 'down':
        logs.insert(0, f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [CRITICAL] Server not responding")
        logs.insert(1, f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [ERROR] Connection refused on primary port")
    
    return {
        "hostname": hostname,
        "log_count": len(logs),
        "logs": logs
    }

@app.get("/servers/{hostname}/metrics")
def get_server_metrics(hostname: str, period: str = "1h"):
    """Get detailed performance metrics"""
    if hostname not in SERVERS:
        raise HTTPException(status_code=404, detail=f"Server {hostname} not found")
    
    server = SERVERS[hostname]
    
    # Generate fake historical metrics
    metrics = {
        "hostname": hostname,
        "period": period,
        "current": {
            "cpu_percent": server['cpu_percent'],
            "memory_percent": server['memory_percent'],
            "disk_percent": server['disk_percent']
        },
        "average": {
            "cpu_percent": round(server['cpu_percent'] * 0.8, 1),
            "memory_percent": round(server['memory_percent'] * 0.9, 1),
            "disk_percent": server['disk_percent']
        },
        "peak": {
            "cpu_percent": min(100, server['cpu_percent'] + random.uniform(10, 20)),
            "memory_percent": min(100, server['memory_percent'] + random.uniform(5, 15)),
            "disk_percent": server['disk_percent']
        }
    }
    
    return metrics

@app.post("/servers/{hostname}/restart")
def restart_server(hostname: str):
    """Simulate server restart"""
    if hostname not in SERVERS:
        raise HTTPException(status_code=404, detail=f"Server {hostname} not found")
    
    return {
        "hostname": hostname,
        "status": "restarting",
        "message": f"Server {hostname} restart initiated at {datetime.now().strftime('%H:%M:%S')}",
        "estimated_time": "2-3 minutes"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)