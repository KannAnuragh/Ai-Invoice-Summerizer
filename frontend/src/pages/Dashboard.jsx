import React, { useState, useCallback } from 'react';
import { DollarSign, FileText, Clock, AlertTriangle, Upload } from '../components/icons';
import { useInvoices, useApprovalStats, useUploadInvoice, useHealthCheck } from '../api/hooks';
import { Link } from 'react-router-dom';

const statusColors = {
  pending: 'var(--color-warning)',
  approved: 'var(--color-success)',
  review: 'var(--color-info)',
  processing: 'var(--color-info)',
  paid: 'var(--color-text-muted)',
  rejected: 'var(--color-error)',
  uploaded: 'var(--color-primary)',
};

function StatCard({ label, value, change, icon: Icon, color, isLoading }) {
  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <div>
          <p style={{ 
            fontSize: 'var(--font-size-sm)', 
            color: 'var(--color-text-secondary)',
            marginBottom: 'var(--space-1)'
          }}>
            {label}
          </p>
          {isLoading ? (
            <div className="skeleton" style={{ height: 32, width: 60 }} />
          ) : (
            <p style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 700 }}>
              {value}
            </p>
          )}
          {change && (
            <p style={{ 
              fontSize: 'var(--font-size-xs)', 
              color: change.startsWith('+') ? 'var(--color-success)' : 'var(--color-text-muted)'
            }}>
              {change} from last month
            </p>
          )}
        </div>
        <div style={{
          width: 48,
          height: 48,
          borderRadius: 'var(--radius-lg)',
          background: `${color}20`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: color,
        }}>
          <Icon size={24} />
        </div>
      </div>
    </div>
  );
}

