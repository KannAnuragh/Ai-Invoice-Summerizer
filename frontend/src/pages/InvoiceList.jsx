import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Eye, Edit, Check, X, Upload } from '../components/icons';
import { useInvoices, useApproveInvoice, useRejectInvoice } from '../api/hooks';

const statusColors = {
  pending: 'var(--color-warning)',
  approved: 'var(--color-success)',
  review: 'var(--color-info)',
  processing: 'var(--color-info)',
  paid: 'var(--color-text-muted)',
  rejected: 'var(--color-error)',
  uploaded: 'var(--color-primary)',
  extracted: 'var(--color-info)',
  validated: 'var(--color-success)',
};

const riskColors = {
  low: 'var(--color-success)',
  medium: 'var(--color-warning)',
  high: 'var(--color-error)',
};

function ConfidenceBar({ value }) {
  const numValue = typeof value === 'number' ? value : 0.5;
  const level = numValue >= 0.8 ? 'high' : numValue >= 0.6 ? 'medium' : 'low';
  
  return (
    <div className="confidence-bar">
      <div className="confidence-bar-track">
        <div 
          className={`confidence-bar-fill ${level}`}
          style={{ width: `${numValue * 100}%` }}
        />
      </div>
      <span style={{ fontSize: 'var(--font-size-xs)', minWidth: 40 }}>
        {(numValue * 100).toFixed(0)}%
      </span>
    </div>
  );
}

export default function InvoiceList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState(searchParams.get('search') || '');
  const [statusFilter, setStatusFilter] = useState(searchParams.get('status') || '');
  
  const { data, isLoading, error } = useInvoices({
    search: search || undefined,
    status: statusFilter || undefined,
    limit: 50,
  });
  
  const approveMutation = useApproveInvoice();
  const rejectMutation = useRejectInvoice();
  
  const invoices = data?.invoices || [];
  const total = data?.total || 0;

  const handleSearch = (e) => {
    e.preventDefault();
    setSearchParams({ search, status: statusFilter });
  };

  const handleApprove = (invoiceId) => {
    approveMutation.mutate({ taskId: invoiceId, comment: 'Approved from list view' });
  };

  const handleReject = (invoiceId) => {
    rejectMutation.mutate({ taskId: invoiceId, comment: 'Rejected from list view' });
  };

  return (
    <div>
      <div className="flex justify-between items-center" style={{ marginBottom: 'var(--space-6)' }}>
        <div>
          <h1 style={{ marginBottom: 'var(--space-2)' }}>Invoices</h1>
          <p style={{ color: 'var(--color-text-secondary)' }}>
            {isLoading ? 'Loading...' : `${total} invoice${total !== 1 ? 's' : ''} total`}
          </p>
        </div>
        <form onSubmit={handleSearch} className="flex gap-2">
          <input 
            type="text" 
            className="input" 
            placeholder="Search invoices..." 
            style={{ width: 280 }}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select 
            className="input" 
            style={{ width: 150 }}
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setSearchParams({ search, status: e.target.value });
            }}
          >
            <option value="">All Status</option>
            <option value="uploaded">Uploaded</option>
            <option value="processing">Processing</option>
            <option value="pending">Pending</option>
            <option value="review">Review</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="paid">Paid</option>
          </select>
        </form>
      </div>

      {error && (
        <div className="card" style={{ 
          background: 'var(--color-error-light)', 
          borderColor: 'var(--color-error)',
          marginBottom: 'var(--space-4)'
        }}>
          <p style={{ color: 'var(--color-error)' }}>
            Error loading invoices: {error.message}
          </p>
        </div>
      )}

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {isLoading ? (
          <div style={{ padding: 'var(--space-4)' }}>
            {[1, 2, 3, 4, 5].map(i => (
              <div key={i} className="skeleton" style={{ height: 52, marginBottom: 'var(--space-2)' }} />
            ))}
          </div>
        ) : invoices.length === 0 ? (
          <div style={{ 
            padding: 'var(--space-8)', 
            textAlign: 'center',
            color: 'var(--color-text-muted)'
          }}>
            <Upload size={48} style={{ marginBottom: 'var(--space-4)', opacity: 0.5 }} />
            <p>No invoices found</p>
            <p style={{ fontSize: 'var(--font-size-sm)', marginTop: 'var(--space-2)' }}>
              {search || statusFilter ? 'Try adjusting your filters' : 'Upload your first invoice to get started'}
            </p>
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Invoice</th>
                <th>Vendor</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Confidence</th>
                <th>Risk</th>
                <th>Date</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((invoice) => {
                const riskLevel = invoice.risk_score > 0.6 ? 'high' : invoice.risk_score > 0.3 ? 'medium' : 'low';
                
                return (
                  <tr key={invoice.id}>
                    <td>
                      <Link 
                        to={`/invoices/${invoice.id}`}
                        style={{ fontWeight: 500, color: 'var(--color-primary)' }}
                      >
                        {invoice.invoice_number || invoice.id.substring(0, 12)}
                      </Link>
                    </td>
                    <td>{invoice.vendor?.name || 'Unknown'}</td>
                    <td style={{ fontWeight: 500 }}>
                      ${(invoice.total_amount || 0).toLocaleString()}
                    </td>
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
                    <td style={{ minWidth: 120 }}>
                      <ConfidenceBar value={invoice.confidence || 0.85} />
                    </td>
                    <td>
                      <span 
                        className="status-indicator"
                        style={{ color: riskColors[riskLevel] }}
                      >
                        <span className={`status-dot ${riskLevel === 'high' ? 'error' : riskLevel === 'medium' ? 'warning' : 'success'}`} />
                        {riskLevel}
                      </span>
                    </td>
                    <td style={{ color: 'var(--color-text-secondary)' }}>
                      {invoice.created_at ? new Date(invoice.created_at).toLocaleDateString() : '-'}
                    </td>
                    <td>
                      <div className="flex gap-2">
                        <Link 
                          to={`/invoices/${invoice.id}`}
                          className="btn btn-secondary"
                          style={{ padding: 'var(--space-1)' }}
                        >
                          <Eye size={16} />
                        </Link>
                        {['pending', 'review'].includes(invoice.status) && (
                          <>
                            <button 
                              className="btn btn-success" 
                              style={{ padding: 'var(--space-1)' }}
                              onClick={() => handleApprove(invoice.id)}
                              disabled={approveMutation.isPending}
                            >
                              <Check size={16} />
                            </button>
                            <button 
                              className="btn btn-danger" 
                              style={{ padding: 'var(--space-1)' }}
                              onClick={() => handleReject(invoice.id)}
                              disabled={rejectMutation.isPending}
                            >
                              <X size={16} />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
