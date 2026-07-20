"""
Health Check and System Diagnostics Routers.
Monitors database latency, CPU averages, memory footprints and platform stats.
"""

import os
import sys
import time
import platform
from datetime import datetime
from fastapi import APIRouter, Response
from api import database
from api.utils.api_response import ApiResponse

router = APIRouter()

app_start_time = time.time()


def get_system_load() -> list:
    """Safely fetch CPU load averages. Returns [0.0, 0.0, 0.0] on Windows fallbacks."""
    getloadavg = getattr(os, "getloadavg", None)
    if getloadavg is not None:
        return list(getloadavg())
    return [0.0, 0.0, 0.0]


def get_memory_info() -> tuple:
    """Fetch total memory, free memory, and usage percentage (ctypes on Windows)."""
    free_mem = 0
    total_mem = 0
    
    if sys.platform == "win32":
        try:
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_uint64),
                    ("ullAvailPhys", ctypes.c_uint64),
                    ("ullTotalPageFile", ctypes.c_uint64),
                    ("ullAvailPageFile", ctypes.c_uint64),
                    ("ullTotalVirtual", ctypes.c_uint64),
                    ("ullAvailVirtual", ctypes.c_uint64),
                    ("ullAvailExtendedVirtual", ctypes.c_uint64),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            total_mem = stat.ullTotalPhys
            free_mem = stat.ullAvailPhys
        except Exception:
            total_mem = 16 * 1024 * 1024 * 1024  # 16 GB fallback
            free_mem = 8 * 1024 * 1024 * 1024    # 8 GB fallback
    else:
        try:
            with open('/proc/meminfo', 'r') as f:
                lines = f.readlines()
            mem = {}
            for line in lines:
                parts = line.split(':')
                if len(parts) == 2:
                    mem[parts[0].strip()] = int(parts[1].replace('kB', '').strip()) * 1024
            total_mem = mem.get('MemTotal', 0)
            free_mem = mem.get('MemFree', 0)
        except Exception:
            total_mem = 16 * 1024 * 1024 * 1024
            free_mem = 8 * 1024 * 1024 * 1024
            
    usage_pct = ((total_mem - free_mem) / total_mem) * 100.0 if total_mem > 0 else 0.0
    return total_mem, free_mem, usage_pct


def get_process_memory() -> int:
    """Fetch process resident memory size (RSS)."""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss
    except Exception:
        return 120 * 1024 * 1024  # 120 MB fallback


# --- Routes ---

@router.get("")
async def health_check(response: Response):
    """Retrieve system health and database connectivity diagnostics."""
    db_status = "UP"
    db_latency = 0
    
    try:
        db_start = time.time()
        await database.query("SELECT 1")
        db_latency = int((time.time() - db_start) * 1000)
    except Exception:
        db_status = "DOWN"
        
    total_mem, free_mem, usage_pct = get_memory_info()
    rss_bytes = get_process_memory()
    
    data = {
        "status": "HEALTHY" if db_status == "UP" else "UNHEALTHY",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "uptimeSeconds": time.time() - app_start_time,
        "services": {
            "database": {
                "status": db_status,
                "latencyMs": db_latency
            }
        },
        "system": {
            "platform": sys.platform,
            "arch": platform.machine(),
            "cpuLoadAvg": get_system_load(),
            "memory": {
                "freeBytes": free_mem,
                "totalBytes": total_mem,
                "usagePercentage": usage_pct
            },
            "processMemory": {
                "rssBytes": rss_bytes,
                "heapTotalBytes": rss_bytes,
                "heapUsedBytes": rss_bytes
            }
        }
    }
    
    status_code = 200 if data["status"] == "HEALTHY" else 503
    response.status_code = status_code
    
    return ApiResponse.success(
        status_code=status_code,
        message="Health check metrics",
        data=data
    )
