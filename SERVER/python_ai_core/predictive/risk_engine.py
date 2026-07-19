class RiskEngine:
    def __init__(self, db_conn):
        self.db = db_conn

    def calculate_risk(self, asset_id, telemetry, criticality):
        """Calculates combined Risk Score 0-100 based on technical and business factors."""
        tech_risk = 0
        biz_risk = 0
        op_risk = 0
        sec_risk = 0

        # Base technical risk
        cpu = float(telemetry.get('cpu_usage', 0))
        disk = float(telemetry.get('disk_usage', 0))
        ram = float(telemetry.get('ram_usage', 0))

        if cpu > 90:
            tech_risk += 40
        elif cpu > 75:
            tech_risk += 20
            
        if disk > 95:
            tech_risk += 60
        elif disk > 85:
            tech_risk += 30

        if ram > 90:
            tech_risk += 30

        # Network/App technical risk
        if 'latency_ms' in telemetry and telemetry['latency_ms'] > 500:
            tech_risk += 20
        if 'web_errors' in telemetry and telemetry['web_errors']:
            tech_risk += 50
        
        tech_risk = min(100, tech_risk)

        # Business Risk based on criticality
        biz_scores = {'LOW': 10, 'MEDIUM': 30, 'HIGH': 60, 'CRITICAL': 85, 'BUSINESS CRITICAL': 100}
        biz_risk = biz_scores.get(criticality, 10)

        # Operational Risk (impact on dependencies)
        op_risk = 50 if biz_risk >= 60 else 20
        
        # Security Risk
        if 'tls_error' in telemetry or 'cert_expired' in telemetry:
            sec_risk = 90
            
        # Weighted Total
        total_risk = (tech_risk * 0.4) + (biz_risk * 0.3) + (op_risk * 0.2) + (sec_risk * 0.1)
        
        return {
            "total_risk_score": round(total_risk, 2),
            "technical_risk": tech_risk,
            "business_risk": biz_risk,
            "operational_risk": op_risk,
            "security_risk": sec_risk
        }
