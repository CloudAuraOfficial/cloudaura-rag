# Kubernetes Architecture: Control Plane and Worker Nodes

## Overview

Kubernetes is an open-source container orchestration platform originally developed by Google and now maintained by the Cloud Native Computing Foundation (CNCF). The Kubernetes architecture follows a master-worker model, divided into two primary layers: the **control plane** (formerly called the master node) and the **worker nodes** (also called data plane nodes). Every Kubernetes cluster requires at least one control plane instance and one worker node, though production deployments typically run three or more control plane replicas for high availability.

## Control Plane Components

The control plane is responsible for making global decisions about the cluster, such as scheduling workloads, detecting and responding to cluster events, and maintaining the desired state of all resources. The control plane consists of five core components: the API Server, etcd, the Scheduler, the Controller Manager, and Cloud Controller Manager.

### kube-apiserver

The **Kubernetes API Server** (kube-apiserver) is the central management hub of the entire Kubernetes cluster. Every interaction with Kubernetes — whether from `kubectl`, the Kubernetes Dashboard, or internal components — passes through the API Server. The API Server exposes the Kubernetes REST API over HTTPS on port 443 by default, serving as the single entry point for all cluster operations.

The API Server performs authentication, authorization (via RBAC policies), and admission control before persisting any resource changes. When a user submits a Deployment manifest, the API Server validates the request, applies admission webhooks (such as mutating and validating webhooks), and then writes the resulting object to **etcd**. The API Server is the **only** component that communicates directly with etcd — no other control plane component reads or writes to etcd directly.

The API Server also serves a watch mechanism that allows components like the Scheduler and Controller Manager to receive real-time notifications when resources change. This event-driven architecture is fundamental to how Kubernetes maintains desired state.

### etcd

**etcd** is a distributed, consistent key-value store that serves as the backing store for all Kubernetes cluster data. Every resource definition — Pods, Services, ConfigMaps, Secrets, Deployments, Namespaces — is stored in etcd as serialized protobuf or JSON objects. etcd uses the **Raft consensus algorithm** to ensure data consistency across multiple replicas, which is why production clusters run etcd as a three- or five-member cluster to tolerate one or two node failures respectively.

etcd stores data under a hierarchical key structure rooted at `/registry/`. For example, Pod definitions are stored under `/registry/pods/<namespace>/<pod-name>`. The API Server communicates with etcd over gRPC on port 2379 (client) and port 2380 (peer-to-peer replication). Because etcd holds the entire cluster state, its backup and disaster recovery are critical operational concerns. Tools like `etcdctl snapshot save` create point-in-time backups.

etcd's watch feature enables the API Server to propagate changes efficiently. When a Deployment's replica count changes in etcd, the API Server notifies the Controller Manager, which then reconciles the actual state with the desired state.

### kube-scheduler

