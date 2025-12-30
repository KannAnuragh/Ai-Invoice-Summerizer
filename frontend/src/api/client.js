/**
 * API Client
 * Centralized API communication with the backend
 */

import axios from 'axios';

const API_BASE_URL = '/api/v1';

// Create axios instance with defaults
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ============== Health ==============

export const healthApi = {
  check: () => axios.get('/health'),
};

// ============== Invoices ==============

export const invoicesApi = {
  list: (params = {}) => api.get('/invoices', { params }),
  
  get: (id) => api.get(`/invoices/${id}`),
  
  update: (id, data) => api.patch(`/invoices/${id}`, data),
  
  getSummary: (id, role = 'finance') => 
    api.get(`/invoices/${id}/summary`, { params: { role } }),
  
  getAuditTrail: (id) => api.get(`/invoices/${id}/audit-trail`),
  
  upload: async (file, options = {}) => {
    const formData = new FormData();
    formData.append('file', file);
    
    if (options.vendorId) {
      formData.append('vendor_id', options.vendorId);
    }
    if (options.notes) {
      formData.append('notes', options.notes);
    }
    
    return api.post('/invoices/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: options.onProgress,
    });
  },
  
  uploadBatch: async (files, onProgress) => {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));
    
    return api.post('/invoices/upload/batch', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onProgress,
    });
  },
};

// ============== Approvals ==============

export const approvalsApi = {
  getQueue: (params = {}) => api.get('/approvals/queue', { params }),
  
  get: (taskId) => api.get(`/approvals/${taskId}`),
  
  getStats: () => api.get('/approvals/stats'),
  
  processAction: (taskId, action, comment = null, delegateTo = null) =>
    api.post(`/approvals/${taskId}/action`, {
      action,
      comment,
      delegate_to: delegateTo,
    }),
  
  approve: (taskId, comment) => 
    approvalsApi.processAction(taskId, 'approve', comment),
  
  reject: (taskId, comment) => 
    approvalsApi.processAction(taskId, 'reject', comment),
  
  escalate: (taskId, comment) => 
    approvalsApi.processAction(taskId, 'escalate', comment),
  
  requestInfo: (taskId, comment) => 
    approvalsApi.processAction(taskId, 'request_info', comment),
};

// ============== Admin ==============

export const adminApi = {
  // Vendors
  listVendors: (params = {}) => api.get('/admin/vendors', { params }),
  createVendor: (vendor) => api.post('/admin/vendors', vendor),
  updateVendor: (id, vendor) => api.put(`/admin/vendors/${id}`, vendor),
  
  // Approval Rules
  listApprovalRules: () => api.get('/admin/approval-rules'),
  createApprovalRule: (rule) => api.post('/admin/approval-rules', rule),
  
  // Config
  getConfig: () => api.get('/admin/config'),
  updateConfig: (config) => api.put('/admin/config', config),
  
  // Users
  listUsers: (params = {}) => api.get('/admin/users', { params }),
  createUser: (user) => api.post('/admin/users', user),
};

export default api;
