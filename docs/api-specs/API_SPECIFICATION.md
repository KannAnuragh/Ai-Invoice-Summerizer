# API Specification - AI Invoice Summarizer v2.0

## Overview

REST API specification for all services. All responses follow standard JSON format.

## Base URLs

```
Development:  http://localhost:8000/api/v1
Staging:      https://staging-api.invoicesummarizer.com/api/v1
Production:   https://api.invoicesummarizer.com/api/v1
```

## Authentication

All requests (except `/health`) require authentication via `Authorization` header:

```
Authorization: Bearer <JWT_TOKEN>
```

JWT payload includes:
```json
{
  "sub": "user_id",
  "tenant_id": "tenant_id",
  "roles": ["role1", "role2"],
  "exp": 1234567890
}
```

---

## Common Response Format

### Success Response (2xx)
```json
{
  "status": "success",
  "data": { /* response payload */ },
  "trace_id": "abc123def456"
}
```

### Error Response (4xx, 5xx)
```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid file format",
    "details": [
      "File must be PDF, TIFF, PNG, or JPG"
    ]
  },
  "trace_id": "abc123def456"
}
```

### Error Codes
```
VALIDATION_ERROR        - Input validation failed
AUTHENTICATION_ERROR    - Invalid/expired JWT
AUTHORIZATION_ERROR     - Insufficient permissions
NOT_FOUND              - Resource not found
DUPLICATE_ERROR        - Duplicate document/invoice
CONFLICT_ERROR         - State transition conflict
RATE_LIMIT_ERROR       - Rate limit exceeded
INTERNAL_ERROR         - Server error
```

---

## Endpoints

### 1. UPLOAD SERVICE

#### Upload Invoice Document

**POST** `/upload`

Upload invoice document for processing.

**Request**
```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -F "file=@invoice.pdf" \
  -F "vendor_id=VENDOR_123" \
  -F "po_number=PO-2025-001" \
  -F "metadata={\"department\": \"operations\"}"
```

**Parameters**
- `file` (form-data, required): Invoice document (PDF, TIFF, PNG, JPG, max 50MB)
- `vendor_id` (string, optional): Vendor ID for classification
- `po_number` (string, optional): Associated Purchase Order number
- `metadata` (JSON string, optional): Custom metadata

**Response (201 Created)**
```json
{
  "status": "success",
  "data": {
    "document_id": "doc_550e8400e29b41d4",
    "filename": "invoice.pdf",
    "size_bytes": 2048576,
    "storage_key": "2025/12/22/doc_550e8400e29b41d4.pdf",
    "upload_timestamp": "2025-12-22T10:30:00Z",
    "estimated_processing_time_seconds": 45,
    "status": "processing"
  }
}
```

**Error Responses**
- 400: File too large, unsupported format
- 413: Payload too large
- 429: Rate limit exceeded

---

#### Upload Multiple Documents (Bulk)

**POST** `/upload/bulk`

Upload multiple invoices as ZIP archive.

**Request**
```bash
curl -X POST http://localhost:8000/api/v1/upload/bulk \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -F "file=@invoices.zip"
```

**Response (202 Accepted)**
```json
{
  "status": "success",
  "data": {
    "batch_id": "batch_3fa85f6417174fb03c",
    "document_count": 45,
    "processing_started_at": "2025-12-22T10:30:00Z",
    "estimated_completion_time": "2025-12-22T11:45:00Z",
    "status_url": "/upload/batch/batch_3fa85f6417174fb03c/status"
  }
}
```

---

### 2. INVOICE SERVICE

#### Get Invoice Details

**GET** `/invoices/{invoice_id}`

Retrieve fully processed invoice with all extracted data and AI summaries.

