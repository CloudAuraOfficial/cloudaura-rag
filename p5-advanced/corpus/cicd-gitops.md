# CI/CD Pipelines and GitOps for Kubernetes

## Continuous Integration and Continuous Delivery

**Continuous Integration (CI)** is the practice of automatically building and testing code changes on every commit. **Continuous Delivery (CD)** extends CI by automating the deployment of validated artifacts to staging and production environments. Together, CI/CD pipelines reduce the time between writing code and delivering it to users while maintaining quality through automated gates.

In a Kubernetes-native workflow, a CI/CD pipeline typically follows these stages: code commit triggers the pipeline, the pipeline runs linting and unit tests, builds a container image, pushes it to a container registry, runs integration tests against the image, and finally deploys the image to a Kubernetes cluster by updating the relevant Deployment, StatefulSet, or Helm release.

## GitHub Actions

**GitHub Actions** is a CI/CD platform built into GitHub that executes workflows defined in YAML files stored in the `.github/workflows/` directory of a repository. A **workflow** is triggered by events such as `push`, `pull_request`, `release`, or `schedule` (cron). Each workflow contains one or more **jobs**, and each job runs on a **runner** (a virtual machine provided by GitHub or a self-hosted machine). Jobs contain ordered **steps** that execute shell commands or reusable **actions**.

A typical Kubernetes deployment workflow in GitHub Actions includes:

1. **Checkout**: The `actions/checkout` action clones the repository.
2. **Build and Test**: Steps run `dotnet test`, `pytest`, `go test`, or `npm test` to validate the codebase.
3. **Container Image Build**: The `docker/build-push-action` action builds a Docker image using the repository's Dockerfile and pushes it to a container registry (Docker Hub, **ghcr.io**, Amazon ECR, or Google Artifact Registry).
4. **Image Scanning**: Tools like **Trivy** (from Aqua Security) scan the built image for known vulnerabilities in OS packages and application dependencies.
5. **Deploy**: The workflow updates the Kubernetes Deployment by running `kubectl set image` or by updating a Helm release with `helm upgrade`.

GitHub Actions stores sensitive values in **encrypted secrets** (accessible via `${{ secrets.SECRET_NAME }}`). Secrets can be scoped to a repository, an environment (e.g., `staging`, `production`), or an organization. **Environments** support required reviewers and deployment protection rules, enabling manual approval gates before production deployments.

## GitOps

**GitOps** is an operational model where the desired state of infrastructure and applications is declared in a Git repository, and an automated agent continuously reconciles the live cluster state with the declared state. The Git repository becomes the single source of truth. Changes to the cluster are made exclusively through Git commits — no manual `kubectl apply` commands.

GitOps provides several key benefits: an auditable history of all changes (via Git log), easy rollbacks (via `git revert`), and consistent environments (every cluster converges to the same declared state). The GitOps model was popularized by **Weaveworks** and is formalized by the **CNCF GitOps Working Group**.

### ArgoCD

**ArgoCD** is a declarative GitOps continuous delivery tool for Kubernetes, maintained as a CNCF graduated project. ArgoCD runs inside the Kubernetes cluster and continuously monitors one or more Git repositories for changes to Kubernetes manifests.

ArgoCD's core concept is the **Application** custom resource, which defines the mapping between a Git repository path and a target Kubernetes cluster/namespace. An Application specifies the **source** (Git repo URL, revision, and path to manifests) and the **destination** (Kubernetes API server URL and namespace). ArgoCD supports multiple manifest formats: plain YAML, **Helm charts**, **Kustomize** overlays, **Jsonnet**, and directories of manifests.

ArgoCD continuously compares the desired state (from Git) with the live state (from the Kubernetes API Server). If they differ, the Application is marked as **OutOfSync**. ArgoCD can be configured for **automatic sync** (immediately apply changes when Git is updated) or **manual sync** (require human approval via the ArgoCD UI or CLI). The **sync operation** applies manifests to the cluster using `kubectl apply` semantics, with support for **sync waves** (ordering resources), **sync hooks** (running Jobs before or after sync), and **resource health checks** (waiting for Deployments to roll out before marking sync as successful).

ArgoCD provides a web UI that visualizes the application's resource tree — Deployments, ReplicaSets, Pods, Services, ConfigMaps — with real-time health status. The UI shows diff views between the Git state and live state, making it easy to understand what changed.

### Flux

**Flux** is an alternative GitOps toolkit for Kubernetes, also a CNCF graduated project, developed by Weaveworks. Flux v2 is built on a set of specialized controllers:

- **Source Controller** manages Git repositories and Helm repositories as Kubernetes resources, polling for changes at configurable intervals.
- **Kustomize Controller** reconciles Kustomize overlays and plain YAML manifests from Git sources.
- **Helm Controller** manages Helm releases declaratively via **HelmRelease** custom resources.
- **Notification Controller** sends alerts to Slack, Microsoft Teams, Discord, or webhooks when reconciliation events occur.
- **Image Automation Controllers** detect new container image tags in registries and automatically update Git manifests, closing the GitOps loop.

