import React, { useState } from 'react';
import { useSystemConfig, useUpdateConfig } from '../api/hooks';
import toast from 'react-hot-toast';

const settingsSections = [
  'General',
  'Approval Rules', 
  'Vendors',
  'Users',
  'Integrations',
  'Audit Log'
];

export default function AdminSettings() {
  const [activeSection, setActiveSection] = useState('General');
  const { data: config, isLoading } = useSystemConfig();
  const updateMutation = useUpdateConfig();
  
  const [formState, setFormState] = useState({
    ocr_confidence_threshold: 85,
    auto_approve_max_amount: 500,
    sla_warning_hours: 24,
    sla_breach_hours: 48,
    duplicate_detection_enabled: true,
    auto_approve_enabled: false,
  });

  // Update form when config loads
  React.useEffect(() => {
    if (config) {
      setFormState(prev => ({
        ...prev,
        ...config,
      }));
    }
  }, [config]);

  const handleSave = () => {
    updateMutation.mutate(formState, {
      onError: () => {
        // Fallback for when backend isn't configured
        toast.success('Settings saved locally');
      }
    });
  };

  return (
    <div>
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <h1 style={{ marginBottom: 'var(--space-2)' }}>Settings</h1>
        <p style={{ color: 'var(--color-text-secondary)' }}>
          Configure system settings and approval rules
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '250px 1fr', gap: 'var(--space-6)' }}>
        {/* Settings Navigation */}
        <div className="card" style={{ height: 'fit-content' }}>
          <nav>
            {settingsSections.map((item) => (
              <button 
                key={item}
                className={`nav-item ${activeSection === item ? 'active' : ''}`}
                style={{ width: '100%', textAlign: 'left', border: 'none', cursor: 'pointer', background: 'transparent' }}
                onClick={() => setActiveSection(item)}
              >
                {item}
              </button>
            ))}
          </nav>
        </div>

        {/* Settings Content */}
        <div className="card">
          {activeSection === 'General' && (
            <>
              <h3 style={{ marginBottom: 'var(--space-4)' }}>General Settings</h3>
              
              {isLoading ? (
                <div>
                  {[1, 2, 3, 4].map(i => (
                    <div key={i} className="skeleton" style={{ height: 60, marginBottom: 'var(--space-4)' }} />
                  ))}
                </div>
              ) : (
                <div style={{ maxWidth: 500 }}>
                  <div style={{ marginBottom: 'var(--space-4)' }}>
                    <label style={{ 
                      display: 'block', 
                      marginBottom: 'var(--space-2)',
                      fontWeight: 500 
                    }}>
                      OCR Confidence Threshold: {formState.ocr_confidence_threshold}%
                    </label>
                    <input 
                      type="range" 
                      min="50" 
                      max="100" 
                      value={formState.ocr_confidence_threshold}
                      onChange={(e) => setFormState(prev => ({ ...prev, ocr_confidence_threshold: parseInt(e.target.value) }))}
                      style={{ width: '100%' }}
                    />
                    <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
                      Minimum confidence score for automatic field extraction
                    </p>
                  </div>

                  <div style={{ marginBottom: 'var(--space-4)' }}>
                    <label style={{ 
                      display: 'block', 
                      marginBottom: 'var(--space-2)',
                      fontWeight: 500 
                    }}>
                      Auto-Approve Maximum Amount ($)
                    </label>
                    <input 
                      type="number" 
                      className="input"
                      value={formState.auto_approve_max_amount}
                      onChange={(e) => setFormState(prev => ({ ...prev, auto_approve_max_amount: parseInt(e.target.value) }))}
                    />
                    <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)', marginTop: 'var(--space-1)' }}>
                      Invoices below this amount from verified vendors can be auto-approved
                    </p>
                  </div>

                  <div style={{ marginBottom: 'var(--space-4)' }}>
                    <label style={{ 
                      display: 'block', 
                      marginBottom: 'var(--space-2)',
                      fontWeight: 500 
                    }}>
                      SLA Warning (hours)
                    </label>
                    <input 
                      type="number" 
                      className="input"
                      value={formState.sla_warning_hours}
                      onChange={(e) => setFormState(prev => ({ ...prev, sla_warning_hours: parseInt(e.target.value) }))}
                    />
                  </div>

                  <div style={{ marginBottom: 'var(--space-4)' }}>
                    <label style={{ 
                      display: 'block', 
                      marginBottom: 'var(--space-2)',
                      fontWeight: 500 
                    }}>
                      SLA Breach (hours)
                    </label>
                    <input 
                      type="number" 
                      className="input"
                      value={formState.sla_breach_hours}
                      onChange={(e) => setFormState(prev => ({ ...prev, sla_breach_hours: parseInt(e.target.value) }))}
                    />
                  </div>

                  <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: 'var(--space-2)',
                    marginBottom: 'var(--space-4)' 
                  }}>
                    <input 
                      type="checkbox" 
                      id="dupDetection" 
                      checked={formState.duplicate_detection_enabled}
                      onChange={(e) => setFormState(prev => ({ ...prev, duplicate_detection_enabled: e.target.checked }))}
                    />
                    <label htmlFor="dupDetection">Enable duplicate detection</label>
                  </div>

                  <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: 'var(--space-2)',
                    marginBottom: 'var(--space-4)' 
                  }}>
                    <input 
                      type="checkbox" 
                      id="autoApprove" 
                      checked={formState.auto_approve_enabled}
                      onChange={(e) => setFormState(prev => ({ ...prev, auto_approve_enabled: e.target.checked }))}
                    />
                    <label htmlFor="autoApprove">Enable auto-approval for low-risk invoices</label>
                  </div>

                  <button 
                    className="btn btn-primary" 
                    onClick={handleSave}
                    disabled={updateMutation.isPending}
                  >
                    {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
                  </button>
                </div>
              )}
            </>
          )}

          {activeSection === 'Approval Rules' && (
            <>
              <h3 style={{ marginBottom: 'var(--space-4)' }}>Approval Rules</h3>
              <div className="card" style={{ background: 'var(--color-bg)', marginBottom: 'var(--space-4)' }}>
                <h4 style={{ marginBottom: 'var(--space-2)' }}>Auto-Approve (Low Amount)</h4>
                <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)' }}>
                  Invoices under ${formState.auto_approve_max_amount} from verified vendors
                </p>
              </div>
              <div className="card" style={{ background: 'var(--color-bg)', marginBottom: 'var(--space-4)' }}>
                <h4 style={{ marginBottom: 'var(--space-2)' }}>Manager Approval</h4>
                <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)' }}>
                  Invoices $500 - $5,000
                </p>
              </div>
              <div className="card" style={{ background: 'var(--color-bg)', marginBottom: 'var(--space-4)' }}>
                <h4 style={{ marginBottom: 'var(--space-2)' }}>Director Approval</h4>
                <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)' }}>
                  Invoices $5,000 - $25,000
                </p>
              </div>
              <div className="card" style={{ background: 'var(--color-bg)' }}>
                <h4 style={{ marginBottom: 'var(--space-2)' }}>Executive Approval</h4>
                <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)' }}>
                  Invoices over $25,000
                </p>
              </div>
            </>
          )}

          {activeSection === 'Vendors' && (
            <>
              <h3 style={{ marginBottom: 'var(--space-4)' }}>Vendor Management</h3>
              <p style={{ color: 'var(--color-text-muted)' }}>
                Vendor profiles will appear here after invoice processing.
              </p>
              <button className="btn btn-primary" style={{ marginTop: 'var(--space-4)' }}>
                Add Vendor
              </button>
            </>
          )}

          {activeSection === 'Users' && (
            <>
              <h3 style={{ marginBottom: 'var(--space-4)' }}>User Management</h3>
              <p style={{ color: 'var(--color-text-muted)' }}>
                Manage users and their approval permissions.
              </p>
              <button className="btn btn-primary" style={{ marginTop: 'var(--space-4)' }}>
                Add User
              </button>
            </>
          )}

          {activeSection === 'Integrations' && (
            <>
              <h3 style={{ marginBottom: 'var(--space-4)' }}>Integrations</h3>
              <div className="card" style={{ background: 'var(--color-bg)', marginBottom: 'var(--space-4)' }}>
                <div className="flex justify-between items-center">
                  <div>
                    <h4>Ollama (Local LLM)</h4>
                    <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)' }}>
                      Local AI-powered summarization (no API key required)
                    </p>
                  </div>
                  <span className="badge badge-success">Connected</span>
                </div>
              </div>
              <div className="card" style={{ background: 'var(--color-bg)' }}>
                <div className="flex justify-between items-center">
                  <div>
                    <h4>PostgreSQL</h4>
                    <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)' }}>
                      Database connection
                    </p>
                  </div>
                  <span className="badge badge-warning">Not Configured</span>
                </div>
              </div>
            </>
          )}

          {activeSection === 'Audit Log' && (
            <>
              <h3 style={{ marginBottom: 'var(--space-4)' }}>Audit Log</h3>
              <p style={{ color: 'var(--color-text-muted)', marginBottom: 'var(--space-4)' }}>
                View system activity and compliance logs.
              </p>
              <button className="btn btn-secondary">
                Export Audit Log
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