The **Kubernetes Scheduler** (kube-scheduler) is responsible for assigning newly created Pods to worker nodes. When the API Server notifies the Scheduler that a Pod has been created but not yet assigned to a node (the Pod's `spec.nodeName` is empty), the Scheduler evaluates all available nodes and selects the most appropriate one.

The scheduling process occurs in two phases: **filtering** and **scoring**. During filtering, the Scheduler eliminates nodes that cannot run the Pod — for example, nodes with insufficient CPU or memory resources, nodes that do not match the Pod's `nodeSelector` labels, or nodes that would violate taints and tolerations. During scoring, the remaining candidate nodes are ranked based on criteria such as resource utilization balance (LeastRequestedPriority), data locality, and pod affinity/anti-affinity rules.

The Scheduler writes its decision back to the API Server by setting the Pod's `spec.nodeName` field. The kubelet on the assigned node then picks up the Pod and begins container creation.

### kube-controller-manager

The **Controller Manager** (kube-controller-manager) runs a collection of controllers as a single process. Each controller implements a control loop that watches the cluster state via the API Server and makes changes to move the current state toward the desired state. Key controllers include:

- **ReplicaSet Controller**: Ensures the correct number of Pod replicas are running. When a ReplicaSet specifies three replicas and only two Pods exist, this controller creates a new Pod via the API Server.
- **Deployment Controller**: Manages Deployments by creating and managing ReplicaSets. When a Deployment's Pod template changes, the Deployment Controller creates a new ReplicaSet and scales it up while scaling down the old one (rolling update).
- **Node Controller**: Monitors the health of worker nodes. If a node stops sending heartbeats to the API Server (via the Node Lease mechanism), the Node Controller marks it as `NotReady` and eventually evicts its Pods.
- **Job Controller**: Manages Job resources, ensuring that a specified number of Pods run to successful completion.
- **ServiceAccount Controller**: Automatically creates default ServiceAccount objects in new Namespaces and provisions associated tokens.
- **Endpoint Controller**: Populates Endpoint objects by watching Services and Pods, linking Services to the Pods they route traffic to.

### cloud-controller-manager

The **Cloud Controller Manager** decouples cloud-provider-specific logic from the core Kubernetes codebase. It runs controllers that interact with the underlying cloud provider's API — for example, provisioning cloud load balancers when a Service of type `LoadBalancer` is created, or managing cloud-specific node lifecycle events. Cloud providers such as AWS, Azure, and Google Cloud each implement their own cloud-controller-manager binary.

## Worker Node Components

Worker nodes are the machines (physical or virtual) that run containerized application workloads. Each worker node runs three essential components: the kubelet, kube-proxy, and a container runtime.

### kubelet

The **kubelet** is the primary node agent that runs on every worker node. The kubelet registers the node with the API Server and continuously watches for PodSpecs assigned to its node. When the Scheduler assigns a Pod to the node, the kubelet instructs the container runtime to pull the required container images and start the containers.

The kubelet monitors container health through **liveness probes**, **readiness probes**, and **startup probes**. A failing liveness probe causes the kubelet to restart the container. A failing readiness probe causes the kubelet to remove the Pod's IP from the Service's Endpoints, stopping traffic from reaching it. The kubelet reports node status (CPU, memory, disk, and Pod capacity) back to the API Server every 10 seconds by default through the **Node Lease** mechanism.

The kubelet communicates with the container runtime through the **Container Runtime Interface (CRI)**, a gRPC-based API that abstracts the specific runtime implementation. This allows Kubernetes to work with multiple runtimes such as **containerd**, **CRI-O**, or other CRI-compliant runtimes. Docker was removed as a directly supported runtime in Kubernetes 1.24 in favor of containerd.

### kube-proxy

**kube-proxy** runs on every worker node and implements Kubernetes Service networking. When a Service is created, kube-proxy programs the node's network rules so that traffic destined for the Service's ClusterIP is forwarded to one of the backing Pods. kube-proxy supports three modes:

- **iptables mode** (default): Programs iptables rules that DNAT traffic to Pod IPs. This is efficient for small-to-medium clusters but can degrade with thousands of Services because iptables rules are evaluated linearly.
- **IPVS mode**: Uses the Linux IPVS (IP Virtual Server) kernel module, which provides O(1) lookup performance and supports multiple load-balancing algorithms (round-robin, least connections, shortest expected delay).
- **nftables mode**: A newer mode using nftables as the backend, offering improved performance over iptables.

kube-proxy watches the API Server for changes to Service and Endpoint objects and updates the local networking rules accordingly.

### Container Runtime

The **container runtime** is the software responsible for running containers on the node. Kubernetes requires a CRI-compliant runtime. **containerd** is the most widely used runtime and is the default in most Kubernetes distributions including GKE, EKS, and AKS. containerd pulls images from container registries (such as Docker Hub, Google Container Registry, Amazon ECR, or GitHub Container Registry), creates container filesystem layers using **snapshotter** plugins, and manages the container lifecycle through **runc** (the OCI-compliant low-level runtime).

## Component Communication Patterns

The Kubernetes architecture follows a hub-and-spoke communication pattern centered on the API Server. The kubelet on each worker node communicates with the API Server to receive Pod assignments and report status. The Scheduler communicates with the API Server to watch for unscheduled Pods and write scheduling decisions. The Controller Manager communicates with the API Server to watch resource state and create or delete resources.

All control plane-to-node communication uses TLS-encrypted connections. The API Server authenticates nodes using TLS client certificates, and kubelet endpoints are protected by webhook authentication. etcd communication is also TLS-encrypted, with dedicated certificate authorities for etcd peer and client authentication.

In a highly available Kubernetes cluster, multiple API Server instances run behind a load balancer, multiple etcd members form a cluster, and multiple Scheduler and Controller Manager instances use leader election (via the API Server's Lease resources) to ensure only one active instance at a time. This architecture enables Kubernetes to tolerate the failure of individual control plane components without losing cluster functionality.
