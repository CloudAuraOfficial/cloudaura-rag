# Observability Stack: Metrics, Logging, and Distributed Tracing

## The Three Pillars of Observability

Observability in distributed systems is built on three complementary pillars: **metrics**, **logs**, and **traces**. Each pillar addresses a different dimension of system behavior. **Metrics** provide quantitative measurements over time — CPU usage, request latency, error rates. **Logs** capture discrete events with contextual detail — error messages, audit records, state transitions. **Traces** track a single request as it flows across multiple services in a microservices architecture, revealing latency bottlenecks and failure points. Together, these three pillars enable engineers to understand, debug, and optimize complex distributed systems.

## Prometheus: Metrics Collection and Alerting

**Prometheus** is an open-source monitoring and alerting toolkit developed originally at SoundCloud and now a graduated project of the **Cloud Native Computing Foundation (CNCF)**. Prometheus is the de facto standard for metrics collection in Kubernetes environments.

### Architecture

Prometheus follows a **pull-based model**: the Prometheus server periodically scrapes HTTP endpoints (called **targets**) that expose metrics in the Prometheus exposition format. Each target exposes a `/metrics` endpoint that returns time-series data as labeled key-value pairs. For example, the metric `http_requests_total{method="GET", status="200", handler="/api/v1/users"}` counts HTTP GET requests returning status 200 on a specific handler.

Prometheus stores time-series data in its local **time-series database (TSDB)** on disk, organized in two-hour blocks that are compacted over time. The TSDB supports efficient range queries and aggregations over millions of time series. For long-term storage beyond Prometheus's local retention period, organizations use remote storage solutions: **Thanos** adds a global query layer and stores data in object storage (S3, GCS), while **Cortex** (now part of **Grafana Mimir**) provides horizontally scalable, multi-tenant Prometheus storage.

### Service Discovery in Kubernetes

Prometheus integrates deeply with Kubernetes through its **kubernetes_sd_config** service discovery mechanism. Prometheus can automatically discover scrape targets by querying the Kubernetes API Server for:

- **Pods** with specific annotations (e.g., `prometheus.io/scrape: "true"` and `prometheus.io/port: "8080"`)
- **Services** and their backing Endpoints
- **Nodes** for infrastructure-level metrics
- **Ingress** resources

This automatic discovery eliminates manual target configuration and ensures new Pods and Services are scraped as soon as they appear. The **Prometheus Operator**, installed via Helm chart, extends this with custom resources: **ServiceMonitor** defines which Services to scrape, **PodMonitor** defines which Pods to scrape, and **PrometheusRule** defines alerting rules.

### Exporters

Many systems do not natively expose Prometheus metrics. **Exporters** bridge this gap by converting system-specific metrics into the Prometheus format:

- **Node Exporter** runs as a DaemonSet on every Kubernetes node and exposes hardware metrics — CPU utilization, memory usage, disk I/O, network traffic, filesystem capacity.
- **kube-state-metrics** exposes Kubernetes object state as metrics — Deployment replica counts, Pod phases, DaemonSet desired vs. current counts, PersistentVolumeClaim status.
- **cAdvisor** (Container Advisor) is embedded in the kubelet and exposes per-container resource usage metrics — CPU, memory, filesystem, and network.
- **Blackbox Exporter** performs active probing (HTTP, DNS, TCP, ICMP) to measure endpoint availability and latency.
- **PostgreSQL Exporter**, **MySQL Exporter**, **Redis Exporter**, and **Elasticsearch Exporter** expose database-specific metrics.

### PromQL

**PromQL (Prometheus Query Language)** is a functional query language for selecting, aggregating, and transforming time-series data. Queries can compute rates (`rate(http_requests_total[5m])`), percentiles (`histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))`), and complex aggregations across label dimensions (`sum by (service) (rate(http_requests_total[5m]))`). PromQL powers both Grafana dashboards and Prometheus alerting rules.

### Alertmanager

**Alertmanager** is a companion component to Prometheus that handles alert deduplication, grouping, silencing, and routing. Prometheus evaluates alerting rules defined in **PrometheusRule** resources and sends firing alerts to Alertmanager. Alertmanager then routes alerts to notification channels based on label matching: **PagerDuty** for critical production alerts, **Slack** for warnings, **email** for informational notices. Alertmanager supports **inhibition** (suppressing certain alerts when others are firing) and **silencing** (temporarily muting alerts during maintenance windows).

## Grafana: Visualization and Dashboards

**Grafana** is an open-source visualization platform that connects to multiple data sources and renders metrics, logs, and traces in interactive dashboards. Grafana is the standard visualization layer for Prometheus metrics and is commonly deployed alongside Prometheus in Kubernetes clusters.

### Data Sources

Grafana supports dozens of data sources through built-in and plugin integrations:

