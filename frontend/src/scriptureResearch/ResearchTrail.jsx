function nodeLabel(node) {
  return node.label || node.question
}

export default function ResearchTrail({ trail, ancestry: ancestryProp, active: activeProp, children: childrenProp, childrenTruncated: truncatedProp, onSelectNode }) {
  const active = activeProp ?? trail?.active
  const children = childrenProp ?? trail?.children ?? []
  const childrenTruncated = truncatedProp ?? trail?.childrenTruncated ?? false
  if (!active) return null
  const ancestry = (ancestryProp ?? trail?.ancestry ?? []).filter((node) => node.id !== active.id)
  return (
    <nav className="research-trail" aria-label="Research trail">
      <ol>
        {[...ancestry, active].map((node) => (
          <li key={node.id}>
            <button
              type="button"
              aria-current={node.id === active.id ? 'page' : undefined}
              onClick={() => onSelectNode?.(node)}
            >
              {nodeLabel(node)}
            </button>
          </li>
        ))}
      </ol>
      {children.length > 0 && (
        <section aria-labelledby="research-trail-branches">
          <h2 id="research-trail-branches">Branches</h2>
          <ul>{children.map((node) => (
            <li key={node.id}><button type="button" onClick={() => onSelectNode?.(node)}>{nodeLabel(node)}</button></li>
          ))}</ul>
        </section>
      )}
      {childrenTruncated && <p className="research-trail__truncated">Additional branches are not shown.</p>}
    </nav>
  )
}
