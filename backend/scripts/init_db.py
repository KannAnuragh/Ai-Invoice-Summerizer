"""
Database Initialization Script
===============================
Creates tables and loads demo data.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from decimal import Decimal

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import engine, async_session_maker
from shared.db_models import (
    Base,
    Vendor,
    Invoice,
    InvoiceStatus,
    ApprovalTask,
    ApprovalStatus,
    User,
    SystemConfig,
)


async def init_database():
    """Create all database tables."""
    print("Creating database tables...")
    async with engine.begin() as conn:
        # Drop all tables (for clean start)
        await conn.run_sync(Base.metadata.drop_all)
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    print("✓ Database tables created successfully")


async def load_demo_data():
    """Load demo vendors, invoices, and approval tasks."""
    print("\nLoading demo data...")
    
    async with async_session_maker() as session:
        # Create demo vendors
        vendors = [
            Vendor(
                id="v-001",
                name="Acme Corporation",
                tax_id="12-3456789",
                address="123 Business Ave, San Francisco, CA 94102",
                email="billing@acme.com",
                phone="415-555-0100",
                payment_terms="NET30",
                currency="USD",
                risk_level="low",
                is_verified=True,
                total_invoices=12,
                total_amount=Decimal("150000.00"),
                average_amount=Decimal("12500.00"),
            ),
            Vendor(
                id="v-002",
                name="CloudServices Ltd",
                tax_id="98-7654321",
                address="456 Tech Park, Seattle, WA 98101",
                email="invoices@cloudservices.com",
                payment_terms="NET30",
                currency="USD",
                risk_level="normal",
                is_verified=True,
                total_invoices=8,
                total_amount=Decimal("96000.00"),
                average_amount=Decimal("12000.00"),
            ),
            Vendor(
                id="v-003",
                name="Office Depot",
                tax_id="45-6789012",
                address="789 Supply St, New York, NY 10001",
                payment_terms="NET30",
                currency="USD",
                risk_level="low",
                is_verified=True,
                total_invoices=25,
                total_amount=Decimal("52500.00"),
                average_amount=Decimal("2100.00"),
            ),
        ]
        
        for vendor in vendors:
            session.add(vendor)
        
        print(f"✓ Created {len(vendors)} vendors")
        
        # Create demo invoices
        now = datetime.utcnow()
        
        invoices = [
            Invoice(
                id="inv-001",
                document_id="doc-001",
                status=InvoiceStatus.PENDING,
                vendor_id="v-001",
                vendor_name="Acme Corporation",
                vendor_confidence=0.95,
                invoice_number="INV-2024-0247",
                invoice_number_confidence=0.98,
                invoice_date=now - timedelta(days=2),
                date_confidence=0.92,
                due_date=now + timedelta(days=28),
                due_date_confidence=0.88,
                currency="USD",
                subtotal=Decimal("10500.00"),
                tax_amount=Decimal("2000.00"),
                total_amount=Decimal("12500.00"),
                amount_confidence=0.96,
                line_items=[
                    {"description": "Software License - Enterprise", "quantity": 1, "unit_price": 8000, "total": 8000},
                    {"description": "Implementation Services", "quantity": 10, "unit_price": 150, "total": 1500},
                    {"description": "Training (per hour)", "quantity": 5, "unit_price": 200, "total": 1000},
                ],
                payment_terms="NET30",
                confidence=0.92,
                risk_score=0.15,
                anomalies=[],
                summary="Invoice from Acme Corporation for software licensing and implementation services.",
            ),
            Invoice(
                id="inv-002",
                document_id="doc-002",
                status=InvoiceStatus.REVIEW,
                vendor_id="v-002",
                vendor_name="CloudServices Ltd",
                vendor_confidence=0.72,
                invoice_number="INV-2024-0244",
                invoice_number_confidence=0.88,
                invoice_date=now - timedelta(days=4),
                date_confidence=0.85,
                due_date=now + timedelta(days=26),
                due_date_confidence=0.80,
                currency="USD",
                subtotal=Decimal("13500.00"),
                tax_amount=Decimal("1500.00"),
                total_amount=Decimal("15000.00"),
                amount_confidence=0.90,
                line_items=[
                    {"description": "Cloud Hosting (Monthly)", "quantity": 1, "unit_price": 12000, "total": 12000},
                    {"description": "Support Premium", "quantity": 1, "unit_price": 1500, "total": 1500},
                ],
                payment_terms="NET30",
                confidence=0.72,
                risk_score=0.45,
                anomalies=["Amount 50% higher than historical average"],
                summary="Cloud hosting invoice requires review due to amount deviation.",
            ),
            Invoice(
                id="inv-003",
                document_id="doc-003",
                status=InvoiceStatus.APPROVED,
                vendor_id="v-003",
                vendor_name="Office Depot",
                vendor_confidence=0.98,
                invoice_number="INV-2024-0245",
                invoice_number_confidence=0.99,
                invoice_date=now - timedelta(days=3),
                date_confidence=0.95,
                due_date=now + timedelta(days=27),
                due_date_confidence=0.95,
                currency="USD",
                subtotal=Decimal("2100.00"),
                tax_amount=Decimal("240.00"),
                total_amount=Decimal("2340.00"),
                amount_confidence=0.98,
                line_items=[
                    {"description": "Office Supplies", "quantity": 1, "unit_price": 1200, "total": 1200},
                    {"description": "Printer Cartridges", "quantity": 3, "unit_price": 300, "total": 900},
                ],
                payment_terms="NET30",
                confidence=0.95,
                risk_score=0.08,
                anomalies=[],
                summary="Standard office supplies order from verified vendor.",
            ),
        ]
        
        for invoice in invoices:
            session.add(invoice)
        
        print(f"✓ Created {len(invoices)} invoices")
        
        # Create approval tasks
        approval_tasks = [
            ApprovalTask(
                id="apr-001",
                invoice_id="inv-001",
                status=ApprovalStatus.PENDING,
                priority="normal",
                assigned_to="finance_manager",
                due_date=now + timedelta(days=2),
                sla_status="on_track",
            ),
            ApprovalTask(
                id="apr-002",
                invoice_id="inv-002",
                status=ApprovalStatus.PENDING,
                priority="high",
                assigned_to="finance_manager",
                due_date=now + timedelta(hours=4),
                sla_status="warning",
            ),
        ]
        
        for task in approval_tasks:
            session.add(task)
        
        print(f"✓ Created {len(approval_tasks)} approval tasks")
        
        # Create system config
        config = SystemConfig(
            id=1,
            ocr_confidence_threshold=0.85,
            auto_approve_enabled=False,
            auto_approve_max_amount=Decimal("1000.00"),
            duplicate_detection_enabled=True,
            duplicate_hash_window_days=90,
            sla_warning_hours=24,
            sla_breach_hours=48,
            summary_language="en",
            retention_days=2555,
        )
        session.add(config)
        
        print("✓ Created system configuration")
        
        # Create demo user
        user = User(
            id="user-001",
            email="admin@company.com",
            name="Admin User",
            role="admin",
            department="Finance",
            approval_limit=Decimal("100000.00"),
            active=True,
        )
        session.add(user)
        
        print("✓ Created demo user")
        
        await session.commit()
        print("\n✅ Demo data loaded successfully!")


async def main():
    """Main initialization function."""
    print("=" * 60)
    print("AI Invoice Summarizer - Database Initialization")
    print("=" * 60)
    
    try:
        await init_database()
        await load_demo_data()
        
        print("\n" + "=" * 60)
        print("✅ Database initialization complete!")
        print("=" * 60)
        print("\nYou can now start the API server with:")
        print("  cd backend/api-gateway")
        print("  uvicorn main:app --reload --port 8000")
        
    except Exception as e:
        print(f"\n❌ Error during initialization: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
