import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';

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
      const response = await axios.get(`http://localhost:8000/api/invoices/${id}`);
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

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Invoice Details</h1>
      
      <div className="bg-white rounded-lg shadow p-6 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="font-semibold">Invoice Number:</label>
            <div>{invoice.invoice_number || 'N/A'}</div>
          </div>
          <div>
            <label className="font-semibold">Status:</label>
            <div className="capitalize">{invoice.status}</div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="font-semibold">Vendor:</label>
            <div>{invoice.vendor_name || 'N/A'}</div>
          </div>
          <div>
            <label className="font-semibold">Total Amount:</label>
            <div>${invoice.total_amount?.toFixed(2) || '0.00'}</div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="font-semibold">Invoice Date:</label>
            <div>{invoice.invoice_date ? new Date(invoice.invoice_date).toLocaleDateString() : 'N/A'}</div>
          </div>
          <div>
            <label className="font-semibold">Due Date:</label>
            <div>{invoice.due_date ? new Date(invoice.due_date).toLocaleDateString() : 'N/A'}</div>
          </div>
        </div>

        {invoice.risk_score !== null && (
          <div>
            <label className="font-semibold">Risk Score:</label>
            <div className="flex items-center">
              <div className="w-full bg-gray-200 rounded-full h-2.5 mr-2">
                <div 
                  className="bg-red-600 h-2.5 rounded-full"
                  style={{ width: `${invoice.risk_score * 100}%` }}
                ></div>
              </div>
              <span>{(invoice.risk_score * 100).toFixed(0)}%</span>
            </div>
          </div>
        )}

        {invoice.summary && (
          <div>
            <label className="font-semibold">AI Summary:</label>
            <div className="bg-gray-50 p-4 rounded mt-2">{invoice.summary}</div>
          </div>
        )}

        {invoice.line_items && invoice.line_items.length > 0 && (
          <div>
            <label className="font-semibold">Line Items:</label>
            <div className="mt-2 overflow-x-auto">
              <table className="min-w-full border-collapse border">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="border p-2 text-left">Description</th>
                    <th className="border p-2 text-right">Quantity</th>
                    <th className="border p-2 text-right">Unit Price</th>
                    <th className="border p-2 text-right">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {invoice.line_items.map((item, index) => (
                    <tr key={index} className="hover:bg-gray-50">
                      <td className="border p-2">{item.description}</td>
                      <td className="border p-2 text-right">{item.quantity}</td>
                      <td className="border p-2 text-right">${item.unit_price?.toFixed(2)}</td>
                      <td className="border p-2 text-right">${item.total?.toFixed(2)}</td>
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
