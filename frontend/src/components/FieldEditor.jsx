import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Edit2, Save, X, AlertCircle, Check } from 'lucide-react';
import clsx from 'clsx';

const FieldEditor = ({ label, value, field, onSave, confidence, editable = true, type = 'text' }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(value || '');
  const [error, setError] = useState('');

  const getConfidenceColor = (score) => {
    if (!score) return 'text-text-muted';
    if (score >= 0.9) return 'text-success';
    if (score >= 0.7) return 'text-warning';
    return 'text-error';
  };

  const getConfidenceLabel = (score) => {
    if (!score) return 'Unknown';
    if (score >= 0.9) return 'High';
    if (score >= 0.7) return 'Medium';
    return 'Low';
  };

  const handleSave = async () => {
    setError('');
    
    // Validation
    if (type === 'number' && editValue && isNaN(editValue)) {
      setError('Please enter a valid number');
      return;
    }

    if (type === 'email' && editValue && !editValue.includes('@')) {
      setError('Please enter a valid email');
      return;
    }

    try {
      await onSave(field, editValue);
      setIsEditing(false);
    } catch (err) {
      setError(err.message || 'Failed to save');
    }
  };

  const handleCancel = () => {
    setEditValue(value || '');
    setError('');
    setIsEditing(false);
  };

  return (
    <div className="glass p-4 rounded-lg">
      {/* Label and Confidence */}
      <div className="flex items-center justify-between mb-2">
        <label className="text-sm font-medium text-text-secondary">{label}</label>
        
        {confidence !== undefined && (
          <div className={clsx(
            'text-xs font-medium px-2 py-0.5 rounded',
            confidence >= 0.9 ? 'bg-success/20 text-success' :
            confidence >= 0.7 ? 'bg-warning/20 text-warning' :
            'bg-error/20 text-error'
          )}>
            {getConfidenceLabel(confidence)} ({Math.round(confidence * 100)}%)
          </div>
        )}
      </div>

      {/* Value / Edit Field */}
      <AnimatePresence mode="wait">
        {isEditing ? (
          <motion.div
            key="editing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <div className="flex gap-2">
              <input
                type={type}
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                className="glass-input flex-1"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSave();
                  if (e.key === 'Escape') handleCancel();
                }}
              />
              
              <button
                onClick={handleSave}
                className="glass-button p-2 text-success"
                title="Save"
              >
                <Check className="w-5 h-5" />
              </button>
              
              <button
                onClick={handleCancel}
                className="glass-button p-2 text-error"
                title="Cancel"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {error && (
              <motion.p
                initial={{ opacity: 0, y: -5 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-xs text-error mt-2 flex items-center gap-1"
              >
                <AlertCircle className="w-3 h-3" />
                {error}
              </motion.p>
            )}
          </motion.div>
        ) : (
          <motion.div
            key="viewing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex items-center justify-between group"
          >
            <div className="flex-1">
              {value ? (
                <p className="text-text-primary font-medium">{value}</p>
              ) : (
                <p className="text-text-muted italic">Not extracted</p>
              )}
            </div>

            {editable && (
              <button
                onClick={() => setIsEditing(true)}
                className="opacity-0 group-hover:opacity-100 transition-opacity p-2 hover:bg-glass-bg-hover rounded-lg"
                title="Edit"
              >
                <Edit2 className="w-4 h-4 text-primary" />
              </button>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Low Confidence Warning */}
      {confidence && confidence < 0.7 && !isEditing && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="mt-2 flex items-start gap-2 text-xs text-warning"
        >
          <AlertCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />
          <span>Low confidence - please verify this value</span>
        </motion.div>
      )}
    </div>
  );
};

export default FieldEditor;
