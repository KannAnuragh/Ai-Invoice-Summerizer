# Operations Runbook - AI Invoice Summarizer

## Emergency Response

### Service Down - API Gateway

**Symptoms**: HTTP 502/503, connection timeouts, health checks failing

**Steps**:
```bash
# 1. Check pod status
kubectl get pods -n invoice-summarizer -l app=api-gateway

# 2. Inspect logs for errors
kubectl logs -f deployment/api-gateway -n invoice-summarizer

# 3. Check resource constraints
kubectl top pods -n invoice-summarizer
kubectl describe pod <pod-name> -n invoice-summarizer

# 4. Restart pods
kubectl delete pod -l app=api-gateway -n invoice-summarizer

# 5. Monitor rollout
kubectl rollout status deployment/api-gateway -n invoice-summarizer
```

### Database Connection Pool Exhausted

**Symptoms**: "Connection pool timeout", slow queries, connection refused

**Steps**:
```bash
# 1. Check connection count
kubectl exec postgres -- psql -U postgres -d invoices -c \
  "SELECT count(*) FROM pg_stat_activity;"

# 2. Identify idle connections
kubectl exec postgres -- psql -U postgres -d invoices -c \
  "SELECT pid, usename, state FROM pg_stat_activity WHERE state='idle';"

# 3. Kill idle connections
kubectl exec postgres -- psql -U postgres -d invoices -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity \
   WHERE state='idle' AND state_change < now() - interval '10 min';"

# 4. Scale API Gateway replicas down then up
kubectl scale deployment/api-gateway --replicas=1 -n invoice-summarizer
sleep 30
kubectl scale deployment/api-gateway --replicas=3 -n invoice-summarizer
```

### Memory Leak in Service

**Symptoms**: Increasing memory usage, OOMKilled pods

**Steps**:
```bash
# 1. Check memory trends
kubectl top pods -n invoice-summarizer --sort-by=memory

# 2. Get heap dump
kubectl exec <pod> -- \
  python -c "import tracemalloc; tracemalloc.start(); \
  tracemalloc.take_snapshot().dump('mem.dump')"

# 3. Restart pod
kubectl delete pod <pod-name> -n invoice-summarizer

# 4. Monitor after restart
kubectl logs -f <pod-name> -n invoice-summarizer
```

### Disk Space Full

**Symptoms**: "No space left on device", write failures

**Steps**:
```bash
# 1. Check disk usage
kubectl exec postgres -- \
  psql -U postgres -d invoices -c "SELECT pg_database_size('invoices');"

# 2. Clean up old logs
kubectl exec postgres -- \
  psql -U postgres -d invoices -c "VACUUM ANALYZE;"

# 3. Archive old data
# Run archival process
kubectl run archive-job --image=invoice-summarizer/tools:latest \
  --restart=Never --rm -- python scripts/archive_old_invoices.py

# 4. Expand volume
kubectl patch pvc postgres-pvc \
  -p '{"spec":{"resources":{"requests":{"storage":"200Gi"}}}}'
```

## Scaling Operations

### Horizontal Scaling (Add Pods)

```bash
# Manual scaling
kubectl scale deployment/api-gateway --replicas=5 -n invoice-summarizer

# Check HPA status
kubectl get hpa -n invoice-summarizer

# View HPA details
kubectl describe hpa api-gateway-hpa -n invoice-summarizer
```

### Vertical Scaling (Increase Resources)

```bash
# Update resource requests
kubectl set resources deployment/api-gateway \
  --requests=cpu=1000m,memory=1Gi \
  --limits=cpu=2000m,memory=2Gi \
  -n invoice-summarizer

# Verify changes
kubectl get pod -o jsonpath='{.items[0].spec.containers[0].resources}' \
  -n invoice-summarizer
```

### Database Scaling

