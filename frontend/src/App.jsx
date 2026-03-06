import { useState, useEffect } from 'react';
import { logsAPI } from './api/client';
import Filters from './components/Filters';
import LogList from './components/LogList';
import StatsChart from './components/StatsChart';
import AnomalyPanel from './components/AnomalyPanel';
import './App.css';

function App() {
  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState([]);
  const [services, setServices] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [anomalyStats, setAnomalyStats] = useState([]);
  const [loading, setLoading] = useState(false);
  const [anomalyLoading, setAnomalyLoading] = useState(false);
  const [filters, setFilters] = useState({
    service: '',
    level: '',
    search: '',
    timeRange: '1h'
  });

  // Load services on mount
  useEffect(() => {
    logsAPI.services()
      .then(res => setServices(res.data.services))
      .catch(err => console.error('Failed to load services:', err));
  }, []);

  // Fetch everything when filters change
  useEffect(() => {
    fetchLogs();
    fetchStats();
    fetchAnomalies();
  }, [filters]);

  // Auto-refresh every 10 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      fetchLogs();
      fetchStats();
      fetchAnomalies();
    }, 10000);
    return () => clearInterval(interval);
  }, [filters]);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const params = {};
      if (filters.service) params.service = filters.service;
      if (filters.level)   params.level   = filters.level;
      if (filters.search)  params.search  = filters.search;
      const res = await logsAPI.search(params);
      setLogs(res.data.logs);
    } catch (err) {
      console.error('Failed to fetch logs:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const hours = filters.timeRange === '1h'  ? 1  :
                    filters.timeRange === '6h'  ? 6  :
                    filters.timeRange === '24h' ? 24 : 168;
      const params = { hours };
      if (filters.service) params.service = filters.service;
      const res = await logsAPI.stats(params);
      setStats(res.data.stats);
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  };

  const fetchAnomalies = async () => {
    setAnomalyLoading(true);
    try {
      const hours = filters.timeRange === '1h'  ? 1  :
                    filters.timeRange === '6h'  ? 6  :
                    filters.timeRange === '24h' ? 24 : 168;

      const params = { hours, limit: 50 };
      if (filters.service) params.service = filters.service;

      const [feedRes, statsRes] = await Promise.all([
        logsAPI.anomalies(params),
        logsAPI.anomalyStats({ hours }),
      ]);

      setAnomalies(feedRes.data.anomalies);
      setAnomalyStats(statsRes.data.stats);
    } catch (err) {
      console.error('Failed to fetch anomalies:', err);
    } finally {
      setAnomalyLoading(false);
    }
  };

  return (
    <div className="app">
      <header style={{
        backgroundColor: '#1976d2',
        color: 'white',
        padding: '20px',
        marginBottom: '20px'
      }}>
        <h1 style={{ margin: 0 }}>🔍 AI-Powered Log Observability Platform</h1>
        <p style={{ margin: '5px 0 0 0', opacity: 0.9 }}>
          Real-time log monitoring · Isolation Forest anomaly detection · Auto-retraining
        </p>
      </header>

      <div style={{ padding: '0 20px' }}>

        {/* ── AI Anomaly Panel — sits above everything ── */}
        <AnomalyPanel
          anomalies={anomalies}
          anomalyStats={anomalyStats}
          loading={anomalyLoading}
        />

        {/* ── Existing components unchanged ── */}
        <StatsChart stats={stats} />

        <Filters
          filters={filters}
          setFilters={setFilters}
          services={services}
        />

        <LogList logs={logs} loading={loading} />
      </div>
    </div>
  );
}

export default App;
