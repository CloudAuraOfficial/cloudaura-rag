# Kubernetes Security: RBAC, Network Policies, and Supply Chain Protection

## Authentication and Authorization

Kubernetes security is built on a layered model. Every request to the **Kubernetes API Server** passes through three stages: **authentication** (who is making the request), **authorization** (is this identity allowed to perform this action), and **admission control** (should this request be modified or rejected based on policy). Understanding each layer is essential for securing a Kubernetes cluster.

### Authentication

The API Server supports multiple authentication mechanisms, evaluated in order until one succeeds:

- **X.509 Client Certificates**: The most common method for cluster components. The kubelet, kube-scheduler, and kube-controller-manager each authenticate with certificates signed by the cluster's Certificate Authority (CA). Users can also authenticate with client certificates, where the Common Name (CN) becomes the username and the Organization (O) becomes the group.
- **Bearer Tokens**: Static tokens, bootstrap tokens, or tokens issued by an OpenID Connect (OIDC) provider. **OIDC integration** connects Kubernetes to identity providers like Azure Active Directory, Google Workspace, Okta, or Keycloak, enabling SSO and centralized user management.
- **ServiceAccount Tokens**: Automatically mounted into Pods. Since Kubernetes 1.22, the **TokenRequest API** issues short-lived, audience-bound tokens (projected service account tokens) instead of the legacy non-expiring Secret-based tokens, reducing the risk of token theft.

### RBAC (Role-Based Access Control)

**RBAC** is the standard authorization mode in Kubernetes, enabled by the `--authorization-mode=RBAC` flag on the API Server. RBAC governs access through four resource types:

- **Role**: Defines a set of permissions (verbs on resources) within a single **namespace**. For example, a Role might grant `get`, `list`, and `watch` permissions on Pods and Services in the `production` namespace.
- **ClusterRole**: Like a Role but cluster-wide — it applies across all namespaces and also grants access to cluster-scoped resources such as Nodes, PersistentVolumes, and Namespaces themselves.
- **RoleBinding**: Binds a Role to a **subject** (user, group, or ServiceAccount) within a specific namespace. A RoleBinding referencing the Role `pod-reader` and the user `alice` grants Alice read access to Pods in that namespace.
- **ClusterRoleBinding**: Binds a ClusterRole to a subject across the entire cluster.

RBAC follows the **principle of least privilege**: grant only the minimum permissions required. A common pattern separates responsibilities:

- **Cluster administrators** receive a ClusterRoleBinding to the built-in `cluster-admin` ClusterRole (full access to all resources).
- **Namespace administrators** receive a RoleBinding to the `admin` ClusterRole scoped to their namespace (full access within the namespace but no cluster-wide permissions).
- **Developers** receive custom Roles granting read access to most resources and write access to Deployments and ConfigMaps.
- **CI/CD ServiceAccounts** receive tightly scoped Roles granting only `update` and `patch` on Deployments in specific namespaces.

RBAC permissions are additive — there are no deny rules. If multiple RoleBindings apply to a subject, the subject receives the union of all granted permissions. This makes careful Role design important to avoid permission creep.

## ServiceAccounts

A **ServiceAccount** provides an identity for processes running inside Pods. Every namespace has a `default` ServiceAccount, and every Pod that does not specify a ServiceAccount uses it. Best practice is to create dedicated ServiceAccounts for each workload and assign them only the RBAC permissions they need.

ServiceAccounts are linked to Pods via the `spec.serviceAccountName` field. The kubelet mounts a projected token volume at `/var/run/secrets/kubernetes.io/serviceaccount/` inside the container, providing the token, CA certificate, and namespace. Applications use this token to authenticate with the API Server when they need to interact with Kubernetes resources (e.g., a controller that manages custom resources).

To minimize exposure, set `automountServiceAccountToken: false` on ServiceAccounts or Pod specs when the workload does not need API Server access. This prevents unnecessary token mounting and reduces the attack surface if the container is compromised.

## Pod Security

### Pod Security Standards

Kubernetes defines three **Pod Security Standards** that classify the security posture of Pod configurations:

- **Privileged**: Unrestricted — allows all Pod configurations. Used only for infrastructure-level workloads like CNI plugins or storage drivers that require host-level access.
- **Baseline**: Prevents known privilege escalation vectors. Blocks `hostNetwork`, `hostPID`, `hostIPC`, privileged containers, and most Linux capabilities while allowing common configurations.
- **Restricted**: Heavily restricted — requires running as non-root, dropping all capabilities, using read-only root filesystems, and setting a `seccompProfile` of `RuntimeDefault` or `Localhost`. This is the target standard for application workloads.

These standards are enforced by the **Pod Security Admission** controller (built into Kubernetes since 1.25), which replaces the deprecated PodSecurityPolicy. Pod Security Admission is configured per-namespace via labels:

```
pod-security.kubernetes.io/enforce: restricted
pod-security.kubernetes.io/warn: restricted
pod-security.kubernetes.io/audit: restricted
```

The `enforce` mode rejects non-compliant Pods, `warn` allows them but prints a warning, and `audit` logs violations.

### Security Context

A Pod's **securityContext** field (and per-container `securityContext`) defines runtime security settings:

