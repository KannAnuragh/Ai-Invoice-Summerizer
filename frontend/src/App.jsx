import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import InvoiceList from './pages/InvoiceList';
import InvoiceViewer from './pages/InvoiceViewer';
import ApprovalQueue from './pages/ApprovalQueue';
import AdminSettings from './pages/AdminSettings';

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="invoices" element={<InvoiceList />} />
        <Route path="invoices/:id" element={<InvoiceViewer />} />
        <Route path="approvals" element={<ApprovalQueue />} />
        <Route path="admin" element={<AdminSettings />} />
      </Route>
    </Routes>
  );
}

export default App;
