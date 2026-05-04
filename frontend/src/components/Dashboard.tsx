import React, { useEffect, useState } from 'react';
import { Activity, AlertTriangle, CheckCircle, Clock } from 'lucide-react';
import { fetchWorkItems, fetchHealth, type WorkItem, type Health } from '../api';
import clsx from 'clsx';
import { formatDistanceToNow } from 'date-fns';

interface DashboardProps {
  onSelectIncident: (item: WorkItem) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ onSelectIncident }) => {
  const [items, setItems] = useState<WorkItem[]>([]);
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [itemsData, healthData] = await Promise.all([
          fetchWorkItems(),
          fetchHealth()
        ]);
        setItems(itemsData);
        setHealth(healthData);
      } catch (e) {
        console.error("Failed to load data", e);
      }
    };
    
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'P0': return 'bg-danger text-white border-danger';
      case 'P1': return 'bg-warning text-white border-warning';
      case 'P2': return 'bg-blue-500 text-white border-blue-500';
      default: return 'bg-gray-600 text-white border-gray-600';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'OPEN': return <AlertTriangle className="w-4 h-4 text-warning" />;
      case 'INVESTIGATING': return <Activity className="w-4 h-4 text-primary" />;
      case 'RESOLVED': return <CheckCircle className="w-4 h-4 text-success" />;
      case 'CLOSED': return <CheckCircle className="w-4 h-4 text-gray-500" />;
      default: return <Clock className="w-4 h-4 text-gray-400" />;
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700">
      
      {/* Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="glass-panel rounded-xl p-5 flex flex-col items-center justify-center">
          <span className="text-gray-400 text-sm font-medium uppercase tracking-wider mb-2">System Health</span>
          <div className="flex items-center gap-2">
            <div className={clsx("w-3 h-3 rounded-full animate-pulse", health?.status === 'healthy' ? 'bg-success' : 'bg-danger')} />
            <span className="text-xl font-bold">{health?.status || 'Unknown'}</span>
          </div>
        </div>
        <div className="glass-panel rounded-xl p-5 flex flex-col items-center justify-center">
          <span className="text-gray-400 text-sm font-medium uppercase tracking-wider mb-2">Throughput</span>
          <span className="text-3xl font-bold text-primary">{health?.signals_per_sec.toFixed(1) || '0'} <span className="text-base font-normal text-gray-500">sig/s</span></span>
        </div>
        <div className="glass-panel rounded-xl p-5 flex flex-col items-center justify-center">
          <span className="text-gray-400 text-sm font-medium uppercase tracking-wider mb-2">Active Incidents</span>
          <span className="text-3xl font-bold text-warning">{items.filter(i => i.status !== 'CLOSED').length}</span>
        </div>
        <div className="glass-panel rounded-xl p-5 flex flex-col items-center justify-center">
          <span className="text-gray-400 text-sm font-medium uppercase tracking-wider mb-2">PG Pool Size</span>
          <span className="text-3xl font-bold text-gray-300">{health?.pg_pool_size || '0'}</span>
        </div>
      </div>

      {/* Incident List */}
      <div className="glass-panel rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-white/5 flex justify-between items-center bg-white/5">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Activity className="w-5 h-5 text-primary" />
            Live Feed
          </h2>
          <span className="text-xs text-gray-400 flex items-center gap-1">
            <div className="w-2 h-2 rounded-full bg-success animate-pulse" /> Live updates
          </span>
        </div>
        <div className="divide-y divide-white/5 max-h-[600px] overflow-y-auto custom-scrollbar">
          {items.map(item => (
            <div 
              key={item.id} 
              onClick={() => onSelectIncident(item)}
              className="px-6 py-4 hover:bg-white/5 cursor-pointer transition-colors group flex items-center gap-4"
            >
              <div className={clsx("px-2 py-1 rounded text-xs font-bold border", getSeverityColor(item.severity))}>
                {item.severity}
              </div>
              
              <div className="flex-1">
                <h3 className="font-semibold text-gray-100 group-hover:text-primary transition-colors">{item.title}</h3>
                <div className="text-sm text-gray-400 mt-1 flex items-center gap-4">
                  <span className="flex items-center gap-1">
                    <Activity className="w-3 h-3" /> {item.signal_count} signals
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" /> Started {formatDistanceToNow(new Date(item.first_signal_at), { addSuffix: true })}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-black/30 border border-white/5">
                {getStatusIcon(item.status)}
                <span className="text-sm font-medium">{item.status}</span>
              </div>
            </div>
          ))}
          
          {items.length === 0 && (
            <div className="px-6 py-12 text-center text-gray-500">
              <CheckCircle className="w-12 h-12 mx-auto mb-3 opacity-20" />
              <p>No incidents active. System is running smoothly.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