**Response (200)**
```json
{
  "status": "success",
  "data": {
    "invoice_id": "inv_550e8400e29b41d4",
    "document_id": "doc_550e8400e29b41d4",
    
    "vendor": {
      "name": "Acme Corporation",
      "vendor_id": "VENDOR_001",
      "tax_id": "12-3456789",
      "email": "invoices@acme.com"
    },
    
    "invoice_metadata": {
      "invoice_number": "INV-2025-12-001",
      "invoice_date": "2025-12-15",
      "due_date": "2026-01-15",
      "po_number": "PO-2025-001",
      "project_code": "PROJ-2025-Q4"
    },
    
    "amounts": {
      "subtotal": "10000.00",
      "tax": "1000.00",
      "total": "11000.00",
      "currency": "USD"
    },
    
    "line_items": [
      {
        "line_number": 1,
        "description": "Software License - Enterprise",
        "quantity": "1",
        "unit_price": "5000.00",
        "line_total": "5000.00",
        "tax_rate": "0.10",
        "po_line_number": "001",
        "po_matched": true,
        "variance_percent": 0
      },
      {
        "line_number": 2,
        "description": "Implementation Services",
        "quantity": "100",
        "unit_price": "50.00",
        "line_total": "5000.00",
        "tax_rate": "0.10",
        "po_line_number": "002",
        "po_matched": true,
        "variance_percent": 0
      }
    ],
    
    "extracted_fields": {
      "remittance_address": "123 Main St, New York, NY 10001",
      "billing_address": "123 Main St, New York, NY 10001",
      "payment_terms": "Net 30",
      "discount_terms": "2% 10 Net 30",
      "tax_id": "12-3456789"
    },
    
    "ai_summaries": {
      "finance": {
        "summary": "Routine invoice for enterprise software license and implementation services...",
        "key_points": ["Standard pricing", "All line items matched to PO-2025-001"],
        "financial_impact": "Expense recognition as software and services"
      },
      "procurement": {
        "summary": "Invoice matches approved PO with no variances...",
        "key_points": ["100% matched to PO", "On-time delivery"],
        "vendor_performance": "Excellent"
      },
      "executive": {
        "summary": "Standard vendor invoice, routine processing recommended",
        "key_metrics": {"count": 2, "total": 11000}
      }
    },
    
    "quality_scores": {
      "extraction_confidence": 0.98,
      "ocr_confidence": 0.96,
      "po_match_confidence": 1.0,
      "anomaly_risk_score": 0.02
    },
    
    "po_matching": {
      "po_number": "PO-2025-001",
        "match_status": "full_match",
      "match_confidence": 1.0,
      "line_items_matched": 2,
      "line_items_total": 2,
      "variances": []
    },
    
    "workflow": {
      "status": "review_pending",
      "current_step": "approval",
      "assigned_approver": "user_finance_manager",
      "deadline": "2025-12-24T17:00:00Z",
      "history": [
        {
          "status": "extracted",
          "timestamp": "2025-12-22T10:35:00Z",
          "actor": "system",
          "notes": "Extracted from OCR"
        },
        {
          "status": "review_pending",
          "timestamp": "2025-12-22T10:36:00Z",
          "actor": "system",
          "notes": "Assigned to finance manager"
        }
      ]
    },
    
    "flags": {
      "requires_attention": false,
      "reasons": []
    },
    
    "created_at": "2025-12-22T10:30:00Z",
    "updated_at": "2025-12-22T10:36:00Z"
  }
}
```

---

#### List Invoices

**GET** `/invoices`

List invoices with filtering and pagination.

**Query Parameters**
- `status` (string): Filter by status (extracted, review_pending, approved, rejected, paid)
- `vendor_id` (string): Filter by vendor
- `created_after` (ISO-8601): Filter by creation date
- `created_before` (ISO-8601): Filter by creation date
- `risk_score_min` (float): Filter by minimum risk score
- `risk_score_max` (float): Filter by maximum risk score
- `page` (int, default=1): Page number
- `per_page` (int, default=50, max=500): Items per page
- `sort` (string, default="-created_at"): Sort field (prefix - for descending)

