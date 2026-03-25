import { useRef, useCallback, useEffect } from 'react'
import ForceGraph2D from 'react-force-graph-2d'

const COLORS = {
  SalesOrder: '#3B82F6',
  SalesOrderItem: '#60A5FA',
  Delivery: '#0D9488',
  DeliveryItem: '#2DD4BF',
  BillingDocument: '#E11D48',
  BillingDocumentItem: '#FB7185',
  JournalEntry: '#CA8A04',
  Payment: '#16A34A',
  Customer: '#7C3AED',
  Product: '#EA580C',
  Plant: '#475569',
}

export default function GraphView({ graphData, onNodeClick, highlightNodes }) {
  const fgRef = useRef()

  useEffect(() => {
    if (!fgRef.current) return
    fgRef.current.d3Force('charge').strength(-80)
    fgRef.current.d3Force('link').distance(60)
  }, [])

  const drawNode = useCallback((node, ctx, globalScale) => {
    const highlighted = highlightNodes.has(node.id)
    const r = (node.val || 2) * 2

    ctx.beginPath()
    ctx.arc(node.x, node.y, r, 0, Math.PI * 2)
    ctx.fillStyle = highlighted ? '#FBBF24' : (COLORS[node.entity] || '#94A3B8')
    ctx.fill()

    if (highlighted) {
      ctx.strokeStyle = '#F59E0B'
      ctx.lineWidth = 2
      ctx.stroke()
    }

    if (globalScale > 1.5) {
      const fs = Math.max(10 / globalScale, 1.5)
      ctx.font = `${fs}px Inter, sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'top'
      ctx.fillStyle = '#374151'
      ctx.fillText(node.label || '', node.x, node.y + r + 2)
    }
  }, [highlightNodes])

  const drawLink = useCallback((link, ctx) => {
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.25)'
    ctx.lineWidth = 0.5
    ctx.beginPath()
    ctx.moveTo(link.source.x, link.source.y)
    ctx.lineTo(link.target.x, link.target.y)
    ctx.stroke()
  }, [])

  return (
    <div className="graph-view">
      <ForceGraph2D
        ref={fgRef}
        graphData={graphData}
        nodeCanvasObject={drawNode}
        linkCanvasObject={drawLink}
        onNodeClick={onNodeClick}
        nodeId="id"
        cooldownTicks={100}
        warmupTicks={50}
        backgroundColor="#F8FAFC"
        minZoom={0.3}
        maxZoom={10}
      />
      <div className="graph-legend">
        {Object.entries(COLORS).map(([name, color]) => (
          <div key={name} className="legend-item">
            <span className="legend-dot" style={{ backgroundColor: color }} />
            <span>{name}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
