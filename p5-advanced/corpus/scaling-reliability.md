# Scaling and Reliability in Kubernetes

## Resource Management

Effective scaling and reliability in Kubernetes begin with proper resource management. Every container in a Pod can specify **resource requests** and **resource limits** for CPU and memory.

**Resource requests** define the minimum amount of CPU and memory that the kubelet guarantees to a container. The **kube-scheduler** uses requests when making placement decisions — a Pod with a request of 500m CPU and 256Mi memory will only be scheduled on a node with at least that much allocatable capacity. Requests are used by the scheduler's filtering phase to eliminate nodes that cannot satisfy the Pod's needs.

**Resource limits** define the maximum amount of CPU and memory a container can consume. The kubelet enforces limits through Linux cgroups. CPU limits are enforced via CPU throttling — when a container exceeds its CPU limit, the kernel throttles its CPU time, causing increased latency but not termination. Memory limits are enforced strictly — when a container exceeds its memory limit, the Linux OOM (Out of Memory) killer terminates it, and the kubelet restarts the container according to the Pod's `restartPolicy`.

### Quality of Service Classes

Kubernetes assigns each Pod a **Quality of Service (QoS)** class based on its resource configuration:

- **Guaranteed**: Every container in the Pod has both requests and limits set, and they are equal. Guaranteed Pods receive the highest priority and are the last to be evicted under memory pressure.
- **Burstable**: At least one container has requests set, but requests and limits differ. Burstable Pods can use more resources than requested but are evicted before Guaranteed Pods when the node is under pressure.
- **BestEffort**: No container has any resource requests or limits. BestEffort Pods are the first to be evicted and should be avoided for production workloads.

When a node experiences memory pressure, the kubelet evicts Pods in order: BestEffort first, then Burstable (sorted by how much they exceed their request), and finally Guaranteed. This eviction hierarchy makes properly setting resource requests and limits critical for production reliability.

### LimitRanges and ResourceQuotas

**LimitRange** resources set default, minimum, and maximum resource values for containers within a namespace. If a Pod does not specify resource requests or limits, the LimitRange's default values are applied automatically. This prevents BestEffort Pods from being deployed accidentally.

**ResourceQuota** resources set aggregate resource limits for an entire namespace — for example, limiting the total CPU requests to 32 cores, total memory requests to 64Gi, and the maximum number of Pods to 100. ResourceQuotas enforce multi-tenancy boundaries, preventing a single team's namespace from consuming disproportionate cluster resources. When a ResourceQuota is active, all Pods in the namespace must specify resource requests and limits (enforced by the ResourceQuota admission controller).

## Horizontal Pod Autoscaler (HPA)

The **Horizontal Pod Autoscaler (HPA)** automatically adjusts the number of Pod replicas in a Deployment, ReplicaSet, or StatefulSet based on observed metrics. The HPA controller (running in the kube-controller-manager) queries metrics at a configurable interval (default 15 seconds) and calculates the desired replica count using the formula:

```
desiredReplicas = ceil(currentReplicas * (currentMetricValue / targetMetricValue))
```

### Metric Sources

HPA supports three categories of metrics:

- **Resource metrics**: CPU and memory utilization, provided by the **Metrics Server** (a lightweight, in-cluster component that collects resource metrics from kubelets and exposes them via the `metrics.k8s.io` API). A common HPA target is `averageUtilization: 70` for CPU, meaning the HPA scales up when average CPU utilization across all Pods exceeds 70% of their requested CPU.
- **Custom metrics**: Application-specific metrics exposed via the `custom.metrics.k8s.io` API. The **Prometheus Adapter** bridges Prometheus metrics to this API, enabling HPA to scale based on metrics like requests per second, queue depth, or active connections. For example, an HPA can target `http_requests_per_second` at 1000, scaling up when the per-Pod average exceeds this threshold.
- **External metrics**: Metrics from systems outside the cluster, exposed via the `external.metrics.k8s.io` API. This enables scaling based on cloud queue depth (e.g., AWS SQS queue length), Pub/Sub subscription message count, or external monitoring systems.

