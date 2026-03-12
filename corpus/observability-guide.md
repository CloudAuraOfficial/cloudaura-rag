# Observability Engineering Guide

## The Three Pillars

### Metrics

Metrics are numerical measurements collected at regular intervals. They are efficient to store and query, making them ideal for dashboards, alerting, and trend analysis.

Key metric types:
- **Counter**: Monotonically increasing value (e.g., total requests served). Can only go up or reset to zero.
- **Gauge**: Value that can go up or down (e.g., current memory usage, active connections).
- **Histogram**: Samples observations and counts them in configurable buckets (e.g., request duration distribution). Enables percentile calculations (p50, p95, p99).
- **Summary**: Similar to histogram but calculates quantiles on the client side. Less flexible for aggregation across instances.

### Logs

Logs are discrete, timestamped records of events. They provide detailed context about what happened.

Structured logging best practices:
- Use JSON format for machine parseability
- Include: timestamp, level, service name, trace ID, span ID
- Log at appropriate levels (DEBUG for development, INFO for operations, ERROR for failures)
- Never log secrets, tokens, or PII
- Include enough context to diagnose issues without accessing the code

### Traces

Distributed traces track a request's journey across multiple services. A trace consists of spans — units of work within a service.

Trace components:
- **Trace ID**: Unique identifier for the entire request flow
- **Span**: A single operation within a trace (e.g., database query, HTTP call)
- **Parent Span ID**: Links spans into a tree structure
- **Tags/Attributes**: Key-value pairs providing context (HTTP method, status code, user ID)

## Prometheus

### Architecture

Prometheus uses a pull-based model: the server scrapes HTTP endpoints at configured intervals. Components:

- **Prometheus Server**: Scrapes and stores time-series data
- **Alertmanager**: Handles alert routing, deduplication, and notification
- **Pushgateway**: For short-lived jobs that can't be scraped
- **Exporters**: Expose metrics from third-party systems (node_exporter, postgres_exporter)

### PromQL

Prometheus Query Language enables powerful metric queries:

- Instant vectors: `http_requests_total{status="200"}`
- Range vectors: `http_requests_total[5m]`
- Rate: `rate(http_requests_total[5m])` — per-second average increase
- Aggregation: `sum by (service)(rate(http_requests_total[5m]))`
- Percentiles: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))`

### Instrumentation

Application-level metrics should include:

RED Method (for services):
- **R**ate: Number of requests per second
- **E**rrors: Number of failed requests per second
- **D**uration: Distribution of request latencies

USE Method (for resources):
- **U**tilization: Percentage of resource busy time
- **S**aturation: Amount of work queued
- **E**rrors: Count of error events

### Alerting Best Practices

- Alert on symptoms (high latency, error rate) not causes (CPU usage)
- Use multi-window, multi-burn-rate alerts for SLO-based alerting
- Include runbook links in alert annotations
- Set appropriate severity levels (critical = pages, warning = ticket)
- Avoid alert fatigue: every alert should be actionable

## Grafana

### Dashboard Design

Effective dashboards follow these principles:

1. **Start with the golden signals**: Latency, Traffic, Errors, Saturation
2. **Layer from overview to detail**: Summary dashboard → service dashboard → debug dashboard
3. **Use consistent units and scales** across panels
4. **Include time range controls** and template variables for filtering
5. **Add annotations** for deployments, incidents, and configuration changes

### Panel Types

- **Time series**: For metrics over time (latency, throughput)
- **Stat**: Single value with optional sparkline (current error rate)
- **Gauge**: For values with a known range (CPU utilization)
- **Table**: For listing items (top slow endpoints, recent errors)
- **Heatmap**: For distribution visualization (latency buckets over time)
- **Logs**: For correlating log events with metric anomalies

## SLOs and Error Budgets

### Service Level Indicators (SLI)

An SLI is a quantitative measure of service reliability:
- Availability: proportion of successful requests
- Latency: proportion of requests faster than a threshold
- Throughput: proportion of time throughput exceeds a minimum
- Correctness: proportion of responses with correct data

### Service Level Objectives (SLO)

An SLO is a target value for an SLI over a time window:
- "99.9% of requests will return successfully in a 30-day window"
- "95% of requests will complete in under 200ms"

### Error Budgets

Error budget = 1 - SLO. For a 99.9% availability SLO:
- 30-day error budget = 0.1% = 43.2 minutes of downtime
- When budget is consumed, prioritize reliability over features
- Track burn rate: how fast the error budget is being consumed

## Cost Tracking

### Per-Request Cost

For AI/ML services, track cost at the request level:
- Input tokens × input price per token
- Output tokens × output price per token
- Embedding API calls
- Vector database query costs
- Compute time (GPU/CPU seconds)

Aggregate into:
- Cost per user
- Cost per feature
- Daily/monthly spend trends
- Cost anomaly detection

### Optimization

- Cache frequently requested embeddings
- Use smaller models for simple queries (routing)
- Batch embedding requests where possible
- Set per-user rate limits and cost caps
- Monitor cost-per-quality ratio to avoid over-spending on marginal improvements
