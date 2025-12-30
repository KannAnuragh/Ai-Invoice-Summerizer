import React from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { FileText, Calendar, DollarSign, Building2, AlertTriangle } from 'lucide-react';
import { format } from 'date-fns';
import clsx from 'clsx';

const InvoiceCard = ({ invoice, index = 0 }) => {
  const navigate = useNavigate();

  const getStatusBadge = (status) => {
    const statusConfig = {
      uploaded: { class: 'badge-info', label: 'Uploaded' },
      processing: { class: 'badge-warning', label: 'Processing' },
      extracted: { class: 'badge-info', label: 'Extracted' },
      review_pending: { class: 'badge-warning', label: 'Pending Review' },
      approved: { class: 'badge-success', label: 'Approved' },
      rejected: { class: 'badge-error', label: 'Rejected' },
      paid: { class: 'badge-success', label: 'Paid' },
    };

    const config = statusConfig[status] || { class: 'badge-neutral', label: status };
    return <span className={`badge ${config.class}`}>{config.label}</span>;
  };

  const getRiskBadge = (riskScore) => {
    if (!riskScore) return null;
    
    if (riskScore >= 0.7) {
      return <span className="badge badge-error">High Risk</span>;
    } else if (riskScore >= 0.4) {
      return <span className="badge badge-warning">Medium Risk</span>;
    }
    return <span className="badge badge-success">Low Risk</span>;
  };

  const formatCurrency = (amount, currency = 'USD') => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency,
    }).format(amount);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      onClick={() => navigate(`/invoices/${invoice.id}`)}
      className="glass-card p-6 cursor-pointer"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-start gap-3">
          <div className="p-3 bg-primary/20 rounded-xl">
            <FileText className="w-6 h-6 text-primary" />
          </div>
          
          <div>
            <h3 className="text-lg font-semibold text-text-primary mb-1">
              {invoice.invoice_number || 'N/A'}
            </h3>
            <p className="text-sm text-text-secondary flex items-center gap-2">
              <Building2 className="w-4 h-4" />
              {invoice.vendor_name || 'Unknown Vendor'}
            </p>
          </div>
        </div>

        <div className="flex flex-col items-end gap-2">
          {getStatusBadge(invoice.status)}
          {getRiskBadge(invoice.risk_score)}
        </div>
      </div>

      {/* Details Grid */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="glass p-3 rounded-lg">
          <p className="text-xs text-text-muted mb-1">Amount</p>
          <p className="text-lg font-bold text-text-primary flex items-center gap-1">
            <DollarSign className="w-4 h-4" />
            {invoice.total_amount ? formatCurrency(invoice.total_amount, invoice.currency) : 'N/A'}
          </p>
        </div>

        <div className="glass p-3 rounded-lg">
          <p className="text-xs text-text-muted mb-1">Invoice Date</p>
          <p className="text-sm font-semibold text-text-primary flex items-center gap-1">
            <Calendar className="w-4 h-4" />
            {invoice.invoice_date ? format(new Date(invoice.invoice_date), 'MMM dd, yyyy') : 'N/A'}
          </p>
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-4 border-t border-glass-border">
        <div className="text-xs text-text-muted">
          Uploaded {invoice.uploaded_at ? format(new Date(invoice.uploaded_at), 'MMM dd, HH:mm') : 'N/A'}
        </div>

        {invoice.extracted_data?.confidence_score && (
          <div className="flex items-center gap-1">
            <div className={clsx(
              'text-xs font-medium px-2 py-1 rounded',
              invoice.extracted_data.confidence_score >= 0.9 ? 'text-success bg-success/20' :
              invoice.extracted_data.confidence_score >= 0.7 ? 'text-warning bg-warning/20' :
              'text-error bg-error/20'
            )}>
              {Math.round(invoice.extracted_data.confidence_score * 100)}% confidence
            </div>
          </div>
        )}
      </div>

      {/* Risk Indicators */}
      {invoice.risk_factors && invoice.risk_factors.length > 0 && (
        <div className="mt-4 pt-4 border-t border-glass-border">
          <div className="flex items-center gap-2 text-warning">
            <AlertTriangle className="w-4 h-4" />
            <span className="text-xs font-medium">
              {invoice.risk_factors.length} risk factor(s) detected
            </span>
          </div>
        </div>
      )}
    </motion.div>
  );
};

export default InvoiceCard;
