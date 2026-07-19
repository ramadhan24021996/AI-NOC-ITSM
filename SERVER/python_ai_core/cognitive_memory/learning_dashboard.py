import os
import json
import redis
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class LearningDashboard:
    """
    Event-driven AI Observability Module.
    Tracks cognitive and runtime metrics in Redis and publishes to NATS.
    """
    def __init__(self):
        self.redis_host = os.environ.get("REDIS_HOST", "redis")
        self.redis_port = int(os.environ.get("REDIS_PORT", "6379"))
        self.redis_password = os.environ.get("REDIS_PASSWORD")
        self.redis_client = redis.Redis(
            host=self.redis_host, 
            port=self.redis_port, 
            password=self.redis_password,
            decode_responses=True,
            protocol=2
        )
        
        # Keys for Redis
        self.KEY_COGNITIVE = "metrics:ai:cognitive"
        self.KEY_RUNTIME = "metrics:ai:runtime"
        
        self._init_defaults()

    def _init_defaults(self):
        """Initialize counters if they don't exist"""
        try:
            if not self.redis_client.exists(self.KEY_COGNITIVE):
                self.redis_client.hset(self.KEY_COGNITIVE, mapping={
                    "total_incidents_analyzed": 0,
                    "knowledge_vectors_count": 0,
                    "feedback_received": 0,
                    "human_override_rate": 0.0,
                    "false_positive_count": 0,
                    "mean_confidence": 0.0,
                    "total_high_confidence": 0,
                    "total_confidence_sum": 0.0
                })
                
            if not self.redis_client.exists(self.KEY_RUNTIME):
                self.redis_client.hset(self.KEY_RUNTIME, mapping={
                    "avg_inference_latency_ms": 0.0,
                    "avg_embedding_latency_ms": 0.0,
                    "total_inferences": 0,
                    "llm_response_errors": 0,
                    "queue_backlog": 0
                })
        except Exception as e:
            logger.error(f"Redis connection failed during init: {e}")

    def record_incident_resolved(self, confidence: float, latency_ms: float, is_false_positive: bool = False):
        """Called when an incident is fully analyzed."""
        try:
            self.redis_client.hincrby(self.KEY_COGNITIVE, "total_incidents_analyzed", 1)
            self.redis_client.hincrbyfloat(self.KEY_COGNITIVE, "total_confidence_sum", confidence)
            
            if confidence >= 90.0:
                self.redis_client.hincrby(self.KEY_COGNITIVE, "total_high_confidence", 1)
            
            if is_false_positive:
                self.redis_client.hincrby(self.KEY_COGNITIVE, "false_positive_count", 1)
                
            self.redis_client.hincrby(self.KEY_RUNTIME, "total_inferences", 1)
            self.redis_client.hset(self.KEY_RUNTIME, "avg_inference_latency_ms", latency_ms)
        except Exception as e:
            logger.error(f"Failed to record incident metric: {e}")

    def record_feedback(self, is_human_override: bool):
        """Called when admin gives feedback or overrides AI."""
        try:
            self.redis_client.hincrby(self.KEY_COGNITIVE, "feedback_received", 1)
            if is_human_override:
                # Can be used later for detailed override rate calculation
                pass
        except Exception as e:
            logger.error(f"Failed to record feedback metric: {e}")

    def record_knowledge_added(self):
        """Called when new playbook is embedded into pgvector."""
        try:
            self.redis_client.hincrby(self.KEY_COGNITIVE, "knowledge_vectors_count", 1)
        except Exception as e:
            logger.error(f"Failed to record knowledge metric: {e}")

    def get_cognitive_metrics(self) -> Dict[str, Any]:
        """Fetch pre-calculated cognitive metrics from Redis"""
        try:
            data = self.redis_client.hgetall(self.KEY_COGNITIVE)
            
            # Derived metrics
            total = int(data.get("total_incidents_analyzed", 0))
            sum_conf = float(data.get("total_confidence_sum", 0.0))
            fp = int(data.get("false_positive_count", 0))
            
            return {
                "total_incidents_analyzed": total,
                "knowledge_vectors_count": int(data.get("knowledge_vectors_count", 0)),
                "feedback_received": int(data.get("feedback_received", 0)),
                "high_confidence_count": int(data.get("total_high_confidence", 0)),
                "mean_confidence": round(sum_conf / total, 2) if total > 0 else 0.0,
                "false_positive_rate": round(fp / total, 2) if total > 0 else 0.0
            }
        except Exception as e:
            logger.error(f"Failed to get cognitive metrics: {e}")
            return {}

    def get_runtime_metrics(self) -> Dict[str, Any]:
        """Fetch pre-calculated runtime metrics from Redis"""
        try:
            data = self.redis_client.hgetall(self.KEY_RUNTIME)
            return {
                "inference_latency_ms": float(data.get("avg_inference_latency_ms", 0.0)),
                "embedding_latency_ms": float(data.get("avg_embedding_latency_ms", 0.0)),
                "llm_response_errors": int(data.get("llm_response_errors", 0)),
                "queue_backlog": int(data.get("queue_backlog", 0))
            }
        except Exception as e:
            logger.error(f"Failed to get runtime metrics: {e}")
            return {}

    async def publish_metrics(self, nats_client):
        """Publish JSON payload to NATS (called directly after events)"""
        try:
            cog_metrics = self.get_cognitive_metrics()
            run_metrics = self.get_runtime_metrics()
            
            await nats_client.publish(
                "telemetry.ai.cognitive", 
                json.dumps(cog_metrics).encode('utf-8')
            )
            await nats_client.publish(
                "telemetry.ai.runtime", 
                json.dumps(run_metrics).encode('utf-8')
            )
        except Exception as e:
            logger.error(f"Failed to publish metrics to NATS: {e}")