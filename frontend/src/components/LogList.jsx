import React from 'react';
import { format } from 'date-fns';

export default function LogList({ logs, loading }) {
  if (loading) {
    return <div style={{ textAlign: 'center', padding: '40px' }}>Loading...</div>;
  }

  if (logs.length === 0) {
    return <div style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
      No logs found
    </div>;
  }

  const getLevelColor = (level) => {
    switch(level) {
      case 'ERROR': return '#ffebee';
      case 'WARN': return '#fff3e0';
      case 'INFO': return '#e3f2fd';
      default: return '#f5f5f5';
    }
  };

  const getLevelBorder = (level) => {
    switch(level) {
      case 'ERROR': return '#f44336';
      case 'WARN': return '#ff9800';
      case 'INFO': return '#2196f3';
      default: return '#9e9e9e';
    }
  };

  return (
    <div>
      <div style={{ marginBottom: '10px', color: '#666' }}>
        Showing {logs.length} logs
      </div>
      
      {logs.map((log, i) => (
        <div 
          key={i} 
          style={{
            padding: '12px',
            marginBottom: '8px',
            backgroundColor: getLevelColor(log.level),
            borderLeft: `4px solid ${getLevelBorder(log.level)}`,
            borderRadius: '4px',
            fontFamily: 'monospace',
            fontSize: '13px'
          }}
        >
          <div style={{ marginBottom: '5px', color: '#666', fontSize: '11px' }}>
            <strong>{format(new Date(log.timestamp), 'yyyy-MM-dd HH:mm:ss.SSS')}</strong>
            {' | '}
            <span style={{ 
              fontWeight: 'bold',
              color: getLevelBorder(log.level)
            }}>
              {log.level}
            </span>
            {' | '}
            {log.service}
            {' | '}
            {log.host}
          </div>
          
          <div style={{ marginBottom: '5px' }}>
            {log.message}
          </div>
          
          {(log.trace_id || log.user_id) && (
            <div style={{ fontSize: '11px', color: '#999' }}>
              {log.trace_id && <span>trace: {log.trace_id} </span>}
              {log.user_id && <span>user: {log.user_id}</span>}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}