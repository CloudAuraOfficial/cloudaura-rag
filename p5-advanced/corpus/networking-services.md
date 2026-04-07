# Kubernetes Networking and Service Discovery

## The Kubernetes Network Model

Kubernetes enforces a flat network model with three fundamental rules: every Pod gets its own unique IP address, all Pods can communicate with every other Pod without NAT, and the IP that a Pod sees for itself is the same IP that other Pods see for it. This model is implemented by **Container Network Interface (CNI)** plugins — the most widely used are **Calico**, **Cilium**, **Flannel**, and **Weave Net**. Each CNI plugin implements Pod-to-Pod networking differently: Calico uses BGP routing and iptables or eBPF, Cilium uses eBPF for high-performance data plane operations, and Flannel uses a simple overlay network with VXLAN encapsulation.

Each Kubernetes cluster allocates two CIDR ranges: a **Pod CIDR** for Pod IP addresses (e.g., `10.244.0.0/16`) and a **Service CIDR** for Service ClusterIPs (e.g., `10.96.0.0/12`). The Pod CIDR is subdivided per node — each node receives a smaller range (e.g., `/24`) and assigns addresses from it to its local Pods. The CNI plugin handles this allocation and configures the network interfaces inside each Pod's network namespace.

## Kubernetes Service Types

A **Kubernetes Service** provides a stable network endpoint for a dynamic set of Pods. Since Pods are ephemeral and their IP addresses change on restart, Services provide a fixed **ClusterIP** and **DNS name** that automatically routes traffic to healthy backing Pods selected by a **label selector**. The **Endpoint Controller** (running in the kube-controller-manager) watches for Pods matching a Service's selector and maintains an **Endpoints** object (or the newer **EndpointSlice** objects) listing the IP addresses and ports of ready Pods.

### ClusterIP