- **Prometheus** for metrics queries using PromQL
- **Loki** for log queries using LogQL
- **Jaeger** and **Zipkin** for distributed trace exploration
- **Elasticsearch** for log and full-text search queries
- **PostgreSQL**, **MySQL**, and **InfluxDB** for direct database queries
- **Tempo** (Grafana's distributed tracing backend) for trace queries

### Dashboards and Panels

Grafana dashboards are composed of **panels**, each displaying a single visualization. Panel types include time-series graphs, stat panels, gauge panels, bar charts, tables, heatmaps, and log panels. Dashboards support **template variables** that enable dynamic filtering — for example, a variable `$namespace` that populates a dropdown with all Kubernetes namespaces, allowing users to switch context without editing queries.

The Grafana community maintains a library of pre-built dashboards at **grafana.com/grafana/dashboards**. Popular dashboards include the Kubernetes cluster monitoring dashboard (ID: 6417), the Node Exporter Full dashboard (ID: 1860), and the NGINX Ingress Controller dashboard (ID: 9614). These can be imported directly and customized.

### Grafana Alerting

Grafana includes its own alerting engine (Grafana Alerting, formerly Unified Alerting) that can evaluate queries against any configured data source and fire alerts. Grafana alerting supports **multi-dimensional alerts** that create a separate alert instance for each label combination, **notification policies** for routing, and **contact points** for delivery to Slack, PagerDuty, OpsGenie, Microsoft Teams, and webhooks.

## Logging: Collecting and Querying Logs

### The ELK Stack

The **ELK Stack** consists of **Elasticsearch**, **Logstash**, and **Kibana**. **Elasticsearch** is a distributed search and analytics engine that stores log data in inverted indices for fast full-text search. **Logstash** is a data processing pipeline that ingests logs from multiple sources, transforms them (parsing, filtering, enriching), and outputs them to Elasticsearch. **Kibana** is the visualization layer that provides a web UI for searching, filtering, and visualizing log data stored in Elasticsearch. In Kubernetes, **Filebeat** (a lightweight log shipper from Elastic) typically replaces Logstash for collection — Filebeat runs as a DaemonSet, reads container logs from `/var/log/containers/`, and ships them to Elasticsearch.

### Grafana Loki

**Grafana Loki** is a log aggregation system designed by Grafana Labs as a lightweight alternative to Elasticsearch. Unlike Elasticsearch, which indexes the full content of every log line, Loki indexes only **labels** (metadata) and stores the raw log content in compressed chunks in object storage (S3, GCS, Azure Blob). This approach dramatically reduces storage and operational costs.

Loki's collection agent is **Promtail**, which runs as a DaemonSet on every Kubernetes node. Promtail discovers Pods through the Kubernetes API, attaches labels (namespace, pod name, container name) to log streams, and pushes them to Loki. **Grafana Alloy** (formerly Grafana Agent) can also collect logs alongside metrics and traces in a single agent.

Loki uses **LogQL** as its query language, which combines log filtering with PromQL-style metric aggregations. A query like `{namespace="production", app="api-gateway"} |= "error" | json | rate({} [5m])` filters logs from the api-gateway in production containing "error", parses them as JSON, and computes the error rate over 5-minute windows.

## Distributed Tracing

Distributed tracing tracks the lifecycle of a request as it traverses multiple services in a microservices architecture. A **trace** represents the entire journey and consists of multiple **spans**. Each span represents a unit of work within a single service — an HTTP handler, a database query, a message queue publish. Spans form a tree structure via parent-child relationships, and the root span represents the initial entry point.

### OpenTelemetry

**OpenTelemetry (OTel)** is the CNCF standard for generating, collecting, and exporting telemetry data (metrics, logs, and traces). OpenTelemetry merges the previous **OpenTracing** and **OpenCensus** projects into a unified framework. OTel provides SDKs for all major languages (Go, Java, Python, .NET, JavaScript, Rust) that instrument application code to generate spans.

The **OpenTelemetry Collector** is a vendor-neutral pipeline that receives telemetry data, processes it (batching, filtering, sampling, enriching), and exports it to backends. The Collector can receive data via OTLP (OpenTelemetry Protocol), Jaeger, or Zipkin formats and export to Jaeger, Zipkin, Grafana Tempo, AWS X-Ray, Datadog, or New Relic.

### Jaeger

**Jaeger** is a distributed tracing backend developed by Uber and donated to the CNCF (graduated project). Jaeger stores traces and provides a web UI for visualizing trace timelines, comparing traces, and analyzing latency distributions. Jaeger supports multiple storage backends: **Elasticsearch**, **Apache Cassandra**, **Kafka** (as a buffer), and **Badger** (for local development). In a Kubernetes deployment, the **Jaeger Operator** automates deployment and configuration.

### Zipkin

**Zipkin** is an earlier distributed tracing system originally developed by Twitter based on Google's Dapper paper. Zipkin provides similar trace collection and visualization capabilities as Jaeger but with a different architecture. Zipkin stores traces in Elasticsearch, MySQL, or Apache Cassandra. While Jaeger has largely superseded Zipkin in Kubernetes environments, many legacy systems still export traces in Zipkin format, which both Jaeger and the OpenTelemetry Collector can accept.

### Grafana Tempo

**Grafana Tempo** is a high-scale, cost-efficient distributed tracing backend from Grafana Labs. Like Loki's approach to logs, Tempo stores traces in object storage without indexing trace content — it relies on trace IDs and integration with Loki and Prometheus for trace discovery. Tempo accepts traces via OTLP, Jaeger, and Zipkin protocols and integrates natively with Grafana for visualization, enabling a seamless **metrics-to-traces-to-logs** correlation workflow within a single Grafana dashboard.
