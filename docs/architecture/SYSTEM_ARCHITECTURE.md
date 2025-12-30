# AI Invoice Summarizer - System Architecture

## Executive Overview

The AI Invoice Summarizer is an enterprise-grade invoice processing platform that combines document intelligence, AI-powered analysis, and robust workflow orchestration. It's designed to process thousands of invoices daily with high accuracy, audit compliance, and seamless ERP integration.

### Core Principles

1. **Separation of Concerns**: Three independent systems (Document Processing, AI Reasoning, Enterprise Workflow)
2. **Audit Trail**: Every action is immutably logged for compliance
3. **Scalability**: Stateless services that scale horizontally
4. **Observability**: Complete visibility into all operations
5. **Security**: Multi-layer authentication, encryption, and validation

---

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Frontend (Enterprise UX)                     │
│  ┌──────────────┬──────────────────┬────────────┬───────────┐   │
│  │Invoice Viewer│ Approvals Queue  │  Admin    │  Chat     │   │
│  └──────────────┴──────────────────┴────────────┴───────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP/REST
┌─────────────────────────────────────────────────────────────────┐
│                   API Gateway (8000) - Auth & Routing            │
│  ┌────────────┬───────────┬─────────┬──────────┬─────────────┐  │
│  │Auth/OAuth  │Rate Limit │Tracing  │Logging   │CORS Filter  │  │
│  └────────────┴───────────┴─────────┴──────────┴─────────────┘  │
└────────┬──────────┬──────────┬──────────┬──────────┬──────────────┘
         │          │          │          │          │
         ↓          ↓          ↓          ↓          ↓
    ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
    │Ingestion │ │Document  │ │Workflow  │ │Validation│ │Audit    │
    │Service   │ │Service   │ │Service   │ │Service   │ │Service  │
    │(8001)    │ │(8002)    │ │(8006)    │ │(8007)    │ │(8008)   │
    └─────┬────┘ └─────┬────┘ └────┬─────┘ └────┬─────┘ └────┬────┘
          │            │           │            │           │
          └────────────┬───────────┴────────────┴───────────┘
                       │ Message Queue (RabbitMQ/Redis)
         ┌─────────────┼─────────────┐
         ↓             ↓             ↓
    ┌─────────┐  ┌──────────┐  ┌──────────────┐
    │   OCR   │  │Extraction│  │Summarization │
    │Service  │  │Service   │  │Service       │
    │ (8003)  │  │(8004)    │  │(8005)        │
    └─────────┘  └──────────┘  └──────────────┘
         │             │             │
         └─────────────┼─────────────┘
                       ↓
         ┌──────────────────────────┐
         │  Anomaly Detection       │
         │  PO Matching             │
         │  Risk Scoring            │
         │  Feedback Loop           │
         └──────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ↓             ↓             ↓
    ┌────────┐  ┌──────────┐  ┌─────────────┐
    │Postgres│  │Redis     │  │Object Store │
    │        │  │(Cache)   │  │(S3/Local)   │
    └────────┘  └──────────┘  └─────────────┘
         │             │             │
         └─────────────┼─────────────┘
                       │
         ┌─────────────┴─────────────┐
         ↓                           ↓
    ┌──────────────┐         ┌────────────────┐
    │ERP Systems   │         │Payment Systems │
    │(SAP, Coupa)  │         │(Check, ACH)    │
    └──────────────┘         └────────────────┘
```

---

## Service Layer Details

### 1. API Gateway (Port 8000)

**Responsibility**: Single entry point for all requests

#### Key Features
- JWT/OAuth2 authentication
- Multi-tenant resolution
- Request logging with trace IDs
- Rate limiting (per-tenant, per-user, per-IP)
- CORS filtering
- Request/response serialization

#### Routes
```
POST   /api/v1/upload                    - Upload invoice
GET    /api/v1/invoices                  - List invoices
GET    /api/v1/invoices/{id}             - Get invoice details
POST   /api/v1/invoices/{id}/approve     - Approve invoice
GET    /api/v1/invoices/{id}/match-po    - PO matching
POST   /api/v1/admin/config              - Update config
GET    /health                           - Health check
```

#### Middleware Stack (Bottom-to-Top)
1. CORS Middleware
2. Logging Middleware (request/response)
3. Rate Limit Middleware
4. Auth Middleware (if needed)
5. Tracing Middleware

---

### 2. Ingestion Service (Port 8001)

**Responsibility**: Get invoices into the system safely

#### Data Flow
```
Upload Request
    ↓
[Validate File Type, Size, Format]
    ↓
[Scan for Viruses/Malware]
    ↓
[Generate Document ID]
    ↓
[Check for Duplicates]
    ↓
[Store to Object Storage]
    ↓
[Emit Ingestion Event]
    ↓
