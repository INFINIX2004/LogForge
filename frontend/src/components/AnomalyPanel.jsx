import { useState } from 'react';

// ── Colour helpers ──────────────────────────────────────────────
const confidenceColor = (pct) => {
  if (pct >= 75) return '#d32f2f';   // red   — high confidence
  if (pct >= 40) return '#f57c00';   // orange — medium
  return '#f9a825';                  // amber  — low
};

const confidenceBg = (pct) => {
  if (pct >= 75) return '#ffebee';
  if (pct >= 40) return '#fff3e0';
  return '#fffde7';
};

const serviceColor = (service) => {
  const palette = {
    'payment-api':   '#1565c0',
    'auth-service':  '#2e7d32',
    'inventory':     '#6a1b9a',
    'notification':  '#00838f',
  };
  return palette[service] || '#455a64';
};

// ── Sub-components ──────────────────────────────────────────────
function ServiceSummaryCard({ stat }) {
  return (
    <div style={{
      background: 'white',
      border: `2px solid ${confidenceColor(stat.avg_confidence)}`,
      borderRadius: 10,
      padding: '14px 18px',
      minWidth: 160,
      flex: '1 1 160px',
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', marginBottom: 8
      }}>
        <span style={{
          background: serviceColor(stat.service),
          color: 'white', borderRadius: 5,
          padding: '2px 8px', fontSize: 11, fontWeight: 700
        }}>
          {stat.service}
        </span>
        <span style={{
          background: confidenceBg(stat.avg_confidence),
          color: confidenceColor(stat.avg_confidence),
          borderRadius: 5, padding: '2px 8px',
          fontSize: 11, fontWeight: 700
        }}>
          {stat.avg_confidence.toFixed(0)}% conf
        </span>
      </div>
      <div style={{ fontSize: 28, fontWeight: 800, color: '#212121' }}>
        {stat.anomaly_count}
      </div>
      <div style={{ fontSize: 12, color: '#757575' }}>anomalies this hour</div>
    </div>
  );
}

function AnomalyRow({ anomaly }) {
  const time = new Date(anomaly.detected_at).toLocaleTimeString();
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '10px 14px',
      borderBottom: '1px solid #f0f0f0',
      background: 'white',
      transition: 'background 0.15s',
    }}
      onMouseEnter={e => e.currentTarget.style.background = '#fafafa'}
      onMouseLeave={e => e.currentTarget.style.background = 'white'}
    >
      {/* Time */}
      <span style={{ fontSize: 11, color: '#9e9e9e', minWidth: 70 }}>{time}</span>

      {/* Service badge */}
      <span style={{
        background: serviceColor(anomaly.service),
        color: 'white', borderRadius: 5,
        padding: '2px 8px', fontSize: 11,
        fontWeight: 700, minWidth: 110, textAlign: 'center'
      }}>
        {anomaly.service}
      </span>

      {/* Confidence bar */}
      <div style={{ flex: 1, minWidth: 80 }}>
        <div style={{
          background: '#f0f0f0', borderRadius: 4, height: 8, overflow: 'hidden'
        }}>
          <div style={{
            width: `${Math.min(anomaly.confidence, 100)}%`,
            height: '100%',
            background: confidenceColor(anomaly.confidence),
            borderRadius: 4,
            transition: 'width 0.3s'
          }} />
        </div>
        <div style={{ fontSize: 10, color: '#757575', marginTop: 2 }}>
          {anomaly.confidence.toFixed(0)}% confidence
        </div>
      </div>

      {/* Metrics */}
      <div style={{ display: 'flex', gap: 10, fontSize: 11 }}>
        <span style={{ color: '#d32f2f' }}>
          ✕ {anomaly.error_count} err
        </span>
        <span style={{ color: '#f57c00' }}>
          ⚠ {anomaly.warn_count} warn
        </span>
        <span style={{ color: '#616161' }}>
          ∑ {anomaly.total_logs} total
        </span>
      </div>

      {/* Error ratio pill */}
      <span style={{
        background: confidenceBg(anomaly.error_ratio * 100),
        color: confidenceColor(anomaly.error_ratio * 100),
        borderRadius: 5, padding: '2px 8px',
        fontSize: 11, fontWeight: 600, minWidth: 52, textAlign: 'center'
      }}>
        {(anomaly.error_ratio * 100).toFixed(1)}%
      </span>
    </div>
  );
}

