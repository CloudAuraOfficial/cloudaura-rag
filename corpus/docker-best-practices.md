# Docker Production Best Practices

## Image Building

### Multi-Stage Builds

Multi-stage builds reduce final image size by separating build dependencies from runtime. Use a builder stage for compilation and a minimal runtime stage for the final image.

Benefits:
- Smaller images (often 10-100x reduction)
- Reduced attack surface (no build tools in production)
- Faster pulls and deployments
- Cleaner separation of concerns

Example pattern: Use a full SDK image for building, then copy only the compiled artifacts to a slim or distroless base image.

### Base Image Selection

Choose base images carefully:
- **Alpine** (5MB): Minimal, uses musl libc. Good for Go, static binaries. Can cause issues with glibc-dependent software.
- **Debian Slim** (80MB): Good balance of size and compatibility. Uses glibc.
- **Distroless** (2-20MB): Google's minimal images containing only the application and its runtime dependencies. No shell, no package manager. Excellent for security.
- **Ubuntu** (75MB): Most compatible, largest. Use only when specific Ubuntu packages are required.

### Layer Optimization

Docker images are built in layers, each corresponding to a Dockerfile instruction. Optimize by:
- Combining RUN commands to reduce layers
- Ordering instructions from least to most frequently changed
- Using .dockerignore to exclude unnecessary files from the build context
- Leveraging build cache by placing dependency installation before code copy

### Security Scanning

Scan images for vulnerabilities before deployment:
- Use `docker scout` or `trivy` for vulnerability scanning
- Integrate scanning into CI/CD pipelines
- Set policies to block deployment of images with critical CVEs
- Regularly rebuild images to incorporate security patches in base layers

## Runtime Configuration

### Non-Root Containers

Never run containers as root in production. Create a dedicated user:
- Use the USER directive in Dockerfile
- Set filesystem permissions appropriately
- Use read-only root filesystems where possible
- Drop all Linux capabilities and add back only what's needed

### Resource Limits

Always set resource constraints:
- Memory limits prevent OOM situations from affecting other containers
- CPU limits ensure fair scheduling
- PID limits prevent fork bombs
- Use --ulimit for file descriptor and process limits

### Health Checks

Implement health checks for container orchestration:
- **HEALTHCHECK** directive in Dockerfile for Docker Compose
- Liveness probes in Kubernetes (is the process alive?)
- Readiness probes (can it accept traffic?)
- Startup probes (for slow-starting containers)

Health check endpoints should verify critical dependencies (database connectivity, external service availability) without performing expensive operations.

## Networking

### Port Binding

Bind container ports to 127.0.0.1 in production when behind a reverse proxy. This prevents direct access to containers from external networks.

Never expose database ports (5432, 3306, 27017) to the host network. Use Docker networks for inter-container communication.

### Docker Networks

Use user-defined bridge networks instead of the default bridge:
- Automatic DNS resolution between containers by name
- Better isolation between groups of containers
- Configurable subnet and gateway
- Network-level firewall rules

## Secrets Management

### Never Store Secrets in Images

Secrets should never be:
- Hardcoded in Dockerfiles or application code
- Stored in environment variables in docker-compose.yml committed to git
- Included in image layers (even if deleted in a later layer)

Instead use:
- Docker Secrets (Swarm mode)
- Environment variables injected at runtime from a secrets manager
- Volume-mounted secret files
- External secrets managers (HashiCorp Vault, AWS Secrets Manager)

## Logging

### Structured Logging

Applications in containers should:
- Log to stdout/stderr (not files)
- Use structured formats (JSON) for machine parsing
- Include correlation IDs for request tracing
- Avoid logging sensitive data (passwords, tokens, PII)

Docker captures stdout/stderr automatically. Use log drivers (json-file, fluentd, syslog) to route logs to centralized systems.

### Log Rotation

Configure log rotation to prevent disk exhaustion:
- Set max-size and max-file options for the json-file log driver
- Use a centralized logging stack (ELK, Loki) for persistent storage
- Monitor disk usage on Docker hosts

## Compose Best Practices

### Environment Configuration

Use .env files for environment-specific configuration:
- .env.example committed to git with placeholder values
- .env gitignored, containing actual values
- Separate compose files for development and production
- Use variable substitution for DRY configuration

### Volume Management

- Use named volumes for persistent data (databases, uploads)
- Use bind mounts for development (hot reload)
- Set appropriate permissions on mounted volumes
- Back up named volumes regularly

### Dependency Management

Use depends_on with health check conditions:
- service_healthy waits for the health check to pass
- service_started only waits for the container to start
- service_completed_successfully waits for one-shot containers

Implement retry logic in applications for resilience against startup ordering issues.
