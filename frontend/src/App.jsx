import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Activity, Database, AlertCircle, CheckCircle, Search, Save, Play, Trash2 } from 'lucide-react';

const API_BASE = 'http://localhost:8000/api';

function App() {
  const [hdfsStatus, setHdfsStatus] = useState({ checked: false, connected: false, message: 'Checking HDFS...' });
  const [ingesting, setIngesting] = useState(false);
  const [randomSplit, setRandomSplit] = useState(false);
  const [metrics, setMetrics] = useState(null);
  const [queries, setQueries] = useState([]);
  const [currentQueryName, setCurrentQueryName] = useState('');
  const [currentQuerySql, setCurrentQuerySql] = useState('');
  const [queryResults, setQueryResults] = useState(null);
  const [queryError, setQueryError] = useState(null);
  const [querying, setQuerying] = useState(false);

  useEffect(() => {
    checkHdfs();
    fetchQueries();
  }, []);

  const checkHdfs = async () => {
    try {
      const res = await axios.get(`${API_BASE}/hdfs-status`);
      setHdfsStatus({ checked: true, connected: res.data.status === 'connected', message: res.data.message });
    } catch (err) {
      setHdfsStatus({ checked: true, connected: false, message: 'Could not connect to Backend server.' });
    }
  };

  const fetchQueries = async () => {
    try {
      const res = await axios.get(`${API_BASE}/queries`);
      setQueries(res.data.queries);
    } catch (err) {
      console.error("Failed to load queries", err);
    }
  };

  const handleIngest = async () => {
    setIngesting(true);
    try {
      const res = await axios.post(`${API_BASE}/ingest?random_split=${randomSplit}`);
      setMetrics(res.data.metrics);
    } catch (err) {
      alert(err.response?.data?.detail || "Ingestion failed");
    } finally {
      setIngesting(false);
    }
  };

  const executeQuery = async (sqlToRun = currentQuerySql) => {
    if (!sqlToRun) return;
    setQuerying(true);
    setQueryError(null);
    setQueryResults(null);
    try {
      const res = await axios.post(`${API_BASE}/query`, { query: sqlToRun });
      setQueryResults(res.data);
    } catch (err) {
      setQueryError(err.response?.data?.detail || "Query failed");
    } finally {
      setQuerying(false);
    }
  };

  const saveQuery = async () => {
    if (!currentQueryName || !currentQuerySql) return alert("Need name and SQL");
    try {
      await axios.post(`${API_BASE}/queries`, { name: currentQueryName, query: currentQuerySql });
      fetchQueries();
      alert("Saved!");
    } catch (err) {
      alert("Failed to save");
    }
  };

  const deleteQuery = async (name, e) => {
    e.stopPropagation();
    try {
      await axios.delete(`${API_BASE}/queries/${name}`);
      fetchQueries();
    } catch (err) {
      alert("Failed to delete");
    }
  };

  const loadQuery = (q) => {
    setCurrentQueryName(q.name);
    setCurrentQuerySql(q.query);
  };

  return (
    <div className="app-container">
      {/* SIDEBAR */}
      <div className="sidebar">
        <div className="sidebar-header">Shipment Analytics</div>
        <div className="nav-group">
          <div className="nav-title">Operations</div>
          <div className="nav-item active"><Activity size={18} /> Dashboard</div>
          <div className="nav-item"><Database size={18} /> Data Explorer</div>
        </div>
      </div>

      {/* MAIN CONTENT */}
      <div className="main-content">
        <div className="topbar">
          <h1>Dashboard Overview</h1>
          <div style={{color: 'var(--text-secondary)'}}>System Administrator</div>
        </div>

        <div className="content-area">
          
          {/* HDFS Banner */}
          {hdfsStatus.checked && (
            <div className={`status-banner ${hdfsStatus.connected ? 'success' : 'error'}`}>
              {hdfsStatus.connected ? <CheckCircle size={24} /> : <AlertCircle size={24} />}
              <div>
                <strong>{hdfsStatus.connected ? 'HDFS Connected' : 'HDFS Disconnected'}</strong>
                <div style={{fontSize: '0.875rem', marginTop: '4px'}}>{hdfsStatus.message}</div>
              </div>
              <div style={{marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '15px'}}>
                <label style={{display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.875rem', cursor: 'pointer'}}>
                  <input 
                    type="checkbox" 
                    checked={randomSplit} 
                    onChange={e => setRandomSplit(e.target.checked)} 
                    disabled={!hdfsStatus.connected || ingesting}
                  />
                  Randomize Split
                </label>
                <button 
                  className={`btn ${hdfsStatus.connected ? 'btn-success' : 'btn-danger'}`} 
                  onClick={handleIngest}
                  disabled={!hdfsStatus.connected || ingesting}
                >
                  {ingesting ? 'Processing...' : 'Ingest & Process Data'}
                </button>
              </div>
            </div>
          )}

          {/* Metrics Grid (only if ingested) */}
          {metrics && (
            <>
              <h2 style={{fontSize: '1rem', marginBottom: '15px'}}>Machine Learning Metrics (Logistic Regression)</h2>
              <div className="card-grid">
                <div className="card primary">
                  <div className="card-title">Processed Rows</div>
                  <div className="card-value">{metrics.total_rows.toLocaleString()}</div>
                </div>
                <div className="card success">
                  <div className="card-title">Accuracy</div>
                  <div className="card-value">{(metrics.accuracy * 100).toFixed(2)}%</div>
                </div>
                <div className="card warning">
                  <div className="card-title">Recall</div>
                  <div className="card-value">{(metrics.recall * 100).toFixed(2)}%</div>
                </div>
                <div className="card">
                  <div className="card-title">F1 Score</div>
                  <div className="card-value">{(metrics.f1 * 100).toFixed(2)}%</div>
                </div>
              </div>

              {/* SQL Console Section */}
              <div className="query-section">
                {/* Predefined queries list */}
                <div className="query-list">
                  <div className="query-list-header">Saved Queries</div>
                  {queries.map(q => (
                    <div className="query-list-item" key={q.name} onClick={() => loadQuery(q)}>
                      <span>{q.name}</span>
                      <Trash2 size={16} style={{color: 'var(--text-secondary)'}} onClick={(e) => deleteQuery(q.name, e)} />
                    </div>
                  ))}
                  {queries.length === 0 && <div style={{padding: 15, fontSize: '0.875rem'}}>No queries saved.</div>}
                </div>

                {/* Console Editor */}
                <div className="query-console">
                  <div style={{display: 'flex', gap: 10}}>
                    <input 
                      type="text" 
                      placeholder="Query Name (for saving)" 
                      value={currentQueryName} 
                      onChange={e => setCurrentQueryName(e.target.value)}
                      style={{padding: '10px', borderRadius: '6px', border: '1px solid var(--border-color)', flex: 1}}
                    />
                  </div>
                  <textarea 
                    className="query-textarea"
                    placeholder="Enter Spark SQL query here (e.g. SELECT * FROM shipments)"
                    value={currentQuerySql}
                    onChange={e => setCurrentQuerySql(e.target.value)}
                  />
                  <div className="query-actions">
                    <button className="btn btn-primary" onClick={() => executeQuery()} disabled={querying}>
                      <Play size={16} style={{display: 'inline', verticalAlign: 'text-bottom', marginRight: 5}}/>
                      {querying ? 'Running...' : 'Execute Query'}
                    </button>
                    <button className="btn" style={{backgroundColor: '#e5e7eb'}} onClick={saveQuery}>
                      <Save size={16} style={{display: 'inline', verticalAlign: 'text-bottom', marginRight: 5}}/>
                      Save
                    </button>
                  </div>

                  {/* Results */}
                  {queryError && (
                    <div style={{color: 'var(--danger-color)', padding: 10, background: '#fef2f2', borderRadius: 6}}>
                      Error: {queryError}
                    </div>
                  )}

                  {queryResults && (
                    <div className="table-container">
                      <table>
                        <thead>
                          <tr>
                            {queryResults.columns.map(c => <th key={c}>{c}</th>)}
                          </tr>
                        </thead>
                        <tbody>
                          {queryResults.data.map((row, i) => (
                            <tr key={i}>
                              {queryResults.columns.map(c => <td key={c}>{row[c]?.toString()}</td>)}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {queryResults.data.length === 0 && <div style={{padding: 15}}>No results found.</div>}
                    </div>
                  )}
                </div>
              </div>
            </>
          )}

        </div>
      </div>
    </div>
  )
}

export default App
