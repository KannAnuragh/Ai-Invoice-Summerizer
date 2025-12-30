import React, { useState, useCallback } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useUploadInvoice, useHealthCheck } from '../api/hooks';
import { 
  LayoutDashboard, 
  FileText, 
  CheckSquare, 
  Settings, 
  Upload,
  LogOut 
} from './icons';

const navigation = [
  { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
  { name: 'Invoices', path: '/invoices', icon: FileText },
  { name: 'Approvals', path: '/approvals', icon: CheckSquare },
  { name: 'Settings', path: '/admin', icon: Settings },
];

function UploadModal({ isOpen, onClose }) {
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const uploadMutation = useUploadInvoice();

  const handleFiles = useCallback(async (files) => {
    if (files.length === 0) return;
    
    setUploading(true);
    
    for (const file of files) {
      await uploadMutation.mutateAsync({ file, options: {} }).catch(() => {});
    }
    
    setUploading(false);
    onClose();
  }, [uploadMutation, onClose]);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer?.files || []);
    handleFiles(files);
  };

  const handleFileInput = (e) => {
    const files = Array.from(e.target.files || []);
    handleFiles(files);
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
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          style={{
            border: `2px dashed ${dragOver ? 'var(--color-primary)' : 'var(--color-border)'}`,
            borderRadius: 'var(--radius-lg)',
            padding: 'var(--space-8)',
            textAlign: 'center',
            background: dragOver ? 'var(--color-primary-light)' : 'var(--color-bg)',
            transition: 'all var(--transition-fast)',
            cursor: 'pointer',
            opacity: uploading ? 0.7 : 1,
            pointerEvents: uploading ? 'none' : 'auto',
          }}
        >
          <Upload size={48} style={{ color: 'var(--color-text-muted)', marginBottom: 'var(--space-4)' }} />
          {uploading ? (
            <p>Uploading...</p>
          ) : (
            <>
              <p style={{ marginBottom: 'var(--space-2)' }}>
                Drag & drop invoice files here
              </p>
              <p style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)' }}>
                Supports PDF, PNG, JPG (max 50MB)
              </p>
            </>
          )}
          <input
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.tiff"
            multiple
            onChange={handleFileInput}
            style={{ display: 'none' }}
            id="upload-file-input"
            disabled={uploading}
          />
          <label 
            htmlFor="upload-file-input" 
            className="btn btn-secondary" 
            style={{ marginTop: 'var(--space-4)', cursor: uploading ? 'not-allowed' : 'pointer' }}
          >
            {uploading ? 'Uploading...' : 'Browse Files'}
          </label>
        </div>

        <div className="flex gap-2" style={{ marginTop: 'var(--space-4)', justifyContent: 'flex-end' }}>
          <button className="btn btn-secondary" onClick={onClose} disabled={uploading}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Layout() {
  const [uploadOpen, setUploadOpen] = useState(false);
  const { data: healthData } = useHealthCheck();
  const isConnected = !!healthData;

  return (
    <div className="layout">
      <aside className="sidebar">
        {/* Logo */}
        <div style={{ padding: 'var(--space-4)', marginBottom: 'var(--space-6)' }}>
          <h1 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 700 }}>
            <span style={{ color: 'var(--color-primary)' }}>AI</span> Invoice
          </h1>
          <div className="flex items-center gap-2" style={{ marginTop: 'var(--space-1)' }}>
            <p style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
              Enterprise Summarizer
            </p>
            <span 
              className={`status-dot ${isConnected ? 'success' : 'error'}`} 
              style={{ width: 6, height: 6 }}
              title={isConnected ? 'API Connected' : 'API Disconnected'}
            />
          </div>
        </div>

        {/* Upload Button */}
        <button 
          className="btn btn-primary" 
          style={{ width: '100%', marginBottom: 'var(--space-6)' }}
          onClick={() => setUploadOpen(true)}
        >
          <Upload size={16} />
          Upload Invoice
        </button>

        {/* Navigation */}
        <nav style={{ flex: 1 }}>
          {navigation.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => 
                `nav-item ${isActive ? 'active' : ''}`
              }
            >
              <item.icon size={18} />
              {item.name}
            </NavLink>
          ))}
        </nav>

        {/* User */}
        <div style={{ 
          padding: 'var(--space-4)', 
          borderTop: '1px solid var(--color-border)',
          marginTop: 'auto'
        }}>
          <div className="flex items-center gap-2">
            <div style={{
              width: 32,
              height: 32,
              borderRadius: 'var(--radius-full)',
              background: 'var(--color-primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white',
              fontWeight: 600,
              fontSize: 'var(--font-size-sm)'
            }}>
              U
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 'var(--font-size-sm)', fontWeight: 500 }}>
                User
              </div>
              <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                Finance Team
              </div>
            </div>
            <button className="btn btn-secondary" style={{ padding: 'var(--space-2)' }}>
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>

      <UploadModal isOpen={uploadOpen} onClose={() => setUploadOpen(false)} />
    </div>
  );
}
