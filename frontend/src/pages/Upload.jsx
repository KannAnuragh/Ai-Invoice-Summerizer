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

  const onDrop = useCallback((acceptedFiles) => {
    const newFiles = acceptedFiles.map(file => ({
      file,
      id: Math.random().toString(36),
      status: 'pending', // pending, uploading, success, error
      progress: 0,
      error: null,
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

  const uploadFiles = async () => {
    if (files.length === 0) {
      toast.error('Please select files to upload');
      return;
    }

    setUploading(true);

    // Upload files one by one
    for (const fileItem of files) {
      if (fileItem.status === 'success') continue;

      try {
        setFiles(prev => prev.map(f => 
          f.id === fileItem.id ? { ...f, status: 'uploading', progress: 0 } : f
        ));

        const formData = new FormData();
        formData.append('file', fileItem.file);

        await invoiceAPI.upload(formData, (progressEvent) => {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setFiles(prev => prev.map(f => 
            f.id === fileItem.id ? { ...f, progress } : f
          ));
        });

        setFiles(prev => prev.map(f => 
          f.id === fileItem.id ? { ...f, status: 'success', progress: 100 } : f
        ));
        
        toast.success(`${fileItem.file.name} uploaded successfully`);
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
    <div className="min-h-screen p-6">
      <div className="max-w-6xl mx-auto">
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

            {/* Upload Button */}
            <motion.button
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              onClick={uploadFiles}
              disabled={uploading || files.every(f => f.status === 'success')}
              className="glass-button-primary w-full py-3 mt-6 font-semibold flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {uploading ? (
                <>
                  <div className="spinner border-2 w-5 h-5" />
                  Uploading...
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
