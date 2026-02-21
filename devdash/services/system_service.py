"""System service — CPU temp, memory, uptime."""

from __future__ import annotations

import logging
import platform

log = logging.getLogger(__name__)


class SystemService:
    async def get_cpu_temp(self) -> float:
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                return int(f.read().strip()) / 1000
        except (FileNotFoundError, ValueError):
            return 0.0

    async def get_memory_usage(self) -> dict:
        try:
            with open("/proc/meminfo") as f:
                lines = f.readlines()
            info = {}
            for line in lines[:3]:
                key, val = line.split(":")
                info[key.strip()] = int(val.strip().split()[0])
            total = info.get("MemTotal", 1)
            free = info.get("MemAvailable", info.get("MemFree", 0))
            return {"total_mb": total // 1024, "used_mb": (total - free) // 1024,
                    "percent": round((total - free) / total * 100)}
        except Exception:
            return {"total_mb": 0, "used_mb": 0, "percent": 0}

    def is_raspberry_pi(self) -> bool:
        try:
            with open("/proc/device-tree/model") as f:
                return "raspberry pi" in f.read().lower()
        except FileNotFoundError:
            return False

    def get_platform_info(self) -> str:
        return f"{platform.system()} {platform.machine()}"
