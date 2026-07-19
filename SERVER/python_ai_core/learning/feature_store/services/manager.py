import psycopg2
import json
from datetime import datetime
from typing import Dict, Any
from ..schemas.feature_schema import Feature, FeatureLifecycle, FeatureQualityScore, FeatureLineage

class FeatureStoreManager:
    def __init__(self, db_config: Dict[str, Any]):
        self.conn = psycopg2.connect(**db_config)
        self.conn.autocommit = True

    def _generate_checksum(self, payload: dict) -> str:
        import hashlib
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def register_feature(self, payload: dict) -> str:
        # Validate schema via Pydantic
        feature = Feature(**payload)
        
        # Quality check (must be high quality to be ACTIVE)
        if feature.quality.confidence < 0.5:
            raise ValueError("Feature quality score too low. Rejected.")

        cur = self.conn.cursor()
        
        # 1. Insert Registry
        cur.execute("""
            INSERT INTO feature_registry 
            (feature_id, feature_name, category, tenant_id, source, current_version, schema_version, status, checksum)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (feature_id) DO NOTHING
        """, (feature.feature_id, feature.feature_name, feature.category, feature.tenant_id, 
              feature.source, feature.version, 1, feature.status.value, feature.checksum))

        # 2. Insert Immutable Version
        try:
            cur.execute("""
                INSERT INTO feature_versions 
                (feature_id, version, feature_value, unit, confidence, evidence, checksum)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (feature.feature_id, feature.version, json.dumps(feature.feature_value), 
                  feature.unit, feature.confidence, feature.evidence, feature.checksum))
        except psycopg2.errors.UniqueViolation:
            raise ValueError(f"Immutable Policy Violation: Version {feature.version} of feature {feature.feature_id} already exists.")
            
        # 3. Insert Lineage
        cur.execute("""
            INSERT INTO feature_lineage 
            (feature_id, version, telemetry_id, collector_id, normalizer_version, extractor_version, validator_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (feature.feature_id, feature.version, feature.lineage.telemetry_id, feature.lineage.collector_id,
              feature.lineage.normalizer_version, feature.lineage.extractor_version, feature.lineage.validator_version))

        # 4. Insert Quality
        cur.execute("""
            INSERT INTO feature_quality
            (feature_id, version, completeness, consistency, freshness, confidence_score, evidence_score, reuse_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (feature.feature_id, feature.version, feature.quality.completeness, feature.quality.consistency,
              feature.quality.freshness, feature.quality.confidence, feature.quality.evidence_score, feature.quality.reuse_score))

        # 5. Audit Log
        cur.execute("""
            INSERT INTO feature_audit (correlation_id, feature_id, tenant_id, event, version, reason)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, ("corr-new", feature.feature_id, feature.tenant_id, "CREATED", feature.version, "Initial extraction"))
        
        cur.close()
        return feature.feature_id

    def archive_feature(self, feature_id: str):
        cur = self.conn.cursor()
        cur.execute("UPDATE feature_registry SET status = 'ARCHIVED' WHERE feature_id = %s", (feature_id,))
        cur.execute("""
            INSERT INTO feature_audit (feature_id, event, reason)
            VALUES (%s, %s, %s)
        """, (feature_id, "ARCHIVED", "Soft delete requested"))
        cur.close()
