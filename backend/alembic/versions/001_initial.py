"""Initial migration

Revision ID: 001_initial
Revises: 
Create Date: 2025-12-29 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE invoicestatus AS ENUM ('uploaded', 'processing', 'extracted', 'validated', 'review_pending', 'pending', 'review', 'approved', 'rejected', 'paid', 'archived')")
    op.execute("CREATE TYPE approvalstatus AS ENUM ('pending', 'approved', 'rejected', 'escalated', 'expired')")
    
    # Vendors table
    op.create_table('vendors',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('tax_id', sa.String(length=50), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('payment_terms', sa.String(length=50), nullable=True, server_default='NET30'),
        sa.Column('currency', sa.String(length=3), nullable=True, server_default='USD'),
        sa.Column('risk_level', sa.String(length=20), nullable=True, server_default='normal'),
        sa.Column('auto_approve_threshold', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('default_gl_code', sa.String(length=50), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('is_verified', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('total_invoices', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_amount', sa.Numeric(precision=15, scale=2), nullable=True, server_default='0'),
        sa.Column('average_amount', sa.Numeric(precision=12, scale=2), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_vendors_name'), 'vendors', ['name'], unique=False)
    
    # Invoices table
    op.create_table('invoices',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('document_id', sa.String(length=50), nullable=True),
        sa.Column('status', postgresql.ENUM('uploaded', 'processing', 'extracted', 'validated', 'review_pending', 'pending', 'review', 'approved', 'rejected', 'paid', 'archived', name='invoicestatus'), nullable=True),
        sa.Column('vendor_id', sa.String(length=50), nullable=True),
        sa.Column('vendor_name', sa.String(length=255), nullable=True),
        sa.Column('vendor_address', sa.Text(), nullable=True),
        sa.Column('vendor_confidence', sa.Float(), nullable=True),
        sa.Column('invoice_number', sa.String(length=100), nullable=True),
        sa.Column('invoice_number_confidence', sa.Float(), nullable=True),
        sa.Column('invoice_date', sa.DateTime(), nullable=True),
        sa.Column('date_confidence', sa.Float(), nullable=True),
        sa.Column('due_date', sa.DateTime(), nullable=True),
        sa.Column('due_date_confidence', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=True, server_default='USD'),
        sa.Column('subtotal', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('tax_amount', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('total_amount', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('amount_confidence', sa.Float(), nullable=True),
        sa.Column('line_items', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('po_number', sa.String(length=100), nullable=True),
        sa.Column('payment_terms', sa.String(length=100), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('risk_score', sa.Float(), nullable=True),
        sa.Column('anomalies', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('source_filename', sa.String(length=255), nullable=True),
        sa.Column('source_size', sa.Integer(), nullable=True),
        sa.Column('file_hash', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('updated_by', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id')
    )
    op.create_index(op.f('ix_invoices_created_at'), 'invoices', ['created_at'], unique=False)
    op.create_index(op.f('ix_invoices_document_id'), 'invoices', ['document_id'], unique=False)
    op.create_index(op.f('ix_invoices_file_hash'), 'invoices', ['file_hash'], unique=False)
    op.create_index(op.f('ix_invoices_invoice_number'), 'invoices', ['invoice_number'], unique=False)
    op.create_index(op.f('ix_invoices_risk_score'), 'invoices', ['risk_score'], unique=False)
    op.create_index(op.f('ix_invoices_status'), 'invoices', ['status'], unique=False)
    op.create_index(op.f('ix_invoices_total_amount'), 'invoices', ['total_amount'], unique=False)
    op.create_index(op.f('ix_invoices_vendor_id'), 'invoices', ['vendor_id'], unique=False)
    op.create_index('idx_invoice_status_created', 'invoices', ['status', 'created_at'], unique=False)
    op.create_index('idx_invoice_vendor_date', 'invoices', ['vendor_id', 'invoice_date'], unique=False)
    
    # Approval tasks table
    op.create_table('approval_tasks',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('invoice_id', sa.String(length=50), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'approved', 'rejected', 'escalated', 'expired', name='approvalstatus'), nullable=True),
        sa.Column('priority', sa.String(length=20), nullable=True, server_default='normal'),
        sa.Column('assigned_to', sa.String(length=100), nullable=True),
        sa.Column('assigned_role', sa.String(length=50), nullable=True),
        sa.Column('due_date', sa.DateTime(), nullable=True),
        sa.Column('sla_status', sa.String(length=20), nullable=True, server_default='on_track'),
        sa.Column('action_taken', sa.String(length=50), nullable=True),
        sa.Column('approved_by', sa.String(length=100), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('delegated_to', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_approval_assigned', 'approval_tasks', ['assigned_to', 'status'], unique=False)
    op.create_index('idx_approval_status_due', 'approval_tasks', ['status', 'due_date'], unique=False)
    op.create_index(op.f('ix_approval_tasks_assigned_to'), 'approval_tasks', ['assigned_to'], unique=False)
    op.create_index(op.f('ix_approval_tasks_due_date'), 'approval_tasks', ['due_date'], unique=False)
    op.create_index(op.f('ix_approval_tasks_invoice_id'), 'approval_tasks', ['invoice_id'], unique=False)
    op.create_index(op.f('ix_approval_tasks_priority'), 'approval_tasks', ['priority'], unique=False)
    op.create_index(op.f('ix_approval_tasks_status'), 'approval_tasks', ['status'], unique=False)
    
    # Users table
    op.create_table('users',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('department', sa.String(length=100), nullable=True),
        sa.Column('approval_limit', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('google_id', sa.String(length=255), nullable=True),
        sa.Column('picture_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('google_id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=False)
    op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)
    
    # Approval rules table
    op.create_table('approval_rules',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('conditions', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('actions', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # System config table
    op.create_table('system_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ocr_confidence_threshold', sa.Float(), nullable=True, server_default='0.85'),
        sa.Column('auto_approve_enabled', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('auto_approve_max_amount', sa.Numeric(precision=12, scale=2), nullable=True, server_default='1000.0'),
        sa.Column('duplicate_detection_enabled', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('duplicate_hash_window_days', sa.Integer(), nullable=True, server_default='90'),
        sa.Column('sla_warning_hours', sa.Integer(), nullable=True, server_default='24'),
        sa.Column('sla_breach_hours', sa.Integer(), nullable=True, server_default='48'),
        sa.Column('summary_language', sa.String(length=10), nullable=True, server_default='en'),
        sa.Column('retention_days', sa.Integer(), nullable=True, server_default='2555'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Audit logs table
    op.create_table('audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=True),
        sa.Column('entity_id', sa.String(length=50), nullable=True),
        sa.Column('user_id', sa.String(length=100), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', sa.String(length=50), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_audit_entity', 'audit_logs', ['entity_type', 'entity_id'], unique=False)
    op.create_index('idx_audit_user_time', 'audit_logs', ['user_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_audit_logs_entity_id'), 'audit_logs', ['entity_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_event_type'), 'audit_logs', ['event_type'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index(op.f('ix_audit_logs_event_type'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_entity_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_created_at'), table_name='audit_logs')
    op.drop_index('idx_audit_user_time', table_name='audit_logs')
    op.drop_index('idx_audit_entity', table_name='audit_logs')
    op.drop_table('audit_logs')
    
    op.drop_table('system_config')
    op.drop_table('approval_rules')
    
    op.drop_index(op.f('ix_users_role'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    
    op.drop_index(op.f('ix_approval_tasks_status'), table_name='approval_tasks')
    op.drop_index(op.f('ix_approval_tasks_priority'), table_name='approval_tasks')
    op.drop_index(op.f('ix_approval_tasks_invoice_id'), table_name='approval_tasks')
    op.drop_index(op.f('ix_approval_tasks_due_date'), table_name='approval_tasks')
    op.drop_index(op.f('ix_approval_tasks_assigned_to'), table_name='approval_tasks')
    op.drop_index('idx_approval_status_due', table_name='approval_tasks')
    op.drop_index('idx_approval_assigned', table_name='approval_tasks')
    op.drop_table('approval_tasks')
    
    op.drop_index('idx_invoice_vendor_date', table_name='invoices')
    op.drop_index('idx_invoice_status_created', table_name='invoices')
    op.drop_index(op.f('ix_invoices_vendor_id'), table_name='invoices')
    op.drop_index(op.f('ix_invoices_total_amount'), table_name='invoices')
    op.drop_index(op.f('ix_invoices_status'), table_name='invoices')
    op.drop_index(op.f('ix_invoices_risk_score'), table_name='invoices')
    op.drop_index(op.f('ix_invoices_invoice_number'), table_name='invoices')
    op.drop_index(op.f('ix_invoices_file_hash'), table_name='invoices')
    op.drop_index(op.f('ix_invoices_document_id'), table_name='invoices')
    op.drop_index(op.f('ix_invoices_created_at'), table_name='invoices')
    op.drop_table('invoices')
    
    op.drop_index(op.f('ix_vendors_name'), table_name='vendors')
    op.drop_table('vendors')
    
    # Drop enum types
    op.execute("DROP TYPE approvalstatus")
    op.execute("DROP TYPE invoicestatus")
