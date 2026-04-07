# Kubernetes Storage and State Management

## The Storage Challenge in Kubernetes

Containers are ephemeral by design — when a container restarts, its writable filesystem layer is discarded. This presents a fundamental challenge for stateful workloads such as databases, message queues, and file storage services that must persist data beyond the container's lifecycle. Kubernetes addresses this through a comprehensive storage abstraction layer built around **Volumes**, **PersistentVolumes**, **PersistentVolumeClaims**, **StorageClasses**, and the **Container Storage Interface (CSI)**.

## Volume Types

A Kubernetes **Volume** is a directory accessible to containers in a Pod, with a lifecycle tied to the Pod (not the container). Kubernetes supports numerous volume types:

### emptyDir

An **emptyDir** volume is created when a Pod is assigned to a node and exists for the lifetime of the Pod. It starts empty and is deleted when the Pod is removed from the node. emptyDir volumes are stored on the node's local disk or, if `medium: Memory` is specified, in a tmpfs (RAM-backed filesystem). emptyDir is used for scratch space, caching, and sharing files between containers in the same Pod — for example, a sidecar container writing processed logs to an emptyDir that the main container reads from.

### hostPath

A **hostPath** volume mounts a file or directory from the host node's filesystem into the Pod. hostPath is used by system-level components like the **Node Exporter** (which reads `/proc` and `/sys` for hardware metrics) and **Promtail** (which reads container logs from `/var/log/containers/`). hostPath volumes are inherently non-portable because they depend on the specific node's filesystem, and they pose security risks because they can expose sensitive host files to containers. Pod Security Standards at the **Restricted** level block hostPath mounts entirely.

### configMap and secret

**ConfigMap volumes** mount the contents of a **ConfigMap** resource as files in the Pod's filesystem. Each key in the ConfigMap becomes a filename, and its value becomes the file's content. This is the standard mechanism for injecting configuration files (Nginx configs, application.yaml, prometheus.yml) into containers. ConfigMap volume contents are automatically updated when the ConfigMap is modified, with a propagation delay of up to the kubelet sync period (default 60 seconds).

**Secret volumes** work identically to ConfigMap volumes but mount Kubernetes **Secret** data. Secret files are stored in a tmpfs (never written to disk on the node) for additional security. TLS certificates, database credentials, and API keys are commonly mounted as Secret volumes.

### projected

A **projected volume** combines multiple volume sources into a single mount point. It can project data from ConfigMaps, Secrets, the Downward API (Pod metadata such as labels, annotations, namespace, and resource limits), and ServiceAccount tokens into a single directory. Projected volumes are used for complex configuration scenarios and are the mechanism by which the kubelet mounts **bound ServiceAccount tokens** (short-lived, audience-scoped tokens issued by the TokenRequest API).

## PersistentVolumes and PersistentVolumeClaims

For data that must survive Pod restarts and rescheduling, Kubernetes provides the **PersistentVolume (PV)** and **PersistentVolumeClaim (PVC)** abstraction.

### PersistentVolume (PV)

A **PersistentVolume** is a cluster-wide storage resource provisioned by an administrator or dynamically by a **StorageClass**. A PV represents a piece of physical storage — an AWS EBS volume, a Google Persistent Disk, an Azure Disk, an NFS share, or a local SSD. The PV resource defines the storage capacity, access modes, reclaim policy, and the storage backend.

PVs support three **access modes**:
- **ReadWriteOnce (RWO)**: The volume can be mounted as read-write by a single node. This is the most common mode, used by block storage like EBS and Azure Disk.
- **ReadOnlyMany (ROX)**: The volume can be mounted as read-only by many nodes simultaneously.
- **ReadWriteMany (RWX)**: The volume can be mounted as read-write by many nodes simultaneously. Only specific storage types support RWX, including NFS, Amazon EFS, Azure Files, and CephFS.

The **reclaim policy** determines what happens to the PV's data when its PVC is deleted:
- **Retain**: The PV and its data are preserved. An administrator must manually reclaim the storage.
- **Delete**: The PV and its underlying storage resource (e.g., the EBS volume) are automatically deleted. This is the default for dynamically provisioned volumes.

### PersistentVolumeClaim (PVC)

A **PersistentVolumeClaim** is a user's request for storage. A PVC specifies the desired capacity, access mode, and optionally a StorageClass. The Kubernetes **PV controller** (part of the kube-controller-manager) matches PVCs to available PVs based on capacity, access mode, and StorageClass. Once bound, the PVC and PV form a one-to-one relationship.

Pods reference PVCs in their volume definitions. When the kubelet schedules the Pod, it mounts the PV's underlying storage at the specified path inside the container. If the Pod is rescheduled to a different node, the PV is detached from the old node and attached to the new node (for network-attached storage like EBS or Persistent Disk). This enables stateful workloads to survive node failures.

PVCs support **volume expansion**: if the StorageClass has `allowVolumeExpansion: true`, users can edit the PVC to increase its capacity. The CSI driver handles the underlying resize operation, which may require a Pod restart for filesystem expansion.

## StorageClasses

A **StorageClass** defines a "class" of storage with specific characteristics — performance tier, replication, filesystem type, or provisioner. StorageClasses enable **dynamic provisioning**: when a PVC references a StorageClass and no matching PV exists, the StorageClass's provisioner automatically creates a new PV that satisfies the claim.

