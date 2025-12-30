# Production Deployment Guide

## Overview

This guide covers deploying the AI Invoice Summarizer to a production Kubernetes cluster. The system is designed for high availability, automatic scaling, and zero-downtime updates.

## Prerequisites

### Infrastructure Requirements

- Kubernetes 1.26+ cluster (3 control planes, 10+ workers)
- Cloud provider: AWS, GCP, or Azure
- PostgreSQL 15 (managed service or HA setup)
- Redis 7 (managed service recommended)
- S3 or equivalent object storage
- Domain name with SSL certificate

### Tools Required

```bash
# Install kubectl
curl -LO "https://dl.k8s.io/release/v1.28.0/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Install kustomize
curl -s "https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh" | bash
```

## Step 1: Prepare Kubernetes Cluster

### 1.1 Create Namespace

```bash
kubectl create namespace invoice-summarizer
kubectl label namespace invoice-summarizer environment=production
```

### 1.2 Configure RBAC

```bash
kubectl apply -f infra/kubernetes/rbac.yaml
```

### 1.3 Setup Secrets

```bash
# Create secrets for database and API keys
kubectl create secret generic invoice-summarizer-secrets \
  --from-literal=DATABASE_PASSWORD=your-secure-password \
  --from-literal=JWT_SECRET_KEY=your-secret-jwt-key-min-32-chars \
  --from-literal=AWS_ACCESS_KEY_ID=your-aws-key \
  --from-literal=AWS_SECRET_ACCESS_KEY=your-aws-secret \
  --from-literal=OPENAI_API_KEY=sk-your-key \
  -n invoice-summarizer
```

## Step 2: Deploy Infrastructure

### 2.1 Install PostgreSQL

For production, use a managed PostgreSQL service (RDS, CloudSQL, Azure Database):

```bash
# Example: AWS RDS
aws rds create-db-instance \
  --db-instance-identifier invoice-summarizer-prod \
  --db-instance-class db.r6g.xlarge \
  --engine postgres \
  --master-username postgres \
  --master-user-password <secure-password> \
  --allocated-storage 1000 \
  --storage-type gp3 \
  --multi-az \
  --backup-retention-period 30 \
  --enable-cloudwatch-logs-exports postgresql
```

### 2.2 Install Redis

For production, use ElastiCache or similar managed service:

```bash
# Example: AWS ElastiCache
aws elasticache create-replication-group \
  --replication-group-description "Invoice Summarizer Cache" \
  --engine redis \
  --cache-node-type cache.r6g.xlarge \
  --num-cache-clusters 3 \
  --automatic-failover-enabled
```

### 2.3 Deploy Kubernetes Infrastructure

```bash
# Deploy PostgreSQL and Redis (if using K8s versions)
kubectl apply -f infra/kubernetes/postgres-redis.yaml -n invoice-summarizer

# Create storage classes
kubectl apply -f infra/kubernetes/storage-classes.yaml -n invoice-summarizer

# Wait for statefulsets to be ready
kubectl wait --for=condition=ready pod -l app=postgres \
  -n invoice-summarizer --timeout=300s
```

## Step 3: Deploy Applications

### 3.1 Configure Application Secrets

Update `infra/kubernetes/api-gateway.yaml` with your environment values:

```bash
kubectl set env configmap/invoice-summarizer-config \
  DATABASE_URL="postgresql://user:pass@db.example.com:5432/invoices" \
  REDIS_URL="redis://cache.example.com:6379" \
  CORS_ORIGINS="https://app.invoicesummarizer.com" \
  -n invoice-summarizer
```

### 3.2 Deploy API Gateway

```bash
# Deploy all services
kubectl apply -f infra/kubernetes/api-gateway.yaml -n invoice-summarizer
kubectl apply -f infra/kubernetes/ingress-monitoring.yaml -n invoice-summarizer

# Verify deployments
kubectl get deployments -n invoice-summarizer
kubectl get pods -n invoice-summarizer

# Wait for rollout
kubectl rollout status deployment/api-gateway -n invoice-summarizer
```

### 3.3 Configure Ingress

```bash
# Install cert-manager for SSL
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create certificate issuer
kubectl apply -f infra/kubernetes/cert-issuer.yaml -n invoice-summarizer

# Apply ingress
kubectl apply -f infra/kubernetes/ingress.yaml -n invoice-summarizer
```

## Step 4: Database Migrations

```bash
# Run database migrations
kubectl run db-migration \
  --image=invoice-summarizer/api-gateway:latest \
  --restart=Never \
  --rm \
  -it \
  -- alembic upgrade head

# Verify database
kubectl exec -it deployment/postgres -n invoice-summarizer -- \
  psql -U postgres -d invoices -c "\dt"
```

## Step 5: Monitoring and Logging

### 5.1 Install Prometheus

```bash
# Add Prometheus Helm repository
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install Prometheus
helm install prometheus prometheus-community/kube-prometheus-stack \
  -n invoice-summarizer \
  -f infra/kubernetes/prometheus-values.yaml
```

### 5.2 Install Grafana

```bash
# Grafana is included in kube-prometheus-stack
# Access via port-forward
kubectl port-forward -n invoice-summarizer svc/prometheus-grafana 3000:80

# Login with admin/prom-operator (default)
# Add dashboards from: https://grafana.com/grafana/dashboards
```

### 5.3 Setup ELK Stack for Logging

```bash
# Deploy Elasticsearch, Logstash, Kibana
helm install elk elastic/eck-operator -n invoice-summarizer

# Configure Filebeat to send logs
kubectl apply -f infra/kubernetes/filebeat.yaml -n invoice-summarizer
```

