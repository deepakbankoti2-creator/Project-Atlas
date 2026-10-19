"""
Numeric Calculator Tool for Project Atlas AI Agent Workflow
Executes deterministic mathematical projections and CAGR calculations in Python.
"""

from typing import Dict, Any, List, Optional
import math
import logging
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class DerivedValue(BaseModel):
    """Detailed record of a computed/derived projection."""
    metric_name: str
    target_year: int
    formula: str
    base_value_str: str
    cagr_str: str
    result_primary: str
    result_secondary: Optional[str] = None
    assumptions: List[str]
    is_out_of_horizon: bool = False
    limitation_warning: Optional[str] = None


class MarketCalculator:
    """Performs financial, CAGR, and market projection calculations."""

    @staticmethod
    def project_cagr(base_value: float, cagr: float, years: int) -> float:
        """
        Future Value = Base Value * (1 + CAGR)^Years
        """
        return base_value * math.pow(1.0 + cagr, years)

    @classmethod
    def calculate_smart_water_meter_projection(
        cls,
        target_year: int = 2030,
        region: str = "APAC"
    ) -> DerivedValue:
        """
        Calculates market projection based on R-101 parameters with full formula transparency
        and explicit handling of base-year ambiguity and horizon boundaries.
        """
        base_value_2024 = 4.21  # USD Billion
        cagr = 0.112  # 11.2%
        apac_share = 0.38  # 38%
        max_forecast_year = 2030

        # Horizon check
        if target_year > max_forecast_year:
            return DerivedValue(
                metric_name=f"{region} Smart Water Meter Market Valuation",
                target_year=target_year,
                formula="Future Value = Base Value * (1 + CAGR)^n",
                base_value_str=f"USD {base_value_2024} B (2024)",
                cagr_str=f"{cagr * 100:.1f}%",
                result_primary="N/A (Projection Exceeds Forecast Horizon)",
                assumptions=[
                    f"R-101 published forecast period strictly ends at {max_forecast_year}.",
                    f"R-102 published forecast period ends at 2029.",
                    f"Forecasting for {target_year} requires unverified long-term trend assumptions."
                ],
                is_out_of_horizon=True,
                limitation_warning=(
                    f"The published forecast window in R-101 ends in {max_forecast_year} (and R-102 ends in 2029). "
                    f"Projecting to {target_year} exceeds verified analyst models and requires human analyst escalation."
                )
            )

        # Base-year ambiguity handling:
        # Interpretation 1: 2024 base compounded 6 years to 2030 (2030 - 2024 = 6)
        n_years_6 = target_year - 2024
        global_2030_v1 = cls.project_cagr(base_value_2024, cagr, n_years_6)
        apac_2030_v1 = global_2030_v1 * apac_share

        # Interpretation 2: 2025 base (stated forecast window 2025-2030 = 5 years)
        n_years_5 = max(target_year - 2025, 1)
        global_2030_v2 = cls.project_cagr(base_value_2024, cagr, n_years_5)
        apac_2030_v2 = global_2030_v2 * apac_share

        assumptions = [
            f"Base global market size = USD {base_value_2024} B in 2024 (R-101, p.8).",
            f"CAGR = {cagr * 100:.1f}% stated for the 2025–2030 forecast window (R-101, p.8).",
            f"Asia-Pacific share assumed constant at {apac_share * 100:.0f}% of global market.",
            "Base-Year Ambiguity: Formula evaluated across both 6-year (from 2024) and 5-year (from 2025) compounding periods.",
            "Labelled as a Derived Estimate (not a quoted fact from the report text)."
        ]

        return DerivedValue(
            metric_name=f"{region} Smart Water Meter Market Valuation ({target_year})",
            target_year=target_year,
            formula=f"Future Value = Base Value * (1 + CAGR)^{n_years_6} | APAC = Global * {apac_share * 100:.0f}%",
            base_value_str=f"USD {base_value_2024} B (2024)",
            cagr_str=f"{cagr * 100:.1f}%",
            result_primary=f"USD {apac_2030_v1:.2f} B (6-year compounding from 2024)",
            result_secondary=f"USD {apac_2030_v2:.2f} B (5-year compounding from 2025)",
            assumptions=assumptions,
            is_out_of_horizon=False,
            limitation_warning=None
        )