**Example**
```bash
curl "http://localhost:8000/api/v1/invoices?status=review_pending&per_page=20" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

**Response (200)**
```json
{
  "status": "success",
  "data": {
    "items": [
      { /* invoice object */ },
      { /* invoice object */ }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total_items": 245,
      "total_pages": 13
    }
  }
}
```

---

#### Update Invoice Fields

**PATCH** `/invoices/{invoice_id}`

Manually correct extracted fields.

**Request**
```json
{
  "updates": {
    "vendor_name": "ACME Corporation (corrected)",
    "invoice_number": "INV-2025-12-001",
    "line_items": [
      {
        "line_number": 1,
        "quantity": "2"
      }
    ]
  },
  "reason": "Manual correction - vendor name typo"
}
```

**Response (200)**
```json
{
  "status": "success",
  "data": {
    "invoice_id": "inv_550e8400e29b41d4",
    "updated_fields": ["vendor_name", "line_items"],
    "requires_reprocessing": true,
    "audit_event_id": "audit_6ba7b810"
  }
}
```

---

### 3. APPROVAL SERVICE

#### Get Approval Queue

**GET** `/approvals`

List invoices pending approval.

**Query Parameters**
- `assigned_to` (string, optional): Filter by approver user ID
- `priority` (string, optional): Filter by priority (high, normal, low)
- `overdue` (boolean, optional): Only overdue items

**Response (200)**
```json
{
  "status": "success",
  "data": {
    "items": [
      {
        "invoice_id": "inv_550e8400e29b41d4",
        "vendor_name": "Acme Corporation",
        "total_amount": "11000.00",
        "invoice_date": "2025-12-15",
        "assigned_to": "user_finance_manager",
        "deadline": "2025-12-24T17:00:00Z",
        "is_overdue": false,
        "risk_flags": [],
        "summary": "Routine invoice..."
      }
    ],
    "pagination": { /* ... */ }
  }
}
```

---

#### Approve Invoice

**POST** `/invoices/{invoice_id}/approve`

Approve an invoice for payment.

**Request**
```json
{
  "approved_by": "user_finance_manager",
  "notes": "Approved as routine",
  "approval_code": "MFA_123456"
}
```

**Response (200)**
```json
{
  "status": "success",
  "data": {
    "invoice_id": "inv_550e8400e29b41d4",
    "status": "approved",
    "approved_at": "2025-12-22T14:30:00Z",
    "next_step": "Ready for payment processing",
    "audit_event_id": "audit_7ba7b811"
  }
}
```

---

#### Reject Invoice

**POST** `/invoices/{invoice_id}/reject`

Reject an invoice with reason.

**Request**
```json
{
  "reason_code": "pricing_mismatch",
  "reason_description": "Line item total doesn't match PO",
  "requested_corrections": [
    {
      "field": "line_items[0].quantity",
      "current_value": "100",
      "suggested_value": "50"
    }
  ]
}
```

**Response (200)**
```json
{
  "status": "success",
  "data": {
    "invoice_id": "inv_550e8400e29b41d4",
    "status": "rejected",
    "rejected_at": "2025-12-22T14:30:00Z",
    "vendor_notification_sent": true,
    "audit_event_id": "audit_7ba7b812"
  }
}
```

---

### 4. PO MATCHING SERVICE

#### Match Invoice to PO

**POST** `/invoices/{invoice_id}/match-po`

Match invoice against purchase order.

**Request**
```json
{
  "po_number": "PO-2025-001",
  "force_rematch": false
}
```

**Response (200)**
```json
{
  "status": "success",
  "data": {
    "invoice_id": "inv_550e8400e29b41d4",
    "po_number": "PO-2025-001",
    "match_status": "full_match",
    "match_confidence": 1.0,
    "summary": {
      "invoice_lines": 2,
      "po_lines": 2,
      "matched_lines": 2,
      "matched_amount": "11000.00",
      "invoice_amount": "11000.00"
    },
    "line_item_matches": [
      {
        "invoice_line": 1,
        "po_line": 1,
        "match_status": "exact_match",
        "description_match_score": 1.0,
        "quantity_match": true,
        "quantity_variance_percent": 0,
        "price_match": true,
        "price_variance_percent": 0
      }
    ],
    "variances": [],
    "recommendations": "Ready for payment"
  }
}
```

---

### 5. ANOMALY DETECTION

#### Get Risk Assessment

**GET** `/invoices/{invoice_id}/risk-assessment`

Get comprehensive risk analysis.

**Response (200)**
```json
{
  "status": "success",
  "data": {
    "invoice_id": "inv_550e8400e29b41d4",
    "overall_risk_score": 0.15,
    "risk_level": "low",
    "risk_factors": [
      {
        "factor": "amount_variance",
        "score": 0.05,
        "description": "Amount is 5% higher than average for this vendor"
      },
      {
        "factor": "duplicate_risk",
        "score": 0.00,
        "description": "No duplicate found"
      },
      {
        "factor": "vendor_behavior",
        "score": 0.10,
        "description": "Vendor has submitted 3 invoices in last 7 days (unusual)"
      }
    ],
    "flagged_for_review": false,
    "requires_additional_approval": false,
    "insights": {
      "vendor_pattern": "Normal for Acme Corporation",
      "seasonal_anomaly": false,
      "potential_fraud_indicators": []
    }
  }
}
```

---

### 6. ADMIN SERVICE

#### Update Approval Rules

**PUT** `/admin/approval-rules`

Update workflow approval rules.

**Request**
```yaml
rules:
  - name: "High Value Review"
    condition: "amount > 50000"
    required_approvers:
      - role: "finance_manager"
        deadline_hours: 48
  - name: "Vendor Risk"
    condition: "vendor_risk_score > 0.7"
    required_approvers:
      - role: "compliance_officer"
        deadline_hours: 24
