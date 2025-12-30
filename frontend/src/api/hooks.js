/**
 * React Query Hooks for API calls
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { invoicesApi, approvalsApi, adminApi, healthApi } from './client';
import toast from 'react-hot-toast';

// ============== Health ==============

export function useHealthCheck() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => healthApi.check(),
    refetchInterval: 30000, // Check every 30 seconds
  });
}

// ============== Invoices ==============

export function useInvoices(params = {}) {
  return useQuery({
    queryKey: ['invoices', params],
    queryFn: () => invoicesApi.list(params).then(res => res.data),
  });
}

export function useInvoice(id) {
  return useQuery({
    queryKey: ['invoice', id],
    queryFn: () => invoicesApi.get(id).then(res => res.data),
    enabled: !!id,
  });
}

export function useInvoiceSummary(id, role = 'finance') {
  return useQuery({
    queryKey: ['invoice-summary', id, role],
    queryFn: () => invoicesApi.getSummary(id, role).then(res => res.data),
    enabled: !!id,
  });
}

export function useUploadInvoice() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ file, options }) => invoicesApi.upload(file, options),
    onSuccess: (data) => {
      toast.success('Invoice uploaded successfully');
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      return data;
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Upload failed');
    },
  });
}

export function useUpdateInvoice() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, data, status }) => invoicesApi.update(id, { data, status }),
    onSuccess: (_, variables) => {
      toast.success('Invoice updated');
      queryClient.invalidateQueries({ queryKey: ['invoice', variables.id] });
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Update failed');
    },
  });
}

// ============== Approvals ==============

export function useApprovalQueue(params = {}) {
  return useQuery({
    queryKey: ['approvals', 'queue', params],
    queryFn: () => approvalsApi.getQueue(params).then(res => res.data),
    refetchInterval: 10000, // Refresh every 10 seconds
  });
}

export function useApprovalStats() {
  return useQuery({
    queryKey: ['approvals', 'stats'],
    queryFn: () => approvalsApi.getStats().then(res => res.data),
  });
}

export function useApproveInvoice() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ taskId, comment }) => approvalsApi.approve(taskId, comment),
    onSuccess: () => {
      toast.success('Invoice approved');
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Approval failed');
    },
  });
}

export function useRejectInvoice() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ taskId, comment }) => approvalsApi.reject(taskId, comment),
    onSuccess: () => {
      toast.success('Invoice rejected');
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Rejection failed');
    },
  });
}

// ============== Admin ==============

export function useVendors(params = {}) {
  return useQuery({
    queryKey: ['vendors', params],
    queryFn: () => adminApi.listVendors(params).then(res => res.data),
  });
}

export function useSystemConfig() {
  return useQuery({
    queryKey: ['config'],
    queryFn: () => adminApi.getConfig().then(res => res.data),
  });
}

export function useUpdateConfig() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (config) => adminApi.updateConfig(config),
    onSuccess: () => {
      toast.success('Settings saved');
      queryClient.invalidateQueries({ queryKey: ['config'] });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to save settings');
    },
  });
}