// ── Main Component ──────────────────────────────────────────────
export default function AnomalyPanel({ anomalies, anomalyStats, loading }) {
  const [tab, setTab] = useState('feed'); // 'feed' | 'summary'

  const totalAnomalies = anomalyStats.reduce((s, x) => s + x.anomaly_count, 0);
  const avgConfidence  = anomalyStats.length
    ? (anomalyStats.reduce((s, x) => s + x.avg_confidence, 0) / anomalyStats.length).toFixed(0)
    : 0;

  return (
    <div style={{
      background: '#fafafa',
      border: '1px solid #e0e0e0',
      borderRadius: 12,
      marginBottom: 24,
      overflow: 'hidden',
    }}>

      {/* ── Header ── */}
      <div style={{
        background: 'linear-gradient(135deg, #b71c1c 0%, #d32f2f 100%)',
        padding: '14px 20px',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center'
      }}>
        <div>
          <h2 style={{ margin: 0, color: 'white', fontSize: 16, fontWeight: 700 }}>
            ⚠️ AI Anomaly Detection
          </h2>
          <p style={{ margin: '3px 0 0', color: 'rgba(255,255,255,0.8)', fontSize: 12 }}>
            Isolation Forest · 5 features per service · auto-retraining
          </p>
        </div>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          {/* Live indicator */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{
              width: 8, height: 8, borderRadius: '50%',
              background: loading ? '#ffb300' : '#69f0ae',
              boxShadow: `0 0 6px ${loading ? '#ffb300' : '#69f0ae'}`
            }} />
            <span style={{ color: 'white', fontSize: 11 }}>
              {loading ? 'refreshing' : 'live'}
            </span>
          </div>
          {/* Summary pills */}
          <div style={{
            background: 'rgba(255,255,255,0.15)',
            borderRadius: 8, padding: '6px 14px', textAlign: 'center'
          }}>
            <div style={{ color: 'white', fontSize: 20, fontWeight: 800 }}>
              {totalAnomalies}
            </div>
            <div style={{ color: 'rgba(255,255,255,0.7)', fontSize: 10 }}>
              anomalies / hour
            </div>
          </div>
          <div style={{
            background: 'rgba(255,255,255,0.15)',
            borderRadius: 8, padding: '6px 14px', textAlign: 'center'
          }}>
            <div style={{ color: 'white', fontSize: 20, fontWeight: 800 }}>
              {avgConfidence}%
            </div>
            <div style={{ color: 'rgba(255,255,255,0.7)', fontSize: 10 }}>
              avg confidence
            </div>
          </div>
        </div>
      </div>

      {/* ── Tabs ── */}
      <div style={{
        display: 'flex', borderBottom: '1px solid #e0e0e0',
        background: 'white'
      }}>
        {['feed', 'summary'].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '10px 20px', border: 'none', cursor: 'pointer',
            background: tab === t ? '#fff' : '#fafafa',
            borderBottom: tab === t ? '2px solid #d32f2f' : '2px solid transparent',
            color: tab === t ? '#d32f2f' : '#757575',
            fontWeight: tab === t ? 700 : 400,
            fontSize: 13, textTransform: 'capitalize'
          }}>
            {t === 'feed' ? `Live Feed (${anomalies.length})` : 'By Service'}
          </button>
        ))}
      </div>

      {/* ── Tab: Live Feed ── */}
      {tab === 'feed' && (
        <div>
          {anomalies.length === 0 ? (
            <div style={{
              padding: 40, textAlign: 'center', color: '#9e9e9e'
            }}>
              <div style={{ fontSize: 32, marginBottom: 8 }}>✅</div>
              <div style={{ fontWeight: 600 }}>No anomalies detected recently</div>
              <div style={{ fontSize: 12, marginTop: 4 }}>
                Run the log generator to see anomalies appear here
              </div>
            </div>
          ) : (
            <div style={{ maxHeight: 340, overflowY: 'auto' }}>
              {anomalies.map((a, i) => (
                <AnomalyRow key={i} anomaly={a} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Tab: By Service ── */}
      {tab === 'summary' && (
        <div style={{ padding: 16 }}>
          {anomalyStats.length === 0 ? (
            <div style={{ padding: 24, textAlign: 'center', color: '#9e9e9e' }}>
              No anomaly stats available yet
            </div>
          ) : (
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              {anomalyStats.map((s, i) => (
                <ServiceSummaryCard key={i} stat={s} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
