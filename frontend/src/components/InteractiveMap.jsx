import { useState, useEffect, useRef, useMemo } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import './InteractiveMap.css'
import { BIBLICAL_LOCATIONS } from '../data/biblicalLocations'

// Historical periods
const HISTORICAL_PERIODS = [
  'All Periods',
  'Patriarchal Period',
  'Exodus Period',
  'Period of Judges',
  'United Kingdom',
  'Divided Kingdom',
  'Babylonian Exile',
  'Persian Period',
  'Time of Jesus',
  'Apostolic Era',
  'Early Church'
];

// Map layers
const MAP_LAYERS = [
  'Biblical Events',
  'People & Nations',
  'African Biblical World',
  'Empires',
  'Journeys & Routes',
  'Modern Countries',
  'Ethiopian Canon Connections'
];

// People groups
const PEOPLE_GROUPS = [
  'All People Groups',
  'Israelites',
  'Egyptians',
  'Cushites / Ethiopians',
  'Nubians',
  'Canaanites',
  'Babylonians',
  'Assyrians',
  'Persians',
  'Romans',
  'Greeks',
  'Samaritans',
  'Philistines',
  'Moabites',
  'Edomites',
  'Cyrenians'
];

// Modern countries
const MODERN_COUNTRIES = [
  'All Modern Countries',
  'Israel / Palestine',
  'Egypt',
  'Sudan',
  'South Sudan',
  'Ethiopia',
  'Eritrea',
  'Jordan',
  'Syria',
  'Iraq',
  'Iran',
  'Turkey',
  'Greece',
  'Italy',
  'Saudi Arabia',
  'Lebanon'
];

// Canon Connections
const CANON_CONNECTIONS = [
  'All',
  'Ethiopian Canon',
  'Protestant Canon',
  'Catholic Canon',
  'Orthodox Canon',
  '1 Enoch',
  'Jubilees',
  'Meqabyan'
];

// Seeded Route coordinates for polyline overlays
const ROUTES_DATA = {
  "Paul's Journeys": [
    [36.2021, 36.1601], // Antioch
    [35.1264, 33.4299], // Cyprus
    [37.9397, 27.3411], // Ephesus
    [37.9333, 22.9333], // Corinth
    [35.2401, 24.8092], // Crete
    [41.0125, 24.2858], // Philippi
    [41.9028, 12.4964]  // Rome
  ],
  "Exodus Route": [
    [26.8206, 30.8025], // Egypt / Memphis
    [28.5392, 33.9750], // Sinai
    [30.6500, 34.4167], // Kadesh Barnea (traditional)
    [31.7683, 35.2137]  // Jerusalem
  ],
  "Places Connected to Jesus": [
    [32.7019, 35.3033], // Nazareth
    [32.8167, 35.5833], // Sea of Galilee
    [31.7683, 35.2137], // Jerusalem
    [31.7058, 35.2024]  // Bethlehem
  ],
  "African Places in the Bible": [
    [15.0000, 32.5000], // Cush
    [26.8206, 30.8025], // Egypt
    [31.2001, 29.9187], // Alexandria
    [32.8239, 21.8569]  // Cyrene
  ]
};