```bash
# Add read replicas
aws rds create-db-instance-read-replica \
  --db-instance-identifier invoice-summarizer-prod-read-1 \
  --source-db-instance-identifier invoice-summarizer-prod

# Monitor replication lag
aws rds describe-db-instances \
  --db-instance-identifier invoice-summarizer-prod-read-1 \
  --query 'DBInstances[0].[DBInstanceStatus]'
```

## Performance Tuning

### Query Optimization

```bash
# Identify slow queries
kubectl exec postgres -- \
  psql -U postgres -d invoices -c \
  "SELECT query, calls, total_time, mean_time FROM pg_stat_statements \
   ORDER BY mean_time DESC LIMIT 10;"

# Create missing indexes
kubectl exec postgres -- \
  psql -U postgres -d invoices -c \
  "CREATE INDEX idx_invoice_status ON invoices(status, created_at);"

# Analyze query plan
kubectl exec postgres -- \
  psql -U postgres -d invoices -c \
  "EXPLAIN ANALYZE SELECT * FROM invoices WHERE status='review_pending';"
```

### Cache Optimization

```bash
# Monitor Redis memory
kubectl exec redis -- redis-cli info memory

# Check hit rate
kubectl exec redis -- redis-cli info stats | grep hits

# Adjust eviction policy
kubectl exec redis -- redis-cli config set maxmemory-policy allkeys-lru
```

### API Performance

```bash
# Monitor endpoints with slowest latency
curl http://localhost:3000/prometheus \
  -d 'query=histogram_quantile(0.95, http_request_duration_seconds)'

# Check throughput
curl http://localhost:3000/prometheus \
  -d 'query=rate(http_requests_total[5m])'

# Analyze error rate
curl http://localhost:3000/prometheus \
  -d 'query=rate(http_requests_total{status=~"5.."}[5m])'
```

## Maintenance Tasks

### Weekly Tasks

```bash
# Update dependencies
cd backend && pip list --outdated
pip install --upgrade <package>
git commit -am "Update dependencies"

# Review logs for errors
kubectl logs -n invoice-summarizer \
  --timestamps=true --since=1w | grep ERROR | sort | uniq -c

# Check certificate expiration
kubectl get certificate -n invoice-summarizer -o jsonpath='{.items[*].status.notAfter}'
```

### Monthly Tasks

```bash
# Full database maintenance
kubectl exec postgres -- \
  psql -U postgres -d invoices -c "VACUUM FULL ANALYZE;"

# Archive processed invoices
kubectl run monthly-archive --image=invoice-summarizer/tools:latest \
  --restart=Never --rm -- \
  python scripts/archive_old_invoices.py --months=3

# Security audit
kubectl get rolebindings -n invoice-summarizer -o wide
kubectl get networkpolicies -n invoice-summarizer

# Update security patches
kubectl set image deployment/api-gateway \
  api-gateway=invoice-summarizer/api-gateway:v2.0.1 \
  -n invoice-summarizer
```

### Quarterly Tasks

```bash
# Disaster recovery drill
# 1. Create backup
kubectl run db-backup --image=postgres:15 --restart=Never \
  --rm -- pg_basebackup -h postgres -U postgres -D /tmp/backup

# 2. Restore to test environment
kubectl apply -f infra/kubernetes/postgres-test.yaml -n invoice-summarizer-test

# 3. Verify data integrity
kubectl exec postgres-test -- \
  psql -U postgres -d invoices -c "SELECT count(*) FROM invoices;"

# 4. Document process
# Create runbook entry with results

# Penetration testing
# Schedule with security team
# Review findings and remediate

# Full security audit
# Run vulnerability scans
# Review access logs
# Audit RBAC policies
```

## Backup & Restore

### Manual Backup

```bash
# Create immediate backup
kubectl exec postgres -- \
  pg_basebackup -D /tmp/backup -Ft

# Upload to S3
aws s3 cp /tmp/backup s3://invoice-summarizer-backups/backup-$(date +%Y%m%d).tar.gz

# Verify backup
aws s3 ls s3://invoice-summarizer-backups/
```

