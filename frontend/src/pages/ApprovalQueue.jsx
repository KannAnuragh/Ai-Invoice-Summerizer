import React from 'react';
import { Link } from 'react-router-dom';
import { Check, X, Clock, AlertTriangle } from '../components/icons';
import { useApprovalQueue, useApprovalStats, useApproveInvoice, useRejectInvoice } from '../api/hooks';

const priorityColors = {
  normal: 'var(--color-text-muted)',
  high: 'var(--color-warning)',
  urgent: 'var(--color-error)',
};

const slaColors = {
  on_track: 'var(--color-success)',
  warning: 'var(--color-warning)',
  breached: 'var(--color-error)',
};

export default function ApprovalQueue() {
  const { data: queueData, isLoading, error } = useApprovalQueue();
  const { data: stats, isLoading: statsLoading } = useApprovalStats();
  const approveMutation = useApproveInvoice();
  const rejectMutation = useRejectInvoice();

  const approvals = queueData?.tasks || [];

  const handleApprove = (taskId) => {
    approveMutation.mutate({ taskId, comment: 'Approved from queue' });
  };

  const handleReject = (taskId) => {
    const reason = prompt('Enter rejection reason:');
    if (reason) {
      rejectMutation.mutate({ taskId, comment: reason });
    }
  };

  return (
    <div>
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <h1 style={{ marginBottom: 'var(--space-2)' }}>Approval Queue</h1>
        <p style={{ color: 'var(--color-text-secondary)' }}>
          Invoices awaiting your review and approval
        </p>
      </div>

      {/* Stats */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(3, 1fr)', 
        gap: 'var(--space-4)',
        marginBottom: 'var(--space-6)'
      }}>
        <div className="card" style={{ textAlign: 'center' }}>
          {statsLoading ? (
            <div className="skeleton" style={{ height: 48, margin: '0 auto', width: 60 }} />
          ) : (
            <>
              <p style={{ fontSize: 'var(--font-size-3xl)', fontWeight: 700 }}>
                {stats?.pending || approvals.length}
              </p>
              <p style={{ color: 'var(--color-text-secondary)' }}>Pending</p>
            </>
          )}
        </div>
        <div className="card" style={{ textAlign: 'center' }}>
          {statsLoading ? (
            <div className="skeleton" style={{ height: 48, margin: '0 auto', width: 60 }} />
          ) : (
            <>
              <p style={{ fontSize: 'var(--font-size-3xl)', fontWeight: 700, color: 'var(--color-warning)' }}>
                {stats?.warning || 0}
              </p>
              <p style={{ color: 'var(--color-text-secondary)' }}>SLA Warning</p>
            </>
          )}
        </div>
        <div className="card" style={{ textAlign: 'center' }}>
          {statsLoading ? (
            <div className="skeleton" style={{ height: 48, margin: '0 auto', width: 60 }} />
          ) : (
            <>
              <p style={{ fontSize: 'var(--font-size-3xl)', fontWeight: 700, color: 'var(--color-error)' }}>
                {stats?.breached || 0}
              </p>
              <p style={{ color: 'var(--color-text-secondary)' }}>Breached</p>
            </>
          )}
        </div>
      </div>

      {error && (
        <div className="card" style={{ 
          background: 'var(--color-error-light)', 
          borderColor: 'var(--color-error)',
          marginBottom: 'var(--space-4)'
        }}>
          <p style={{ color: 'var(--color-error)' }}>
            Error loading queue: {error.message}
          </p>
        </div>
      )}

      {/* Queue */}
      {isLoading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          {[1, 2, 3].map(i => (
            <div key={i} className="skeleton" style={{ height: 120 }} />
          ))}
        </div>
      ) : approvals.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
          <Check size={48} style={{ color: 'var(--color-success)', marginBottom: 'var(--space-4)' }} />
          <h2>All caught up!</h2>
          <p style={{ color: 'var(--color-text-muted)', marginTop: 'var(--space-2)' }}>
            No invoices pending approval
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          {approvals.map((approval) => {
            const slaStatus = approval.sla_status || 'on_track';
            const priority = approval.priority || 'normal';
            
            return (
              <div 
                key={approval.id} 
                className="card"
                style={{ 
                  borderLeft: `4px solid ${slaColors[slaStatus] || slaColors.on_track}`,
                }}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2" style={{ marginBottom: 'var(--space-2)' }}>
                      <Link 
                        to={`/invoices/${approval.invoice_id}`}
                        style={{ fontWeight: 600, fontSize: 'var(--font-size-lg)', color: 'var(--color-primary)' }}
                      >
                        {approval.invoice_number || approval.invoice_id}
                      </Link>
                      <span 
                        className="badge"
                        style={{ 
                          background: `${priorityColors[priority]}20`,
                          color: priorityColors[priority],
                        }}
                      >
                        {priority}
                      </span>
                      {slaStatus === 'breached' && (
                        <span className="badge" style={{ background: 'var(--color-error-light)', color: 'var(--color-error)' }}>
                          <AlertTriangle size={12} style={{ marginRight: 4 }} />
                          Overdue
                        </span>
                      )}
                    </div>
                    <p style={{ color: 'var(--color-text-secondary)', marginBottom: 'var(--space-1)' }}>
                      {approval.vendor_name || 'Unknown Vendor'}
                    </p>
                    <p style={{ fontSize: 'var(--font-size-xl)', fontWeight: 600 }}>
                      ${(approval.amount || 0).toLocaleString()}
                    </p>
                  </div>

                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <div className="flex items-center gap-2" style={{ 
                        color: slaColors[slaStatus] || slaColors.on_track,
                        marginBottom: 'var(--space-1)'
                      }}>
                        <Clock size={16} />
                        {approval.due_in || 'No deadline'}
                      </div>
                      <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
                        Assigned to {approval.assigned_to || 'You'}
                      </p>
                    </div>

                    <div className="flex gap-2">
                      <Link to={`/invoices/${approval.invoice_id}`} className="btn btn-primary">
                        Review
                      </Link>
                      <button 
                        className="btn btn-success" 
                        style={{ padding: 'var(--space-2)' }}
                        onClick={() => handleApprove(approval.id)}
                        disabled={approveMutation.isPending}
                      >
                        <Check size={18} />
                      </button>
                      <button 
                        className="btn btn-danger" 
                        style={{ padding: 'var(--space-2)' }}
                        onClick={() => handleReject(approval.id)}
                        disabled={rejectMutation.isPending}
                      >
                        <X size={18} />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
