"""Small process-local HTTP metrics in Prometheus text exposition format."""

from __future__ import annotations

from collections import Counter, defaultdict
from threading import Lock

HISTOGRAM_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


class HttpMetrics:
    """Track bounded-cardinality request counts and latency per API route."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._requests: Counter[tuple[str, str, int]] = Counter()
        self._assistant_outcomes: Counter[str] = Counter()
        self._feedback: Counter[tuple[str, bool]] = Counter()
        self._duration_count: Counter[tuple[str, str]] = Counter()
        self._duration_sum: defaultdict[tuple[str, str], float] = defaultdict(float)
        self._duration_buckets: Counter[tuple[str, str, float]] = Counter()

    def observe(self, method: str, route: str, status: int, duration_seconds: float) -> None:
        key = (method, route, status)
        duration_key = (method, route)
        with self._lock:
            self._requests[key] += 1
            self._duration_count[duration_key] += 1
            self._duration_sum[duration_key] += duration_seconds
            for boundary in HISTOGRAM_BUCKETS:
                if duration_seconds <= boundary:
                    self._duration_buckets[(method, route, boundary)] += 1

    def observe_assistant_outcome(self, outcome: str) -> None:
        """Count bounded assistant route outcomes without user or prompt labels."""
        allowed = {
            "answer",
            "clarify",
            "refuse",
            "escalate",
            "out_of_scope",
            "provider_unavailable",
            "retrieval_unavailable",
        }
        with self._lock:
            self._assistant_outcomes[outcome if outcome in allowed else "other"] += 1

    def observe_feedback(self, rating: str, reported: bool) -> None:
        """Count a bounded rating/report choice without collecting its content."""
        if rating not in {"helpful", "not_helpful"}:
            rating = "other"
        with self._lock:
            self._feedback[(rating, reported)] += 1

    def render(self) -> str:
        """Render aggregate request/error/latency metrics with no user data labels."""
        lines = [
            "# HELP lexaware_http_requests_total Completed HTTP requests.",
            "# TYPE lexaware_http_requests_total counter",
            "# HELP lexaware_http_request_duration_seconds HTTP request duration.",
            "# TYPE lexaware_http_request_duration_seconds histogram",
            "# HELP lexaware_assistant_responses_total Assistant response routes.",
            "# TYPE lexaware_assistant_responses_total counter",
            "# HELP lexaware_assistant_feedback_total Aggregate assistant ratings and reports.",
            "# TYPE lexaware_assistant_feedback_total counter",
        ]
        with self._lock:
            for (rating, reported), value in sorted(self._feedback.items()):
                lines.append(
                    f'lexaware_assistant_feedback_total{{rating="{rating}",'
                    f'reported="{str(reported).lower()}"}} {value}'
                )
            for outcome, value in sorted(self._assistant_outcomes.items()):
                lines.append(f'lexaware_assistant_responses_total{{outcome="{outcome}"}} {value}')
            for (method, route, status), value in sorted(self._requests.items()):
                lines.append(
                    f'lexaware_http_requests_total{{method="{method}",route="{route}",'
                    f'status="{status}"}} {value}'
                )
            for method, route in sorted(self._duration_count):
                labels = f'method="{method}",route="{route}"'
                for boundary in HISTOGRAM_BUCKETS:
                    count = self._duration_buckets[(method, route, boundary)]
                    lines.append(
                        f"lexaware_http_request_duration_seconds_bucket{{{labels},"
                        f'le="{boundary}"}} {count}'
                    )
                count = self._duration_count[(method, route)]
                lines.append(
                    f'lexaware_http_request_duration_seconds_bucket{{{labels},le="+Inf"}} {count}'
                )
                total = self._duration_sum[(method, route)]
                lines.append(f"lexaware_http_request_duration_seconds_sum{{{labels}}} {total:.6f}")
                lines.append(f"lexaware_http_request_duration_seconds_count{{{labels}}} {count}")
        return "\n".join(lines) + "\n"


http_metrics = HttpMetrics()