### Restore from Backup

```bash
# 1. Download backup
aws s3 cp s3://invoice-summarizer-backups/backup-20240101.tar.gz .
tar -xzf backup-20240101.tar.gz -C /tmp/restore

# 2. Stop application
kubectl scale deployment/api-gateway --replicas=0 -n invoice-summarizer

# 3. Restore database
kubectl exec -it postgres -- \
  psql -U postgres -d invoices -f /tmp/restore/backup.sql

# 4. Verify integrity
kubectl exec postgres -- \
  psql -U postgres -d invoices -c "SELECT count(*) FROM invoices;"

# 5. Resume application
kubectl scale deployment/api-gateway --replicas=3 -n invoice-summarizer

# 6. Monitor logs
kubectl logs -f deployment/api-gateway -n invoice-summarizer
```

## Monitoring & Alerting

### Key Metrics to Monitor

```
API Performance:
├── Request latency (p50, p95, p99)
├── Error rate
├── Throughput (requests/second)
└── Active connections

Database:
├── Query latency
├── Connection count
├── Disk usage
└── Replication lag

Infrastructure:
├── CPU usage
├── Memory usage
├── Disk I/O
└── Network I/O
```

### Creating Custom Alerts

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: custom-alert
  namespace: invoice-summarizer
spec:
  groups:
  - name: custom
    rules:
    - alert: CustomAlert
      expr: your_metric > 0.8
      for: 5m
      annotations:
        summary: "Alert triggered"
```

## Incident Management

### Severity Levels

- **SEV 1**: Complete outage, affecting all users
  - Response time: Immediate
  - Escalation: CEO, VP Ops notified

- **SEV 2**: Partial outage, degraded performance
  - Response time: <15 minutes
  - Escalation: Engineering manager

- **SEV 3**: Minor issues, workaround available
  - Response time: <1 hour
  - Escalation: Team lead

### Incident Response Template

```
INCIDENT ID: INC-2024-001
SEVERITY: SEV 2
DETECT TIME: 2024-01-15 10:30 UTC
RESOLVE TIME: 2024-01-15 10:45 UTC (15 minutes)

IMPACT:
- 50% of invoices failed processing
- ~500 users unable to access system

TIMELINE:
10:30 - Prometheus alert triggered (high error rate)
10:32 - On-call engineer acknowledged
10:35 - Root cause identified (database connection pool)
10:40 - Mitigation applied (restart API pods)
10:45 - Service restored, all metrics normal

ROOT CAUSE:
Memory leak in database connection handling

REMEDIATION:
1. Deployed patch v2.0.1
2. Increased connection pool size
3. Added connection monitoring alert

LESSONS LEARNED:
- Should have caught this in staging
- Need better pre-release testing
```

## Contact & Escalation

**On-Call Schedule**: [Link to calendar]

**Escalation Path**:
1. On-call engineer (immediate)
2. Engineering manager (+30 min)
3. VP Engineering (+1 hour)
4. CTO (+2 hours)

**Communication**:
- Slack: #incident-response
- Email: incidents@invoicesummarizer.com
- Phone: +1-XXX-XXX-XXXX

**Stakeholder Updates**:
- Every 15 minutes during incident
- Status page update
- Post-incident review within 24 hours

## Tools & Access

**Essential Tools**:
- kubectl: Kubernetes cluster access
- aws-cli: AWS resource management
- psql: PostgreSQL database queries
- redis-cli: Redis cache commands
- curl: API testing

**Access Requirements**:
- Kubernetes cluster kubeconfig
- AWS IAM credentials
- PostgreSQL credentials
- RabbitMQ credentials

**Documentation**:
- [System Architecture](../architecture/SYSTEM_ARCHITECTURE.md)
- [API Specification](../api-specs/API_SPECIFICATION.md)
- [Deployment Guide](PRODUCTION_DEPLOYMENT.md)
