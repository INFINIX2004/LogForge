import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { format } from 'date-fns';

export default function StatsChart({ stats }) {
  if (!stats || stats.length === 0) {
    return null;
  }

  // Group by hour
  const grouped = stats.reduce((acc, item) => {
    const key = item.hour;
    if (!acc[key]) {
      acc[key] = { hour: key, ERROR: 0, WARN: 0, INFO: 0, DEBUG: 0 };
    }
    acc[key][item.level] = item.count;
    return acc;
  }, {});

  const chartData = Object.values(grouped).map(item => ({
    ...item,
    hour: format(new Date(item.hour), 'HH:mm')
  }));

  return (
    <div style={{ 
      backgroundColor: '#fff', 
      padding: '20px', 
      borderRadius: '8px',
      marginBottom: '20px',
      boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
    }}>
      <h3 style={{ marginTop: 0 }}>Log Volume Over Time</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="hour" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="ERROR" stroke="#f44336" strokeWidth={2} />
          <Line type="monotone" dataKey="WARN" stroke="#ff9800" strokeWidth={2} />
          <Line type="monotone" dataKey="INFO" stroke="#2196f3" strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}