- `runAsNonRoot: true` prevents the container from running as UID 0.
- `runAsUser: 1000` sets the user ID for the container process.
- `readOnlyRootFilesystem: true` makes the root filesystem read-only, forcing applications to write only to explicitly mounted volumes.
- `allowPrivilegeEscalation: false` prevents child processes from gaining more privileges than the parent.
- `capabilities.drop: ["ALL"]` drops all Linux capabilities, and specific capabilities can be added back with `capabilities.add`.
- `seccompProfile.type: RuntimeDefault` applies the container runtime's default seccomp profile, restricting the system calls the container can make.

## Network Policies

**NetworkPolicies** enforce micro-segmentation within a Kubernetes cluster, controlling which Pods can communicate with each other. By default, all Pod-to-Pod traffic is unrestricted. Applying a NetworkPolicy to a Pod immediately blocks all traffic not explicitly allowed by the policy rules.

A zero-trust network posture begins with a **default deny** policy per namespace:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
spec:
  podSelector: {}
  policyTypes: ["Ingress", "Egress"]
```

This blocks all ingress and egress traffic for every Pod in the namespace. Subsequent NetworkPolicies then selectively open traffic paths. For example, allowing the `api-server` Pods to receive traffic from `ingress-controller` Pods and to send traffic to `database` Pods on port 5432.

NetworkPolicy enforcement requires a compatible CNI plugin. **Calico** provides full NetworkPolicy support along with its own **GlobalNetworkPolicy** CRD for cluster-wide rules. **Cilium** enforces policies using eBPF and extends Kubernetes NetworkPolicies with Layer 7 HTTP-aware policies via **CiliumNetworkPolicy** CRDs — for example, allowing GET requests but denying DELETE requests to a specific URL path.

## Secrets Management

### Kubernetes Secrets

Kubernetes **Secrets** store sensitive data such as passwords, API keys, TLS certificates, and SSH keys. Secrets are stored in **etcd** and are base64-encoded (not encrypted) by default. To protect Secrets at rest, administrators enable **encryption at rest** by configuring the API Server with an `EncryptionConfiguration` that specifies a provider — **aescbc** (AES-CBC with PKCS7 padding), **aesgcm**, or a KMS provider that delegates encryption to an external key management service.

Secrets are mounted into Pods either as files in a volume (`volumeMounts`) or as environment variables (`envFrom`). Volume-mounted Secrets are automatically updated when the Secret changes (with a propagation delay), while environment-variable Secrets require a Pod restart.

### HashiCorp Vault

**HashiCorp Vault** is the leading external secrets management platform. Vault provides dynamic secret generation, automatic rotation, encryption as a service, and detailed audit logging. In Kubernetes, Vault integrates through two primary mechanisms:

- **Vault Agent Injector**: A mutating admission webhook that injects a Vault Agent sidecar into Pods. The sidecar authenticates with Vault using the Pod's **ServiceAccount token** (Kubernetes auth method), retrieves secrets, and writes them to a shared volume that the application container reads.
- **Vault CSI Provider**: Implements the **Secrets Store CSI Driver** interface, mounting Vault secrets as volumes without requiring a sidecar. This approach uses less resources than the injector.

### Sealed Secrets

**Sealed Secrets** (by Bitnami) addresses the problem of storing encrypted Secrets in Git. A **SealedSecret** is encrypted using the cluster's public key and can only be decrypted by the Sealed Secrets controller running in the cluster. Developers encrypt Secrets with the `kubeseal` CLI and commit the resulting SealedSecret manifests to Git. The controller decrypts them into standard Kubernetes Secrets. This enables GitOps workflows where even sensitive configuration is version-controlled.

The **External Secrets Operator** is an alternative that synchronizes secrets from external providers (Vault, AWS Secrets Manager, Azure Key Vault, Google Secret Manager, Doppler) into Kubernetes Secrets. It uses **ExternalSecret** custom resources that define which external secrets to fetch and how to map them to Kubernetes Secret keys.

## Mutual TLS (mTLS)

**Mutual TLS** ensures that both the client and server authenticate each other using TLS certificates, preventing unauthorized services from communicating within the cluster. Service meshes — **Istio** and **Linkerd** — automate mTLS between all services without code changes. Istio's **istiod** component includes a built-in certificate authority that issues short-lived certificates to Envoy sidecar proxies. Linkerd's **identity controller** performs the same function for its Rust-based proxies. Both meshes rotate certificates automatically, typically every 24 hours.

## Supply Chain Security

Container supply chain security protects against compromised images, vulnerable dependencies, and unauthorized deployments:

- **Image Signing**: **Cosign** (from the Sigstore project) signs container images with keyless or key-based signatures. **Sigstore** provides a transparency log (**Rekor**) that records all signing events.
- **Admission Enforcement**: **Kyverno** and **Open Policy Agent (OPA) Gatekeeper** are Kubernetes policy engines that enforce admission policies. Kyverno uses declarative YAML policies, while OPA Gatekeeper uses the Rego policy language. Policies can require image signatures, block images from untrusted registries, enforce resource limits, and mandate security context settings.
- **Vulnerability Scanning**: **Trivy** (by Aqua Security) scans container images, Kubernetes manifests, IaC files, and SBOMs for known vulnerabilities. Trivy can run in CI/CD pipelines (GitHub Actions, GitLab CI) and as a Kubernetes operator (**Trivy Operator**) that continuously scans running workloads and reports findings as Kubernetes custom resources.
- **SBOM Generation**: **Syft** generates Software Bills of Materials (SBOMs) in SPDX and CycloneDX formats, listing every package and dependency in a container image for audit and compliance purposes.
