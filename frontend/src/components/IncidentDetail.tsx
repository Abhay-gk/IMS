import React, { useEffect, useState } from 'react';
import { ArrowLeft, Database, Terminal, Server, AlertOctagon, RefreshCw } from 'lucide-react';
import { fetchSignals, type WorkItem, type Signal, api } from '../api';
import clsx from 'clsx';
import { format } from 'date-fns';

interface IncidentDetailProps {
  item: WorkItem;
  onBack: () => void;
  onRcaClick: () => void;
}

export const IncidentDetail: React.FC<IncidentDetailProps> = ({ item, onBack, onRcaClick }) => {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSignals();
  }, [item.id]);

  const loadSignals = async () => {
    setLoading(true);
    try {
      const data = await fetchSignals(item.id);
      setSignals(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const getComponentIcon = (type: string) => {
    switch (type) {
      case 'RDBMS': return <Database className="w-5 h-5" />;
      case 'CACHE': return <Server className="w-5 h-5" />;
      case 'API': return <Terminal className="w-5 h-5" />;
      default: return <AlertOctagon className="w-5 h-5" />;
    }
  };

  const advanceState = async (nextState: string) => {
    try {
      await api.post(`/work_items/${item.id}/status`, null, { params: { target_status: nextState } });
      onBack(); // Refresh list basically by going back
    } catch(e) {
      alert("Failed to advance state. Is RCA required?");
    }
  }

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-right-8 duration-500">
      
      {/* Header */}
      <div className="flex items-center justify-between">
        <button onClick={onBack} className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors">
          <ArrowLeft className="w-4 h-4" /> Back to Dashboard
        </button>
        <div className="flex items-center gap-3">
           {item.status === 'OPEN' && (
             <button onClick={() => advanceState('INVESTIGATING')} className="px-4 py-2 bg-primary/20 text-primary border border-primary/50 hover:bg-primary/40 rounded-lg text-sm font-semibold transition-colors">
               Investigate
             </button>
           )}
           {item.status === 'INVESTIGATING' && (
             <button onClick={() => advanceState('RESOLVED')} className="px-4 py-2 bg-success/20 text-success border border-success/50 hover:bg-success/40 rounded-lg text-sm font-semibold transition-colors">
               Mark Resolved
             </button>
           )}
           {item.status !== 'CLOSED' && (
             <button onClick={onRcaClick} className="px-4 py-2 bg-danger/20 text-danger border border-danger/50 hover:bg-danger/40 rounded-lg text-sm font-semibold transition-colors">
               Submit RCA & Close
             </button>
           )}
        </div>
      </div>

      {/* Incident Summary Card */}
      <div className="glass-panel rounded-xl p-6 relative overflow-hidden">
        <div className="absolute top-0 left-0 w-1 h-full bg-warning" />
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-bold text-white mb-2">{item.title}</h1>
            <div className="flex items-center gap-4 text-sm text-gray-400">
              <span className="flex items-center gap-1">
                {getComponentIcon(item.component_type)} {item.component_id}
              </span>
              <span>•</span>
              <span>Status: <strong className="text-white">{item.status}</strong></span>
              <span>•</span>
              <span>Severity: <strong className="text-warning">{item.severity}</strong></span>
            </div>
          </div>
          <div className="text-right">
            <div className="text-sm text-gray-400">Total Signals</div>
            <div className="text-3xl font-bold text-primary">{item.signal_count}</div>
          </div>
        </div>
      </div>

      {/* Raw Signals Table */}
      <div className="glass-panel rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-white/5 flex justify-between items-center bg-white/5">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Terminal className="w-5 h-5 text-gray-400" />
            Raw Audit Log (MongoDB Sink)
          </h2>
          <button onClick={loadSignals} className="text-gray-400 hover:text-white transition-colors">
            <RefreshCw className={clsx("w-4 h-4", loading && "animate-spin")} />
          </button>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-gray-300">
            <thead className="text-xs uppercase bg-black/40 text-gray-400">
              <tr>
                <th className="px-6 py-3">Timestamp</th>
                <th className="px-6 py-3">Error Type</th>
                <th className="px-6 py-3">Latency (ms)</th>
                <th className="px-6 py-3">Message</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {signals.map((sig) => (
                <tr key={sig._id} className="hover:bg-white/5">
                  <td className="px-6 py-4 whitespace-nowrap font-mono text-xs">
                    {format(new Date(sig.timestamp), 'HH:mm:ss.SSS')}
                  </td>
                  <td className="px-6 py-4">
                    <span className="bg-danger/20 text-danger border border-danger/30 px-2 py-1 rounded text-xs font-medium">
                      {sig.error_type}
                    </span>
                  </td>
                  <td className="px-6 py-4 font-mono text-xs">
                    {sig.latency_ms?.toFixed(2) || 'N/A'}
                  </td>
                  <td className="px-6 py-4 max-w-md truncate">
                    {sig.message}
                  </td>
                </tr>
              ))}
              {signals.length === 0 && !loading && (
                <tr>
                  <td colSpan={4} className="px-6 py-8 text-center text-gray-500">
                    No signals found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
};