**ClusterIP** is the default Service type. It allocates a virtual IP address from the Service CIDR range that is only reachable from within the cluster. When a Pod sends traffic to the ClusterIP, **kube-proxy** (running on the Pod's node) intercepts the traffic using iptables or IPVS rules and redirects it to one of the backing Pod IPs using round-robin load balancing. ClusterIP Services are the foundation for internal service-to-service communication.

A special variant is the **Headless Service**, created by setting `clusterIP: None`. A Headless Service does not allocate a virtual IP. Instead, DNS queries for the Service name return the individual Pod IP addresses directly. This is essential for **StatefulSets**, where clients need to connect to specific Pods (e.g., connecting to the primary database replica `postgres-0.postgres-headless.default.svc.cluster.local`).

### NodePort

A **NodePort** Service extends ClusterIP by additionally opening a static port (in the range 30000-32767 by default) on every node in the cluster. External traffic sent to `<any-node-IP>:<NodePort>` is forwarded to the Service's ClusterIP and then to a backing Pod. NodePort is a basic mechanism for exposing services externally and is often used in development or on-premises environments where a cloud load balancer is unavailable.

### LoadBalancer

A **LoadBalancer** Service extends NodePort by provisioning an external load balancer through the cloud provider's API. On **AWS**, this creates an Elastic Load Balancer (ELB or NLB). On **Google Cloud**, it creates a Google Cloud Load Balancer. On **Azure**, it creates an Azure Load Balancer. The **cloud-controller-manager** communicates with the cloud provider to create the load balancer, configure health checks, and set up routing rules that forward traffic to the NodePort on each node.

The external load balancer receives a public IP address, which is reflected in the Service's `status.loadBalancer.ingress` field. This is the standard way to expose services to internet traffic in cloud-hosted Kubernetes clusters. The `externalTrafficPolicy` field controls traffic routing: `Cluster` (default) distributes traffic evenly across all nodes but adds an extra hop, while `Local` routes traffic only to nodes running backing Pods, preserving the client's source IP address.

### ExternalName

An **ExternalName** Service maps a Service name to an external DNS name (e.g., `my-database.example.com`). It creates a CNAME record in the cluster DNS rather than routing through kube-proxy. ExternalName Services are used to provide a Kubernetes-native DNS alias for external resources such as managed databases or third-party APIs.

## DNS Resolution in Kubernetes

**CoreDNS** is the default DNS server in Kubernetes, deployed as a Deployment in the `kube-system` namespace. CoreDNS watches the API Server for Service and Pod changes and serves DNS records accordingly. Every Service receives a DNS A record in the format:

```
<service-name>.<namespace>.svc.cluster.local
```

For example, a Service named `api-gateway` in the `production` namespace is resolvable at `api-gateway.production.svc.cluster.local`. SRV records are also created for named ports, enabling service discovery of both IP and port.

Pods are configured to use CoreDNS by the kubelet, which sets each Pod's `/etc/resolv.conf` to point to the CoreDNS Service's ClusterIP (typically `10.96.0.10`). The default search domains allow short names: a Pod in the `production` namespace can resolve `api-gateway` (without the full suffix) because `production.svc.cluster.local` is in its DNS search path.

CoreDNS is extensible via plugins. The **forward** plugin delegates external DNS queries to upstream resolvers. The **cache** plugin caches responses to reduce load. The **kubernetes** plugin is responsible for serving cluster-internal DNS records.

## Ingress and Ingress Controllers

An **Ingress** resource defines HTTP and HTTPS routing rules for external traffic entering the cluster. Unlike LoadBalancer Services (which operate at Layer 4), Ingress operates at Layer 7 and supports host-based routing, path-based routing, TLS termination, and URL rewriting.

An Ingress resource alone does nothing — it requires an **Ingress Controller** to implement the rules. Popular Ingress Controllers include:

- **NGINX Ingress Controller**: The most widely deployed controller, maintained by the Kubernetes community. It configures an Nginx reverse proxy based on Ingress resources. Supports annotations for rate limiting, authentication, rewriting, and canary deployments.
- **Traefik**: An edge router that supports automatic TLS via Let's Encrypt, TCP/UDP routing, and middleware chains. Traefik can read routing configuration from Kubernetes Ingress resources, its own IngressRoute CRD, or Docker labels.
- **HAProxy Ingress**: High-performance controller based on HAProxy, optimized for large-scale deployments.
- **AWS ALB Ingress Controller**: Provisions AWS Application Load Balancers (ALBs) for Ingress resources on EKS clusters, supporting target groups, WAF integration, and Cognito authentication.

Kubernetes 1.19 introduced the **Gateway API** as a successor to Ingress, offering a more expressive and extensible model. The Gateway API defines **GatewayClass**, **Gateway**, **HTTPRoute**, **TCPRoute**, and **TLSRoute** resources. Gateway API separates infrastructure concerns (managed by platform operators via Gateway resources) from application routing concerns (managed by developers via HTTPRoute resources).

## Network Policies

**NetworkPolicies** are Kubernetes resources that control traffic flow between Pods and between Pods and external endpoints. By default, all Pods in a Kubernetes cluster can communicate freely with each other. NetworkPolicies implement a whitelist model: once a NetworkPolicy selects a Pod (via label selector), all traffic not explicitly allowed by a policy rule is denied.

NetworkPolicies define **ingress rules** (incoming traffic) and **egress rules** (outgoing traffic) separately. Each rule specifies allowed sources or destinations using Pod selectors, namespace selectors, or IP block CIDR ranges. For example, a NetworkPolicy can restrict the `database` Pods to only accept traffic from Pods labeled `app: api-server` in the same namespace.

NetworkPolicies are enforced by the CNI plugin, not by Kubernetes itself. **Calico** provides full NetworkPolicy support plus additional **GlobalNetworkPolicy** resources for cluster-wide rules. **Cilium** enforces NetworkPolicies using eBPF and adds Layer 7 filtering capabilities (e.g., allowing HTTP GET but blocking HTTP DELETE). **Flannel** does not support NetworkPolicies natively and requires an additional tool like Calico for policy enforcement.

## Service Mesh

A **service mesh** is an infrastructure layer that manages service-to-service communication within a Kubernetes cluster. Service meshes provide **mutual TLS (mTLS)** encryption between services, **traffic management** (canary releases, traffic splitting, retries, circuit breaking), and **observability** (distributed tracing, metrics, access logs) without requiring changes to application code.

### Istio

**Istio** is the most feature-rich service mesh for Kubernetes, originally developed by Google, IBM, and Lyft. Istio deploys an **Envoy proxy** as a **sidecar container** in every Pod. The Envoy sidecar intercepts all inbound and outbound traffic for the Pod, enabling Istio's control plane to manage routing, security, and observability.

Istio's control plane component is **istiod**, which combines the Pilot (traffic management), Citadel (certificate management for mTLS), and Galley (configuration management) functions. istiod pushes routing configuration to Envoy sidecars via the **xDS (discovery service)** API. Istio defines custom resources including **VirtualService** (routing rules), **DestinationRule** (traffic policies like load balancing and circuit breaking), **Gateway** (edge traffic entry), and **PeerAuthentication** (mTLS settings).

### Linkerd

**Linkerd** is a lightweight service mesh developed by Buoyant and a CNCF graduated project. Linkerd uses its own ultra-lightweight proxy (linkerd2-proxy, written in Rust) instead of Envoy, resulting in lower resource consumption and latency overhead compared to Istio. Linkerd focuses on simplicity and provides automatic mTLS, golden metrics (request rate, success rate, latency), and traffic splitting for canary deployments. Linkerd's control plane runs in the `linkerd` namespace and consists of the **destination controller** (service discovery), **identity controller** (TLS certificate management), and **proxy-injector** (automatic sidecar injection via mutating admission webhook).

Both Istio and Linkerd integrate with **Prometheus** for metrics collection and **Grafana** for dashboard visualization, providing deep insight into service-to-service communication patterns, latency distributions, and error rates.
