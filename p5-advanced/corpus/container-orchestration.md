# Container Orchestration: From Docker Images to Kubernetes Workloads

## Containers and Docker

A **container** is a lightweight, isolated process that packages an application and its dependencies into a single executable unit. Containers share the host operating system's kernel but are isolated via Linux kernel features: **namespaces** provide process, network, and filesystem isolation, while **cgroups** (control groups) enforce resource limits on CPU, memory, and I/O.

**Docker** is the most widely recognized container platform. Docker introduced the concept of a container image — a read-only template built from a **Dockerfile** that specifies a base image, application code, dependencies, and runtime commands. Docker images are composed of **layers**, where each instruction in a Dockerfile creates a new filesystem layer. Layers are cached and shared between images, which reduces storage usage and speeds up builds. A Docker image is identified by its **repository name**, **tag**, and **digest** (a SHA-256 hash of the image manifest).

### Container Registries

Container images are stored in and distributed from **container registries**. **Docker Hub** is the default public registry, hosting millions of images including official images for Nginx, PostgreSQL, Redis, Python, and Node.js. Private registries include **Amazon Elastic Container Registry (ECR)**, **Google Container Registry (GCR)** and its successor **Artifact Registry**, **Azure Container Registry (ACR)**, and **GitHub Container Registry (ghcr.io)**. Organizations often run self-hosted registries using **Harbor** (a CNCF graduated project) for vulnerability scanning, access control, and image replication.

When Kubernetes schedules a Pod on a worker node, the **kubelet** instructs the container runtime (typically **containerd**) to pull the required image from the specified registry. If the image requires authentication, Kubernetes uses **imagePullSecrets** — references to Kubernetes Secrets containing registry credentials — attached to the Pod spec or the ServiceAccount.

### Container Runtime Interface

Kubernetes does not run containers directly. Instead, it delegates container lifecycle management to a **CRI-compliant container runtime**. The **Container Runtime Interface (CRI)** is a gRPC API that the kubelet uses to instruct the runtime to create, start, stop, and delete containers. **containerd** implements CRI natively and is the default runtime in most Kubernetes distributions. **CRI-O** is an alternative runtime developed specifically for Kubernetes by Red Hat. Both containerd and CRI-O use **runc** as the low-level OCI runtime to create container processes using Linux namespaces and cgroups.

## Kubernetes Workload Resources

Kubernetes provides several resource types for managing containerized workloads, each designed for specific deployment patterns.

### Pods

A **Pod** is the smallest deployable unit in Kubernetes. A Pod encapsulates one or more containers that share the same network namespace (they communicate via `localhost`), the same IPC namespace, and optionally the same storage volumes. Every Pod receives a unique IP address within the cluster's Pod network (CIDR range).

Pods are ephemeral — they are not self-healing. If a Pod's node fails or the Pod is evicted, it is not automatically recreated unless managed by a higher-level controller. Pods can contain **init containers** that run to completion before the main application containers start, commonly used for database migrations, configuration downloads, or waiting for dependencies.

A Pod's lifecycle progresses through phases: **Pending** (accepted but not yet scheduled or pulling images), **Running** (at least one container is running), **Succeeded** (all containers terminated successfully), **Failed** (at least one container terminated with an error), and **Unknown** (node communication lost).

### ReplicaSets

A **ReplicaSet** ensures that a specified number of identical Pod replicas are running at any given time. The ReplicaSet controller, which runs inside the kube-controller-manager, continuously monitors the number of Pods matching its **label selector**. If the actual count is less than the desired count, the ReplicaSet creates new Pods via the API Server. If the count exceeds the desired number, it deletes excess Pods.

ReplicaSets use **label selectors** to identify which Pods they manage. A label selector such as `app: web-frontend, version: v2` matches all Pods carrying both labels. This decoupled ownership model means a ReplicaSet does not directly "contain" Pods — it discovers them by label match.

In practice, users rarely create ReplicaSets directly. Instead, they create **Deployments**, which manage ReplicaSets automatically.

### Deployments

A **Deployment** is the standard resource for managing stateless applications in Kubernetes. A Deployment declares the desired state — container image, replica count, resource limits, environment variables, volumes — and the Deployment controller creates and manages a **ReplicaSet** to fulfill that state.

When a Deployment's Pod template is updated (for example, changing the container image tag from `v1.2.0` to `v1.3.0`), the Deployment controller creates a **new ReplicaSet** with the updated template and gradually scales it up while scaling down the old ReplicaSet. This process is called a **rolling update**. The `maxSurge` and `maxUnavailable` parameters control the pace: `maxSurge` defines how many extra Pods can exist above the desired count during the update, and `maxUnavailable` defines how many Pods can be unavailable.