### Scaling Behavior

HPA v2 (the current version) supports **scaling policies** that control the rate of scaling up and down:

- `scaleUp.stabilizationWindowSeconds` prevents rapid scale-up by requiring the metric to exceed the threshold for a sustained period (default: 0 seconds for scale-up).
- `scaleDown.stabilizationWindowSeconds` prevents premature scale-down by waiting for metrics to stabilize below the threshold (default: 300 seconds, meaning the HPA waits 5 minutes before scaling down).
- `policies` allow specifying the maximum number of Pods or percentage of Pods that can be added or removed in a given time period.

These controls prevent **flapping** — rapid, oscillating scale-up and scale-down cycles caused by transient metric spikes.

## Vertical Pod Autoscaler (VPA)

The **Vertical Pod Autoscaler (VPA)** automatically adjusts the CPU and memory requests and limits of containers based on historical usage data. Unlike HPA, which scales horizontally by adding or removing Pods, VPA scales vertically by right-sizing individual Pods.

VPA consists of three components:

- **VPA Recommender**: Analyzes historical resource usage from the **Metrics Server** (or Prometheus) and generates recommendations for optimal CPU and memory requests.
- **VPA Updater**: Evicts Pods that are significantly over- or under-provisioned so they can be recreated with updated resource values.
- **VPA Admission Controller**: A mutating webhook that modifies the resource requests of new Pods to match VPA recommendations at creation time.

VPA operates in three modes:
- **Off**: Generates recommendations but does not apply them (recommendation-only mode, useful for initial analysis).
- **Initial**: Applies recommendations only when Pods are created but does not evict running Pods.
- **Auto**: Applies recommendations at creation time and evicts running Pods to apply updated recommendations.

An important limitation is that **HPA and VPA should not target the same metric simultaneously**. Running HPA on CPU utilization while VPA adjusts CPU requests creates a feedback loop — VPA increases the request, which lowers the utilization percentage, causing HPA to scale down, which increases utilization, causing HPA to scale back up. The recommended approach is to use HPA for scaling based on traffic metrics (requests per second, queue depth) and VPA for right-sizing resource requests based on actual usage.

## Cluster Autoscaler

The **Cluster Autoscaler** adjusts the number of nodes in a Kubernetes cluster based on Pod scheduling demands. It operates at the infrastructure level, complementing HPA's Pod-level scaling.

**Scale-up** is triggered when Pods are in `Pending` state because no node has sufficient allocatable resources to schedule them. The Cluster Autoscaler evaluates which **node group** (AWS Auto Scaling Group, GCP Managed Instance Group, or Azure Virtual Machine Scale Set) can accommodate the pending Pods and requests additional nodes from the cloud provider. New nodes register with the API Server within minutes.

**Scale-down** occurs when a node's utilization drops below a configurable threshold (default: 50%) for a sustained period (default: 10 minutes). Before removing a node, the Cluster Autoscaler checks that all Pods on the node can be rescheduled elsewhere. It respects **Pod Disruption Budgets** and will not evict Pods that block safe removal — for example, Pods with local storage (emptyDir with data), Pods not managed by a controller, or Pods with restrictive PDBs.

**Karpenter** (originally developed by AWS, now a CNCF project) is a next-generation node autoscaler that provisions nodes directly using cloud provider APIs rather than relying on node groups. Karpenter evaluates pending Pod requirements (resource requests, node selectors, tolerations, topology spread constraints) and provisions optimally sized nodes in seconds. Karpenter's **NodePool** resource replaces traditional node groups, offering more granular control over instance types, availability zones, and capacity types (on-demand vs. spot).

## Pod Disruption Budgets (PDB)

