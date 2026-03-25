import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'

export default function ChatPanel({ apiBase, onHighlightNodes, onNavigateToNode }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Welcome to **ChatGraph AI**. I can help you explore the Order to Cash process — ask me about sales orders, deliveries, billing, payments, or products.',
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSubmit(e) {
    e.preventDefault()
    const query = input.trim()
    if (!query || loading) return

    setMessages(prev => [...prev, { role: 'user', content: query }])
    setInput('')
    setLoading(true)

    try {
      const history = messages
        .filter(m => m.role !== 'system')
        .slice(-6)
        .map(m => ({ role: m.role, content: m.content }))

      const res = await fetch(`${apiBase}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: query, conversation_history: history }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Request failed' }))
        throw new Error(err.detail || 'Something went wrong')
      }

      const data = await res.json()

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.answer,
        sql: data.sql_query,
        results: data.query_results,
        referencedNodes: data.referenced_nodes,
      }])

      if (data.referenced_nodes?.length > 0) {
        onHighlightNodes(data.referenced_nodes)
      }
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: `Something went wrong: ${err.message}` }])
    }

    setLoading(false)
  }

  const examples = [
    'Which products have the most billing documents?',
    'Trace the full flow of sales order 1',
    'Find orders delivered but not billed',
    'Show top 5 customers by total billing amount',
  ]

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <h3>ChatGraph AI</h3>
        <span className="chat-subtitle">Query the O2C graph</span>
      </div>

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-msg chat-msg-${msg.role}`}>
            {msg.role === 'assistant' && (
              <div className="msg-avatar">
                <span className="avatar-icon">CG</span>
                <div className="msg-meta">
                  <span className="msg-name">ChatGraph AI</span>
                </div>
              </div>
            )}
            {msg.role === 'user' && (
              <div className="msg-avatar msg-avatar-user">
                <div className="msg-meta">
                  <span className="msg-name">You</span>
                </div>
                <span className="avatar-icon avatar-user">U</span>
              </div>
            )}
            <div className="msg-content">
              <ReactMarkdown>{msg.content}</ReactMarkdown>

              {msg.sql && (
                <details className="sql-details">
                  <summary>View SQL</summary>
                  <pre className="sql-code">{msg.sql}</pre>
                </details>
              )}

              {msg.results?.length > 0 && (
                <details className="results-details">
                  <summary>Results ({msg.results.length} rows)</summary>
                  <div className="results-table-wrap">
                    <table className="results-table">
                      <thead>
                        <tr>
                          {Object.keys(msg.results[0]).map(col => (
                            <th key={col}>{col}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {msg.results.slice(0, 20).map((row, ri) => (
                          <tr key={ri}>
                            {Object.values(row).map((val, ci) => (
                              <td key={ci}>{val}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              )}

              {msg.referencedNodes?.length > 0 && (
                <div className="referenced-nodes">
                  {msg.referencedNodes.slice(0, 8).map(nodeId => (
                    <button
                      key={nodeId}
                      className="node-chip"
                      onClick={() => onNavigateToNode(nodeId)}
                    >
                      {nodeId.split(':')[1]}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="chat-msg chat-msg-assistant">
            <div className="msg-avatar">
              <span className="avatar-icon">CG</span>
            </div>
            <div className="msg-content">
              <div className="typing-indicator">
                <span /><span /><span />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {messages.length <= 1 && (
        <div className="example-queries">
          {examples.map((q, i) => (
            <button key={i} className="example-btn" onClick={() => { setInput(q); inputRef.current?.focus() }}>
              {q}
            </button>
          ))}
        </div>
      )}

      <form className="chat-input-form" onSubmit={handleSubmit}>
        <div className="chat-input-wrap">
          <div className="input-status">
            <span className="status-dot" />
            <span>Ready</span>
          </div>
          <input
            ref={inputRef}
            type="text"
            className="chat-input"
            placeholder="Ask about orders, deliveries, billing..."
            value={input}
            onChange={e => setInput(e.target.value)}
            disabled={loading}
          />
          <button type="submit" className="send-btn" disabled={loading || !input.trim()}>
            Send
          </button>
        </div>
      </form>
    </div>
  )
}