Document Ready for Processing
```

#### Key Components

**File Validators**
- Type checks (PDF, TIFF, PNG, JPG)
- Size limits (max 50MB)
- Format validation
- Virus scanning hooks (ClamAV)

**Duplicate Detection**
- File hash comparison (MD5/SHA256)
- Vendor + invoice number similarity
- Previous N days lookback

**Storage Service**
- Abstract backend interface
- Local filesystem backend
- S3 backend (production)
- Organized by date: `YYYY/MM/DD/document_id.ext`

**Email Integration**
- IMAP-based vendor inbox monitoring
- Automatic attachment extraction
- Sender → Vendor mapping
- Webhook receiver for email events

---

### 3. Document Service (Port 8002)

**Responsibility**: Prepare documents for OCR

#### Processing Pipeline
```
Raw Document
    ↓
[Image Cleanup - Remove stamps, watermarks]
    ↓
[Deskew - Rotate to correct orientation]
    ↓
[DPI Normalization - Standardize to 300 DPI]
    ↓
[Language Detection - Determine OCR language]
    ↓
[Classification - Invoice/Receipt/Credit Note]
    ↓
[Store Processed Version]
    ↓
Ready for OCR
```

#### Components

**Image Preprocessing**
- OpenCV-based processing
- Grayscale conversion
- Binarization (for text extraction)
- Deskewing algorithm
- DPI normalization

**Classification**
- Document type detection (invoice, receipt, credit note)
- Used to select correct extraction rules

**Language Detection**
- Multi-language support (EN, FR, DE, ES, IT, etc.)
- Used to select OCR language + LLM language

---

### 4. OCR Service (Port 8003)

**Responsibility**: Extract text and layout information

#### Processing Pipeline
```
Preprocessed Image
    ↓
[Layout Detection - Identify tables, headers, line items]
    ↓
[Text Recognition - Tesseract/Paddle OCR]
    ↓
[Table Extraction - Parse structured data]
    ↓
[Confidence Scoring - Quality assessment]
    ↓
Structured Text Output
```

#### Technology Stack
- **OCR Engines**: Tesseract (open-source) + Paddle OCR (Chinese/complex)
- **Layout Detection**: CRAFT or YOLOv5
- **Table Extraction**: Custom ML model + rule-based

#### Output Format
```json
{
  "text": "raw extracted text",
  "regions": [
    {
      "type": "header",
      "text": "...",
      "confidence": 0.95,
      "bbox": [x, y, w, h]
    }
  ],
  "tables": [
    {
      "rows": [...],
      "columns": [...],
      "confidence": 0.92
    }
  ],
  "overall_confidence": 0.93
}
```

---

### 5. Extraction Service (Port 8004)

**Responsibility**: Turn OCR text into structured invoice data

#### Extraction Pipeline
```
OCR Output
    ↓
[Field Extraction - vendor, date, amount, PO, etc.]
    ↓
[Value Normalization - currencies, dates, formats]
    ↓
[Validation Rules - enforce constraints]
    ↓
[Confidence Scoring]
    ↓
Structured Invoice JSON
```

#### Key Features

**Field Extractors**
- Vendor/Company name
- Invoice number
- Invoice date
- Due date
- Line items (description, quantity, unit price, tax)
- Total amount
- Tax amount
- Purchase order number
- Currency
- Payment terms

**Normalization**
- Currency conversion to base currency
- Date parsing (handles multiple formats)
- Phone/email parsing
- Address parsing

**Validation Rules**
- Amount consistency (line items sum to total)
- Date logic (invoice date ≤ due date)
- Vendor name not empty
- Minimum line items count

---

### 6. Summarization Service (Port 8005)

**Responsibility**: Generate AI-powered summaries and insights

#### Processing Pipeline
```
Structured Invoice
    ↓
[Select Role Template - CFO/Finance/Procurement]
    ↓
[Generate Summary - LLM with constraints]
    ↓
[Extract Key Insights]
    ↓
[Generate Explainability - "why was this flagged?"]
    ↓
Role-Specific Summaries
```

#### Prompt Templates

**Finance Template**
```
Analyze this invoice from an accounting perspective:
- Liability impact
- Revenue recognition implications
- Tax treatment recommendations
- Financial impact

Invoice: {invoice_data}
```

**Procurement Template**
```
Analyze this invoice from a procurement perspective:
- Vendor performance
- Price vs. contract
- Delivery vs. PO
- Compliance with terms

Invoice: {invoice_data}
```

**Executive Template** (CFO)
```
Executive summary for board reporting:
- Key metrics
- Risk highlights
- Vendor portfolio impact
- Cost trends