```

**Response (200)**
```json
{
  "status": "success",
  "data": {
    "rules_updated": 2,
    "effective_at": "2025-12-22T15:00:00Z",
    "audit_event_id": "audit_7ba7b813"
  }
}
```

---

#### Get System Health

**GET** `/admin/health`

System health and service status.

**Response (200)**
```json
{
  "status": "healthy",
  "timestamp": "2025-12-22T15:00:00Z",
  "services": {
    "api_gateway": { "status": "healthy", "latency_ms": 2 },
    "ingestion_service": { "status": "healthy", "queue_depth": 42 },
    "ocr_service": { "status": "healthy", "processing": 3 },
    "database": { "status": "healthy", "connections": 15 },
    "cache": { "status": "healthy", "hit_rate": 0.87 },
    "storage": { "status": "healthy", "available_gb": 450 }
  },
  "metrics": {
    "documents_processed_24h": 1250,
    "average_processing_time_seconds": 45,
    "success_rate_percent": 99.2,
    "queue_depth": 42
  }
}
```

---

#### Get Audit Logs

**GET** `/admin/audit-logs`

Retrieve audit trail.

**Query Parameters**
- `event_type` (string): Filter by event type
- `resource_type` (string): Filter by resource (invoice, document, workflow)
- `actor_id` (string): Filter by user
- `date_from` (ISO-8601): Start date
- `date_to` (ISO-8601): End date
- `page` (int): Page number

**Response (200)**
```json
{
  "status": "success",
  "data": {
    "items": [
      {
        "event_id": "audit_6ba7b810",
        "timestamp": "2025-12-22T14:30:00Z",
        "event_type": "invoice.approved",
        "actor": {
          "user_id": "user_finance_manager",
          "email": "manager@company.com"
        },
        "resource": {
          "type": "invoice",
          "id": "inv_550e8400e29b41d4"
        },
        "changes": {
          "status": ["review_pending", "approved"]
        },
        "reason": "Approved as routine"
      }
    ],
    "pagination": { /* ... */ }
  }
}
```

---

### 7. HEALTH CHECK

#### Liveness Probe

**GET** `/health`

Check if API is responding.

**Response (200)**
```json
{
  "status": "ok",
  "timestamp": "2025-12-22T15:00:00Z",
  "service": "api-gateway",
  "version": "2.0.0"
}
```

---

## Rate Limiting

All endpoints are rate-limited:

```
Default: 100 requests per minute per user
Bulk Upload: 10 requests per hour
Admin: 50 requests per minute
```

Rate limit headers:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1703257800
```

---

## Error Handling

### Validation Errors (400)
```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      "vendor_id: must be non-empty",
      "file: must be PDF or image format"
    ]
  }
}
```

### Not Found (404)
```json
{
  "status": "error",
  "error": {
    "code": "NOT_FOUND",
    "message": "Invoice not found",
    "details": ["invoice_id: inv_550e8400e29b41d4"]
  }
}
```

### Conflict (409)
```json
{
  "status": "error",
  "error": {
    "code": "CONFLICT_ERROR",
    "message": "Invoice cannot be approved in current state",
    "details": ["current_status: rejected"]
  }
}
```

---

## Webhooks

Services can subscribe to events:

### Supported Events
- `invoice.extracted`
- `invoice.approved`
- `invoice.rejected`
- `approval.escalated`
- `document.processed`

### Webhook Payload
```json
{
  "event_id": "evt_550e8400e29b41d4",
  "event_type": "invoice.approved",
  "timestamp": "2025-12-22T14:30:00Z",
  "data": {
    "invoice_id": "inv_550e8400e29b41d4",
    "status": "approved"
  }
}
```

### Retry Policy
- 3 automatic retries with exponential backoff
- 5 second timeout
- 24-hour retention

---

## OpenAPI/Swagger

Full OpenAPI 3.0 specification available at:

```
GET /docs              - Swagger UI
GET /redoc             - ReDoc UI
GET /openapi.json      - OpenAPI JSON schema
```

