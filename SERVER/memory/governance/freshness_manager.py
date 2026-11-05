"""
SERVER.memory.governance.freshness_manager
===========================================
Component: Knowledge Freshness Manager

Tracks SOP review dates and warns operators when an SOP is stale (not reviewed in > 12 months):
"SOP ini belum direview selama 18 bulan."
"""
import time
import logging
from dataclasses import dataclass
from typing import Dict, Any

logger = logging.getLogger("memory.governance.freshness")


@dataclass
class FreshnessStatus:
    created_date: str
    last_review_date: str
    next_review_date: str
    is_stale: bool
    stale_warning: str = ""
    months_since_last_review: int = 0

    def to_dict(self) -> dict:
        return {
            "created_date": self.created_date,
            "last_review_date": self.last_review_date,
            "next_review_date": self.next_review_date,
            "is_stale": self.is_stale,
            "stale_warning": self.stale_warning,
            "months_since_last_review": self.months_since_last_review,
        }


class KnowledgeFreshnessManager:
    """
    Manages freshness lifecycle and annual review schedules for SOPs.
    """

    def evaluate_freshness(
        self, created_date: str = "", last_review_date: str = ""
    ) -> FreshnessStatus:
        now_str = time.strftime("%Y-%m-%d")

        if not created_date:
            created_date = now_str
        if not last_review_date:
            last_review_date = created_date

        # Calculate next review date (12 months from last_review_date)
        try:
            year, month, day = map(int, last_review_date.split("-")[:3])
            next_year = year + 1
            next_review_date = f"{next_year:04d}-{month:02d}-{day:02d}"
        except Exception as e:
            logger.error("[FreshnessManager] Operation failed: %s", e, exc_info=True)
            next_review_date = f"2027-01-01"

        # Calculate elapsed months from last review
        current_year = int(time.strftime("%Y"))
        current_month = int(time.strftime("%m"))
        try:
            l_year, l_month = map(int, last_review_date.split("-")[:2])
            months_elapsed = ((current_year - l_year) * 12) + (current_month - l_month)
        except Exception as e:
            logger.error("[FreshnessManager] Operation failed: %s", e, exc_info=True)
            months_elapsed = 0

        is_stale = months_elapsed >= 12
        warning = ""
        if is_stale:
            warning = f"SOP ini belum direview selama {months_elapsed} bulan."
            logger.info(f"[KnowledgeFreshnessManager] Stale warning: {warning}")

        return FreshnessStatus(
            created_date=created_date,
            last_review_date=last_review_date,
            next_review_date=next_review_date,
            is_stale=is_stale,
            stale_warning=warning,
            months_since_last_review=months_elapsed,
        )