A **Pod Disruption Budget** protects application availability during **voluntary disruptions** — events like node drains (during upgrades or maintenance), cluster autoscaler scale-downs, or manual Pod evictions. PDBs do **not** protect against involuntary disruptions such as hardware failures or kernel panics.

A PDB specifies either `minAvailable` (the minimum number of Pods that must remain running) or `maxUnavailable` (the maximum number of Pods that can be unavailable) for a set of Pods selected by label. For example, a PDB with `minAvailable: 2` for a three-replica Deployment ensures that at most one Pod can be evicted at a time during a rolling node drain.

The **Eviction API** (used by `kubectl drain`, the Cluster Autoscaler, and Karpenter) respects PDBs. If evicting a Pod would violate the PDB, the eviction request is rejected and retried after a backoff. This mechanism ensures that cluster maintenance operations do not degrade application availability below defined thresholds.

## Node Affinity and Anti-Affinity

**Node affinity** controls which nodes a Pod can be scheduled on, based on node labels. Node affinity comes in two forms:

- **requiredDuringSchedulingIgnoredDuringExecution**: A hard requirement — the Pod is only scheduled on nodes matching the specified label expressions. Used to ensure GPU workloads run on nodes with GPUs (`nvidia.com/gpu: "true"`) or to restrict workloads to specific availability zones.
- **preferredDuringSchedulingIgnoredDuringExecution**: A soft preference — the Scheduler prefers matching nodes but will schedule elsewhere if necessary, with configurable weights.

**Pod affinity and anti-affinity** control Pod placement relative to other Pods:

- **Pod affinity** schedules Pods near other Pods with matching labels. For example, scheduling a cache Pod on the same node as the web server Pod it serves, reducing network latency.
- **Pod anti-affinity** prevents Pods from being co-located. A common pattern uses `requiredDuringSchedulingIgnoredDuringExecution` pod anti-affinity to spread replicas of a Deployment across different nodes or availability zones, ensuring that a single node failure does not take down all replicas.

### Topology Spread Constraints

**Topology spread constraints** provide finer-grained control over how Pods are distributed across failure domains (nodes, zones, regions). A topology spread constraint specifies a `topologyKey` (e.g., `topology.kubernetes.io/zone`), a `maxSkew` (the maximum difference in Pod count between any two topology domains), and a `whenUnsatisfiable` action (`DoNotSchedule` or `ScheduleAnyway`).

For example, a constraint with `topologyKey: topology.kubernetes.io/zone` and `maxSkew: 1` ensures that Pod replicas are evenly distributed across availability zones. If zone-a has 3 Pods and zone-b has 2, the next Pod must go to zone-b to maintain the skew within 1.

## High Availability Patterns

### Multi-Zone Deployments

Production Kubernetes clusters span multiple **availability zones** within a cloud region. The control plane components (API Server, etcd, Scheduler, Controller Manager) run across three zones. Worker nodes are distributed across zones, and topology spread constraints ensure application Pods are zone-balanced. Cloud load balancers (used by LoadBalancer Services) distribute traffic across all zones.

### etcd High Availability

etcd requires an odd number of members (3 or 5) to maintain quorum via the Raft consensus protocol. A three-member etcd cluster tolerates one member failure; a five-member cluster tolerates two. etcd members should run on dedicated nodes in separate availability zones to prevent correlated failures. Regular etcd snapshots (via `etcdctl snapshot save`) are essential for disaster recovery — if quorum is permanently lost, the cluster must be restored from a snapshot.

### Application-Level HA

Applications achieve high availability through multiple patterns working together: running multiple replicas via Deployments (minimum 3 for critical services), spreading replicas across zones with pod anti-affinity and topology spread constraints, configuring PDBs to protect against cascading failures during maintenance, setting appropriate readiness probes to prevent traffic routing to unhealthy Pods, and using **preStop lifecycle hooks** (e.g., `sleep 5`) to allow in-flight requests to complete before the Pod is removed from Service endpoints during termination.
