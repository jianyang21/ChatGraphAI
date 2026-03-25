export default function NodeDetail({ node, onClose, onExpand, onNavigate }) {
  if (!node) return null

  const props = Object.entries(node.properties || {}).filter(
    ([k, v]) => v != null && v !== '' && k !== 'entity'
  )

  return (
    <div className="node-detail">
      <div className="node-detail-header">
        <h3>{node.entity}</h3>
        <button className="close-btn" onClick={onClose}>x</button>
      </div>

      <div className="node-detail-body">
        {props.slice(0, 12).map(([key, val]) => (
          <div key={key} className="prop-row">
            <span className="prop-key">{prettyKey(key)}</span>
            <span className="prop-val">{prettyVal(val)}</span>
          </div>
        ))}
        {props.length > 12 && (
          <div className="prop-row prop-hidden">
            <em>+{props.length - 12} more fields</em>
          </div>
        )}

        <div className="node-connections">
          Connections: {node.connection_count}
        </div>

        <div className="node-actions">
          <button className="btn-expand" onClick={() => onExpand(node.id)}>
            Expand Connections
          </button>
        </div>

        {node.connections?.length > 0 && (
          <div className="connection-list">
            <h4>Linked Entities</h4>
            {node.connections.slice(0, 15).map((conn, i) => (
              <button key={i} className="connection-item" onClick={() => onNavigate(conn.id)}>
                <span className={`conn-dir ${conn.direction}`}>
                  {conn.direction === 'outgoing' ? '->' : '<-'}
                </span>
                <span className="conn-relation">{conn.relation}</span>
                <span className="conn-label">{conn.label}</span>
              </button>
            ))}
            {node.connections.length > 15 && (
              <div className="more-connections">
                +{node.connections.length - 15} more
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function prettyKey(key) {
  return key.replace(/([A-Z])/g, ' $1').replace(/^./, s => s.toUpperCase()).trim()
}

function prettyVal(val) {
  if (typeof val === 'string' && val.match(/^\d{4}-\d{2}-\d{2}T/)) {
    return val.split('T')[0]
  }
  return String(val)
}