Deployments maintain a **revision history** of ReplicaSets, enabling **rollbacks**. The command `kubectl rollout undo deployment/my-app` reverts to the previous ReplicaSet. The `revisionHistoryLimit` field controls how many old ReplicaSets are retained (default: 10).

### StatefulSets

A **StatefulSet** manages Pods that require stable, persistent identity and ordered deployment. Unlike Deployment-managed Pods that receive random names (e.g., `web-abc123`), StatefulSet Pods receive deterministic names with ordinal indices: `database-0`, `database-1`, `database-2`. Each Pod in a StatefulSet maintains its identity across rescheduling — if `database-1` is deleted, its replacement is also named `database-1` and reattaches to the same **PersistentVolumeClaim**.

StatefulSets create Pods in sequential order (0, 1, 2, ...) and delete them in reverse order (2, 1, 0) by default. This ordered lifecycle is critical for distributed systems like **Apache Kafka**, **Apache ZooKeeper**, **PostgreSQL** replicas, and **Elasticsearch** clusters, where nodes must join and leave the cluster in a controlled sequence.

Each StatefulSet Pod gets a stable DNS hostname through the associated **Headless Service** (a Service with `clusterIP: None`). For a StatefulSet named `database` in namespace `prod` with a headless Service named `db-headless`, Pod `database-0` is addressable at `database-0.db-headless.prod.svc.cluster.local`.

### DaemonSets

A **DaemonSet** ensures that a copy of a specific Pod runs on every node in the cluster (or a subset of nodes matching a **node selector**). When a new node joins the cluster, the DaemonSet controller automatically creates a Pod on it. When a node is removed, the Pod is garbage collected.

DaemonSets are used for infrastructure components that must run on every node:

- **Log collectors** such as Fluentd, Fluent Bit, or the Promtail agent that ships logs to Loki.
- **Monitoring agents** such as the Prometheus Node Exporter that exposes hardware and OS-level metrics.
- **Network plugins** such as Calico's Felix agent or Cilium's eBPF agent that implement the Container Network Interface (CNI).
- **Storage plugins** that run CSI node drivers for volume attachment and mounting.

DaemonSets support rolling updates similar to Deployments, controlled by the `updateStrategy` field. The `RollingUpdate` strategy updates one Pod at a time across nodes, while `OnDelete` waits for manual Pod deletion before replacing.

### Jobs and CronJobs

A **Job** creates one or more Pods that run to completion. Unlike Deployments, which maintain long-running processes, Jobs are designed for batch processing, data migrations, or one-time tasks. The Job controller tracks how many Pods have successfully completed and creates new Pods if any fail (up to a configurable `backoffLimit`). Jobs support **parallel execution** through the `parallelism` and `completions` fields — for example, processing 100 items with 5 parallel workers.

A **CronJob** creates Jobs on a time-based schedule using standard cron syntax. CronJobs are used for periodic tasks such as database backups, report generation, or cache cleanup. The `concurrencyPolicy` field controls behavior when a new Job is due while a previous one is still running: `Allow` (default) creates both, `Forbid` skips the new Job, and `Replace` terminates the old Job and starts the new one.

## Pod Lifecycle Management

Kubernetes manages Pod lifecycle through several mechanisms. **Resource requests and limits** define the minimum and maximum CPU and memory a container can use — the Scheduler uses requests for placement decisions, while the kubelet enforces limits. **Liveness probes** detect stuck containers and trigger restarts. **Readiness probes** determine when a Pod is ready to receive traffic, gating its inclusion in Service endpoints. **Startup probes** protect slow-starting containers from being killed by liveness probes before they initialize.

**Pod Disruption Budgets (PDBs)** protect applications during voluntary disruptions such as node drains or cluster upgrades. A PDB specifying `minAvailable: 2` for a three-replica Deployment ensures that at least two Pods remain running during eviction. The Eviction API respects PDBs, blocking eviction requests that would violate the budget.

**Graceful termination** follows a defined sequence: when a Pod is deleted, the kubelet sends a SIGTERM signal to the container's main process and waits for the **terminationGracePeriodSeconds** (default: 30 seconds). If the process does not exit within this period, the kubelet sends SIGKILL. Applications should handle SIGTERM by finishing in-flight requests, closing database connections, and flushing buffers.
