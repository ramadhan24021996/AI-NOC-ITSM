from enum import Enum

class LearningKPI(Enum):
    LEARNING_DELAY = "learning_delay"
    LEARNING_ACCURACY = "learning_accuracy"
    FEATURE_GROWTH = "feature_growth"
    REMEDIATION_SUCCESS = "remediation_success"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"
    KNOWLEDGE_REUSE = "knowledge_reuse"
    TOKEN_COST = "token_cost"

class IMetricsTracker:
    def record(self, kpi: LearningKPI, value: float) -> None:
        raise NotImplementedError("LF-1 Framework: Metrics recording not implemented")