Flux's multi-tenancy model allows platform teams to define **Tenants** with scoped access to specific namespaces and Git repositories, making it suitable for large organizations with multiple teams sharing a cluster.

### ArgoCD vs. Flux

ArgoCD provides a rich web UI and application-centric model, making it easier to visualize and manage deployments interactively. Flux is more composable and Kubernetes-native, using individual controllers that can be adopted incrementally. ArgoCD uses a centralized Application resource; Flux uses distributed **Kustomization** and **HelmRelease** resources that can be managed per-namespace. Many organizations choose ArgoCD for its UI and developer experience, while platform teams favor Flux for its composability and multi-tenancy support.

## Helm: The Kubernetes Package Manager

**Helm** is the package manager for Kubernetes, enabling users to define, install, and upgrade complex Kubernetes applications as a single unit called a **chart**. A Helm chart is a directory containing:

- `Chart.yaml`: Metadata including chart name, version, and dependencies.
- `values.yaml`: Default configuration values that parameterize the templates.
- `templates/`: Go template files that generate Kubernetes manifests when rendered with values.
- `charts/`: Subdirectory for dependent charts.

Helm resolves `{{ .Values.replicaCount }}` placeholders in templates with values from `values.yaml`, command-line overrides (`--set replicaCount=5`), or custom values files (`-f production-values.yaml`). This parameterization enables a single chart to produce different manifests for development, staging, and production environments.

A **Helm release** is an instance of a chart installed in a cluster. Helm tracks releases and their revisions, enabling `helm rollback <release> <revision>` to revert to a previous state. Release metadata is stored as Kubernetes Secrets in the release's namespace.

Helm charts are distributed via **chart repositories** — HTTP servers hosting packaged charts. **Artifact Hub** (artifacthub.io) is the central discovery platform for Helm charts, listing charts from thousands of publishers. Major chart repositories include **Bitnami** (databases, message queues, monitoring tools), **Prometheus Community** (kube-prometheus-stack), and **Jetstack** (cert-manager).

## Kustomize

**Kustomize** is a template-free configuration management tool built into `kubectl` (via `kubectl apply -k`). Unlike Helm's Go templating approach, Kustomize uses a **patch-based model**: a base set of Kubernetes manifests is modified through overlays that add, remove, or change specific fields. A `kustomization.yaml` file in each directory defines the resources and patches to apply.

Kustomize supports **strategic merge patches** (merge partial YAML into existing resources), **JSON patches** (RFC 6902 operations), **name prefixes and suffixes**, **label and annotation injection**, **namespace overrides**, and **ConfigMap/Secret generators** (creating ConfigMaps from files or literals with content-based hash suffixes for automatic rollout on change).

A common Kustomize directory structure uses a `base/` directory with shared manifests and `overlays/` directories (`overlays/dev/`, `overlays/staging/`, `overlays/production/`) that customize the base for each environment. This approach is widely used with both ArgoCD and Flux.

## Deployment Strategies

### Rolling Update

A **rolling update** is the default deployment strategy in Kubernetes Deployments. The Deployment controller creates a new ReplicaSet with the updated Pod template and incrementally shifts traffic by scaling up the new ReplicaSet and scaling down the old one. The `maxSurge` parameter controls how many additional Pods can exist during the update, and `maxUnavailable` controls how many Pods can be offline. Rolling updates provide zero-downtime deployments but run both old and new versions simultaneously during the transition.

### Blue-Green Deployment

A **blue-green deployment** maintains two identical environments: **blue** (current production) and **green** (new version). The new version is deployed to the green environment and fully validated. Once verified, traffic is switched from blue to green by updating the Kubernetes Service's label selector to point to the green Pods. If issues arise, traffic is immediately switched back to blue. Blue-green deployments avoid running mixed versions but require double the resources during the transition. In Kubernetes, this is implemented using two Deployments with different labels and a Service that switches selectors.

### Canary Deployment

A **canary deployment** routes a small percentage of traffic to the new version while the majority continues to the stable version. If metrics (error rate, latency, success rate) remain healthy, the canary percentage is gradually increased until the new version receives 100% of traffic. **Istio**'s **VirtualService** resource enables weighted traffic splitting between two Kubernetes Services. **Flagger** (from Weaveworks/Flux) automates canary analysis by integrating with Prometheus metrics, automatically promoting or rolling back based on configurable success thresholds. ArgoCD supports canary deployments through the **Argo Rollouts** controller, which extends Kubernetes Deployments with canary and blue-green strategies, including automated analysis using Prometheus, Datadog, or custom metrics.
