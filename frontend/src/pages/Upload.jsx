import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, File, X, CheckCircle, AlertCircle, Loader } from 'lucide-react';
import toast from 'react-hot-toast';
import { invoiceAPI } from '../api/client';

const UploadPage = () => {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState({});
  const [uploadedInvoices, setUploadedInvoices] = useState([]);

  const onDrop = useCallback((acceptedFiles) => {
    const newFiles = acceptedFiles.map(file => ({
      file,
      id: Math.random().toString(36),
      status: 'pending', // pending, uploading, success, error
      progress: 0,
      error: null,
      invoiceId: null,
      invoiceData: null,
    }));
    
    setFiles(prev => [...prev, ...newFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.png', '.jpg', '.jpeg', '.tiff'],
    },
    multiple: true,
  });

  const removeFile = (id) => {
    setFiles(prev => prev.filter(f => f.id !== id));
  };

  // Poll for invoice status after upload
  const pollInvoiceStatus = async (invoiceId, fileId) => {
    let attempts = 0;
    const maxAttempts = 30; // 30 seconds max
    
    const poll = async () => {
      try {
        const response = await invoicesApi.get(invoiceId);
        const invoice = response.data;
        
        // Update file item with invoice data
        setFiles(prev => prev.map(f => 
          f.id === fileId ? {
            ...f,
            invoiceData: invoice,
            status: invoice.status === 'extracted' ? 'extracted' : 'processing'
          } : f
        ));
        
        // If extraction is complete, stop polling
        if (invoice.status === 'extracted' || invoice.status === 'validated') {
          setUploadedInvoices(prev => [...prev, invoice]);
          return;
        }
        
        // Continue polling if still processing
        if (attempts < maxAttempts && (invoice.status === 'uploaded' || invoice.status === 'processing')) {
          attempts++;
          setTimeout(poll, 1000);
        }
      } catch (error) {
        console.error('Error polling invoice status:', error);
      }
    };
    
    poll();
  };

  const uploadFiles = async () => {
    if (files.length === 0) {
      toast.error('Please select files to upload');
      return;
    }

    setUploading(true);

    // Upload files one by one
    for (const fileItem of files) {
      if (fileItem.status === 'success' || fileItem.status === 'extracted') continue;

      try {
        setFiles(prev => prev.map(f => 
          f.id === fileItem.id ? { ...f, status: 'uploading', progress: 0 } : f
        ));

        const formData = new FormData();
        formData.append('file', fileItem.file);

        const response = await invoiceAPI.upload(formData, (progressEvent) => {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setFiles(prev => prev.map(f => 
            f.id === fileItem.id ? { ...f, progress } : f
          ));
        });

        const { invoice_id } = response.data;

        setFiles(prev => prev.map(f => 
          f.id === fileItem.id ? { 
            ...f, 
            status: 'processing', 
            progress: 100,
            invoiceId: invoice_id
          } : f
        ));
        
        toast.success(`${fileItem.file.name} uploaded - AI processing started`);
        
        // Start polling for invoice status
        pollInvoiceStatus(invoice_id, fileItem.id);
        
      } catch (error) {
        const errorMsg = error.response?.data?.detail || 'Upload failed';
        setFiles(prev => prev.map(f => 
          f.id === fileItem.id ? { ...f, status: 'error', error: errorMsg } : f
        ));
        toast.error(`Failed to upload ${fileItem.file.name}`);
      }
    }

    setUploading(false);
  };

  const clearAll = () => {
    setFiles([]);
    setUploadProgress({});
  };

  return (
    <div className="page">
      <div className="container" style={{ maxWidth: 1200 }}>
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <h1 className="text-4xl font-bold text-gradient mb-2">Upload Invoices</h1>
          <p className="text-text-secondary">
            Upload your invoice documents for AI-powered processing and analysis
          </p>
        </motion.div>

        {/* Dropzone */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.1 }}
          className="mb-6"
        >
          <div
            {...getRootProps()}
            className={`glass-card p-12 border-2 border-dashed cursor-pointer transition-all ${
              isDragActive 
                ? 'border-primary bg-primary/10 scale-[1.02]' 
                : 'border-glass-border hover:border-primary/50'
            }`}
          >
            <input {...getInputProps()} />
            <div className="text-center">
              <motion.div
                animate={isDragActive ? { scale: 1.1 } : { scale: 1 }}
                className="inline-block mb-4"
              >
                <Upload className="w-16 h-16 text-primary mx-auto" />
              </motion.div>
              
              {isDragActive ? (
                <p className="text-xl font-semibold text-primary">Drop files here...</p>
              ) : (
                <>
                  <p className="text-xl font-semibold text-text-primary mb-2">
                    Drag & drop invoice files here
                  </p>
                  <p className="text-text-secondary mb-4">
                    or click to browse your computer
                  </p>
                  <p className="text-sm text-text-muted">
                    Supports PDF, PNG, JPG, TIFF (Max 10MB per file)
                  </p>
                </>
              )}
            </div>
          </div>
        </motion.div>

        {/* File List */}
        {files.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-card p-6"
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-text-primary">
                Files ({files.length})
              </h2>
              <button
                onClick={clearAll}
                className="glass-button text-sm"
                disabled={uploading}
              >
                Clear All
              </button>
            </div>

            <div className="space-y-3">
              <AnimatePresence>
                {files.map((fileItem) => (
                  <motion.div
                    key={fileItem.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 20 }}
                    className="glass p-4 flex items-center gap-4"
                  >
                    {/* Icon */}
                    <div className="flex-shrink-0">
                      <File className="w-8 h-8 text-primary" />
                    </div>

                    {/* File Info */}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-text-primary truncate">
                        {fileItem.file.name}
                      </p>
                      <p className="text-xs text-text-muted">
                        {(fileItem.file.size / 1024 / 1024).toFixed(2)} MB
                      </p>

                      {/* Progress Bar */}
                      {fileItem.status === 'uploading' && (
                        <div className="mt-2">
                          <div className="h-1.5 bg-glass-bg rounded-full overflow-hidden">
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${fileItem.progress}%` }}
                              className="h-full bg-primary"
                            />
                          </div>
                          <p className="text-xs text-text-muted mt-1">
                            {fileItem.progress}%
                          </p>
                        </div>
                      )}

                      {/* Error Message */}
                      {fileItem.status === 'error' && (
                        <p className="text-xs text-error mt-1">{fileItem.error}</p>
                      )}
                    </div>

                    {/* Status Icon */}
                    <div className="flex-shrink-0">
                      {fileItem.status === 'success' && (
                        <CheckCircle className="w-6 h-6 text-success" />
                      )}
                      {fileItem.status === 'extracted' && (
                        <CheckCircle className="w-6 h-6 text-success" />
                      )}
                      {fileItem.status === 'processing' && (
                        <Loader className="w-6 h-6 text-warning animate-spin" />
                      )}
                      {fileItem.status === 'error' && (
                        <AlertCircle className="w-6 h-6 text-error" />
                      )}
                      {fileItem.status === 'uploading' && (
                        <Loader className="w-6 h-6 text-primary animate-spin" />
                      )}
                      {fileItem.status === 'pending' && (
                        <button
                          onClick={() => removeFile(fileItem.id)}
                          className="p-1 hover:bg-glass-bg-hover rounded-lg transition-colors"
                        >
                          <X className="w-5 h-5 text-text-muted" />
                        </button>
                      )}
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>

            {/* Extracted Invoice Data Section */}
            {files.some(f => f.invoiceData) && (
              <div className="mt-6 space-y-4">
                <h3 className="text-lg font-semibold text-text-primary mb-3">
                  Extracted Invoice Data
                </h3>
                {files.filter(f => f.invoiceData).map((fileItem) => (
                  <motion.div
                    key={`data-${fileItem.id}`}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="glass p-4 space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <h4 className="font-medium text-text-primary">
                        {fileItem.file.name}
                      </h4>
                      {fileItem.status === 'processing' && (
                        <span className="text-xs text-warning flex items-center gap-1">
                          <Loader className="w-3 h-3 animate-spin" />
                          Processing...
                        </span>
                      )}
                      {fileItem.status === 'extracted' && (
                        <span className="text-xs text-success flex items-center gap-1">
                          <CheckCircle className="w-3 h-3" />
                          Extracted
                        </span>
                      )}
                    </div>
                    
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div>
                        <span className="text-text-muted">Vendor:</span>
                        <span className="ml-2 text-text-primary font-medium">
                          {fileItem.invoiceData.vendor?.name || 'Processing...'}
                        </span>
                      </div>
                      <div>
                        <span className="text-text-muted">Invoice #:</span>
                        <span className="ml-2 text-text-primary font-medium">
                          {fileItem.invoiceData.invoice_number || 'Processing...'}
                        </span>
                      </div>
                      <div>
                        <span className="text-text-muted">Total:</span>
                        <span className="ml-2 text-success font-semibold">
                          {fileItem.invoiceData.total_amount 
                            ? `$${fileItem.invoiceData.total_amount.toFixed(2)}`
                            : 'Processing...'}
                        </span>
                      </div>
                      <div>
                        <span className="text-text-muted">Date:</span>
                        <span className="ml-2 text-text-primary font-medium">
                          {fileItem.invoiceData.invoice_date 
                            ? new Date(fileItem.invoiceData.invoice_date).toLocaleDateString()
                            : 'Processing...'}
                        </span>
                      </div>
                      <div>
                        <span className="text-text-muted">Status:</span>
                        <span className={`ml-2 font-medium capitalize ${
                          fileItem.invoiceData.status === 'extracted' ? 'text-success' : 'text-warning'
                        }`}>
                          {fileItem.invoiceData.status}
                        </span>
                      </div>
                      {fileItem.invoiceData.po_number && (
                        <div>
                          <span className="text-text-muted">PO #:</span>
                          <span className="ml-2 text-text-primary font-medium">
                            {fileItem.invoiceData.po_number}
                          </span>
                        </div>
                      )}
                    </div>
                    
                    {fileItem.invoiceId && (
                      <div className="pt-2 border-t border-glass-border">
                        <a 
                          href={`/invoices/${fileItem.invoiceId}`}
                          className="text-sm text-primary hover:underline"
                        >
                          View Full Invoice Details →
                        </a>
                      </div>
                    )}
                  </motion.div>
                ))}
              </div>
            )}

            {/* Upload Button */}
            <motion.button
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              onClick={uploadFiles}
              disabled={uploading || files.every(f => f.status === 'success' || f.status === 'processing' || f.status === 'extracted')}
              className="glass-button-primary w-full py-3 mt-6 font-semibold flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {uploading ? (
                <>
                  <div className="spinner border-2 w-5 h-5" />
                  Uploading...
                </>
              ) : files.some(f => f.status === 'processing') ? (
                <>
                  <Loader className="w-5 h-5 animate-spin" />
                  Processing {files.filter(f => f.status === 'processing').length} invoices...
                </>
              ) : (
                <>
                  <Upload className="w-5 h-5" />
                  Upload {files.filter(f => f.status === 'pending').length} Files
                </>
              )}
            </motion.button>
          </motion.div>
        )}

        {/* Info Cards */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-8"
        >
          <div className="glass-card p-6">
            <div className="text-primary mb-2">
              <CheckCircle className="w-8 h-8" />
            </div>
            <h3 className="font-semibold text-text-primary mb-1">Automatic Processing</h3>
            <p className="text-sm text-text-secondary">
              OCR extraction and AI analysis starts immediately after upload
            </p>
          </div>

          <div className="glass-card p-6">
            <div className="text-secondary mb-2">
              <CheckCircle className="w-8 h-8" />
            </div>
            <h3 className="font-semibold text-text-primary mb-1">Smart Routing</h3>
            <p className="text-sm text-text-secondary">
              Invoices are automatically routed to appropriate approvers
            </p>
          </div>

          <div className="glass-card p-6">
            <div className="text-success mb-2">
              <CheckCircle className="w-8 h-8" />
            </div>
            <h3 className="font-semibold text-text-primary mb-1">Real-time Updates</h3>
            <p className="text-sm text-text-secondary">
              Track processing status and receive instant notifications
            </p>
          </div>
        </motion.div>
      </div>
    </div>
  );
};

export default UploadPage;
