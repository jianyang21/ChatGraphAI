import { useState, useEffect } from 'react'
import GraphView from './components/GraphView'
import ChatPanel from './components/ChatPanel'
import NodeDetail from './components/NodeDetail'
import SearchBar from './components/SearchBar'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

function App() {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] })
  const [selectedNode, setSelectedNode] = useState(null)
  const [highlightNodes, setHighlightNodes] = useState(new Set())
  const [loading, setLoading] = useState(true)
  const [summary, setSummary] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)

  useEffect(() => {
    loadOverview()
    loadSummary()
  }, [])

  async function loadSummary() {
    try {
      const res = await fetch(`${API_BASE}/api/graph/summary`)
      setSummary(await res.json())
    } catch (err) {
      console.error('summary fetch failed', err)
    }
  }

  async function loadOverview() {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/graph/overview`)
      const data = await res.json()
      setGraphData({
        nodes: data.nodes.map(n => ({ ...n, val: nodeSize(n.entity) })),
        links: data.edges.map(e => ({ source: e.source, target: e.target, relation: e.relation })),
      })
    } catch (err) {
      console.error('graph load failed', err)
    }
    setLoading(false)
  }

  async function loadSubgraph(nodeId, depth = 1) {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/graph/subgraph/${encodeURIComponent(nodeId)}?depth=${depth}`)
      const data = await res.json()
      setGraphData({
        nodes: data.nodes.map(n => ({ ...n, val: nodeSize(n.entity) })),
        links: data.edges.map(e => ({ source: e.source, target: e.target, relation: e.relation })),
      })
    } catch (err) {
      console.error('subgraph load failed', err)
    }
    setLoading(false)
  }

  async function handleNodeClick(node) {
    try {
      const res = await fetch(`${API_BASE}/api/graph/node/${encodeURIComponent(node.id)}`)
      setSelectedNode(await res.json())
    } catch (err) {
      console.error('node detail failed', err)
    }
  }

  async function handleSearch(query) {
    try {
      const res = await fetch(`${API_BASE}/api/graph/search?q=${encodeURIComponent(query)}`)
      return await res.json()
    } catch (err) {
      console.error('search failed', err)
      return []
    }
  }

  function handleSearchSelect(node) {
    loadSubgraph(node.id, 1)
    handleNodeClick(node)
  }

  function navigateToNode(nodeId) {
    loadSubgraph(nodeId, 1)
    handleNodeClick({ id: nodeId })
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <span className="logo">CG</span>
          <span className="app-title">ChatGraph AI</span>
          <span className="header-divider">/</span>
          <span className="header-context">Order to Cash</span>
        </div>
        <SearchBar onSearch={handleSearch} onSelect={handleSearchSelect} />
        <div className="header-right">
          {summary && (
            <span className="stats-badge">
              {summary.total_nodes.toLocaleString()} nodes / {summary.total_edges.toLocaleString()} edges
            </span>
          )}
        </div>
      </header>

      <div className="app-body">
        <div className="graph-container">
          <div className="graph-toolbar">
            <button className="toolbar-btn" onClick={loadOverview}>Reset View</button>
            <button className="toolbar-btn" onClick={() => setSidebarOpen(!sidebarOpen)}>
              {sidebarOpen ? 'Hide Chat' : 'Show Chat'}
            </button>
          </div>

          {loading && <div className="loading-overlay">Loading graph data...</div>}

          <GraphView
            graphData={graphData}
            onNodeClick={handleNodeClick}
            highlightNodes={highlightNodes}
          />

          {selectedNode && (
            <NodeDetail
              node={selectedNode}
              onClose={() => setSelectedNode(null)}
              onExpand={(id) => loadSubgraph(id, 1)}
              onNavigate={navigateToNode}
            />
          )}
        </div>

        {sidebarOpen && (
          <div className="sidebar">
            <ChatPanel
              apiBase={API_BASE}
              onHighlightNodes={(ids) => setHighlightNodes(new Set(ids))}
              onNavigateToNode={navigateToNode}
            />
          </div>
        )}
      </div>
    </div>
  )
}

function nodeSize(entity) {
  const sizes = {
    SalesOrder: 4, Customer: 5, BillingDocument: 4,
    Delivery: 3, Product: 3, Plant: 3,
    JournalEntry: 2, Payment: 2,
    SalesOrderItem: 1.5, DeliveryItem: 1.5, BillingDocumentItem: 1.5,
  }
  return sizes[entity] || 2
}

export default App