Invoice: {invoice_data}
```

#### Safety Mechanisms
- Template-based generation (no free-form)
- Output validation (length, format, PII removal)
- Hallucination detection
- Content moderation

---

### 7. Workflow Service (Port 8006)

**Responsibility**: Mirror real enterprise approval flows

#### State Machine
```
┌──────────────┐
│   UPLOADED   │ - Document received
└──────┬───────┘
       │
       ↓
┌──────────────┐
│ PREPROCESSING│ - Image cleanup
└──────┬───────┘
       │
       ↓
┌──────────────┐
│   EXTRACTED  │ - Fields extracted
└──────┬───────┘
       │
       ↓
┌──────────────────┐
│   REVIEW_PENDING │ - Waiting for human review
└──────┬───────────┘
       │
   ┌───┴───┐
   │       │
   ↓       ↓
APPROVED  REJECTED
   │       │
   └───┬───┘
       ↓
┌──────────────┐
│ AUTHORIZED   │ - Ready to pay
└──────┬───────┘
       │
       ↓
┌──────────────┐
│    PAID      │ - Payment completed
└──────────────┘
```

#### Approval Rules Engine

**Rule Format** (YAML)
```yaml
rules:
  - name: "High Value Review"
    condition: "amount > 50000"
    required_approvers:
      - role: "finance_manager"
        deadline: "2 days"
  
  - name: "Vendor Risk Check"
    condition: "vendor_risk_score > 0.7"
    required_approvers:
      - role: "compliance_officer"
        deadline: "1 day"
  
  - name: "Budget Check"
    condition: "project_id in budget_controlled_projects"
    required_approvers:
      - role: "project_manager"
        deadline: "3 days"
```

#### SLA Management
- Automated escalation
- Email/Slack notifications
- Breach detection and reporting
- Auto-assignment based on workload

---

### 8. Validation Service (Port 8007)

**Responsibility**: Validate invoice against purchase orders and contracts

#### PO Matching Algorithm

```
Invoice {vendor, po_number, total_amount, line_items}
    ↓
[Fetch PO from database]
    ↓
[Match Line Items]
    - Quantity variance threshold: 2%
    - Price variance threshold: 5%
    - Description matching (fuzzy)
    ↓
[Calculate Match Confidence]
    - Exact match: 100%
    - Within tolerance: 80%
    - Mismatch: <50%
    ↓
[Generate Variance Report]
    - Overbilled items
    - Missing items
    - Price discrepancies
    ↓
Match Result with Variance Analysis
```

#### Anomaly Detection

**Statistical Models**
- Vendor spending patterns (rolling averages)
- Invoice amount outlier detection (Z-score, IQR)
- Frequency anomalies (unusual spike in invoices)
- Payment term deviations

**Risk Scoring**
```
Risk Score = (
    0.3 * amount_anomaly_score +
    0.2 * vendor_behavior_score +
    0.2 * po_mismatch_score +
    0.15 * duplicate_score +
    0.15 * fraud_indicators_score
)

If Risk Score > 0.7: FLAG_FOR_REVIEW
```

---

### 9. Audit Service (Port 8008)

**Responsibility**: Maintain immutable audit trail

#### Event Types
```
Document Events:
  - document.uploaded
  - document.processed
  - document.deleted

Invoice Events:
  - invoice.created
  - invoice.updated
  - invoice.extracted
  - invoice.validated
  - invoice.approved
  - invoice.rejected
  - invoice.paid

Workflow Events:
  - workflow.started
  - workflow.transitioned
  - review.requested
  - escalation.triggered

User Events:
  - user.login
  - user.logout
  - user.action

System Events:
  - system.error
  - config.changed
  - rule.updated
```

#### Event Storage

**Immutability Guarantees**
- Append-only log
- Hash chain (event N hash includes event N-1)
- Tamper detection via cryptographic signatures
- Write-once storage

**Schema**
```json
{
  "event_id": "uuid",
  "timestamp": "ISO-8601",
  "event_type": "string",
  "actor": {
    "user_id": "string",
    "role": "string",
    "tenant_id": "string"
  },
  "resource": {
    "type": "invoice|document|workflow",
    "id": "string"
  },
  "action": "created|updated|deleted|approved|rejected",
  "old_state": {},
  "new_state": {},
  "reason": "string",
  "previous_event_hash": "hash",
  "event_hash": "hash"
}
```

#### Legal Hold

- Retention policies per document type
- Immutable deletion (only archive)
- Compliance certifications (SOC2, ISO27001)

---

## Data Models

### Core Entities

#### Document
```python
@dataclass
class Document:
    document_id: str
    tenant_id: str
    original_filename: str
    file_size_bytes: int
    mime_type: str
    storage_key: str
    
    # Metadata
    uploaded_at: datetime
    uploaded_by: str
    
    # Processing Status
    classification: str  # "invoice", "receipt", "credit_note"
    language: str       # "en", "fr", "de", "es"
    
    # AI Processing Results
    ocr_output: dict
    extraction_output: dict
    summaries: dict     # {"cfo": "...", "finance": "..."}
    
    # Scores
    confidence_scores: dict
    risk_score: float
    
    # Workflow
    workflow_state: str
    current_approver_id: Optional[str]
    approval_deadline: Optional[datetime]