function UploadModal({ isOpen, onClose }) {
  const [dragOver, setDragOver] = useState(false);
  const uploadMutation = useUploadInvoice();

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    
    const files = Array.from(e.dataTransfer?.files || e.target.files || []);
    if (files.length > 0) {
      files.forEach(file => {
        uploadMutation.mutate({ file, options: {} });
      });
      onClose();
    }
  }, [uploadMutation, onClose]);

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'rgba(0,0,0,0.7)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
    }} onClick={onClose}>
      <div 
        className="card" 
        style={{ width: 500, padding: 'var(--space-6)' }}
        onClick={e => e.stopPropagation()}
      >
        <h2 style={{ marginBottom: 'var(--space-4)' }}>Upload Invoice</h2>
        
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={() => setDragOver(false)}
          style={{
            border: `2px dashed ${dragOver ? 'var(--color-primary)' : 'var(--color-border)'}`,
            borderRadius: 'var(--radius-lg)',
            padding: 'var(--space-8)',
            textAlign: 'center',
            background: dragOver ? 'var(--color-primary-light)' : 'var(--color-bg)',
            transition: 'all var(--transition-fast)',
            cursor: 'pointer',
          }}
        >
          <Upload size={48} style={{ color: 'var(--color-text-muted)', marginBottom: 'var(--space-4)' }} />
          <p style={{ marginBottom: 'var(--space-2)' }}>
            Drag & drop invoice files here
          </p>
          <p style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)' }}>
            Supports PDF, PNG, JPG (max 50MB)
          </p>
          <input
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.tiff"
            multiple
            onChange={handleDrop}
            style={{ display: 'none' }}
            id="file-input"
          />
          <label htmlFor="file-input" className="btn btn-secondary" style={{ marginTop: 'var(--space-4)' }}>
            Browse Files
          </label>
        </div>

        <div className="flex gap-2" style={{ marginTop: 'var(--space-4)', justifyContent: 'flex-end' }}>
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [uploadOpen, setUploadOpen] = useState(false);
  
  // API hooks
  const { data: healthData } = useHealthCheck();
  const { data: invoicesData, isLoading: invoicesLoading } = useInvoices({ limit: 5 });
  const { data: approvalStats, isLoading: statsLoading } = useApprovalStats();

  const invoices = invoicesData?.invoices || [];
  const totalInvoices = invoicesData?.total || 0;
  
  const stats = [
    { 
      label: 'Total Invoices', 
      value: totalInvoices.toString(), 
      icon: FileText, 
      color: 'var(--color-primary)' 
    },
    { 
      label: 'Pending Review', 
      value: approvalStats?.pending?.toString() || '0', 
      icon: Clock, 
      color: 'var(--color-warning)' 
    },
    { 
      label: 'Total Amount', 
      value: `$${((approvalStats?.total_amount || 0) / 1000).toFixed(1)}K`, 
      icon: DollarSign, 
      color: 'var(--color-success)' 
    },
    { 
      label: 'Anomalies', 
      value: approvalStats?.high_risk?.toString() || '0', 
      icon: AlertTriangle, 
      color: 'var(--color-error)' 
    },
  ];

  return (
    <div>
      <div className="flex justify-between items-center" style={{ marginBottom: 'var(--space-6)' }}>
        <div>
          <h1 style={{ marginBottom: 'var(--space-2)' }}>Dashboard</h1>
          <p style={{ color: 'var(--color-text-secondary)' }}>
            Overview of your invoice processing pipeline
            {healthData && (
              <span className="status-indicator" style={{ marginLeft: 'var(--space-2)' }}>
                <span className="status-dot success" />
                API Connected
              </span>
            )}
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setUploadOpen(true)}>
          <Upload size={16} />
          Upload Invoice
        </button>
      </div>

      {/* Stats Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
        gap: 'var(--space-4)',
        marginBottom: 'var(--space-6)',
      }}>
        {stats.map((stat) => (
          <StatCard 
            key={stat.label} 
            {...stat} 
            isLoading={invoicesLoading || statsLoading}
          />
        ))}
      </div>

      {/* Recent Invoices */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Recent Invoices</h3>
          <Link to="/invoices" className="btn btn-secondary">View All</Link>
        </div>
        
        {invoicesLoading ? (
          <div style={{ padding: 'var(--space-4)' }}>
            {[1, 2, 3].map(i => (
              <div key={i} className="skeleton" style={{ height: 48, marginBottom: 'var(--space-2)' }} />
            ))}
          </div>
        ) : invoices.length === 0 ? (
          <div style={{ 
            padding: 'var(--space-8)', 
            textAlign: 'center',
            color: 'var(--color-text-muted)'
          }}>
            <FileText size={48} style={{ marginBottom: 'var(--space-4)', opacity: 0.5 }} />
            <p>No invoices yet</p>
            <button 
              className="btn btn-primary" 
              style={{ marginTop: 'var(--space-4)' }}
              onClick={() => setUploadOpen(true)}
            >
              Upload your first invoice
            </button>
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Invoice</th>
                <th>Vendor</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((invoice) => (
                <tr key={invoice.id} style={{ cursor: 'pointer' }}>
                  <td>
                    <Link 
                      to={`/invoices/${invoice.id}`}
                      style={{ fontWeight: 500, color: 'var(--color-primary)' }}
                    >
                      {invoice.invoice_number || invoice.id}
                    </Link>
                  </td>
                  <td>{invoice.vendor?.name || 'Unknown'}</td>
                  <td>${(invoice.total_amount || 0).toLocaleString()}</td>
                  <td>
                    <span 
                      className="badge"
                      style={{ 
                        background: `${statusColors[invoice.status] || statusColors.pending}20`,
                        color: statusColors[invoice.status] || statusColors.pending,
                      }}
                    >
                      {invoice.status}
                    </span>
                  </td>
                  <td style={{ color: 'var(--color-text-secondary)' }}>
                    {invoice.created_at ? new Date(invoice.created_at).toLocaleDateString() : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <UploadModal isOpen={uploadOpen} onClose={() => setUploadOpen(false)} />
    </div>
  );
}
