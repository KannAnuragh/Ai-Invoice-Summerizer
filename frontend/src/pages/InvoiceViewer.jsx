import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { invoicesApi } from '../api/client';

const InvoiceViewer = () => {
  const { id } = useParams();
  const [invoice, setInvoice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchInvoice();
  }, [id]);

  const fetchInvoice = async () => {
    try {
      setLoading(true);
      const response = await invoicesApi.get(id);
      setInvoice(response.data);
      setError(null);
    } catch (err) {
      setError('Failed to load invoice');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-lg">Loading invoice...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-red-500">{error}</div>
      </div>
    );
  }

  if (!invoice) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div>Invoice not found</div>
      </div>
    );
  }

  const getRiskLevel = (score) => {
    if (!score) return { label: 'Unknown', color: 'var(--color-text-muted)', level: 'medium' };
    if (score < 0.3) return { label: 'Low Risk', color: 'var(--color-success)', level: 'high' };
    if (score < 0.6) return { label: 'Medium Risk', color: 'var(--color-warning)', level: 'medium' };
    return { label: 'High Risk', color: 'var(--color-error)', level: 'low' };
  };

  const riskInfo = getRiskLevel(invoice.risk_score);

  return (
    <div className="page">
      <div className="flex justify-between items-center" style={{ marginBottom: 'var(--space-6)' }}>
        <h1>Invoice Details</h1>
        <span className="badge" style={{ 
          background: `${riskInfo.color}20`, 
          color: riskInfo.color,
          fontSize: 'var(--font-size-sm)',
          padding: 'var(--space-2) var(--space-4)'
        }}>
          {riskInfo.label}
        </span>
      </div>
      
      <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
        <div className="grid grid-cols-2" style={{ marginBottom: 'var(--space-4)' }}>
          <div>
            <label style={{ fontWeight: 600, display: 'block', marginBottom: 'var(--space-1)', color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-xs)', textTransform: 'uppercase' }}>Invoice Number</label>
            <div style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600 }}>{invoice.invoice_number || 'N/A'}</div>
          </div>
          <div>
            <label style={{ fontWeight: 600, display: 'block', marginBottom: 'var(--space-1)', color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-xs)', textTransform: 'uppercase' }}>Status</label>
            <span className="badge" style={{ 
              background: `var(--color-${invoice.status === 'approved' ? 'success' : invoice.status === 'rejected' ? 'error' : 'warning'})20`,
              color: `var(--color-${invoice.status === 'approved' ? 'success' : invoice.status === 'rejected' ? 'error' : 'warning'})`,
              textTransform: 'capitalize'
            }}>
              {invoice.status}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-2" style={{ marginBottom: 'var(--space-4)' }}>
          <div>
            <label style={{ fontWeight: 600, display: 'block', marginBottom: 'var(--space-1)', color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-xs)', textTransform: 'uppercase' }}>Vendor</label>
            <div style={{ fontSize: 'var(--font-size-base)', fontWeight: 500 }}>{invoice.vendor?.name || 'N/A'}</div>
            {invoice.vendor?.address && (
              <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)', marginTop: 'var(--space-1)' }}>{invoice.vendor.address}</div>
            )}
          </div>
          <div>
            <label style={{ fontWeight: 600, display: 'block', marginBottom: 'var(--space-1)', color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-xs)', textTransform: 'uppercase' }}>Total Amount</label>
            <div style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 700, color: 'var(--color-success)' }}>
              ${invoice.total_amount?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}
            </div>
            {invoice.currency && invoice.currency !== 'USD' && (
              <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>{invoice.currency}</div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2" style={{ marginBottom: 'var(--space-4)' }}>
          <div>
            <label style={{ fontWeight: 600, display: 'block', marginBottom: 'var(--space-1)', color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-xs)', textTransform: 'uppercase' }}>Invoice Date</label>
            <div>{invoice.invoice_date ? new Date(invoice.invoice_date).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }) : 'N/A'}</div>
          </div>
          <div>
            <label style={{ fontWeight: 600, display: 'block', marginBottom: 'var(--space-1)', color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-xs)', textTransform: 'uppercase' }}>Due Date</label>
            <div>{invoice.due_date ? new Date(invoice.due_date).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }) : 'N/A'}</div>
          </div>
        </div>

        {(invoice.subtotal || invoice.tax_amount) && (
          <div className="grid grid-cols-2" style={{ marginBottom: 'var(--space-4)', paddingTop: 'var(--space-4)', borderTop: '1px solid var(--color-border)' }}>
            <div>
              <label style={{ fontWeight: 600, display: 'block', marginBottom: 'var(--space-1)', color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-xs)', textTransform: 'uppercase' }}>Subtotal</label>
              <div style={{ fontSize: 'var(--font-size-lg)' }}>${invoice.subtotal?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}</div>
            </div>
            <div>
              <label style={{ fontWeight: 600, display: 'block', marginBottom: 'var(--space-1)', color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-xs)', textTransform: 'uppercase' }}>Tax Amount</label>
              <div style={{ fontSize: 'var(--font-size-lg)' }}>${invoice.tax_amount?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}</div>
            </div>
          </div>
        )}

        {(invoice.risk_score !== null || (invoice.anomalies && invoice.anomalies.length > 0)) && (
          <div style={{ marginBottom: 'var(--space-4)', padding: 'var(--space-4)', background: 'var(--color-surface-elevated)', borderRadius: 'var(--radius-md)', borderLeft: `4px solid ${riskInfo.color}` }}>
            <div className="flex justify-between items-center" style={{ marginBottom: 'var(--space-3)' }}>
              <label style={{ fontWeight: 600, fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', textTransform: 'uppercase' }}>Risk Assessment</label>
              <div className="flex items-center gap-2">
                <div className="confidence-bar" style={{ width: 150 }}>
                  <div className="confidence-bar-track">
                    <div 
                      className={`confidence-bar-fill ${riskInfo.level}`}
                      style={{ width: `${(invoice.risk_score || 0) * 100}%`, background: riskInfo.color }}
                    ></div>
                  </div>
                  <span style={{ fontWeight: 600 }}>{((invoice.risk_score || 0) * 100).toFixed(0)}%</span>
                </div>
              </div>
            </div>
            {invoice.anomalies && invoice.anomalies.length > 0 && (
              <div>
                <div style={{ fontSize: 'var(--font-size-xs)', fontWeight: 600, color: 'var(--color-text-secondary)', marginBottom: 'var(--space-2)', textTransform: 'uppercase' }}>Detected Anomalies:</div>
                <ul style={{ margin: 0, paddingLeft: 'var(--space-5)', fontSize: 'var(--font-size-sm)' }}>
                  {invoice.anomalies.map((anomaly, idx) => (
                    <li key={idx} style={{ color: 'var(--color-warning)', marginBottom: 'var(--space-1)' }}>{anomaly}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {invoice.summary && (
          <div style={{ marginBottom: 'var(--space-4)' }}>
            <label style={{ fontWeight: 600, display: 'block', marginBottom: 'var(--space-2)', color: 'var(--color-text-secondary)' }}>AI Summary:</label>
            <div className="card" style={{ background: 'var(--color-bg)', padding: 'var(--space-4)' }}>{invoice.summary}</div>
          </div>
        )}

        {invoice.line_items && invoice.line_items.length > 0 && (
          <div style={{ paddingTop: 'var(--space-4)', borderTop: '1px solid var(--color-border)' }}>
            <label style={{ fontWeight: 600, display: 'block', marginBottom: 'var(--space-3)', color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-xs)', textTransform: 'uppercase' }}>Line Items ({invoice.line_items.length})</label>
            <div style={{ overflowX: 'auto' }}>
              <table className="table">
                <thead>
                  <tr>
                    <th style={{ width: '50%' }}>Description</th>
                    <th style={{ textAlign: 'right', width: '15%' }}>Quantity</th>
                    <th style={{ textAlign: 'right', width: '17.5%' }}>Unit Price</th>
                    <th style={{ textAlign: 'right', width: '17.5%' }}>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {invoice.line_items.map((item, index) => (
                    <tr key={index}>
                      <td>{item.description}</td>
                      <td style={{ textAlign: 'right' }}>{item.quantity}</td>
                      <td style={{ textAlign: 'right' }}>${item.unit_price?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                      <td style={{ textAlign: 'right', fontWeight: 600 }}>${item.total?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default InvoiceViewer;
