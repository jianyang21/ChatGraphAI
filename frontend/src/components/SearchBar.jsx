import { useState, useRef, useEffect } from 'react'

export default function SearchBar({ onSearch, onSelect }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const wrapRef = useRef(null)
  const timer = useRef(null)

  useEffect(() => {
    function onClickOutside(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  function handleInput(e) {
    const val = e.target.value
    setQuery(val)
    clearTimeout(timer.current)
    if (val.trim().length < 2) {
      setResults([])
      setOpen(false)
      return
    }
    timer.current = setTimeout(async () => {
      const res = await onSearch(val.trim())
      setResults(res || [])
      setOpen(true)
    }, 300)
  }

  function pick(node) {
    setQuery('')
    setResults([])
    setOpen(false)
    onSelect(node)
  }

  return (
    <div className="search-bar" ref={wrapRef}>
      <input
        type="text"
        className="search-input"
        placeholder="Search nodes..."
        value={query}
        onChange={handleInput}
        onFocus={() => results.length > 0 && setOpen(true)}
      />
      {open && results.length > 0 && (
        <div className="search-dropdown">
          {results.map(node => (
            <button key={node.id} className="search-result" onClick={() => pick(node)}>
              <span className="sr-entity">{node.entity}</span>
              <span className="sr-label">{node.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
