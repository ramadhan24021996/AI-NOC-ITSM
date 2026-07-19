import json
import logging
from datetime import datetime

from predictive.risk_engine import RiskEngine
from predictive.forecast_engine import ForecastEngine
from predictive.digital_twin import DigitalTwin
from predictive.causal_engine import CausalEngine

logger = logging.getLogger("PREDICTIVE_ENGINE")

class PredictiveEngine:
    def __init__(self, db_conn):
        self.db = db_conn
        self.risk_engine = RiskEngine(db_conn)
        self.forecast_engine = ForecastEngine(db_conn)
        self.digital_twin = DigitalTwin(db_conn)
        self.causal_engine = CausalEngine(db_conn)

    def predict_incident(self, asset_id, current_telemetry, historical_telemetry, criticality):
        """
        Analyzes multi-signal telemetry to predict future failures.
        Returns a comprehensive predictive intelligence report.
        """
        try:
            # 1. Forecast ETA (e.g. Disk usage trend)
            disk_forecast = self.forecast_engine.forecast_failure(historical_telemetry.get('disk_usage', []), "disk_usage", 95.0)
            cpu_forecast = self.forecast_engine.forecast_failure(historical_telemetry.get('cpu_usage', []), "cpu_usage", 99.0)
            
            # Pick the most critical forecast
            primary_forecast = disk_forecast if disk_forecast and (disk_forecast['eta_minutes'] is not None) else cpu_forecast
            
            if not primary_forecast or primary_forecast['eta_minutes'] is None:
                # No immediate prediction
                return {"prediction": False, "reason": "Stable metrics"}
                
            eta = primary_forecast['eta_minutes']
            probability = primary_forecast['confidence']
            metric = primary_forecast['metric']
            
            incident_type = "Disk Full" if metric == "disk_usage" else "CPU Overload"

            # 2. Risk Score
            risk_data = self.risk_engine.calculate_risk(asset_id, current_telemetry, criticality)
            risk_score = risk_data['total_risk_score']
            
            if risk_score > 80:
                risk_level = "CRITICAL"
            elif risk_score > 60:
                risk_level = "HIGH"
            elif risk_score > 40:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"

            # 3. Causal Chain & RCA
            symptom = "HTTP 503" if incident_type == "Disk Full" else "Service Unavailable"
            causal_data = self.causal_engine.build_causal_chain(symptom, current_telemetry)

            # 4. Playbook & Recommendations
            recommendation = "Cleanup temporary files and extend volume." if incident_type == "Disk Full" else "Restart service or add capacity."
            action_to_simulate = "CLEAR_SPOOLER" if incident_type == "Disk Full" else "RESTART_SERVICE"
            
            # 5. Digital Twin Simulation
            simulation = self.digital_twin.simulate_action(asset_id, action_to_simulate, current_telemetry)
            
            # 5.5. Predict Downtime (Estimasi Menit)
            base_downtime = 5 if incident_type == "Disk Full" else 15
            blast_factor = 0
            try:
                blast_str = str(simulation.get("blast_radius", "0"))
                blast_factor = int(''.join(filter(str.isdigit, blast_str.split(" ")[0])))
            except ValueError:
                blast_factor = 1
                
            downtime_estimate_minutes = base_downtime + (blast_factor * 3)
            
            # 6. Construct Final Report
            report = {
                "prediction": True,
                "probability": probability,
                "eta_minutes": eta,
                "downtime_estimate_minutes": downtime_estimate_minutes,
                "incident_type": incident_type,
                "risk": risk_level,
                "risk_score": risk_score,
                "confidence": max(probability, 90.0), # Example logic
                "early_warning": f"WARNING: {incident_type} predicted in {eta} minutes. Expected downtime: {downtime_estimate_minutes} min.",
                "recommendation": recommendation,
                "playbook": {
                    "checklist": ["Verify metrics", "Run simulated action", "Monitor rollback window"],
                    "action_plan": action_to_simulate,
                    "rollback_plan": "Restore from snapshot" if risk_level == "CRITICAL" else "No rollback required",
                    "verification": "Check telemetry drops below threshold",
                    "owner": "Auto-Remediation System"
                },
                "simulation": simulation,
                "root_cause_analysis": causal_data
            }

            # 7. Record to Learning Database (Shadow Mode)
            self._record_prediction(asset_id, incident_type, probability, eta, risk_score, report['confidence'], current_telemetry, recommendation)

            return report

        except Exception as e:
            logger.error(f"[PREDICTIVE] Engine error: {e}")
            return {"prediction": False, "error": str(e)}

    def _record_prediction(self, asset_id, incident_type, prob, eta, risk, conf, evidence, rec):
        try:
            with self.db.cursor() as cur:
                cur.execute("""
                    INSERT INTO prediction_history 
                    (asset_id, incident_type, probability, eta_minutes, risk_score, confidence, evidence, recommendation)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (asset_id, incident_type, prob, eta, risk, conf, json.dumps(evidence), rec))
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to record prediction: {e}")
