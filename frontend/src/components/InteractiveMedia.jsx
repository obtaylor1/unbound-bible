import { useState } from 'react'
import './InteractiveMedia.css'
import { 
  MOCK_BIBLE_BOOKS, 
  MOCK_PSALMS_CATEGORIES, 
  MOCK_TIMELINE_EVENTS, 
  MOCK_ARCHAEOLOGICAL_SLIDES,
  MOCK_CANON_MATRIX 
} from '../data/mockData'

function InteractiveMedia() {
  const [activePanel, setActivePanel] = useState('books') // 'books', 'psalms', 'archaeology', 'timeline', 'canon'

  // Books Explorer States
  const [hoveredBook, setHoveredBook] = useState(null)
  
  // Psalms Explorer States
  const [activePsalmCategory, setActivePsalmCategory] = useState(MOCK_PSALMS_CATEGORIES[0].category)

  // Archaeology Slider States
  const [activeSlideId, setActiveSlideId] = useState('temple_mount')
  const [sliderPosition, setSliderPosition] = useState(50) // percentage 0 to 100

  const activeSlide = MOCK_ARCHAEOLOGICAL_SLIDES.find(s => s.id === activeSlideId)

  return (
    <div className="interactive-media glass-panel">
      <div className="media-header">
        <span className="media-badge">🎨 SCHOLARLY GRAPHICS</span>
        <h2>Interactive Media Explorer</h2>
        <p className="subtitle">
          Visual and interactive research aids connecting literary structures, geography, and archaeological sites.
        </p>
      </div>

      {/* Selector Tabs */}
      <div className="media-navigation-bar">
        <button className={`nav-btn ${activePanel === 'books' ? 'active' : ''}`} onClick={() => setActivePanel('books')}>
          📚 Books Explorer
        </button>
        <button className={`nav-btn ${activePanel === 'psalms' ? 'active' : ''}`} onClick={() => setActivePanel('psalms')}>
          🎻 Psalms Explorer
        </button>
        <button className={`nav-btn ${activePanel === 'archaeology' ? 'active' : ''}`} onClick={() => setActivePanel('archaeology')}>
          🏛️ Archaeology Slider
        </button>
        <button className={`nav-btn ${activePanel === 'timeline' ? 'active' : ''}`} onClick={() => setActivePanel('timeline')}>
          ⏰ Historical Timeline
        </button>
        <button className={`nav-btn ${activePanel === 'canon' ? 'active' : ''}`} onClick={() => setActivePanel('canon')}>
          📋 Canon Matrix
        </button>
      </div>

      {/* Main Panel Content */}
      <div className="media-workspace-content">

        {/* 1. BIBLE BOOKS EXPLORER */}
        {activePanel === 'books' && (
          <div className="books-explorer-panel">
            <h3>Library of Scripture Books</h3>
            <p className="instructions">Hover over or click a book group to explore genres, structures, and canonical classifications.</p>
            
            <div className="books-grid-layout">
              {MOCK_BIBLE_BOOKS.map((group) => (
                <div 
                  key={group.id} 
                  className="book-genre-group" 
                  style={{ borderTop: `4px solid ${group.color}` }}
                  onMouseEnter={() => setHoveredBook(group)}
                  onMouseLeave={() => setHoveredBook(null)}
                >
                  <span className="genre-title" style={{ color: group.color }}>{group.name}</span>
                  <span className="genre-subtitle">{group.genre}</span>
                  <div className="books-pills">
                    {group.books.map((book) => (
                      <span 
                        key={book} 
                        className={`book-pill ${hoveredBook?.books.includes(book) ? 'highlighted' : ''}`}
                      >
                        {book}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {hoveredBook && (
              <div className="genre-details-tooltip info-glass">
                <h4>{hoveredBook.name}</h4>
                <p><strong>Genre:</strong> {hoveredBook.genre}</p>
                <p>This category forms the primary literary foundation for the {hoveredBook.name.toLowerCase()} collections.</p>
              </div>
            )}
          </div>
        )}

        {/* 2. PSALMS EXPLORER */}
        {activePanel === 'psalms' && (
          <div className="psalms-explorer-panel">
            <h3>Psalms Structural Categorization</h3>
            <div className="psalms-split-layout">
              
              {/* Left Column: Categories list */}
              <div className="psalms-categories-list">
                {MOCK_PSALMS_CATEGORIES.map((cat) => (
                  <button 
                    key={cat.category}
                    className={`psalm-cat-card ${activePsalmCategory === cat.category ? 'active' : ''}`}
                    onClick={() => setActivePsalmCategory(cat.category)}
                  >
                    <div className="cat-header">
                      <h4>{cat.category}</h4>
                      <span className="cat-percentage">{cat.percent}% of Book</span>
                    </div>
                    <p>{cat.description}</p>
                  </button>
                ))}
              </div>

              {/* Right Column: Active Category Details */}
              <div className="psalms-category-details glass-panel">
                {activePsalmCategory && (
                  <div className="cat-details">
                    <h3>{activePsalmCategory} Details</h3>
                    <div className="bar-chart-container">
                      <span className="chart-label">Percentage Share:</span>
                      <div className="chart-bar-wrapper">
                        <div 
                          className="chart-bar" 
                          style={{ 
                            width: `${MOCK_PSALMS_CATEGORIES.find(c => c.category === activePsalmCategory).percent * 4}px`,
                            background: '#D4AF37'
                          }}
                        ></div>
                        <span className="chart-val">{MOCK_PSALMS_CATEGORIES.find(c => c.category === activePsalmCategory).percent}%</span>
                      </div>
                    </div>
                    
                    <div className="examples-box">
                      <h4>Representative Examples:</h4>
                      <div className="examples-grid">
                        {MOCK_PSALMS_CATEGORIES.find(c => c.category === activePsalmCategory).examples.map(ex => (
                          <div key={ex} className="psalm-example-card">
                            🎵 {ex}
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="scholarly-structures">
                      <h4>Standard Liturgical Structure:</h4>
                      {activePsalmCategory === 'Lament' && (
                        <ol>
                          <li><strong>Address to God:</strong> Cry for attention (e.g. "How long, O Lord?")</li>
                          <li><strong>Complaint:</strong> Description of distress or enemies</li>
                          <li><strong>Confession of Trust:</strong> Affirming belief in God's fidelity</li>
                          <li><strong>Petition:</strong> Requesting specific deliverance</li>
                          <li><strong>Vow of Praise:</strong> Promising to declare God's glory in public</li>
                        </ol>
                      )}
                      {activePsalmCategory === 'Praise / Hymns' && (
                        <ol>
                          <li><strong>Call to Worship:</strong> Exhortation to praise God</li>
                          <li><strong>Motive for Praise:</strong> Detailing God's greatness in creation and history</li>
                          <li><strong>Recapitulated Praise:</strong> Final blessing or call to praise</li>
                        </ol>
                      )}
                      {activePsalmCategory !== 'Lament' && activePsalmCategory !== 'Praise / Hymns' && (
                        <p>Standard structures follow Near Eastern poetic parallelism, pairing lines (A and B) where the second line reinforces, expands, or contrasts the first.</p>
                      )}
                    </div>
                  </div>
                )}
              </div>

            </div>
          </div>
        )}

        {/* 3. ARCHAEOLOGY BEFORE-AND-AFTER SLIDER */}
        {activePanel === 'archaeology' && (
          <div className="archaeology-panel">
            <div className="archaeology-header-controls">
              <h3>Archaeological Visualizations</h3>
              <div className="slide-selectors">
                {MOCK_ARCHAEOLOGICAL_SLIDES.map(s => (
                  <button 
                    key={s.id} 
                    className={`slide-select-btn ${activeSlideId === s.id ? 'active' : ''}`}
                    onClick={() => setActiveSlideId(s.id)}
                  >
                    {s.title.split(' (')[0]}
                  </button>
                ))}
              </div>
            </div>

            {activeSlide && (
              <div className="slider-workspace">
                {/* Visual Drag container */}
                <div className="slider-container-card">
                  
                  <div className="image-comparison-wrapper">
                    {/* Before Image (Historical Reconstruction) */}
                    <div className="image-layer before-layer">
                      <img src={activeSlide.beforeImg} alt="Historical View" />
                      <div className="layer-label historical">RECONSTRUCTION VIEW (30 AD)</div>
                    </div>

                    {/* After Image (Modern Ruins) */}
                    <div 
                      className="image-layer after-layer" 
                      style={{ clipPath: `polygon(${sliderPosition}% 0, 100% 0, 100% 100%, ${sliderPosition}% 100%)` }}
                    >
                      <img src={activeSlide.afterImg} alt="Modern Ruins" />
                      <div className="layer-label modern">MODERN ARTIFACT RUINS</div>
                    </div>

                    {/* Draggable Handle */}
                    <div 
                      className="slider-drag-handle" 
                      style={{ left: `${sliderPosition}%` }}
                    >
                      <div className="handle-arrows">⏴ ⏵</div>
                      <input 
                        type="range" 
                        min="0" 
                        max="100" 
                        value={sliderPosition} 
                        onChange={(e) => setSliderPosition(e.target.value)}
                        className="invisible-range-input"
                        title="Drag comparison"
                      />
                    </div>
                  </div>
                </div>

                <div className="slider-descriptions-grid">
                  <div className="desc-box reconstruction">
                    <h4>🏛️ Reconstruction Exegesis</h4>
                    <p>{activeSlide.beforeDesc}</p>
                  </div>
                  <div className="desc-box ruins">
                    <h4>📍 Modern Archaeology Notes</h4>
                    <p>{activeSlide.afterDesc}</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 4. HISTORICAL TIMELINE */}
        {activePanel === 'timeline' && (
          <div className="timeline-explorer-panel">
            <h3>Chronology of Scripture Epochs</h3>
            <div className="interactive-timeline-scroll">
              <div className="scroll-timeline-line"></div>
              <div className="scroll-timeline-cards-flex">
                {MOCK_TIMELINE_EVENTS.map((event, idx) => (
                  <div key={idx} className="epoch-scroll-card glass-panel">
                    <span className="epoch-date">{event.date}</span>
                    <h4>{event.title}</h4>
                    <span className="epoch-label">{event.epoch}</span>
                    <p>{event.desc}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* 5. CANON COMPARISON MATRIX */}
        {activePanel === 'canon' && (
          <div className="canon-matrix-panel">
            <h3>Canonical Book Matrix Comparison</h3>
            <p className="instructions">This table highlights which books are accepted across the major biblical canons. Notice the unique books (e.g. Enoch, Jubilees, Meqabyan) preserved in the Ethiopian tradition.</p>
            
            <div className="matrix-table-container">
              <table className="canon-matrix-table">
                <thead>
                  <tr>
                    <th>Scripture Book Title</th>
                    <th>Protestant Canon (66)</th>
                    <th>Catholic Canon (73)</th>
                    <th>Eastern Orthodox (76)</th>
                    <th>Ethiopian Orthodox (81)</th>
                  </tr>
                </thead>
                <tbody>
                  {MOCK_CANON_MATRIX.map((row) => {
                    const isUniqueEthio = !row.prot && !row.cath && !row.orth && row.eth
                    return (
                      <tr key={row.book} className={isUniqueEthio ? 'ethio-unique-row' : ''}>
                        <td className="book-name-col">
                          <strong>{row.book}</strong>
                          {isUniqueEthio && <span className="unique-tag">Ethio Unique</span>}
                        </td>
                        <td className={row.prot ? 'checked' : 'empty'}>{row.prot ? '✓' : '—'}</td>
                        <td className={row.cath ? 'checked' : 'empty'}>{row.cath ? '✓' : '—'}</td>
                        <td className={row.orth ? 'checked' : 'empty'}>{row.orth ? '✓' : '—'}</td>
                        <td className={row.eth ? 'checked ethio' : 'empty'}>{row.eth ? '✓' : '—'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

      </div>
    </div>
  )
}

export default InteractiveMedia
