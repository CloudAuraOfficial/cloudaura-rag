# Kubernetes Fundamentals

## What is Kubernetes?

Kubernetes (K8s) is an open-source container orchestration platform that automates the deployment, scaling, and management of containerized applications. Originally developed by Google based on their internal Borg system, it was donated to the Cloud Native Computing Foundation (CNCF) in 2014.

Kubernetes provides a framework to run distributed systems resiliently. It handles scaling, failover, deployment patterns, and service discovery for your applications.

## Core Architecture

### Control Plane Components

The control plane manages the overall state of the cluster:

- **kube-apiserver**: The API server is the front end of the Kubernetes control plane. It validates and processes RESTful requests, serving as the gateway for all cluster operations. All communication between components goes through the API server.

- **etcd**: A consistent, distributed key-value store used as Kubernetes' backing store for all cluster data. It stores the desired state of the cluster, including configuration, secrets, and service discovery information. etcd uses the Raft consensus algorithm for leader election and data replication.

- **kube-scheduler**: Watches for newly created Pods with no assigned node and selects an optimal node for them to run on. Scheduling decisions consider resource requirements, hardware/software constraints, affinity specifications, data locality, and inter-workload interference.

- **kube-controller-manager**: Runs controller processes including the Node Controller (monitoring node health), ReplicaSet Controller (maintaining correct pod counts), Endpoints Controller, and Service Account Controller.

### Worker Node Components

Each worker node runs:

- **kubelet**: An agent that ensures containers described in PodSpecs are running and healthy. It communicates with the API server and manages the pod lifecycle on its node.

- **kube-proxy**: Maintains network rules on nodes, implementing the Kubernetes Service abstraction. It handles TCP, UDP, and SCTP forwarding using iptables, IPVS, or userspace proxying.

- **Container Runtime**: Software responsible for running containers. Kubernetes supports containerd, CRI-O, and any implementation of the Container Runtime Interface (CRI).

## Core Concepts

### Pods

A Pod is the smallest deployable unit in Kubernetes. It represents one or more containers that share storage, network, and a specification for how to run. Containers within a pod share the same IP address and port space, can communicate via localhost, and share volumes.

Pods are ephemeral by design. They are created, assigned a UID, and scheduled to nodes where they remain until termination or deletion. A pod is never "rescheduled" — if a node fails, identical pods are created on other available nodes.

### Deployments

A Deployment provides declarative updates for Pods and ReplicaSets. You describe the desired state, and the Deployment Controller changes the actual state to match at a controlled rate.

Key features include:
- Rolling updates with configurable maxSurge and maxUnavailable
- Rollback to previous revisions
- Scaling (manual or via HorizontalPodAutoscaler)
- Pause and resume for batched updates

### Services

A Service is an abstraction that defines a logical set of Pods and a policy for accessing them. Services enable loose coupling between dependent Pods.

Service types:
- **ClusterIP** (default): Exposes the Service on an internal IP. Only reachable from within the cluster.
- **NodePort**: Exposes the Service on each Node's IP at a static port (range 30000-32767).
- **LoadBalancer**: Exposes the Service externally using a cloud provider's load balancer.
- **ExternalName**: Maps the Service to a DNS name via a CNAME record.

### ConfigMaps and Secrets

ConfigMaps store non-confidential configuration data as key-value pairs. They can be consumed as environment variables, command-line arguments, or configuration files in a volume.

Secrets are similar but designed for sensitive data like passwords, tokens, and keys. Secrets are base64-encoded (not encrypted by default) and can be encrypted at rest using EncryptionConfiguration. Access to Secrets should be restricted via RBAC policies.

## Networking

### Pod Networking Model

Kubernetes imposes the following fundamental requirements:
1. Every Pod gets its own IP address
2. Pods on any node can communicate with all Pods on all other nodes without NAT
3. Agents on a node can communicate with all Pods on that node

This is implemented through Container Network Interface (CNI) plugins such as Calico, Cilium, Flannel, or Weave Net.

### Network Policies

NetworkPolicy resources control traffic flow at the IP address or port level. They specify how groups of pods are allowed to communicate with each other and with external endpoints. By default, pods are non-isolated and accept traffic from any source. Once a NetworkPolicy selects a pod, that pod rejects any connections not allowed by any applicable policy.

## Storage

### Persistent Volumes (PV) and Claims (PVC)

A PersistentVolume (PV) is a piece of storage provisioned by an administrator or dynamically using StorageClasses. PVs have a lifecycle independent of any pod.

A PersistentVolumeClaim (PVC) is a request for storage by a user. Claims can request specific size and access modes (ReadWriteOnce, ReadOnlyMany, ReadWriteMany).

### Storage Classes

StorageClasses provide a way to describe different classes of storage (e.g., fast SSD vs. standard HDD). Dynamic provisioning creates PVs automatically when a PVC references a StorageClass.

## Resource Management

### Requests and Limits

Resource requests guarantee a minimum amount of CPU and memory for a container. Resource limits set the maximum. If a container exceeds its memory limit, it is terminated (OOMKilled). If it exceeds its CPU limit, it is throttled.

Best practices:
- Always set memory limits to prevent OOM situations
- Set CPU requests based on observed usage
- Use LimitRanges to enforce defaults at the namespace level
- Use ResourceQuotas to limit total resource consumption per namespace

### Horizontal Pod Autoscaler (HPA)

HPA automatically scales the number of pod replicas based on observed CPU utilization, memory usage, or custom metrics. It checks metrics at a configurable interval (default 15 seconds) and calculates the desired replica count using the formula:

desiredReplicas = ceil(currentReplicas * (currentMetric / desiredMetric))

## Security

### RBAC (Role-Based Access Control)

RBAC regulates access to Kubernetes resources based on the roles of users or service accounts. Key objects:

- **Role/ClusterRole**: Define sets of permissions (verbs on resources)
- **RoleBinding/ClusterRoleBinding**: Grant permissions defined in a Role to subjects (users, groups, or service accounts)

### Pod Security Standards

Kubernetes defines three pod security levels:
- **Privileged**: Unrestricted, for system-level workloads
- **Baseline**: Minimally restrictive, prevents known privilege escalations
- **Restricted**: Heavily restricted, following security best practices

### Service Accounts

Every namespace has a default service account. Pods use service accounts to authenticate to the API server. Best practice is to create dedicated service accounts with minimal RBAC permissions for each workload.