## Step 6: Backup and Disaster Recovery

### 6.1 Database Backups

```bash
# Configure automated backups in RDS
aws rds modify-db-instance \
  --db-instance-identifier invoice-summarizer-prod \
  --backup-retention-period 30 \
  --preferred-backup-window "03:00-04:00"

# Create snapshot
aws rds create-db-snapshot \
  --db-instance-identifier invoice-summarizer-prod \
  --db-snapshot-identifier invoice-summarizer-backup-$(date +%Y%m%d)
```

### 6.2 Persistent Volume Backups

```bash
# Install Velero for Kubernetes backup
wget https://github.com/vmware-tanzu/velero/releases/download/v1.12.0/velero-v1.12.0-linux-amd64.tar.gz
tar -xvf velero-v1.12.0-linux-amd64.tar.gz
sudo mv velero-v1.12.0-linux-amd64/velero /usr/local/bin/

# Initialize Velero with S3
velero install \
  --provider aws \
  --plugins velero/velero-plugin-for-aws:v1.8.0 \
  --bucket invoice-summarizer-backups \
  --secret-file ./credentials-velero
```

### 6.3 Set Backup Schedule

```bash
# Daily backups at midnight UTC
velero schedule create daily-backup \
  --schedule="0 0 * * *" \
  --include-namespaces invoice-summarizer
```

## Step 7: Security Hardening

### 7.1 Network Policies

```bash
# Apply network policies to restrict traffic
kubectl apply -f infra/kubernetes/network-policies.yaml -n invoice-summarizer
```

### 7.2 Pod Security Standards

```bash
# Enable Pod Security Standards
kubectl label namespace invoice-summarizer \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/warn=restricted
```

### 7.3 RBAC Policies

```bash
# Verify RBAC is properly configured
kubectl auth can-i get pods --as=system:serviceaccount:invoice-summarizer:api-gateway
```

### 7.4 TLS/SSL Configuration

```bash
# Update API Gateway to enforce HTTPS
kubectl set env deployment/api-gateway \
  ENFORCE_HTTPS=true \
  HSTS_MAX_AGE=31536000 \
  -n invoice-summarizer
```

## Step 8: Performance Tuning

### 8.1 Vertical Pod Autoscaling

```bash
# Install VPA
helm repo add fairwinds-stable https://charts.fairwinds.com/stable
helm install vpa fairwinds-stable/vpa -n invoice-summarizer
```

### 8.2 Horizontal Pod Autoscaling

```bash
# HPA is already configured in api-gateway.yaml
# Verify it's working
kubectl get hpa -n invoice-summarizer
```

### 8.3 Cluster Autoscaling

```bash
# For AWS EKS
aws eks update-nodegroup-config \
  --cluster-name invoice-summarizer \
  --nodegroup-name workers \
  --scaling-config minSize=10,maxSize=50,desiredSize=20
```

## Step 9: Deployment Verification

```bash
# Check all pods are running
kubectl get pods -n invoice-summarizer

# Check services are available
kubectl get svc -n invoice-summarizer

# Test API health endpoint
kubectl port-forward -n invoice-summarizer svc/api-gateway 8000:80
curl http://localhost:8000/health

# Check logs
kubectl logs -f deployment/api-gateway -n invoice-summarizer

# Monitor resource usage
kubectl top nodes
kubectl top pods -n invoice-summarizer
```

## Step 10: Update Procedures

### 10.1 Rolling Update

```bash
# Update image
kubectl set image deployment/api-gateway \
  api-gateway=invoice-summarizer/api-gateway:v2.0.1 \
  -n invoice-summarizer

# Monitor rollout
kubectl rollout status deployment/api-gateway -n invoice-summarizer

# Rollback if needed
kubectl rollout undo deployment/api-gateway -n invoice-summarizer
```

### 10.2 Blue-Green Deployment

```bash
# Create green environment
kubectl apply -f infra/kubernetes/api-gateway-green.yaml -n invoice-summarizer

# Wait for green to be ready
kubectl wait --for=condition=ready pod -l version=green \
  -n invoice-summarizer --timeout=300s

# Switch traffic (update service selector)
kubectl patch service api-gateway \
  -p '{"spec":{"selector":{"version":"green"}}}' \
  -n invoice-summarizer

# Delete blue after verification
kubectl delete deployment api-gateway-blue -n invoice-summarizer
```

## Troubleshooting

### Pod won't start

```bash
kubectl describe pod <pod-name> -n invoice-summarizer
kubectl logs <pod-name> -n invoice-summarizer
```

### Database connection issues

```bash
# Test connection
kubectl run psql-test \
  --image=postgres:15 \
  --restart=Never \
  --rm \
  -it \
  -- psql -h postgres -U postgres -d invoices
```

### Memory leaks

```bash
# Monitor memory usage
kubectl top pods -n invoice-summarizer --sort-by=memory

# Collect heap dump
kubectl exec <pod> -- jmap -dump:live,format=b,file=/tmp/heap.bin 1
```

## Performance Benchmarks

Expected performance under load:
- **API Latency (p95)**: <1 second
- **Throughput**: 1,000+ invoices/minute
- **Success Rate**: >99.9%
- **Database Connections**: <100 active

## Support and Runbooks

For operational issues, see:
- `docs/runbooks/incident-response.md`
- `docs/runbooks/scaling.md`
- `docs/runbooks/disaster-recovery.md`
