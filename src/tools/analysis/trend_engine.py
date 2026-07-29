"""
Trend Engine — Statistical analysis for production data.

Provides deterministic, reproducible statistical analysis:
- Trend detection (linear regression)
- Anomaly detection (z-score method)
- Moving averages
- Pareto analysis
- Forecasting (linear projection)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional


# ── Result Dataclasses ────────────────────────────────────────

@dataclass
class TrendResult:
    """Result of trend analysis on a time series."""

    series_name: str
    direction: str  # "up", "down", "stable"
    slope: float    # Change per data point
    r_squared: float  # Goodness of fit (0-1)
    current_value: float
    forecast_7d: float
    forecast_30d: float
    forecast_60d: float  # Extended forecast
    forecast_90d: float  # Extended forecast
    improvement_pct: float  # % change from start to end
    decomposition: Optional[dict] = None  # trend/seasonality/noise breakdown

    def to_dict(self) -> dict:
        return {
            "series": self.series_name,
            "direction": self.direction,
            "slope": round(self.slope, 4),
            "r_squared": round(self.r_squared, 4),
            "current_value": round(self.current_value, 2),
            "forecast_7d": round(self.forecast_7d, 2),
            "forecast_30d": round(self.forecast_30d, 2),
            "forecast_60d": round(self.forecast_60d, 2),
            "forecast_90d": round(self.forecast_90d, 2),
            "improvement_pct": round(self.improvement_pct, 2),
            "decomposition": self.decomposition,
        }


@dataclass
class AnomalyResult:
    """Detected anomaly in a time series."""

    index: int
    date: str
    value: float
    expected: float  # Mean-based expectation
    deviation: float  # How many standard deviations away
    severity: str  # "mild", "moderate", "severe"

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "date": self.date,
            "value": round(self.value, 2),
            "expected": round(self.expected, 2),
            "deviation": round(self.deviation, 2),
            "severity": self.severity,
        }


@dataclass
class ParetoResult:
    """Pareto analysis result (80/20 breakdown)."""

    categories: list[str]
    values: list[float]
    cumulative_pct: list[float]
    top_20_contributors: list[str]
    top_20_pct: float
    total: float

    def to_dict(self) -> dict:
        return {
            "categories": self.categories,
            "values": [round(v, 2) for v in self.values],
            "cumulative_pct": [round(p, 2) for p in self.cumulative_pct],
            "top_20_contributors": self.top_20_contributors,
            "top_20_pct": round(self.top_20_pct, 2),
            "total": round(self.total, 2),
        }


@dataclass
class TrendAnalysis:
    """Complete trend analysis result."""

    # Trend metrics
    oee_trend: TrendResult
    availability_trend: TrendResult
    performance_trend: TrendResult
    quality_trend: TrendResult

    # Anomalies
    anomalies: list[AnomalyResult] = field(default_factory=list)

    # Pareto
    downtime_pareto: Optional[ParetoResult] = None

    # Moving averages
    oee_ma_7: list[float] = field(default_factory=list)
    oee_ma_30: list[float] = field(default_factory=list)

    # Summary
    overall_direction: str = ""
    key_finding: str = ""
    risk_level: str = "low"  # "low", "medium", "high"

    def to_dict(self) -> dict:
        result = {
            "oee_trend": self.oee_trend.to_dict(),
            "availability_trend": self.availability_trend.to_dict(),
            "performance_trend": self.performance_trend.to_dict(),
            "quality_trend": self.quality_trend.to_dict(),
            "anomalies": [a.to_dict() for a in self.anomalies],
            "oee_ma_7": [round(v, 2) for v in self.oee_ma_7],
            "oee_ma_30": [round(v, 2) for v in self.oee_ma_30],
            "overall_direction": self.overall_direction,
            "key_finding": self.key_finding,
            "risk_level": self.risk_level,
        }
        if self.downtime_pareto:
            result["downtime_pareto"] = self.downtime_pareto.to_dict()
        return result


# ── Trend Engine Class ────────────────────────────────────────

class TrendEngine:
    """
    Statistical trend analysis engine for production data.

    All methods are deterministic — same input always produces same output.
    Uses numpy/scipy for efficient computation.
    """

    @staticmethod
    def _linear_regression(values: list[float]) -> tuple[float, float, float]:
        """
        Simple linear regression.

        Returns: (slope, intercept, r_squared)
        """
        x = np.arange(len(values), dtype=float)
        y = np.array(values, dtype=float)

        if len(x) < 2:
            return 0.0, y[0] if len(y) > 0 else 0.0, 0.0

        # Calculate slope and intercept
        n = len(x)
        sum_x = np.sum(x)
        sum_y = np.sum(y)
        sum_xy = np.sum(x * y)
        sum_x2 = np.sum(x ** 2)

        denominator = n * sum_x2 - sum_x ** 2
        if denominator == 0:
            return 0.0, np.mean(y), 0.0

        slope = (n * sum_xy - sum_x * sum_y) / denominator
        intercept = (sum_y - slope * sum_x) / n

        # Calculate R²
        y_pred = slope * x + intercept
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)

        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        r_squared = max(0.0, min(1.0, r_squared))

        return slope, intercept, r_squared

    @classmethod
    def analyze_trend(cls, values: list[float], series_name: str = "series") -> TrendResult:
        """
        Analyze trend in a time series using linear regression.

        Args:
            values: Time series values
            series_name: Name of the series for reporting

        Returns:
            TrendResult with direction, forecast, etc.
        """
        if not values or len(values) < 2:
            return cls._empty_trend(series_name)

        slope, intercept, r_squared = cls._linear_regression(values)

        # Determine direction
        if abs(slope) < 0.01:
            direction = "stable"
        elif slope > 0:
            direction = "up"
        else:
            direction = "down"

        current = values[-1]
        forecast_7d = max(0, min(100, round(current + slope * 7, 2)))
        forecast_30d = max(0, min(100, round(current + slope * 30, 2)))
        forecast_60d = max(0, min(100, round(current + slope * 60, 2)))
        forecast_90d = max(0, min(100, round(current + slope * 90, 2)))
        improvement_pct = ((values[-1] - values[0]) / values[0] * 100) if values[0] > 0 else 0

        # Timeseries decomposition (if sufficient data)
        decomposition = None
        if len(values) >= 14:
            decomposition = cls._decompose(values)

        return TrendResult(
            series_name=series_name,
            direction=direction,
            slope=round(slope, 4),
            r_squared=round(r_squared, 4),
            current_value=round(current, 2),
            forecast_7d=forecast_7d,
            forecast_30d=forecast_30d,
            forecast_60d=forecast_60d,
            forecast_90d=forecast_90d,
            improvement_pct=round(improvement_pct, 2),
            decomposition=decomposition,
        )

    @classmethod
    def _decompose(cls, values: list[float], period: int = 7) -> dict:
        """
        Perform classical timeseries decomposition: Trend + Seasonality + Noise.

        Uses moving average for trend extraction, then residual decomposition.
        No external dependencies — pure numpy implementation.

        Args:
            values: Time series values
            period: Seasonal period (default 7 for weekly patterns)

        Returns:
            Dict with trend, seasonal, noise arrays
        """
        if len(values) < period * 2:
            return {"trend": None, "seasonal": None, "noise": None}

        n = len(values)
        values_arr = np.array(values, dtype=float)

        # Step 1: Extract trend using centered moving average
        trend = np.full(n, np.nan)
        half = period // 2
        for i in range(half, n - half):
            window = values_arr[i - half:i + half + 1]
            trend[i] = np.mean(window)

        # Step 2: Detrend to get seasonal + noise
        detrended = values_arr - trend
        detrended[np.isnan(trend)] = 0.0

        # Step 3: Extract seasonal pattern (average by position within period)
        seasonal_pattern = np.zeros(period)
        for i in range(period):
            positions = detrended[i::period]
            positions = positions[positions != 0]  # Exclude NaN positions
            if len(positions) > 0:
                seasonal_pattern[i] = np.mean(positions)
            else:
                seasonal_pattern[i] = 0.0

        # Step 4: Build full seasonal series (repeat pattern)
        seasonal = np.zeros(n)
        for i in range(n):
            seasonal[i] = seasonal_pattern[i % period]

        # Step 5: Noise = actual - trend - seasonal
        noise = values_arr - trend - seasonal
        noise[np.isnan(trend)] = 0.0

        return {
            "trend": np.round(trend, 2).tolist(),
            "seasonal": np.round(seasonal, 2).tolist(),
            "noise": np.round(noise, 2).tolist(),
            "period": period,
            "trend_strength": round(float(np.var(trend[~np.isnan(trend)])) / max(np.var(values_arr), 1e-6), 4),
            "seasonal_strength": round(float(np.var(seasonal)) / max(np.var(values_arr), 1e-6), 4),
        }

    @staticmethod
    def _empty_trend(name: str) -> TrendResult:
        """Return a default trend result for insufficient data."""
        return TrendResult(
            series_name=name,
            direction="stable",
            slope=0.0,
            r_squared=0.0,
            current_value=0.0,
            forecast_7d=0.0,
            forecast_30d=0.0,
            forecast_60d=0.0,
            forecast_90d=0.0,
            improvement_pct=0.0,
            decomposition=None,
        )

    @classmethod
    def detect_anomalies(
        cls,
        values: list[float],
        dates: list[str],
        window_size: int = 10,
        z_threshold: float = 2.5,
    ) -> list[AnomalyResult]:
        """
        Detect anomalies using rolling z-score method.

        Args:
            values: Time series values
            dates: Corresponding dates
            window_size: Window size for rolling statistics
            z_threshold: Z-score threshold for anomaly detection

        Returns:
            List of AnomalyResult objects
        """
        if len(values) < window_size * 2:
            return []

        anomalies = []
        values_array = np.array(values)

        for i in range(window_size, len(values_array)):
            window = values_array[max(0, i - window_size):i]
            mean = np.mean(window)
            std = np.std(window)

            if std == 0:
                # If all values in window are identical and current differs, it's an anomaly
                if values_array[i] != mean:
                    z_score = 999.0  # Treat as extreme anomaly
                else:
                    continue

            z_score = abs(values_array[i] - mean) / std

            if z_score > z_threshold:
                deviation = z_score
                if deviation > 3.5:
                    severity = "severe"
                elif deviation > 2.5:
                    severity = "moderate"
                else:
                    severity = "mild"

                date = dates[i] if i < len(dates) else f"point_{i}"

                anomalies.append(AnomalyResult(
                    index=i,
                    date=date,
                    value=float(values_array[i]),
                    expected=round(float(mean), 2),
                    deviation=round(float(deviation), 2),
                    severity=severity,
                ))

        return anomalies

    @classmethod
    def moving_average(
        cls,
        values: list[float],
        window: int = 7,
    ) -> list[float]:
        """
        Calculate moving average with NaN handling for initial points.

        Args:
            values: Time series values
            window: Window size

        Returns:
            List of moving average values (same length as input)
        """
        if len(values) < window:
            return values[:]

        result = [float('nan')] * len(values)
        values_array = np.array(values, dtype=float)

        for i in range(window - 1, len(values_array)):
            window_data = values_array[max(0, i - window + 1):i + 1]
            result[i] = round(float(np.mean(window_data)), 2)

        return result

    @classmethod
    def pareto_analysis(
        cls,
        categories: list[str],
        values: list[float],
    ) -> ParetoResult:
        """
        Perform Pareto analysis (80/20 rule).

        Args:
            categories: Category names
            values: Numeric values for each category

        Returns:
            ParetoResult with breakdown
        """
        if not categories or not values:
            return ParetoResult(
                categories=[],
                values=[],
                cumulative_pct=[],
                top_20_contributors=[],
                top_20_pct=0.0,
                total=0.0,
            )

        # Sort descending
        pairs = sorted(zip(categories, values), key=lambda x: x[1], reverse=True)
        sorted_categories = [p[0] for p in pairs]
        sorted_values = [p[1] for p in pairs]

        total = sum(sorted_values)
        cumulative = np.cumsum(sorted_values) / total * 100

        # Find top 20% contributors
        top_20_count = max(1, len(sorted_categories) // 5)
        top_20_contributors = sorted_categories[:top_20_count]
        top_20_pct = float(cumulative[min(top_20_count, len(cumulative) - 1)])

        return ParetoResult(
            categories=sorted_categories,
            values=sorted_values,
            cumulative_pct=[round(float(p), 2) for p in cumulative],
            top_20_contributors=top_20_contributors,
            top_20_pct=round(top_20_pct, 2),
            total=round(total, 2),
        )

    @classmethod
    def full_analysis(
        cls,
        oee_values: list[float],
        avail_values: list[float],
        perf_values: list[float],
        qual_values: list[float],
        dates: list[str],
        downtime_categories: Optional[list[str]] = None,
        downtime_values: Optional[list[float]] = None,
    ) -> TrendAnalysis:
        """
        Run full trend analysis on all OEE components.

        Args:
            oee_values: OEE time series
            avail_values: Availability time series
            perf_values: Performance time series
            qual_values: Quality time series
            dates: Corresponding dates
            downtime_categories: Downtime reason categories
            downtime_values: Downtime values per category

        Returns:
            Complete TrendAnalysis result
        """
        oee_trend = cls.analyze_trend(oee_values, "OEE")
        avail_trend = cls.analyze_trend(avail_values, "Availability")
        perf_trend = cls.analyze_trend(perf_values, "Performance")
        qual_trend = cls.analyze_trend(qual_values, "Quality")

        # Moving averages
        ma_7 = cls.moving_average(oee_values, 7)
        ma_30 = cls.moving_average(oee_values, 30)

        # Anomaly detection
        anomalies = cls.detect_anomalies(oee_values, dates)

        # Pareto analysis
        downtime_pareto = None
        if downtime_categories and downtime_values:
            downtime_pareto = cls.pareto_analysis(downtime_categories, downtime_values)

        # Overall direction
        trends = [oee_trend, avail_trend, perf_trend, qual_trend]
        directions = [t.direction for t in trends]

        if directions.count("up") >= 3:
            overall_direction = "improving"
        elif directions.count("down") >= 3:
            overall_direction = "declining"
        else:
            overall_direction = "mixed"

        # Key finding
        worst_trend = min(trends, key=lambda t: t.forecast_30d - t.current_value)
        best_trend = max(trends, key=lambda t: t.forecast_30d - t.current_value)

        key_findings = []
        if oee_trend.forecast_30d < oee_trend.current_value:
            key_findings.append(f"OEE forecast declining ({oee_trend.forecast_30d:.1f}% in 30 days vs {oee_trend.current_value:.1f}% now)")

        if len(anomalies) > 0:
            severe = [a for a in anomalies if a.severity == "severe"]
            if severe:
                key_findings.append(f"{len(severe)} severe anomaly detected")

        if downtime_pareto and downtime_pareto.top_20_pct > 70:
            key_findings.append(f"Top 20% of causes account for {downtime_pareto.top_20_pct:.0f}% of downtime")

        key_finding = "; ".join(key_findings) if key_findings else "No significant trends or anomalies detected"

        # Risk level
        if oee_trend.forecast_30d < 70 or len([a for a in anomalies if a.severity == "severe"]) >= 2:
            risk_level = "high"
        elif oee_trend.forecast_30d < 80 or len(anomalies) > 3:
            risk_level = "medium"
        else:
            risk_level = "low"

        return TrendAnalysis(
            oee_trend=oee_trend,
            availability_trend=avail_trend,
            performance_trend=perf_trend,
            quality_trend=qual_trend,
            anomalies=anomalies,
            downtime_pareto=downtime_pareto,
            oee_ma_7=ma_7,
            oee_ma_30=ma_30,
            overall_direction=overall_direction,
            key_finding=key_finding,
            risk_level=risk_level,
        )
