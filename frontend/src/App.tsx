import { useState } from 'react';
import { ShieldAlert } from 'lucide-react';
import { Dashboard } from './components/Dashboard';
import { IncidentDetail } from './components/IncidentDetail';
import { RCAForm } from './components/RCAForm';
import type { WorkItem } from './api';

function App() {
  const [selectedIncident, setSelectedIncident] = useState<WorkItem | null>(null);
  const [showRcaForm, setShowRcaForm] = useState(false);

  return (
    <div className="min-h-screen relative overflow-hidden bg-background">
      {/* Background decorations */}
      <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] rounded-full bg-primary/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] rounded-full bg-warning/10 blur-[120px] pointer-events-none" />
      
      {/* Top Navbar */}
      <nav className="relative z-10 glass-panel sticky top-0 w-full border-b border-white/5 py-4 px-6 md:px-12 flex justify-between items-center bg-background/80">
        <div className="flex items-center gap-3">
          <ShieldAlert className="w-8 h-8 text-primary" />
          <h1 className="text-xl font-bold tracking-tight text-white">
            IMS <span className="font-light text-gray-400">| Mission Control</span>
          </h1>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="relative z-10 max-w-7xl mx-auto px-4 md:px-6 py-8 h-full">
        {!selectedIncident ? (
          <Dashboard onSelectIncident={setSelectedIncident} />
        ) : (
          <IncidentDetail 
            item={selectedIncident} 
            onBack={() => setSelectedIncident(null)} 
            onRcaClick={() => setShowRcaForm(true)}
          />
        )}
      </main>

      {/* Overlays */}
      {showRcaForm && selectedIncident && (
        <RCAForm 
          item={selectedIncident} 
          onClose={() => setShowRcaForm(false)} 
          onSuccess={() => {
            setShowRcaForm(false);
            setSelectedIncident(null); // Go back to dashboard to see updated state
          }} 
        />
      )}
    </div>
  );
}

export default App;
