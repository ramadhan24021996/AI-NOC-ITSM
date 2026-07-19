from enum import Enum

class FeatureStoreKPI(Enum):
    TOTAL_FEATURE = "total_feature"
    ACTIVE_FEATURE = "active_feature"
    ARCHIVED_FEATURE = "archived_feature"
    FEATURE_GROWTH = "feature_growth"
    VALIDATION_ERROR = "validation_error"
    DUPLICATE_RATE = "duplicate_rate"
    REUSE_COUNT = "reuse_count"
    AVG_CONFIDENCE = "avg_confidence"
    AVG_VALIDATION_TIME = "avg_validation_time"
