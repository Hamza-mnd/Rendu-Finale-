"""observability.py — Logs structurés JSON + métriques (Séance 4)."""
import logging
import json
import time
import threading
import statistics as stats_module


class StructuredLogger:
    """Logger qui émet des logs au format JSON, un objet par ligne."""

    def __init__(self, name: str, log_file: str = None):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        if not self.logger.handlers:
            handler = (
                logging.FileHandler(log_file, encoding="utf-8")
                if log_file else logging.StreamHandler()
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(handler)

    def log(self, level: str, rpc_id: str, method: str,
            message: str, **extra):
        """Émet une ligne de log JSON."""
        entry = {
            "ts":     time.strftime("%Y-%m-%dT%H:%M:%S"),
            "level":  level,
            "rpc_id": rpc_id,
            "method": method,
            "msg":    message,
        }
        entry.update(extra)
        self.logger.info(json.dumps(entry, ensure_ascii=False))

    def info(self, rpc_id, method, msg, **kw):
        self.log("INFO", rpc_id, method, msg, **kw)

    def warn(self, rpc_id, method, msg, **kw):
        self.log("WARN", rpc_id, method, msg, **kw)

    def error(self, rpc_id, method, msg, **kw):
        self.log("ERROR", rpc_id, method, msg, **kw)


class MetricsCollector:
    """Collecteur thread-safe de métriques (compteurs + latences)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._call_counts:  dict[str, int] = {}
        self._error_counts: dict[str, int] = {}
        self._latencies:    dict[str, list[float]] = {}

    def record_call(self, method: str, duration_ms: float, success: bool):
        """Enregistre un appel avec sa durée et son statut."""
        with self._lock:
            self._call_counts[method] = self._call_counts.get(method, 0) + 1
            self._latencies.setdefault(method, []).append(duration_ms)
            if not success:
                self._error_counts[method] = \
                    self._error_counts.get(method, 0) + 1

    def get_report(self) -> dict:
        """Retourne le rapport complet des métriques."""
        with self._lock:
            report = {}
            for method in self._call_counts:
                latencies = self._latencies.get(method, [])
                report[method] = {
                    "total_calls":     self._call_counts[method],
                    "error_calls":     self._error_counts.get(method, 0),
                    "avg_latency_ms":  round(stats_module.mean(latencies), 2)
                                       if latencies else 0,
                    "p50_latency_ms":  round(stats_module.median(latencies), 2)
                                       if latencies else 0,
                    "max_latency_ms":  round(max(latencies), 2)
                                       if latencies else 0,
                    "min_latency_ms":  round(min(latencies), 2)
                                       if latencies else 0,
                }
            return report
