"""
Monitoring and alerting models for KAKEHASHI kek_wrapper.

Defines Pydantic models for metrics, health status, alert rules, and alerts.
"""

from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class MetricType(str, Enum):
    """Metric types for different measurement styles."""
    COUNTER = "COUNTER"           # 累計カウント
    GAUGE = "GAUGE"               # 現在値
    HISTOGRAM = "HISTOGRAM"        # 分布(レイテンシなど)
    RATE = "RATE"                 # 時間あたり頻度


class Metric(BaseModel):
    """Single metric measurement."""
    name: str  # e.g., "kek_vault_cache_hit_rate", "audit_log_write_latency_ms"
    type: MetricType
    value: float
    unit: str  # e.g., "percent", "milliseconds", "count"
    timestamp: datetime
    tags: Dict[str, str] = Field(default_factory=dict)  # e.g., {"secret_name": "user-key-prod"}

    class Config:
        use_enum_values = True


class HealthStatus(BaseModel):
    """Overall health status of all system components."""
    timestamp: datetime
    overall_status: str  # "HEALTHY", "DEGRADED", "UNHEALTHY"
    checks: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    # e.g., {"azure_key_vault": {"status": "HEALTHY", "latency_ms": 42, "version_count": 5}}

    class Config:
        use_enum_values = True


class AlertRule(BaseModel):
    """Alert rule definition with threshold and escalation."""
    rule_id: str
    name: str
    condition: str  # e.g., "metric(kek_vault_error_rate) > 0.05"
    severity: AlertSeverity
    threshold_value: float
    window_minutes: int  # 何分のメトリクスを集約するか
    enabled: bool
    channels: List[str]  # ["slack-security", "email-ops"]
    escalation_rules: Optional[List[str]] = None  # ["PagerDuty", "phone_call_admin"]

    class Config:
        use_enum_values = True


class Alert(BaseModel):
    """Single alert instance."""
    alert_id: str
    timestamp: datetime
    rule_id: str
    severity: AlertSeverity
    title: str
    message: str
    metric_value: float
    metric_name: str
    context: Dict[str, Any]  # 追加情報(user_id, error_code など)
    status: str  # "NEW", "ACKNOWLEDGED", "RESOLVED"

    class Config:
        use_enum_values = True
