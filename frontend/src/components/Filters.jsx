import React from 'react';

export default function Filters({ filters, setFilters, services }) {
  return (
    <div style={{ 
      display: 'flex', 
      gap: '10px', 
      marginBottom: '20px',
      padding: '15px',
      backgroundColor: '#f5f5f5',
      borderRadius: '8px'
    }}>
      <select 
        value={filters.service}
        onChange={(e) => setFilters({...filters, service: e.target.value})}
        style={{ padding: '8px', borderRadius: '4px', border: '1px solid #ddd' }}
      >
        <option value="">All Services</option>
        {services.map(s => <option key={s} value={s}>{s}</option>)}
      </select>
      
      <select 
        value={filters.level}
        onChange={(e) => setFilters({...filters, level: e.target.value})}
        style={{ padding: '8px', borderRadius: '4px', border: '1px solid #ddd' }}
      >
        <option value="">All Levels</option>
        <option value="ERROR">ERROR</option>
        <option value="WARN">WARN</option>
        <option value="INFO">INFO</option>
        <option value="DEBUG">DEBUG</option>
      </select>
      
      <input
        type="text"
        placeholder="Search message..."
        value={filters.search}
        onChange={(e) => setFilters({...filters, search: e.target.value})}
        style={{ 
          flex: 1, 
          padding: '8px', 
          borderRadius: '4px', 
          border: '1px solid #ddd' 
        }}
      />

      <select
        value={filters.timeRange}
        onChange={(e) => setFilters({...filters, timeRange: e.target.value})}
        style={{ padding: '8px', borderRadius: '4px', border: '1px solid #ddd' }}
      >
        <option value="1h">Last 1 Hour</option>
        <option value="6h">Last 6 Hours</option>
        <option value="24h">Last 24 Hours</option>
        <option value="7d">Last 7 Days</option>
      </select>
    </div>
  );
}