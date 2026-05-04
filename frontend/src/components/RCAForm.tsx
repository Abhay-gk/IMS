import React, { useState } from 'react';
import { type WorkItem, submitRca } from '../api';
import { FileText, Save, X } from 'lucide-react';
import { format } from 'date-fns';

interface RCAFormProps {
  item: WorkItem;
  onClose: () => void;
  onSuccess: () => void;
}

export const RCAForm: React.FC<RCAFormProps> = ({ item, onClose, onSuccess }) => {
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    incident_start: format(new Date(item.first_signal_at), "yyyy-MM-dd'T'HH:mm"),
    incident_end: format(new Date(), "yyyy-MM-dd'T'HH:mm"),
    root_cause_category: 'Code Bug',
    root_cause_detail: '',
    fix_applied: '',
    prevention_steps: ''
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      // Append seconds and Z for backend parsing if needed, but local datetime format is fine for ISO if we append :00Z or let backend handle it
      const payload = {
        ...formData,
        incident_start: new Date(formData.incident_start).toISOString(),
        incident_end: new Date(formData.incident_end).toISOString(),
      };
      
      await submitRca(item.id, payload);
      onSuccess();
    } catch (err: any) {
      alert("Failed to submit RCA: " + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-card w-full max-w-3xl rounded-2xl shadow-2xl border border-white/10 overflow-hidden animate-in zoom-in-95 duration-200">
        
        <div className="px-6 py-4 border-b border-white/5 flex justify-between items-center bg-white/5">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <FileText className="text-primary w-5 h-5" />
            Root Cause Analysis (RCA)
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          <div className="grid grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-1">Incident Start</label>
              <input 
                type="datetime-local" 
                required
                value={formData.incident_start}
                onChange={e => setFormData({...formData, incident_start: e.target.value})}
                className="w-full bg-black/30 border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-1">Incident End</label>
              <input 
                type="datetime-local" 
                required
                value={formData.incident_end}
                onChange={e => setFormData({...formData, incident_end: e.target.value})}
                className="w-full bg-black/30 border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-primary"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">Root Cause Category</label>
            <select 
              value={formData.root_cause_category}
              onChange={e => setFormData({...formData, root_cause_category: e.target.value})}
              className="w-full bg-black/30 border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-primary"
            >
              <option>Infrastructure</option>
              <option>Code Bug</option>
              <option>Configuration</option>
              <option>External Dependency</option>
              <option>Capacity</option>
              <option>Network</option>
              <option>Unknown</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">Root Cause Detail (Min 10 chars)</label>
            <textarea 
              required minLength={10} rows={3}
              value={formData.root_cause_detail}
              onChange={e => setFormData({...formData, root_cause_detail: e.target.value})}
              className="w-full bg-black/30 border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-primary"
              placeholder="Explain exactly what caused the failure..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">Fix Applied (Min 10 chars)</label>
            <textarea 
              required minLength={10} rows={3}
              value={formData.fix_applied}
              onChange={e => setFormData({...formData, fix_applied: e.target.value})}
              className="w-full bg-black/30 border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-primary"
              placeholder="What actions were taken to restore service?"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">Prevention Steps (Min 10 chars)</label>
            <textarea 
              required minLength={10} rows={3}
              value={formData.prevention_steps}
              onChange={e => setFormData({...formData, prevention_steps: e.target.value})}
              className="w-full bg-black/30 border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-primary"
              placeholder="How do we prevent this in the future?"
            />
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-white/5">
            <button 
              type="button" 
              onClick={onClose}
              className="px-6 py-2 rounded-lg text-sm font-semibold text-gray-300 hover:text-white"
            >
              Cancel
            </button>
            <button 
              type="submit" 
              disabled={loading}
              className="px-6 py-2 bg-primary hover:bg-blue-600 rounded-lg text-sm font-semibold text-white flex items-center gap-2 transition-colors disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              {loading ? 'Submitting...' : 'Submit & Close Incident'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
