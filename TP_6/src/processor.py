"""processor.py — StreamProcessor : keyed state, watermark, lateness (Séance 6)."""
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class WindowState:
    """Accumulateurs pour une fenêtre (sensor_id, window_start).

    Stocke count, sommes, min/max pour calculer avg_temp et avg_humidity
    sans garder l'historique complet des événements.
    """
    count:        int   = 0
    sum_temp:     float = 0.0
    sum_humidity: float = 0.0
    min_temp:     float = float("inf")
    max_temp:     float = float("-inf")

    def update(self, event):
        """Met à jour les accumulateurs avec un nouvel événement."""
        self.count        += 1
        self.sum_temp     += event.temperature_c
        self.sum_humidity += event.humidity_pct
        self.min_temp      = min(self.min_temp, event.temperature_c)
        self.max_temp      = max(self.max_temp, event.temperature_c)

    @property
    def avg_temp(self) -> float:
        return self.sum_temp / self.count if self.count else 0.0

    @property
    def avg_humidity(self) -> float:
        return self.sum_humidity / self.count if self.count else 0.0

    def to_dict(self) -> dict:
        return {
            "count":        self.count,
            "sum_temp":     round(self.sum_temp, 3),
            "sum_humidity": round(self.sum_humidity, 3),
            "min_temp":     self.min_temp if self.count else None,
            "max_temp":     self.max_temp if self.count else None,
            "avg_temp":     round(self.avg_temp, 2),
            "avg_humidity": round(self.avg_humidity, 2),
        }


class StreamProcessor:
    """Processeur de flux stateful avec fenêtres tumbling et watermark.

    Gère :
      - Keyed state : dict[(sensor_id, window_start)] → WindowState
      - Watermark   : max(event_time) - margin
      - Lateness    : accept / too-late → dropped
      - Flush       : ferme les fenêtres dont window_end <= watermark

    Args:
        window_size:       Durée d'une fenêtre tumbling (secondes).
        allowed_lateness:  Tolérance après fermeture de fenêtre (secondes).
        watermark_margin:  Marge du watermark = max_event_time - margin.
    """

    def __init__(self, window_size: int = 60,
                 allowed_lateness: int = 120,
                 watermark_margin: float = 5.0):
        self.window_size       = window_size
        self.allowed_lateness  = allowed_lateness
        self.watermark_margin  = watermark_margin

        self.state:            dict[tuple[str, int], WindowState] = {}
        self.max_event_time:   float = 0.0
        self.events_processed: int   = 0
        self.late_events:      list[dict] = []
        self.dropped_events:   list[dict] = []
        self.flushed_windows:  list[dict] = []

    @property
    def watermark(self) -> float:
        """Watermark courant = max_event_time - margin."""
        return self.max_event_time - self.watermark_margin

    def _window_key(self, event_time: float) -> int:
        """Retourne le début de la fenêtre tumbling pour un event_time."""
        return int(event_time // self.window_size) * self.window_size

    def process_event(self, event) -> str:
        """Traite un événement : lateness check → update state.

        Returns:
            "ok"       si accepté normalement,
            "late"     si accepté mais en retard,
            "dropped"  si trop tard.
        """
        self.events_processed += 1
        self.max_event_time = max(self.max_event_time, event.event_time)

        wk         = self._window_key(event.event_time)
        window_end = wk + self.window_size

        # --- Politique de lateness ---
        if self.watermark > window_end:
            lateness = self.watermark - window_end
            if lateness > self.allowed_lateness:
                self.dropped_events.append({
                    "event_id":   event.event_id,
                    "sensor_id":  event.sensor_id,
                    "event_time": event.event_time,
                    "reason":     "too-late",
                    "lateness_s": round(lateness, 1),
                })
                logger.warning("DROPPED %s | lateness=%.0fs > allowed=%ds",
                               event.event_id, lateness, self.allowed_lateness)
                return "dropped"
            else:
                self.late_events.append({
                    "event_id":   event.event_id,
                    "sensor_id":  event.sensor_id,
                    "event_time": event.event_time,
                    "reason":     "late-accepted",
                    "lateness_s": round(lateness, 1),
                })
                logger.info("LATE-ACCEPTED %s | lateness=%.0fs",
                            event.event_id, lateness)

        # --- Mise à jour du keyed state ---
        key = (event.sensor_id, wk)
        if key not in self.state:
            self.state[key] = WindowState()
        self.state[key].update(event)
        logger.debug("OK %s → window(%s, %d) count=%d",
                     event.event_id, event.sensor_id, wk,
                     self.state[key].count)
        return "ok" if self.watermark <= window_end else "late"

    def flush_closed_windows(self):
        """Exporte et supprime les fenêtres dont window_end <= watermark.

        Appeler après chaque process_event pour éviter la croissance infinie
        du dictionnaire d'état (memory leak logique).
        """
        to_flush = [
            (sid, wk) for (sid, wk) in list(self.state.keys())
            if self.watermark >= wk + self.window_size
        ]
        for sid, wk in to_flush:
            ws = self.state.pop((sid, wk))
            record = {
                "sensor_id":    sid,
                "window_start": wk,
                "window_end":   wk + self.window_size,
                **ws.to_dict(),
            }
            self.flushed_windows.append(record)
            logger.info("FLUSH window (%s, %d) → avg_temp=%.2f count=%d",
                        sid, wk, ws.avg_temp, ws.count)
