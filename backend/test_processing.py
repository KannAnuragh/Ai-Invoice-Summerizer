"""Test invoice processing pipeline"""
import asyncio
import sys
import os

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_invoice_processing():
    """Test the complete invoice processing pipeline"""
    print("=" * 60)
    print("TESTING INVOICE PROCESSING PIPELINE")
    print("=" * 60)
    
    # Test 1: Import invoice processor
    print("\n[1/5] Testing invoice processor import...")
    try:
        from services.invoice_processor import get_invoice_processor
        processor = get_invoice_processor()
        print("[OK] Invoice processor loaded successfully")
    except Exception as e:
        print(f"[FAIL] Failed to load processor: {e}")
        return
    
    # Test 2: Check OCR service
    print("\n[2/5] Testing OCR service...")
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ai-services', 'ocr-service'))
        from ocr_engine import get_ocr_engine
        ocr = get_ocr_engine()
        print(f"[OK] OCR engine loaded: {type(ocr).__name__}")
    except Exception as e:
        print(f"[WARN] OCR engine not available: {e}")
        print("  (Will use mock mode)")
    
    # Test 3: Check field extractor
    print("\n[3/5] Testing field extractor...")
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ai-services', 'extraction-service', 'field_extractors'))
        from extractors import FieldExtractor
        extractor = FieldExtractor()
        print("[OK] Field extractor loaded successfully")
    except Exception as e:
        print(f"[FAIL] Failed to load extractor: {e}")
        return
    
    # Test 4: Process a real uploaded invoice
    print("\n[4/5] Testing with real uploaded invoice...")
    test_file = r"C:\project\ai invoice summerizer\backend\uploads\2025\12\31\312a0fdb-576c-40b8-806f-7eb55f40cf88.jpg"
    test_invoice_id = "inv-6ca8da96"
    test_document_id = "312a0fdb-576c-40b8-806f-7eb55f40cf88"
    
    if os.path.exists(test_file):
        print(f"  File: {os.path.basename(test_file)}")
        print(f"  Size: {os.path.getsize(test_file)} bytes")
        print(f"  Invoice ID: {test_invoice_id}")
        print("\n  Processing invoice...")
        
        try:
            result = await processor.process_invoice(
                document_id=test_document_id,
                invoice_id=test_invoice_id,
                file_path=test_file,
                filename="test-invoice.jpg",
                correlation_id=test_document_id
            )
            
            print("\n[OK] Processing completed successfully!")
            print(f"\n  Extracted Data:")
            print(f"    Vendor: {result.get('vendor_name', 'N/A')}")
            print(f"    Invoice #: {result.get('invoice_number', 'N/A')}")
            print(f"    Total: ${result.get('total_amount', 0.0)}")
            print(f"    Date: {result.get('invoice_date', 'N/A')}")
            print(f"    Currency: {result.get('currency', 'N/A')}")
            print(f"    Confidence: {result.get('ocr_confidence', 0.0):.2%}")
            
        except Exception as e:
            print(f"\n[FAIL] Processing failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"  [FAIL] File not found: {test_file}")
    
    # Test 5: Check database update
    print("\n[5/5] Checking database update...")
    try:
        from shared.database import get_async_session
        from shared.db_models import Invoice as DBInvoice
        from sqlalchemy import select
        
        async with get_async_session() as db:
            query = select(DBInvoice).where(DBInvoice.id == test_invoice_id)
            result = await db.execute(query)
            invoice = result.scalar_one_or_none()
            
            if invoice:
                print(f"[OK] Invoice found in database")
                print(f"  Status: {invoice.status.value if hasattr(invoice.status, 'value') else invoice.status}")
                print(f"  Vendor: {invoice.vendor_name or 'Not extracted'}")
                print(f"  Total: ${invoice.total_amount or 0.0}")
            else:
                print(f"[FAIL] Invoice not found in database")
    except Exception as e:
        print(f"[WARN] Database check failed: {e}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_invoice_processing())