```

#### Invoice
```python
@dataclass
class Invoice:
    invoice_id: str
    document_id: str
    vendor_id: str
    
    # Core Fields
    vendor_name: str
    invoice_number: str
    invoice_date: date
    due_date: date
    
    # Amounts
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    currency: str
    
    # Line Items
    line_items: List[LineItem]
    
    # Purchase Order
    po_number: Optional[str]
    po_match_confidence: Optional[float]
    
    # Workflow
    status: str  # "extracted", "review_pending", "approved", "paid"
    created_at: datetime
    updated_at: datetime
```

#### AuditEvent (Immutable)
```python
@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    timestamp: datetime
    event_type: str
    actor: Actor
    resource: Resource
    action: str
    changes: dict
    reason: Optional[str]
    previous_event_hash: Optional[str]
    event_hash: str  # SHA-256
```

---

## Data Flow: PII Handling

### Principle: Minimize PII Surface

```
External Input (May contain PII)
    ↓
[Ingestion Service - Mark PII fields]
    ↓
[Database - Encrypt PII columns]
    ↓
[In-Memory - PII only when necessary]
    ↓
[Summarization - Redact PII from output]
    ↓
[Audit Logs - Log PII redacted]
    ↓
[Output to User - PII visible to authorized roles only]
```

### PII Fields
- Vendor contact information (emails, phone, address)
- Employee names (approvers, handlers)
- Bank account numbers
- Tax IDs

### Protection Mechanisms
- Column-level encryption (PII sensitive)
- TLS in transit
- Field-level redaction in logs
- Role-based visibility
- Audit trail for PII access

---

## Technology Stack Summary

| Layer | Technology |
|-------|-----------|
| API Gateway | FastAPI + Uvicorn |
| Authentication | JWT + OAuth2 (OIDC) |
| Message Queue | RabbitMQ / Redis Streams |
| OCR | Tesseract + Paddle OCR |
| AI/LLM | OpenAI GPT-4 / Azure OpenAI |
| Database | PostgreSQL 15 |
| Cache | Redis 7 |
| Storage | S3 / Local filesystem |
| Tracing | OpenTelemetry + Jaeger |
| Metrics | Prometheus |
| Logging | Structured JSON logs → ELK |
| Containerization | Docker |
| Orchestration | Kubernetes |
| CI/CD | GitHub Actions / GitLab CI |

---

## Deployment Architecture

### Development Environment
- Docker Compose for local services
- In-memory event queue
- SQLite for prototyping

### Staging Environment
- Kubernetes cluster (1 master, 2 workers)
- Managed PostgreSQL (AWS RDS)
- S3 for document storage
- CloudWatch for logging

### Production Environment
- Kubernetes cluster (3+ masters, 10+ workers)
- Multi-AZ RDS PostgreSQL
- S3 with versioning and lifecycle policies
- CloudFront CDN
- WAF + rate limiting
- Auto-scaling based on metrics
- Multi-region disaster recovery

---

## Scalability Considerations

### Horizontal Scaling
- All services are stateless
- Replicate service pods as needed
- Use Kubernetes HPA (Horizontal Pod Autoscaler)

### Database Scaling
- Read replicas for reporting queries
- Partitioning on tenant_id for isolation
- Archive old documents after 7 years

### Message Queue
- Consumer groups for parallel processing
- Dead-letter queues for failed events

### Caching Strategy
- Redis for session data
- Cache OCR results (expensive operation)
- Cache PO matching results (24hr TTL)

---

## Security Architecture

### Authentication Layers
1. **Network Layer**: TLS 1.3, WAF
2. **API Layer**: JWT + OAuth2/OIDC
3. **Database Layer**: Encryption at rest
4. **Field Layer**: Column-level encryption for PII

### Authorization
- RBAC (Role-Based Access Control)
- Tenant isolation
- Resource-level permissions

### Audit & Compliance
- Immutable audit logs
- PII access tracking
- Export for regulatory audits

---

## Disaster Recovery

### RPO (Recovery Point Objective)
- 5 minutes (acceptable data loss)

### RTO (Recovery Time Objective)
- 1 hour (acceptable downtime)

### Backup Strategy
- Continuous replication to secondary region
- Daily snapshots of databases
- Document versioning in S3
- Point-in-time recovery capability

---

This architecture is designed to scale to 1M+ invoices/day while maintaining audit compliance, security, and operational excellence.