function InteractiveMap() {
  // State
  const [searchTerm, setSearchTerm] = useState('')
  const [activeLayer, setActiveLayer] = useState('Biblical Events')
  const [activePeriod, setActivePeriod] = useState('All Periods')
  const [activePeopleGroup, setActivePeopleGroup] = useState('All People Groups')
  const [activeCountry, setActiveCountry] = useState('All Modern Countries')
  const [activeCanon, setActiveCanon] = useState('All')
  
  const [selectedLocation, setSelectedLocation] = useState(BIBLICAL_LOCATIONS.find(l => l.id === 'jerusalem'))
  const [locationTab, setLocationTab] = useState('overview')
  const [bottomTab, setBottomTab] = useState('scriptures')
  const [tileMode, setTileMode] = useState('satellite') // 'satellite' or 'street'
  
  // AI assistant chat history
  const [chatInput, setChatInput] = useState('')
  const [chatHistory, setChatHistory] = useState([
    {
      role: 'ai',
      text: 'Shalom! I am your Geography AI Assistant. Ask me anything about biblical locations, people groups, ancient empires, routes, or modern-day equivalents. I am aware of the selected location.'
    }
  ])

  // Custom User Study Notes
  const [userNotes, setUserNotes] = useState('')

  // Map Ref and Leaflet objects
  const mapContainerRef = useRef(null)
  const leafletMapRef = useRef(null)
  const markersGroupRef = useRef(null)
  const polylinesGroupRef = useRef(null)

  // Filter logic
  const filteredLocations = useMemo(() => {
    return BIBLICAL_LOCATIONS.filter(loc => {
      // Search Term Match
      if (searchTerm.trim()) {
        const query = searchTerm.toLowerCase()
        const matchSearch =
          loc.ancientName.toLowerCase().includes(query) ||
          loc.alternateNames.some(alt => alt.toLowerCase().includes(query)) ||
          loc.modernEquivalent.toLowerCase().includes(query) ||
          loc.modernCountries.some(c => c.toLowerCase().includes(query)) ||
          loc.connectedPeople.some(p => p.toLowerCase().includes(query)) ||
          loc.summary.toLowerCase().includes(query)

        if (!matchSearch) return false
      }

      // Layer Match
      if (activeLayer === 'African Biblical World') {
        const isAfrican = ['cush', 'egypt', 'cyrene', 'sheba'].includes(loc.id)
        if (!isAfrican) return false
      } else if (activeLayer === 'Ethiopian Canon Connections') {
        if (!loc.ethiopianCanonConnection) return false
      }

      // Period Match
      if (activePeriod !== 'All Periods') {
        if (!loc.periods.includes(activePeriod)) return false
      }

      // People Group Match
      if (activePeopleGroup !== 'All People Groups') {
        const pgQuery = activePeopleGroup.split(' / ')[0].toLowerCase()
        const hasPeopleMatch = loc.connectedPeople.some(p => p.toLowerCase().includes(pgQuery))
        if (!hasPeopleMatch) return false
      }

      // Modern Country Match
      if (activeCountry !== 'All Modern Countries') {
        const countryQuery = activeCountry.split(' / ')[0].toLowerCase()
        const hasCountryMatch = loc.modernCountries.some(c => c.toLowerCase().includes(countryQuery))
        if (!hasCountryMatch) return false
      }

      // Canon Match
      if (activeCanon !== 'All') {
        if (activeCanon === 'Ethiopian Canon' && !loc.ethiopianCanonConnection) return false
      }

      return true
    })
  }, [searchTerm, activeLayer, activePeriod, activePeopleGroup, activeCountry, activeCanon])

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current) return

    // If map already initialized, skip
    if (leafletMapRef.current) return

    // Create Leaflet Map instance centering around Middle East/East Africa
    const map = L.map(mapContainerRef.current, {
      center: [28.0, 32.0],
      zoom: 4,
      zoomControl: false // Custom placement via CSS/Leaflet control later
    })

    leafletMapRef.current = map

    // Create marker & polyline layer groups
    markersGroupRef.current = L.layerGroup().addTo(map)
    polylinesGroupRef.current = L.layerGroup().addTo(map)

    // Add standard zoom control at the bottom right
    L.control.zoom({ position: 'bottomright' }).addTo(map)

    // Clean up on unmount
    return () => {
      if (leafletMapRef.current) {
        leafletMapRef.current.remove()
        leafletMapRef.current = null
      }
    }
  }, [])

  // Sync Map Tiles (Satellite vs Color Street Map)
  useEffect(() => {
    const map = leafletMapRef.current
    if (!map) return

    // Remove existing tile layer if present
    map.eachLayer((layer) => {
      if (layer instanceof L.TileLayer) {
        map.removeLayer(layer)
      }
    })

    let tileUrl = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
    let attrib = '© Esri World Imagery'

    if (tileMode === 'street') {
      tileUrl = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
      attrib = '© OpenStreetMap contributors'
    }

    L.tileLayer(tileUrl, {
      attribution: attrib,
      maxZoom: 18,
      minZoom: 3
    }).addTo(map)
  }, [tileMode])

  // Render Pins and Routes
  useEffect(() => {
    const map = leafletMapRef.current
    const markersGroup = markersGroupRef.current
    const polylinesGroup = polylinesGroupRef.current

    if (!map || !markersGroup || !polylinesGroup) return

    // Clear previous elements
    markersGroup.clearLayers()
    polylinesGroup.clearLayers()

    // 1. Draw Route polylines if suitable filters are selected
    if (activeLayer === 'Journeys & Routes' || activeLayer === 'African Biblical World' || activePeriod === 'Exodus Period' || activePeriod === 'Time of Jesus') {
      let activeRouteKeys = []
      if (activeLayer === 'Journeys & Routes') {
        activeRouteKeys = ["Paul's Journeys", "Exodus Route", "Places Connected to Jesus", "African Places in the Bible"]
      } else if (activeLayer === 'African Biblical World') {
        activeRouteKeys = ["African Places in the Bible"]
      } else if (activePeriod === 'Exodus Period') {
        activeRouteKeys = ["Exodus Route"]
      } else if (activePeriod === 'Time of Jesus') {
        activeRouteKeys = ["Places Connected to Jesus"]
      }

      activeRouteKeys.forEach(routeKey => {
        const coords = ROUTES_DATA[routeKey]
        if (coords) {
          let color = '#8B5CF6' // default purple
          if (routeKey === 'Exodus Route') color = '#22C55E' // green
          if (routeKey === 'African Places in the Bible') color = '#D4AF37' // gold

          L.polyline(coords, {
            color: color,
            weight: 3,
            dashArray: '5, 8',
            opacity: 0.8
          }).addTo(polylinesGroup)
        }
      })
    }

    // 2. Draw location markers
    filteredLocations.forEach(loc => {
      const isSelected = selectedLocation && selectedLocation.id === loc.id

      // Create a custom styled marker HTML
      const pinColor = isSelected ? '#D4AF37' : '#8B5CF6'
      const shadowGlow = isSelected ? '0 0 12px #D4AF37' : '0 0 8px #8B5CF6'
      
      const customHtmlIcon = L.divIcon({
        className: 'custom-leaflet-pin',
        html: `
          <div style="
            display: flex;
            flex-direction: column;
            align-items: center;
            transform: translate(0, -50%);
          ">
            <span style="
              width: 10px;
              height: 10px;
              background-color: ${pinColor};
              border: 2px solid white;
              border-radius: 50%;
              box-shadow: ${shadowGlow};
            "></span>
            <span style="
              font-size: 11px;
              font-weight: 700;
              color: white;
              background: rgba(11, 16, 32, 0.9);
              border: 1px solid rgba(255, 255, 255, 0.15);
              padding: 2px 6px;
              border-radius: 4px;
              margin-top: 4px;
              white-space: nowrap;
            ">${loc.ancientName}</span>
          </div>
        `,
        iconSize: [20, 20],
        iconAnchor: [10, 5]
      })

      const marker = L.marker([loc.coordinates.lat, loc.coordinates.lng], { icon: customHtmlIcon })
      
      marker.on('click', () => {
        setSelectedLocation(loc)
        setLocationTab('overview')
        
        // Pan slightly towards location
        map.panTo([loc.coordinates.lat, loc.coordinates.lng])
      })

      marker.addTo(markersGroup)
    })
  }, [filteredLocations, selectedLocation, activeLayer, activePeriod])

  // Pan to selected location coordinates initially or when selected outside
  const panToLocation = (loc) => {
    const map = leafletMapRef.current
    if (map && loc) {
      map.setView([loc.coordinates.lat, loc.coordinates.lng], 6)
    }
  }

  // Handlers
  const handleResetFilters = () => {
    setSearchTerm('')
    setActiveLayer('Biblical Events')
    setActivePeriod('All Periods')
    setActivePeopleGroup('All People Groups')
    setActiveCountry('All Modern Countries')
    setActiveCanon('All')
    const jerusalem = BIBLICAL_LOCATIONS.find(l => l.id === 'jerusalem')
    setSelectedLocation(jerusalem)
    panToLocation(jerusalem)
  }

  const handleSelectLocation = (loc) => {
    setSelectedLocation(loc)
    setLocationTab('overview')
    panToLocation(loc)
  }

  const handleSendPrompt = (promptText) => {
    if (!promptText.trim()) return

    const newChatHistory = [
      ...chatHistory,
      { role: 'user', text: promptText }
    ]
    setChatHistory(newChatHistory)
    setChatInput('')

    // Generate simulated geographic analysis based on selected location
    setTimeout(() => {
      let aiResponse = 'AI geography backend not connected yet.'
      if (selectedLocation) {
        if (promptText.includes('today')) {
          aiResponse = `The ancient location of **${selectedLocation.ancientName}** is located in modern-day **${selectedLocation.modernEquivalent}** (${selectedLocation.modernCountries.join(', ')}). In archaeological databases, this is classified under *${selectedLocation.confidence}* accuracy.`
        } else if (promptText.includes('Bible') || promptText.includes('happened')) {
          aiResponse = `According to the scriptures, ${selectedLocation.summary} Key references include: ${selectedLocation.scriptureReferences.map(r => r.ref).join(', ')}.`
        } else if (promptText.includes('Ethiopian')) {
          aiResponse = selectedLocation.ethiopianCanonConnection || `Ancient ${selectedLocation.ancientName} features in early church histories and canon structures preserved in Ge'ez text traditions.`
        } else {
          aiResponse = `Here is a scholarly summary of **${selectedLocation.ancientName}**:\n\n${selectedLocation.whyItMatters}\n\n*Decolonial Context:* ${selectedLocation.decolonialNote}`
        }
      }

      setChatHistory(prev => [
        ...prev,
        { role: 'ai', text: aiResponse }
      ])
    }, 800)
  }

  return (
    <div className="ub-map-lab-layout">
      {/* Top Header */}
      <div className="map-lab-header">
        <h1>Interactive Biblical Map</h1>
        <p>Explore ancient biblical locations, modern-day equivalents, people groups, routes, and historical context.</p>
      </div>

      {/* Toolbar / Filters */}
      <div className="map-toolbar-panel">
        <div className="search-bar-row">
          <span className="search-icon-inside">🔍</span>
          <input
            type="text"
            placeholder="Search Jerusalem, Cush, Egypt, Babylon, Paul’s journeys..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="filters-grid">
          <div className="filter-select-box">
            <label>Map Layer</label>
            <select value={activeLayer} onChange={(e) => setActiveLayer(e.target.value)}>
              {MAP_LAYERS.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
          </div>

          <div className="filter-select-box">
            <label>Time Period</label>
            <select value={activePeriod} onChange={(e) => setActivePeriod(e.target.value)}>
              {HISTORICAL_PERIODS.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>

          <div className="filter-select-box">
            <label>People Group</label>
            <select value={activePeopleGroup} onChange={(e) => setActivePeopleGroup(e.target.value)}>
              {PEOPLE_GROUPS.map(g => <option key={g} value={g}>{g}</option>)}
            </select>
          </div>

          <div className="filter-select-box">
            <label>Modern Country</label>
            <select value={activeCountry} onChange={(e) => setActiveCountry(e.target.value)}>
              {MODERN_COUNTRIES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          <div className="filter-select-box">
            <label>Canon Connection</label>
            <select value={activeCanon} onChange={(e) => setActiveCanon(e.target.value)}>
              {CANON_CONNECTIONS.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          <button className="reset-filters-btn" onClick={handleResetFilters}>
            Reset Filters
          </button>
        </div>
      </div>

      {/* Main Workspace Area (Map + Sidebars in a Three Column Layout) */}
      <div className="map-workspace-grid">
        {/* Left Map Panel */}
        <div className="map-view-card">
          <div className="map-card-header">
            <h3>Biblical World Map</h3>
            <div className="map-header-badges">
              <span className="badge-tag green">Ancient + Modern</span>
              <span className="badge-tag purple">Ethiopian Canon Aware</span>
              <span className="badge-tag gold">Scripture Linked</span>
            </div>
            <button 
              className="layers-toggle-btn" 
              onClick={() => setTileMode(prev => prev === 'satellite' ? 'street' : 'satellite')}
            >
              Layer: {tileMode === 'satellite' ? 'Satellite 🛰️' : 'Color Map 🗺️'}
            </button>
          </div>

          <div className="map-viewport-wrapper">
            <div ref={mapContainerRef} style={{ width: '100%', height: '100%' }}></div>
            
            {/* Map Legend */}
            <div className="map-legend-overlay">
              <h4>Map Legend</h4>
              <ul>
                <li><span className="legend-dot city"></span> Cities</li>
                <li><span className="legend-dot region"></span> Regions</li>
                <li><span className="legend-dot mountain"></span> Mountains</li>
                <li><span className="legend-dot water"></span> Bodies of Water</li>
                <li><span className="legend-dot people"></span> People Groups</li>
                <li><span className="legend-line route"></span> Routes / Journeys</li>
                <li><span className="legend-star event"></span> Key Events</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Middle Details Panel */}
        <div className="location-details-sidebar-card">
          {selectedLocation ? (
            <>
              <div className="details-header-top">
                <div className="details-title-row">
                  <span className="details-location-icon">📍</span>
                  <h2>{selectedLocation.ancientName}</h2>
                </div>
                <span className="badge-confidence gold">{selectedLocation.confidence}</span>
              </div>

              {/* Details Tabs */}
              <div className="details-nav-tabs">
                <button className={locationTab === 'overview' ? 'active' : ''} onClick={() => setLocationTab('overview')}>Overview</button>
                <button className={locationTab === 'scriptures' ? 'active' : ''} onClick={() => setLocationTab('scriptures')}>Scriptures</button>
                <button className={locationTab === 'people' ? 'active' : ''} onClick={() => setLocationTab('people')}>People</button>
                <button className={locationTab === 'timeline' ? 'active' : ''} onClick={() => setLocationTab('timeline')}>Timeline</button>
                <button className={locationTab === 'modern' ? 'active' : ''} onClick={() => setLocationTab('modern')}>Modern Location</button>
                <button className={locationTab === 'ai' ? 'active' : ''} onClick={() => setLocationTab('ai')}>AI Notes</button>
              </div>

              {/* Tab content */}
              <div className="details-tab-contents">
                {locationTab === 'overview' && (
                  <div className="overview-tab-pane">
                    <div className="meta-info-grid">
                      <div className="meta-field">
                        <strong>Ancient Name</strong>
                        <span>{selectedLocation.ancientName}</span>
                      </div>
                      <div className="meta-field">
                        <strong>Modern Location</strong>
                        <span>{selectedLocation.modernEquivalent}</span>
                      </div>
                      <div className="meta-field">
                        <strong>Location Type</strong>
                        <span>{selectedLocation.type}</span>
                      </div>
                      <div className="meta-field">
                        <strong>Ancient Region</strong>
                        <span>{selectedLocation.ancientRegion}</span>
                      </div>
                      <div className="meta-field">
                        <strong>Biblical Periods</strong>
                        <span>{selectedLocation.periods.join(', ')}</span>
                      </div>
                      <div className="meta-field">
                        <strong>Confidence Level</strong>
                        <span>{selectedLocation.confidence}</span>
                      </div>
                    </div>

                    <div className="why-matters-box">
                      <h4>Why It Matters</h4>
                      <p>{selectedLocation.whyItMatters}</p>
                    </div>

                    <div className="connected-people-pills">
                      <h4>Connected People</h4>
                      <div className="pill-row">
                        {selectedLocation.connectedPeople.map(p => (
                          <span key={p} className="person-pill">{p}</span>
                        ))}
                      </div>
                    </div>

                    <div className="related-events-list">
                      <h4>Related Events</h4>
                      <ul>
                        {selectedLocation.relatedEvents.map(e => <li key={e}>• {e}</li>)}
                      </ul>
                    </div>
                  </div>
                )}

                {locationTab === 'scriptures' && (
                  <div className="scriptures-tab-pane">
                    <div className="scrolling-verses-list">
                      {selectedLocation.scriptureReferences.map((ref, idx) => (
                        <div key={idx} className="tab-scripture-verse-card">
                          <h5>{ref.ref}</h5>
                          <p>{ref.summary}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {locationTab === 'people' && (
                  <div className="people-tab-pane">
                    <h4>Connected Figures & People Groups</h4>
                    <p>The following figures/groups are geographically and historically documented at this location:</p>
                    <ul className="people-details-bullet-list">
                      {selectedLocation.connectedPeople.map(p => (
                        <li key={p}>
                          <strong>{p}</strong>: Geographically documented during the {selectedLocation.periods.join(', ')}.
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {locationTab === 'timeline' && (
                  <div className="timeline-tab-pane">
                    <h4>Timeline & Historical Periods</h4>
                    <div className="timeline-flow-list">
                      {selectedLocation.periods.map((p, idx) => (
                        <div key={p} className="timeline-flow-step">
                          <span className="step-circle">{idx + 1}</span>
                          <div className="step-content">
                            <h5>{p}</h5>
                            <p>Verified scriptural interactions occurred at {selectedLocation.ancientName} during this era.</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {locationTab === 'modern' && (
                  <div className="modern-tab-pane">
                    <h4>Modern Equivalents & Countries</h4>
                    <div className="modern-details-card">
                      <p><strong>Modern region:</strong> {selectedLocation.modernEquivalent}</p>
                      <p><strong>Borders span across:</strong> {selectedLocation.modernCountries.join(', ')}</p>
                      <p><strong>Geographical status:</strong> Classified as a <em>{selectedLocation.confidence}</em>.</p>
                    </div>
                    {selectedLocation.decolonialNote && (
                      <div className="decolonial-note-callout">
                        <h5>Decolonial Scripture Note</h5>
                        <p>{selectedLocation.decolonialNote}</p>
                      </div>
                    )}
                  </div>
                )}

                {locationTab === 'ai' && (
                  <div className="ai-notes-tab-pane">
                    <h4>AI Geography Insights</h4>
                    <p className="ai-notes-p">{selectedLocation.summary}</p>
                    <p className="ai-notes-p"><strong>Ethiopian Canon Connection:</strong> {selectedLocation.ethiopianCanonConnection}</p>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="details-empty-state">
              <h3>Start Exploring Biblical Geography</h3>
              <p>Select a location pin on the map or choose a location from the Quick Explore list to review exegesis, modern equivalents, and decolonial research notes.</p>
            </div>
          )}
        </div>

        {/* Right AI Assistant Panel */}
        <div className="map-ai-assistant-card">
          <div className="ai-header-title-bar">
            <span className="ai-bot-icon">🤖</span>
            <h3>Geography AI Assistant</h3>
            <span className="atlas-chat-badge">Atlas Chat</span>
          </div>

          <div className="ai-chat-viewport">
            {chatHistory.map((chat, idx) => (
              <div key={idx} className={`chat-bubble-msg ${chat.role}`}>
                <p>{chat.text}</p>
              </div>
            ))}
          </div>

          <div className="ai-chat-suggested-prompts-row">
            <button onClick={() => handleSendPrompt('Where is this place today?')}>Where is this place today?</button>
            <button onClick={() => handleSendPrompt('What happened here in the Bible?')}>What happened here in the Bible?</button>
            <button onClick={() => handleSendPrompt('How does this connect to Ethiopia?')}>How does this connect to Ethiopia?</button>
            <button onClick={() => handleSendPrompt('Explain this location to a beginner.')}>Explain this location to a beginner.</button>
          </div>

          <div className="ai-chat-input-row">
            <input
              type="text"
              placeholder="Ask about the selected location or any biblical place..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSendPrompt(chatInput)}
            />
            <button className="ask-ai-action-btn" onClick={() => handleSendPrompt(chatInput)}>Ask AI</button>
          </div>
          <div className="ai-subtext-offline">AI geography backend not connected yet.</div>
        </div>
      </div>

      {/* Bottom Study Drawer (Tabbed Study Drawer + Quick Explore Panel side-by-side) */}
      <div className="bottom-study-drawer-row">
        {/* Drawer content (Left/Center 70% width) */}
        <div className="drawer-main-notebook">
          <div className="drawer-tabs-row">
            <button className={bottomTab === 'scriptures' ? 'active' : ''} onClick={() => setBottomTab('scriptures')}>📖 Scripture References</button>
            <button className={bottomTab === 'people' ? 'active' : ''} onClick={() => setBottomTab('people')}>👥 Related People</button>
            <button className={bottomTab === 'routes' ? 'active' : ''} onClick={() => setBottomTab('routes')}>🛣️ Routes</button>
            <button className={bottomTab === 'timeline' ? 'active' : ''} onClick={() => setBottomTab('timeline')}>📅 Timeline</button>
            <button className={bottomTab === 'notes' ? 'active' : ''} onClick={() => setBottomTab('notes')}>✍️ Study Notes</button>
            <button className={bottomTab === 'canon' ? 'active' : ''} onClick={() => setBottomTab('canon')}>📜 Ethiopian Canon Connection</button>
          </div>

          <div className="drawer-tab-view-box">
            {bottomTab === 'scriptures' && (
              <div className="drawer-scriptures-pane">
                {selectedLocation ? (
                  <>
                    <div className="drawer-cards-flex-row">
                      {selectedLocation.scriptureReferences.map((ref, idx) => (
                        <div key={idx} className="drawer-scripture-ref-card">
                          <h4>{ref.ref}</h4>
                          <p>{ref.summary}</p>
                          <div className="card-actions-row">
                            <button className="action-pill-btn">Read Passage</button>
                            <button className="action-pill-btn">Compare</button>
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="view-all-scriptures-footer">
                      <button className="view-all-verses-btn">View All Scriptures (128)</button>
                    </div>
                  </>
                ) : (
                  <p className="drawer-empty-text">Select a location pin to view scripture reference cards.</p>
                )}
              </div>
            )}

            {bottomTab === 'people' && (
              <div className="drawer-people-pane">
                {selectedLocation ? (
                  <div className="people-group-cards-row">
                    {selectedLocation.connectedPeople.map(p => (
                      <div key={p} className="drawer-person-card">
                        <span className="person-avatar">👤</span>
                        <div>
                          <h4>{p}</h4>
                          <p>Documented resident or traveler at {selectedLocation.ancientName}.</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="drawer-empty-text">Select a location pin to view related people.</p>
                )}
              </div>
            )}

            {bottomTab === 'routes' && (
              <div className="drawer-routes-pane">
                {selectedLocation ? (
                  <div className="routes-info-row">
                    {selectedLocation.relatedRoutes.map(r => (
                      <div key={r} className="route-info-card">
                        <span className="route-icon-pin">🛣️</span>
                        <div>
                          <h4>{r}</h4>
                          <p>Ancient path passing through {selectedLocation.ancientName} connecting to trade networks.</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="drawer-empty-text">Select a location pin to view related routes.</p>
                )}
              </div>
            )}

            {bottomTab === 'timeline' && (
              <div className="drawer-timeline-pane">
                {selectedLocation ? (
                  <div className="horizontal-timeline-steps">
                    {selectedLocation.periods.map((p, idx) => (
                      <div key={p} className="timeline-horizontal-step">
                        <span className="num-dot">{idx + 1}</span>
                        <h4>{p}</h4>
                        <p>Historical interaction documented at {selectedLocation.ancientName}.</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="drawer-empty-text">Select a location pin to view timeline.</p>
                )}
              </div>
            )}

            {bottomTab === 'notes' && (
              <div className="drawer-notes-pane">
                <h4>Personal Geography Study Notes</h4>
                <textarea
                  placeholder="Record your geographic insights, observations, and findings from your study here..."
                  value={userNotes}
                  onChange={(e) => setUserNotes(e.target.value)}
                  className="study-notes-textarea"
                />
                <div className="notes-actions-row">
                  <button className="save-notes-btn">Save Study Note</button>
                </div>
              </div>
            )}

            {bottomTab === 'canon' && (
              <div className="drawer-canon-pane">
                {selectedLocation ? (
                  <div className="canon-connection-full-card">
                    <h4>Ethiopian Canon & Decolonial Context</h4>
                    <p className="canon-context-text">{selectedLocation.ethiopianCanonConnection}</p>
                    {selectedLocation.decolonialNote && (
                      <div className="decolonial-note-box">
                        <strong>Decolonial Translation Audit:</strong>
                        <p>{selectedLocation.decolonialNote}</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="drawer-empty-text">Select a location pin to view canon connections.</p>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Quick Explore Panel (Right 30% width) */}
        <div className="drawer-quick-explore-sidebar">
          <h3>Quick Explore</h3>
          <div className="quick-explore-grid">
            <button className="quick-exp-btn" onClick={() => handleSelectLocation(BIBLICAL_LOCATIONS.find(l => l.id === 'egypt'))}>
              <span className="quick-icon">🏜️</span>
              <span>Show Egypt</span>
            </button>
            
            <button className="quick-exp-btn" onClick={() => handleSelectLocation(BIBLICAL_LOCATIONS.find(l => l.id === 'cush'))}>
              <span className="quick-icon">🌍</span>
              <span>Show Cush / Ethiopia</span>
            </button>

            <button className="quick-exp-btn" onClick={() => {
              setActiveLayer('Journeys & Routes');
              handleSelectLocation(BIBLICAL_LOCATIONS.find(l => l.id === 'rome'));
            }}>
              <span className="quick-icon">🛣️</span>
              <span>Paul's Journeys</span>
            </button>

            <button className="quick-exp-btn" onClick={() => {
              setActiveLayer('African Biblical World');
              handleSelectLocation(BIBLICAL_LOCATIONS.find(l => l.id === 'cush'));
            }}>
              <span className="quick-icon">✊</span>
              <span>African Places in the Bible</span>
            </button>

            <button className="quick-exp-btn" onClick={() => {
              setActivePeriod('Exodus Period');
              handleSelectLocation(BIBLICAL_LOCATIONS.find(l => l.id === 'mount_sinai'));
            }}>
              <span className="quick-icon">🚶</span>
              <span>Exodus Route</span>
            </button>

            <button className="quick-exp-btn" onClick={() => handleSelectLocation(BIBLICAL_LOCATIONS.find(l => l.id === 'babylon'))}>
              <span className="quick-icon">🏰</span>
              <span>Show Babylon</span>
            </button>

            <button className="quick-exp-btn" onClick={() => {
              setActivePeriod('Time of Jesus');
              handleSelectLocation(BIBLICAL_LOCATIONS.find(l => l.id === 'bethlehem'));
            }}>
              <span className="quick-icon">✝️</span>
              <span>Places Connected to Jesus</span>
            </button>

            <button className="quick-exp-btn" onClick={() => {
              setActiveLayer('Ethiopian Canon Connections');
              handleSelectLocation(BIBLICAL_LOCATIONS.find(l => l.id === 'cush'));
            }}>
              <span className="quick-icon">📜</span>
              <span>Ethiopian Canon Locations</span>
            </button>
          </div>
          <div className="drawer-explore-sub-tip">💡 Click any marker on the map to explore more details.</div>
        </div>
      </div>
    </div>
  )
}

export default InteractiveMap
