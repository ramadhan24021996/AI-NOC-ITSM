import numpy as np
import logging

logger = logging.getLogger("FORECAST_ENGINE")

class ForecastEngine:
    def __init__(self, db_conn):
        self.db = db_conn

    def forecast_failure(self, time_series_data, metric_name, threshold=95.0):
        """
        Analyzes time series data (list of [timestamp, value]) to predict ETA to failure.
        Output: Failure ETA in minutes, slope, acceleration, and confidence.
        """
        if not time_series_data or len(time_series_data) < 3:
            return None
            
        try:
            # We assume time_series_data is sorted chronologically
            x = np.array([float(i) for i in range(len(time_series_data))])
            y = np.array([float(d[1]) for d in time_series_data])
            
            # Simple Linear Regression for Slope
            slope, intercept = np.polyfit(x, y, 1)
            
            # Acceleration (2nd derivative approximation)
            if len(y) >= 4:
                dy = np.diff(y)
                ddy = np.diff(dy)
                acceleration = np.mean(ddy)
            else:
                acceleration = 0.0

            trend = "STABLE"
            eta_minutes = -1
            confidence = 50.0

            if slope > 0.5:
                trend = "INCREASING"
                # If current value is already above threshold, it's 0 minutes
                current_val = y[-1]
                if current_val >= threshold:
                    eta_minutes = 0
                    confidence = 99.0
                else:
                    # How many steps to reach threshold? (assuming each step is 5 minutes polling)
                    steps_to_fail = (threshold - current_val) / slope
                    eta_minutes = int(steps_to_fail * 5)
                    # Higher slope/accel = higher confidence
                    confidence = min(98.0, 50 + (slope * 5) + (acceleration * 2))
            elif slope < -0.5:
                trend = "DECREASING"
                confidence = 80.0
            
            return {
                "metric": metric_name,
                "eta_minutes": eta_minutes if eta_minutes >= 0 else None,
                "confidence": round(confidence, 2),
                "trend": trend,
                "slope": round(slope, 3),
                "acceleration": round(acceleration, 3)
            }

        except Exception as e:
            logger.error(f"[FORECAST] Error forecasting {metric_name}: {e}")
            return None
