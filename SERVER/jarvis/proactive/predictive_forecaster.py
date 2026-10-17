"""
SERVER.jarvis.proactive.predictive_forecaster — Predictive Anomaly Time-Series Forecaster
========================================================================================
Tahap 3.2 — Production-Ready AI NOC Predictive Telemetry Forecasting

Menganalisis tren metrik time-series CPU, RAM, dan Disk dari host_metrics secara real-time.
Menghitung regresi linier slope (m = Δy / Δt) dan mengeluarkan sinyal peringatan proaktif
apabila sumber daya diprediksi akan habis dalam kurun waktu <= 20 menit.
"""
import logging
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger("jarvis.proactive.forecaster")


@dataclass
class PredictiveAnomalyAlertDTO:
    metric_type: str        # "CPU", "RAM", "DISK"
    current_value: float    # e.g. 88.5
    predicted_value: float  # e.g. 98.0
    slope_pct_per_min: float # e.g. 2.1
    time_to_exhaustion_min: int # e.g. 12
    device_name: str
    alert_text: str
    recommended_action: str


class PredictiveAnomalyForecaster:
    """
    Forecaster tren metrik proaktif menggunakan analisis regresi linier.
    """

    def __init__(self, warning_threshold_pct: float = 85.0, critical_threshold_pct: float = 95.0):
        self.warning_threshold_pct = warning_threshold_pct
        self.critical_threshold_pct = critical_threshold_pct
        self._history: Dict[str, List[Dict[str, float]]] = {}  # device_metric -> list of {ts, val}

    def add_metric_sample(self, device_name: str, metric_type: str, value: float, timestamp: Optional[float] = None):
        """Menambahkan sampel data time-series metrik terbaru."""
        ts = timestamp or time.time()
        key = f"{device_name}:{metric_type.upper()}"
        if key not in self._history:
            self._history[key] = []
        
        self._history[key].append({"ts": ts, "val": float(value)})
        # Keep last 20 samples (~10 mins if sampled every 30s)
        if len(self._history[key]) > 20:
            self._history[key].pop(0)

    def evaluate_forecast(self, device_name: str, metric_type: str) -> Optional[PredictiveAnomalyAlertDTO]:
        """
        Menghitung tren regresi linier dan mengembalikan sinyal alert jika ada proyeksi masalah.
        """
        key = f"{device_name}:{metric_type.upper()}"
        samples = self._history.get(key, [])
        if len(samples) < 3:
            return None

        # Extract X (minutes from first sample) and Y (metric percentage)
        t0 = samples[0]["ts"]
        x = [(s["ts"] - t0) / 60.0 for s in samples]
        y = [s["val"] for s in samples]

        n = len(samples)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi ** 2 for xi in x)

        denom = (n * sum_x2 - sum_x ** 2)
        if abs(denom) < 1e-6:
            return None

        # Linear regression slope m (% change per minute) and intercept b
        m = (n * sum_xy - sum_x * sum_y) / denom
        b = (sum_y - m * sum_x) / n

        current_val = y[-1]
        
        # Only alert if metric is currently above warning threshold AND slope is positive (> 0.5%/min)
        if current_val >= self.warning_threshold_pct and m > 0.5:
            # Predict value 15 mins into the future
            future_x = x[-1] + 15.0
            predicted_val = m * future_x + b
            
            # Time remaining until critical threshold
            rem_pct = max(0.0, self.critical_threshold_pct - current_val)
            time_to_crit = int(rem_pct / m) if m > 0 else 999

            if time_to_crit <= 20 or predicted_val >= self.critical_threshold_pct:
                rec_action = "RESTART_SERVICE" if metric_type.upper() == "CPU" else ("RESTART_REDIS" if metric_type.upper() == "RAM" else "CLEAR_CACHE")
                alert_text = (
                    f"📢 PERINGATAN PROAKTIF AI:\n"
                    f"• Metrik        : {metric_type.upper()} pada {device_name}\n"
                    f"• Penggunaan    : Saat ini {current_val:.1f}% (Laju Kenaikan: +{m:.1f}%/menit)\n"
                    f"• Proyeksi AI   : Diprediksi mencapai {min(100.0, predicted_val):.1f}% dalam {time_to_crit} menit\n"
                    f"• Rekomendasi   : Eksekusi {rec_action} sebelum kecelakaan sistem."
                )
                logger.warning(f"[PredictiveForecaster] FORECAST ALERT: {key} -> slope={m:.2f}%/min, time_to_crit={time_to_crit}m")
                return PredictiveAnomalyAlertDTO(
                    metric_type=metric_type.upper(),
                    current_value=current_val,
                    predicted_value=predicted_val,
                    slope_pct_per_min=m,
                    time_to_exhaustion_min=time_to_crit,
                    device_name=device_name,
                    alert_text=alert_text,
                    recommended_action=rec_action
                )

        return None