Each cloud provider offers StorageClasses backed by their storage services:

- **AWS**: The `ebs.csi.aws.com` provisioner creates Amazon EBS volumes. StorageClasses define the volume type (`gp3`, `io2`, `st1`), IOPS, throughput, and encryption settings.
- **Google Cloud**: The `pd.csi.storage.gke.io` provisioner creates Google Persistent Disks. StorageClasses specify the disk type (`pd-standard`, `pd-ssd`, `pd-balanced`).
- **Azure**: The `disk.csi.azure.com` provisioner creates Azure Managed Disks with options for `Standard_LRS`, `Premium_LRS`, `StandardSSD_LRS`, and `UltraSSD_LRS`.

On-premises clusters use StorageClasses backed by **Ceph** (via Rook-Ceph), **Longhorn** (a CNCF sandbox project providing distributed block storage), **OpenEBS**, or NFS provisioners. Each StorageClass specifies parameters specific to its provisioner — for example, Rook-Ceph StorageClasses define the Ceph pool, replication factor, and filesystem type.

A cluster can have a **default StorageClass** (annotated with `storageclass.kubernetes.io/is-default-class: "true"`). PVCs that do not specify a StorageClass use the default.

## Container Storage Interface (CSI)

The **Container Storage Interface (CSI)** is a standard API that allows storage vendors to develop plugins (drivers) that work with Kubernetes without modifying Kubernetes core code. CSI replaced the older in-tree volume plugins (which were compiled directly into Kubernetes binaries) with an out-of-tree, pluggable architecture.

A CSI driver consists of two components:

- **Controller Plugin**: Runs as a Deployment or StatefulSet, typically with one replica. It handles volume lifecycle operations — creating volumes, deleting volumes, attaching volumes to nodes, taking snapshots. The controller plugin communicates with the cloud provider or storage backend API.
- **Node Plugin**: Runs as a DaemonSet on every node. It handles node-level operations — mounting the volume's filesystem, formatting the volume, and staging the volume on the node. The kubelet communicates with the node plugin via a Unix socket.

CSI drivers are registered with Kubernetes via the **CSIDriver** resource and the **CSINode** resource. The **external-provisioner**, **external-attacher**, **external-snapshotter**, and **external-resizer** sidecar containers run alongside the controller plugin and translate Kubernetes PVC events into CSI RPC calls.

Major CSI drivers include **aws-ebs-csi-driver**, **gcp-pd-csi-driver**, **azuredisk-csi-driver**, **csi-driver-nfs**, **rook-ceph-csi**, and **longhorn-csi-driver**.

## StatefulSets and Storage

**StatefulSets** are the primary workload resource for stateful applications because they provide a direct integration with PVCs via **volumeClaimTemplates**. Each Pod in a StatefulSet automatically gets its own PVC, created from the template. For a StatefulSet named `postgres` with a volumeClaimTemplate named `data`, the Pods receive PVCs named `data-postgres-0`, `data-postgres-1`, and `data-postgres-2`.

When a StatefulSet Pod is deleted and recreated (e.g., during a rolling update or node failure recovery), the replacement Pod reattaches to its original PVC. This guarantees that `postgres-1` always mounts the same persistent storage, preserving database files across restarts. PVCs created by StatefulSets are **not** automatically deleted when the StatefulSet is scaled down — this prevents accidental data loss. Administrators must manually delete orphaned PVCs.

## ConfigMaps and Secrets as Configuration State

While not traditional "storage," **ConfigMaps** and **Secrets** are Kubernetes resources that manage application configuration state.

**ConfigMaps** store non-sensitive key-value configuration data. They can hold individual values (`database_host: postgres.prod.svc.cluster.local`), multi-line configuration files (an entire `nginx.conf`), or binary data. ConfigMaps are injected into Pods via environment variables (`envFrom` or individual `env` value references) or volume mounts. Best practice is to use volume mounts for configuration files and environment variables for simple values.

**Secrets** store sensitive configuration data. Kubernetes supports several Secret types: `Opaque` (generic), `kubernetes.io/tls` (TLS certificate and key pair, used by Ingress controllers and service meshes), `kubernetes.io/dockerconfigjson` (registry credentials for image pulls), and `kubernetes.io/service-account-token` (legacy ServiceAccount tokens). Secrets should always be encrypted at rest (via API Server encryption configuration) and access should be restricted via RBAC — a common security mistake is granting broad Secret read access across namespaces.

## Volume Snapshots

Kubernetes supports **VolumeSnapshots** as a CSI-enabled feature for creating point-in-time copies of PersistentVolumes. A **VolumeSnapshotClass** defines the snapshot provider (typically the same CSI driver that manages the volume). A **VolumeSnapshot** resource triggers the CSI driver to take a snapshot of the specified PVC. A **VolumeSnapshotContent** represents the actual snapshot in the storage backend.

Snapshots enable backup and restore workflows: a new PVC can be created from a VolumeSnapshot using `dataSource` in the PVC spec, restoring the volume to the snapshot's point-in-time state. This is used for database backups, disaster recovery, and cloning environments. The **Velero** backup tool (a CNCF project) leverages VolumeSnapshots as part of its cluster backup and migration capabilities.
