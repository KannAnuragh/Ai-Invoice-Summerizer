# AI Invoice Extraction - Complete Guide

## Overview

The AI Invoice Summarizer now features complete invoice scanning and data extraction with AI. When you upload an invoice:

1. **Upload** - File is uploaded and stored
2. **OCR Processing** - Tesseract extracts text from the document
3. **AI Extraction** - Fields are extracted using pattern matching and AI
4. **Database Update** - Invoice record is updated with extracted data
5. **Frontend Display** - Real-time status updates and data display

## Architecture Flow

```
User Upload → API Gateway → Database (UPLOADED)
                ↓
        Message Queue Event (INVOICE_UPLOADED)
                ↓
        Event Handler → Invoice Processor
                ↓
        OCR Service (Tesseract)
                ↓
        Extraction Service (AI/Patterns)
                ↓
        Message Queue Event (INVOICE_PROCESSED)
                ↓
        Event Handler → Database Update (EXTRACTED)
                ↓
        Frontend Polling → Display Data
```

## Features

### Backend Features

- **Automatic OCR**: Uses Tesseract OCR to extract text from PDF/image files
- **AI Field Extraction**: Intelligent extraction of:
  - Invoice number
  - Vendor name and address
  - Invoice date and due date
  - Subtotal, tax, and total amounts
  - Line items
  - PO numbers
  - Payment terms
  - Tax IDs

- **Event-Driven Processing**: Message queue ensures reliable processing
- **Database Persistence**: All extracted data saved to PostgreSQL
- **Status Tracking**: Real-time status updates (uploaded → processing → extracted)

### Frontend Features

- **Real-Time Polling**: Automatically polls for processing status
- **Live Data Display**: Shows extracted data as it becomes available
- **Processing Indicators**: Visual feedback during OCR and extraction
- **Extracted Data Preview**: Displays key fields immediately after extraction
- **Direct Navigation**: Link to full invoice details from upload page

## How to Use

### 1. Start the System

```powershell
# Terminal 1: Start Backend
cd "c:\project\ai invoice summerizer\backend"
python -m uvicorn api-gateway.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start Frontend
cd "c:\project\ai invoice summerizer\frontend"
npm run dev
```

### 2. Upload an Invoice

1. Navigate to http://localhost:5173/upload
2. Drag & drop or click to select invoice files (PDF, PNG, JPG, TIFF)
3. Click "Upload Files"
4. Watch as the system processes each invoice:
   - **Uploading** - File being uploaded
   - **Processing** - OCR and AI extraction in progress
   - **Extracted** - Data extraction complete

### 3. View Extracted Data

**On Upload Page:**
- Extracted data appears automatically below the file list
- Shows vendor, invoice number, total, date, status, PO number
- Click "View Full Invoice Details" to see complete information

**On Invoice List:**
- Navigate to http://localhost:5173/invoices
- All invoices with extracted data are listed
- Filter by status: uploaded, processing, extracted, validated

**On Invoice Viewer:**
- Click any invoice to view full details
- Complete extracted data with confidence scores
- Risk assessment and anomalies
- Audit trail and processing history

## Technical Details

### Message Queue Events

**INVOICE_UPLOADED Event**
```json
{
  "event_type": "INVOICE_UPLOADED",
  "data": {
    "document_id": "uuid",
    "invoice_id": "inv-xxxxx",
    "filename": "invoice.pdf",
    "storage_path": "/uploads/2025/01/01/uuid.pdf"
  }
}
```

**INVOICE_PROCESSED Event**
```json
{
  "event_type": "INVOICE_PROCESSED",
  "data": {
    "invoice_id": "inv-xxxxx",
    "extracted_data": {
      "vendor_name": "Acme Corp",
      "invoice_number": "INV-2025-001",
      "total_amount": 1250.00,
      "invoice_date": "2025-01-15",
      "currency": "USD",
      ...
    }
  }
}
```

### Database Schema

Invoice records are updated with extracted fields:
- `status`: uploaded → processing → extracted → validated
- `vendor_name`, `vendor_address`: Extracted vendor information
- `invoice_number`, `invoice_date`, `due_date`: Invoice metadata
- `subtotal`, `tax_amount`, `total_amount`: Financial amounts
- `line_items`: Array of line item objects
- `po_number`, `payment_terms`, `tax_id`: Additional fields

### Frontend Polling

The upload page polls for invoice status every second for up to 30 seconds:

```javascript
const pollInvoiceStatus = async (invoiceId, fileId) => {
  let attempts = 0;
  const maxAttempts = 30;
  
  const poll = async () => {
    const response = await invoicesApi.get(invoiceId);
    const invoice = response.data;
    
    // Update UI with invoice data
    setFiles(prev => prev.map(f => 
      f.id === fileId ? {
        ...f,
        invoiceData: invoice,
        status: invoice.status === 'extracted' ? 'extracted' : 'processing'
      } : f
    ));
    
    // Stop if extracted or continue polling
    if (invoice.status === 'extracted' || attempts >= maxAttempts) {
      return;
    }
    
    attempts++;
    setTimeout(poll, 1000);
  };
  
  poll();
};
```

## Configuration

### Environment Variables

**Backend (.env)**
```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:1234@localhost/invoices

# Redis (optional - uses in-memory fallback)
REDIS_URL=redis://localhost:6379

# Ollama AI
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:0.5b

# Tesseract OCR
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe

# Upload Settings
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=52428800  # 50MB
```

**Frontend (.env)**
```bash
VITE_API_BASE_URL=/api/v1
```

## Troubleshooting

### Issue: Invoices stuck in "processing" status

**Cause**: Message queue consumers not running or event handlers failed

**Solution**:
1. Check backend logs for errors
2. Ensure Redis is running (or in-memory queue is working)
3. Restart backend to reinitialize consumers
4. Check Tesseract OCR is installed and in PATH

### Issue: No extracted data showing

**Cause**: OCR failed or extraction patterns didn't match

**Solution**:
1. Check invoice file is readable (not corrupted)
2. Verify Tesseract can process the file format
3. Check backend logs for OCR/extraction errors
4. Try with a different invoice format

### Issue: Frontend not updating after upload

**Cause**: Polling timeout or API connection issue

**Solution**:
1. Check browser console for errors
2. Verify API endpoint is accessible
3. Increase polling timeout in Upload.jsx
4. Check CORS settings in backend

## Performance Optimization

### For Large Volume Processing

1. **Batch Upload**: Use the batch upload endpoint for multiple files
2. **Background Processing**: Event-driven architecture handles scale
3. **Database Indexing**: Ensure indexes on `status`, `created_at` columns
4. **Redis Caching**: Use Redis for message queue in production

### OCR Performance

- **PDF Processing**: ~2-5 seconds per page
- **Image Processing**: ~1-3 seconds per image
- **Concurrent Processing**: Multiple invoices processed in parallel via async

## API Endpoints

### Upload Invoice
```
POST /api/v1/invoices/upload
Content-Type: multipart/form-data

Request:
- file: invoice file (PDF/image)
- vendor_id: optional vendor ID
- notes: optional notes

Response:
{
  "document_id": "uuid",
  "invoice_id": "inv-xxxxx",
  "filename": "invoice.pdf",
  "status": "uploaded",
  "message": "Invoice uploaded successfully. Processing will begin shortly."
}
```

### Get Invoice
```
GET /api/v1/invoices/{invoice_id}

Response:
{
  "id": "inv-xxxxx",
  "status": "extracted",
  "vendor": {
    "name": "Acme Corp",
    "address": "123 Main St"
  },
  "invoice_number": "INV-2025-001",
  "invoice_date": "2025-01-15",
  "total_amount": 1250.00,
  ...
}
```

### List Invoices
```
GET /api/v1/invoices?status=extracted&limit=50

Response:
{
  "invoices": [...],
  "total": 42,
  "page": 1,
  "page_size": 50,
  "has_more": false
}
```

## Testing

### Manual Testing

1. Upload a sample invoice
2. Watch console logs in backend terminal
3. Check database for updated record:
   ```sql
   SELECT id, status, vendor_name, total_amount FROM invoices;
   ```
4. Verify frontend displays extracted data

### Sample Test Invoice

Create a simple test invoice with clear text:

```
INVOICE

From: Test Vendor Inc
      123 Test Street
      Test City, TS 12345

Invoice Number: INV-2025-TEST-001
Date: January 15, 2025
Due Date: February 15, 2025

Description         Quantity    Price      Total
Widget A            5           $100.00    $500.00
Widget B            3           $250.00    $750.00

                              Subtotal:    $1,250.00
                              Tax (10%):   $125.00
                              TOTAL:       $1,375.00
```

Save as PDF and upload to test the complete flow.

## Next Steps

1. **Approval Workflow**: Extracted invoices can be routed for approval
2. **Risk Scoring**: Anomaly detection on extracted data
3. **ERP Integration**: Sync extracted data to QuickBooks/Xero
4. **Payment Processing**: Initiate payments via Stripe
5. **Audit Trail**: Complete tracking of all processing steps

## Support

For issues or questions:
1. Check backend logs: `python -m uvicorn api-gateway.main:app --reload`
2. Check frontend console: Browser DevTools
3. Review documentation in `/docs` folder
4. Check API documentation: http://localhost:8000/docs
