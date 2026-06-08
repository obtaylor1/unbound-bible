import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import './InteractiveMap.css'

function InteractiveMap() {
  const [locations, setLocations] = useState([])
  const [selectedLocation, setSelectedLocation] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  
  // New state for the redesigned interface
  const [mapLayer, setMapLayer] = useState('Biblical Events')
  const [period, setPeriod] = useState('All Periods')
  const [isPeriodDropdownOpen, setIsPeriodDropdownOpen] = useState(false)
  const [isSelectLocationDropdownOpen, setIsSelectLocationDropdownOpen] = useState(false)
  const [locationDropdownSearchTerm, setLocationDropdownSearchTerm] = useState('')
  const [isHistoricalLegendOpen, setIsHistoricalLegendOpen] = useState(true)
  const [darkMode, setDarkMode] = useState(true)
  const [chatMessage, setChatMessage] = useState('')
  const [chatHistory, setChatHistory] = useState([])
  
  // Map-related state
  const mapRef = useRef(null)
  const mapInstanceRef = useRef(null)
  const dropdownRef = useRef(null)
  const selectLocationDropdownRef = useRef(null)
  const [mapCenter, setMapCenter] = useState({ lat: 31.5, lng: 35.0 }) // Jerusalem center
  const [mapZoom, setMapZoom] = useState(6)
  const [showDetailedAnalysis, setShowDetailedAnalysis] = useState(true)

  useEffect(() => {
    fetchLocations()
  }, [])

  // Close dropdowns when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsPeriodDropdownOpen(false)
      }
      if (selectLocationDropdownRef.current && !selectLocationDropdownRef.current.contains(event.target)) {
        setIsSelectLocationDropdownOpen(false)
      }
    }

    if (isPeriodDropdownOpen || isSelectLocationDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => {
        document.removeEventListener('mousedown', handleClickOutside)
      }
    }
  }, [isPeriodDropdownOpen, isSelectLocationDropdownOpen])

  // Clear location dropdown search when dropdown closes
  useEffect(() => {
    if (!isSelectLocationDropdownOpen) {
      setLocationDropdownSearchTerm('')
    }
  }, [isSelectLocationDropdownOpen])


  const initializeMap = useCallback(() => {
    const container = mapRef.current
    if (!container) {
      console.log('Container not available for map initialization')
      return null
    }

    // Check if map is already initialized
    if (container._leafletMap) {
      console.log('Map already exists, skipping initialization')
      return container._leafletMap
    }

    // Force cleanup of any existing Leaflet instances
    try {
      if (container._leafletMap) {
        container._leafletMap.remove()
        container._leafletMap = null
      }
      container.innerHTML = ''
      container.removeAttribute('data-leaflet-map')
    } catch (e) {
      console.warn('Cleanup warning:', e)
    }
    
    try {
      console.log('Creating new Leaflet map...')
      
      const map = L.map(container, {
        center: [31.5, 35.0], // Jerusalem center
        zoom: 6,
        zoomControl: false, // Disable default zoom controls (using custom ones)
        attributionControl: true,
        closePopupOnClick: false, // Don't close popup when clicking map
        maxBoundsViscosity: 1.0, // Prevent panning outside bounds
      })

      // Add CartoDB Positron tiles (English labels, clean design)
      const tileLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://carto.com/attributions">CARTO</a>',
        maxZoom: 19,
        minZoom: 2,
        subdomains: 'abcd'
      })
      
      // Add loading and error event handlers for debugging
      tileLayer.on('loading', function() {
        console.log('Map tiles are loading...')
      })
      
      tileLayer.on('load', function() {
        console.log('Map tiles loaded successfully')
      })
      
      tileLayer.on('tileerror', function(e) {
        console.error('Tile loading error:', e)
      })
      
      tileLayer.addTo(map)
      
      // Force map refresh after adding tiles
      setTimeout(() => {
        map.invalidateSize()
        console.log('Map size invalidated and refreshed')
      }, 100)

      // Store map instance for later use
      container._leafletMap = map
      mapInstanceRef.current = map
      container.setAttribute('data-leaflet-map', 'true')

      console.log('Leaflet map initialized successfully')
      return map
      
    } catch (error) {
      console.error('Error initializing map:', error)
      // Clean up on error
      try {
        if (container._leafletMap) {
          container._leafletMap.remove()
        }
      } catch (e) {
        console.warn('Error during cleanup:', e)
      }
      container._leafletMap = null
      container.innerHTML = ''
      container.removeAttribute('data-leaflet-map')
      return null
    }
  }, []) // No dependencies - function is stable

  const addLocationMarkers = useCallback((map, selectedLocationData) => {
    if (!map) return

    // Clear existing markers
    map.eachLayer((layer) => {
      if (layer instanceof L.Marker) {
        map.removeLayer(layer)
      }
    })

    // Only add marker for selected location
    if (selectedLocationData) {
      const lat = parseFloat(selectedLocationData.latitude)
      const lng = parseFloat(selectedLocationData.longitude)
      
      // Validate coordinates
      if (isNaN(lat) || isNaN(lng)) return
      
      // Create custom icon using the blue map pin image
      const icon = L.icon({
        iconUrl: '/assets/map-pin.png',
        iconSize: [32, 40], // Adjusted size for PNG pin
        iconAnchor: [16, 40], // Pin point at bottom center
        popupAnchor: [0, -40], // Popup appears above the pin
        className: 'custom-map-pin'
      })

      const marker = L.marker([lat, lng], { icon })
        .addTo(map)
        .bindPopup(`
          <div class="popup-content">
            <div class="popup-title">${sanitizeHTML(selectedLocationData.name)}</div>
            <div class="popup-modern">${sanitizeHTML(selectedLocationData.modern_name || 'Ancient biblical location')}</div>
            
            ${selectedLocationData.description ? `
              <div class="popup-significance">
                <strong>Biblical Significance:</strong>
                <p>${sanitizeHTML(selectedLocationData.description)}</p>
              </div>
            ` : ''}
            
            ${selectedLocationData.archaeological_evidence ? `
              <div class="popup-archaeology">
                <strong>Archaeological Evidence:</strong>
                <p>${sanitizeHTML(selectedLocationData.archaeological_evidence)}</p>
              </div>
            ` : ''}
            
            <div class="popup-coordinates">
              <strong>Location:</strong> ${lat.toFixed(4)}°N, ${lng.toFixed(4)}°E
            </div>
          </div>
        `, {
          maxWidth: 320,
          minWidth: 280,
          maxHeight: 400,
          autoPan: true, // Auto-pan to keep popup in view
          autoPanPadding: [20, 20], // Padding from edges
          keepInView: true, // Keep popup in view when map is panned
          closeButton: true, // Show close button
          autoClose: false, // Don't auto-close when opening another popup
          className: 'custom-popup' // Custom CSS class
        })
        .openPopup()

      // Center map on selected location
      map.setView([lat, lng], 10)
    }
  }, []) // Stable function - no dependencies

  // Use stable reference for locations to prevent useEffect triggering
  const stableLocations = useMemo(() => locations, [locations.length])

  // Initialize map after loading is complete and container is mounted
  useEffect(() => {
    if (loading) {
      console.log('Still loading data, waiting before map initialization...')
      return
    }
    
    const container = mapRef.current
    if (!container) {
      console.log('Container not available for map initialization')
      return
    }
    
    if (container && !container._leafletMap) {
      console.log('Initializing Leaflet map...')
      const map = initializeMap()
      // Don't add any markers initially - only when location is selected
    }

    // Cleanup function only runs on component unmount
    return () => {
      const container = mapRef.current
      if (container && container._leafletMap) {
        console.log('Cleaning up map on component unmount')
        try {
          container._leafletMap.remove()
        } catch (e) {
          console.warn('Cleanup warning:', e)
        }
        container._leafletMap = null
      }
    }
  }, [loading, initializeMap]) // Now depends on loading state

  // Update markers when selected location changes
  useEffect(() => {
    const container = mapRef.current
    if (container && container._leafletMap) {
      addLocationMarkers(container._leafletMap, selectedLocation)
    }
  }, [selectedLocation, addLocationMarkers]) // Update when selected location changes

  // Period-based location mapping
  const getPeriodKey = (periodString) => {
    if (!periodString || periodString === 'All Periods') return 'all'
    return periodString.split(' (')[0].toLowerCase().replace(/ /g, '_')
  }

  // String normalization for robust matching
  const normalizeString = (str) => {
    return str.toLowerCase()
             .replace(/[^\w\s]/g, '') // Remove punctuation
             .replace(/\s+/g, ' ')    // Collapse whitespace
             .trim()
  }

  // Historical periods with colors
  const historicalPeriods = [
    { name: 'All Periods', key: 'all', color: null },
    { name: 'Patriarchal Era', key: 'patriarchal_era', color: '#FF6B35', description: 'c. 2100-1700 BC' },
    { name: 'Exodus Period', key: 'exodus_period', color: '#F7931E', description: 'c. 1300 BC' },
    { name: 'Period of Judges', key: 'period_of_judges', color: '#FFD23F', description: 'c. 1200-1000 BC' },
    { name: 'United Kingdom', key: 'united_kingdom', color: '#06FFA5', description: 'c. 1000-930 BC' },
    { name: 'Divided Kingdom', key: 'divided_kingdom', color: '#3B82F6', description: 'c. 930-586 BC' },
    { name: 'Babylonian Exile', key: 'babylonian_exile', color: '#8B5CF6', description: 'c. 586-538 BC' },
    { name: 'Post-Exile', key: 'post-exile', color: '#10B981', description: 'c. 538-400 BC' },
    { name: 'Time of Jesus', key: 'time_of_jesus', color: '#F59E0B', description: 'c. 4 BC - 30 AD' },
    { name: 'Apostolic Era', key: 'apostolic_era', color: '#EF4444', description: 'c. 30-100 AD' }
  ]

  const locationPeriodMap = {
    // Patriarchal Era (c. 2100-1700 BC)
    'patriarchal_era': ['Ur', 'Haran', 'Shechem', 'Bethel', 'Hebron', 'Beersheba', 'Mamre', 'Salem'],
    
    // Exodus Period (c. 1300 BC) 
    'exodus_period': ['Egypt', 'Goshen', 'Mount Sinai', 'Kadesh Barnea', 'Wilderness of Sin', 'Rephidim', 'Mount Horeb', 'Red Sea'],
    
    // Period of Judges (c. 1200-1000 BC)
    'period_of_judges': ['Shiloh', 'Mizpah', 'Ramah', 'Gilgal', 'Jericho', 'Ai', 'Gibeon', 'Debir', 'Hazor'],
    
    // United Kingdom (c. 1000-930 BC)
    'united_kingdom': ['Jerusalem', 'Bethlehem', 'Hebron', 'Gibeon', 'Geba', 'Temple Mount', 'City of David'],
    
    // Divided Kingdom (c. 930-586 BC)
    'divided_kingdom': ['Jerusalem', 'Samaria', 'Bethel', 'Dan', 'Beersheba', 'Damascus'],
    
    // Babylonian Exile (c. 586-538 BC)
    'babylonian_exile': ['Babylon', 'Jerusalem', 'Riblah', 'Ramah', 'Mizpah', 'Tel Aviv'],
    
    // Post-Exile (c. 538-400 BC)
    'post-exile': ['Jerusalem', 'Temple Mount'],
    
    // Time of Jesus (c. 4 BC - 30 AD)
    'time_of_jesus': ['Bethlehem', 'Nazareth', 'Jerusalem', 'Sea of Galilee', 'Capernaum', 'Jordan River', 'Mount of Olives', 'Golgotha', 'Bethany', 'Jericho'],
    
    // Apostolic Era (c. 30-100 AD)
    'apostolic_era': ['Jerusalem', 'Antioch', 'Damascus', 'Ephesus', 'Corinth', 'Rome', 'Philippi', 'Thessalonica', 'Athens', 'Caesarea']
  }

  const getQuickAccessForPeriod = (periodString) => {
    const periodKey = getPeriodKey(periodString)
    
    if (periodKey === 'all') {
      return [
        { name: 'Jerusalem', icon: '🏛️', subtext: 'Jerusalem' },
        { name: 'Mount Sinai', icon: '⛰️', subtext: 'Jabal Musa (traditional)' },
        { name: 'Bethlehem', icon: '⭐', subtext: 'Bethlehem' },
        { name: 'Sea of Galilee', icon: '🌊', subtext: 'Lake Kinneret' }
      ]
    }

    const periodLocations = {
      'patriarchal_era': [
        { name: 'Ur', icon: '🏺', subtext: 'Abraham\'s birthplace' },
        { name: 'Haran', icon: '🏕️', subtext: 'Terah\'s dwelling' },
        { name: 'Hebron', icon: '⛺', subtext: 'Abraham\'s oak' },
        { name: 'Beersheba', icon: '💧', subtext: 'Well of the oath' }
      ],
      'exodus_period': [
        { name: 'Egypt', icon: '🏜️', subtext: 'Land of bondage' },
        { name: 'Mount Sinai', icon: '⛰️', subtext: 'The Law given' },
        { name: 'Red Sea', icon: '🌊', subtext: 'Miraculous crossing' },
        { name: 'Kadesh-Barnea', icon: '🏕️', subtext: 'Wilderness camp' }
      ],
      'period_of_judges': [
        { name: 'Shiloh', icon: '⛪', subtext: 'Tabernacle location' },
        { name: 'Jericho', icon: '🏰', subtext: 'Walls fell down' },
        { name: 'Gibeon', icon: '⚔️', subtext: 'Sun stood still' },
        { name: 'Mizpah', icon: '🏛️', subtext: 'Samuel\'s circuit' }
      ],
      'united_kingdom': [
        { name: 'Jerusalem', icon: '👑', subtext: 'David\'s capital' },
        { name: 'Bethlehem', icon: '🏠', subtext: 'David\'s birthplace' },
        { name: 'Hebron', icon: '👑', subtext: 'David\'s first capital' },
        { name: 'Temple Mount', icon: '🏛️', subtext: 'Solomon\'s temple' }
      ],
      'divided_kingdom': [
        { name: 'Jerusalem', icon: '🏛️', subtext: 'Judah\'s capital' },
        { name: 'Samaria', icon: '🏰', subtext: 'Israel\'s capital' },
        { name: 'Bethel', icon: '🐄', subtext: 'Golden calf shrine' },
        { name: 'Dan', icon: '🐄', subtext: 'Northern shrine' }
      ],
      'babylonian_exile': [
        { name: 'Babylon', icon: '🏛️', subtext: 'Exile destination' },
        { name: 'Jerusalem', icon: '💥', subtext: 'Temple destroyed' },
        { name: 'Riblah', icon: '⚖️', subtext: 'Judgment seat' },
        { name: 'Tel-abib', icon: '🏕️', subtext: 'Ezekiel\'s vision' }
      ],
      'post-exile': [
        { name: 'Jerusalem', icon: '🔨', subtext: 'Temple rebuilt' },
        { name: 'Temple Mount', icon: '⛪', subtext: 'Second temple' },
        { name: 'Nehemiah\'s Wall', icon: '🧱', subtext: 'Wall rebuilt' },
        { name: 'Samaria', icon: '🏰', subtext: 'Samaritan conflict' }
      ],
      'time_of_jesus': [
        { name: 'Bethlehem', icon: '⭐', subtext: 'Jesus born' },
        { name: 'Nazareth', icon: '🏠', subtext: 'Jesus raised' },
        { name: 'Sea of Galilee', icon: '🌊', subtext: 'Ministry center' },
        { name: 'Jerusalem', icon: '✝️', subtext: 'Crucifixion' }
      ],
      'apostolic_era': [
        { name: 'Jerusalem', icon: '🕊️', subtext: 'Pentecost' },
        { name: 'Antioch', icon: '🌍', subtext: 'First Gentile church' },
        { name: 'Damascus', icon: '⚡', subtext: 'Paul\'s conversion' },
        { name: 'Rome', icon: '🏛️', subtext: 'Empire\'s heart' }
      ]
    }

    return periodLocations[periodKey] || []
  }


  // Filter locations for the dropdown based on dropdown search term
  const filteredDropdownLocations = useMemo(() => {
    if (!locationDropdownSearchTerm.trim()) {
      return locations
    }
    
    const searchNormalized = normalizeString(locationDropdownSearchTerm)
    return locations.filter(location => 
      normalizeString(location.name).includes(searchNormalized) ||
      (location.modern_name && normalizeString(location.modern_name).includes(searchNormalized))
    )
  }, [locations, locationDropdownSearchTerm])


  const fetchLocations = async () => {
    try {
      setLoading(true)
      const response = await fetch('/api/v1/geography/locations')
      
      if (!response.ok) {
        throw new Error(`Failed to fetch locations: ${response.status} ${response.statusText}`)
      }
      
      const data = await response.json()
      
      if (!Array.isArray(data)) {
        throw new Error(`Expected array response, got: ${typeof data}`)
      }
      
      const validLocations = data.filter(location => 
        location.latitude !== null && location.latitude !== undefined && 
        location.longitude !== null && location.longitude !== undefined &&
        !isNaN(parseFloat(location.latitude)) && 
        !isNaN(parseFloat(location.longitude))
      )
      
      setLocations(validLocations)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred'
      setError(errorMessage)
      console.error('Error fetching geographical locations:', err)
    } finally {
      setLoading(false)
    }
  }

  const formatLocationName = (location) => {
    if (location.modern_name) {
      return `${location.name} - ${location.modern_name}`
    }
    return location.name
  }

  const handleLocationSelect = (location) => {
    setSelectedLocation(location)
  }

  const handleResetView = () => {
    setSelectedLocation(null)
  }



  const handleRandomLocation = () => {
    if (locations.length > 0) {
      const randomIndex = Math.floor(Math.random() * locations.length)
      setSelectedLocation(locations[randomIndex])
    }
  }

  const selectLocationByName = (name) => {
    const location = locations.find(loc => 
      loc.name.toLowerCase().includes(name.toLowerCase()) ||
      (loc.modern_name && loc.modern_name.toLowerCase().includes(name.toLowerCase()))
    )
    if (location) {
      setSelectedLocation(location)
    }
  }

  // Safe HTML sanitization function to prevent XSS
  const sanitizeHTML = (str) => {
    if (!str) return ''
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;')
  }

  const getMapStyle = () => {
    // Remove CSS scaling to allow proper Leaflet zoom
    return {
      width: '100%',
      height: '100%'
    }
  }

  if (loading) {
    return (
      <div className="geography-hub">
        <div className="hub-header">
          <h1 className="hub-title">Interactive Biblical Geography Hub</h1>
          <button className="dark-mode-btn active">Dark Mode</button>
        </div>
        <div className="filter-controls">
          <div className="filter-row">
            <div className="filter-group">
              <label className="filter-label">🌍 Map Layer:</label>
              <select className="filter-dropdown">
                <option>Biblical Events</option>
              </select>
            </div>
          </div>
        </div>
        <div className="hub-content">
          <div className="map-panel">
            <div className="panel-header">
              <div className="panel-title">
                <span className="panel-icon">🌍</span>
                <span>Biblical World Map</span>
              </div>
            </div>
            <div className="map-loading">
              <p>📍 Loading biblical locations...</p>
            </div>
          </div>
          <div className="location-panel">
            <div className="location-placeholder-new">
              <div className="panel-header">
                <div className="panel-title">
                  <span className="panel-icon">📍</span>
                  <span>Location Details</span>
                </div>
              </div>
              <div className="placeholder-content">
                <div className="placeholder-icon">🗺️</div>
                <p>Loading locations...</p>
              </div>
            </div>
          </div>
          <div className="ai-panel">
            <div className="panel-header">
              <div className="panel-title">
                <span className="panel-icon">🤖</span>
                <span>Geography AI Assistant</span>
              </div>
            </div>
            <div className="chat-container">
              <div className="chat-messages">
                <div className="ai-message">
                  <div className="message-avatar">AI</div>
                  <div className="message-content">
                    <div className="message-text">Loading biblical geography data...</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="geography-hub">
        <div className="hub-header">
          <h1 className="hub-title">Interactive Biblical Geography Hub</h1>
          <button className="dark-mode-btn active">Dark Mode</button>
        </div>
        <div className="filter-controls">
          <div className="filter-row">
            <div className="filter-group">
              <label className="filter-label">🌍 Map Layer:</label>
              <select className="filter-dropdown">
                <option>Biblical Events</option>
              </select>
            </div>
          </div>
        </div>
        <div className="hub-content">
          <div className="map-panel">
            <div className="panel-header">
              <div className="panel-title">
                <span className="panel-icon">🌍</span>
                <span>Biblical World Map</span>
              </div>
            </div>
            <div className="map-error">
              <p>❌ Error loading map: {error}</p>
              <button onClick={fetchLocations} className="retry-button">
                Retry
              </button>
            </div>
          </div>
          <div className="location-panel">
            <div className="location-placeholder-new">
              <div className="panel-header">
                <div className="panel-title">
                  <span className="panel-icon">📍</span>
                  <span>Location Details</span>
                </div>
              </div>
              <div className="placeholder-content">
                <div className="placeholder-icon">❌</div>
                <p>Unable to load locations</p>
              </div>
            </div>
          </div>
          <div className="ai-panel">
            <div className="panel-header">
              <div className="panel-title">
                <span className="panel-icon">🤖</span>
                <span>Geography AI Assistant</span>
              </div>
            </div>
            <div className="chat-container">
              <div className="chat-messages">
                <div className="ai-message">
                  <div className="message-avatar">AI</div>
                  <div className="message-content">
                    <div className="message-text">Error loading geography data. Please try again.</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Map control functions
  const handleZoomIn = () => {
    if (mapInstanceRef.current) {
      mapInstanceRef.current.zoomIn()
    }
  }

  const handleZoomOut = () => {
    if (mapInstanceRef.current) {
      mapInstanceRef.current.zoomOut()
    }
  }

  const handleHome = () => {
    if (mapInstanceRef.current) {
      mapInstanceRef.current.setView([31.5, 35.0], 6) // Jerusalem center, zoom 6
    }
  }

  return (
    <div className={`geography-hub ${darkMode ? 'dark-mode' : 'light-mode'}`}>
      {/* Header */}
      <div className="hub-header">
        <h1 className="hub-title">Interactive Biblical Geography Hub</h1>
        <button 
          className={`dark-mode-btn ${darkMode ? 'active' : ''}`}
          onClick={() => setDarkMode(!darkMode)}
        >
          {darkMode ? 'Dark Mode' : 'Light Mode'}
        </button>
      </div>

      {/* Filter Controls */}
      <div className="filter-controls">
        <div className="filter-row">
          <div className="filter-group">
            <label className="filter-label">🌍 Map Layer:</label>
            <select 
              value={mapLayer} 
              onChange={(e) => setMapLayer(e.target.value)}
              className="filter-dropdown"
            >
              <option>Biblical Events</option>
              <option>Archaeological Sites</option>
              <option>Trade Routes</option>
            </select>
          </div>
          
          <div className="filter-group">
            <label className="filter-label">🕊️ Period:</label>
            <div className="custom-period-dropdown" ref={dropdownRef}>
              <div 
                className="period-dropdown-trigger"
                onClick={() => setIsPeriodDropdownOpen(!isPeriodDropdownOpen)}
              >
                {period === 'All Periods' ? (
                  <span>All Periods</span>
                ) : (
                  <div className="selected-period">
                    <div 
                      className="period-dot" 
                      style={{ 
                        backgroundColor: historicalPeriods.find(p => p.name === period.split(' (')[0])?.color 
                      }}
                    ></div>
                    <span>{period.split(' (')[0]}</span>
                  </div>
                )}
                <span className="dropdown-arrow">{isPeriodDropdownOpen ? '▲' : '▼'}</span>
              </div>
              
              {isPeriodDropdownOpen && (
                <div className="period-dropdown-content">
                  <div className="period-dropdown-header">
                    <span>Historical Periods</span>
                    <button 
                      className="close-dropdown-btn"
                      onClick={() => setIsPeriodDropdownOpen(false)}
                    >
                      ✕
                    </button>
                  </div>
                  <div className="period-options">
                    {period === 'All Periods' ? (
                      // Show all periods when "All Periods" is selected
                      historicalPeriods.map((periodOption) => (
                        <div
                          key={periodOption.key}
                          className={`period-option ${period === (periodOption.name === 'All Periods' ? 'All Periods' : `${periodOption.name} (${periodOption.description})`) ? 'selected' : ''}`}
                          onClick={() => {
                            const newPeriod = periodOption.name === 'All Periods' 
                              ? 'All Periods' 
                              : `${periodOption.name} (${periodOption.description})`
                            setPeriod(newPeriod)
                            setIsPeriodDropdownOpen(false)
                          }}
                        >
                          {periodOption.color && (
                            <div 
                              className="period-dot" 
                              style={{ backgroundColor: periodOption.color }}
                            ></div>
                          )}
                          <span className="period-name">{periodOption.name}</span>
                        </div>
                      ))
                    ) : (
                      // Show only the selected period when a specific period is chosen
                      (() => {
                        const selectedPeriodName = period.split(' (')[0]
                        const selectedPeriodData = historicalPeriods.find(p => p.name === selectedPeriodName)
                        const periodLocations = getQuickAccessForPeriod(period)
                        
                        return selectedPeriodData ? (
                          <div className="selected-period-display">
                            <div className="period-header-section">
                              <div className="period-option selected">
                                {selectedPeriodData.color && (
                                  <div 
                                    className="period-dot" 
                                    style={{ backgroundColor: selectedPeriodData.color }}
                                  ></div>
                                )}
                                <span className="period-name">{selectedPeriodData.name}</span>
                              </div>
                            </div>
                            
                            <div className="period-locations-section">
                              <div className="locations-header">Historical Places</div>
                              <div className="location-list">
                                {periodLocations.map((location, index) => (
                                  <div 
                                    key={index}
                                    className="location-item"
                                    onClick={() => {
                                      // Find the location in our locations array and select it
                                      const targetName = normalizeString(location.name)
                                      let foundLocation = locations.find(loc => {
                                        const locName = normalizeString(loc.name)
                                        const locModern = normalizeString(loc.modern_name || '')
                                        
                                        // Try exact matches first
                                        if (locName === targetName || locModern === targetName) {
                                          return true
                                        }
                                        
                                        // Try inclusive matches
                                        if (locName.includes(targetName) || targetName.includes(locName)) {
                                          return true
                                        }
                                        
                                        // Try modern name inclusive matches
                                        if (locModern && (locModern.includes(targetName) || targetName.includes(locModern))) {
                                          return true
                                        }
                                        
                                        return false
                                      })
                                      
                                      // Handle common name variations
                                      if (!foundLocation) {
                                        const nameVariations = {
                                          'tel-abib': 'tel aviv',
                                          'telaviv': 'tel aviv',
                                          'kadesh-barnea': 'kadesh barnea',
                                          'kadeshbarnea': 'kadesh barnea',
                                          'mount sinai': 'sinai',
                                          'red sea': 'red sea',
                                          'sea of galilee': 'galilee'
                                        }
                                        
                                        const variation = nameVariations[targetName]
                                        if (variation) {
                                          foundLocation = locations.find(loc => 
                                            normalizeString(loc.name).includes(variation) ||
                                            normalizeString(loc.modern_name || '').includes(variation)
                                          )
                                        }
                                      }
                                      
                                      if (foundLocation) {
                                        setSelectedLocation(foundLocation)
                                        setIsPeriodDropdownOpen(false)
                                      } else {
                                        console.log(`Location "${location.name}" not found in dataset`)
                                        // Keep dropdown open but provide feedback
                                      }
                                    }}
                                  >
                                    <span className="location-icon">{location.icon}</span>
                                    <div className="location-info">
                                      <span className="location-name">{location.name}</span>
                                      <span className="location-subtext">{location.subtext}</span>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                            
                            <div className="period-actions">
                              <button 
                                className="change-period-btn"
                                onClick={() => {
                                  setPeriod('All Periods')
                                }}
                              >
                                View All Periods
                              </button>
                            </div>
                          </div>
                        ) : null
                      })()
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="select-location-container">
            <div className="select-location-group" ref={selectLocationDropdownRef}>
              <button 
                className="select-location-btn"
                onClick={() => {
                  const newState = !isSelectLocationDropdownOpen
                  setIsSelectLocationDropdownOpen(newState)
                  // Clear search when closing
                  if (!newState) {
                    setLocationDropdownSearchTerm('')
                  }
                }}
              >
                <span>Select Locations</span>
                <span className="dropdown-arrow">{isSelectLocationDropdownOpen ? '▲' : '▼'}</span>
              </button>
              
              {isSelectLocationDropdownOpen && (
                <div className="select-location-dropdown">
                  <div className="select-location-header">
                    <span>Select Location</span>
                  </div>
                  <div className="select-location-search">
                    <input
                      type="text"
                      placeholder="Search locations..."
                      value={locationDropdownSearchTerm}
                      onChange={(e) => setLocationDropdownSearchTerm(e.target.value)}
                      className="location-search-input"
                    />
                  </div>
                  <div className="select-location-list">
                    {filteredDropdownLocations.map((location) => (
                      <div
                        key={location.id}
                        className="select-location-item"
                        onClick={() => {
                          setSelectedLocation(location)
                          setIsSelectLocationDropdownOpen(false)
                          setLocationDropdownSearchTerm('')
                        }}
                      >
                        <span className="location-name">{location.name}</span>
                        {location.modern_name && (
                          <span className="location-modern">({location.modern_name})</span>
                        )}
                      </div>
                    ))}
                  </div>
                  <div className="select-location-footer">
                    {filteredDropdownLocations.length} of {locations.length} locations available
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="hub-content">
        {/* Left Column - Map */}
        <div className="map-panel">
          <div className="panel-header">
            <div className="panel-title">
              <span className="panel-icon">🌍</span>
              <span>Biblical World Map</span>
              <span className="panel-badge">Political Events</span>
            </div>
            <div className="view-controls">
              <div className="view-btn" onClick={handleZoomIn} title="Zoom In">
                <span className="control-icon">+</span>
              </div>
              <div className="view-btn" onClick={handleZoomOut} title="Zoom Out">
                <span className="control-icon">−</span>
              </div>
              <div className="view-btn" onClick={handleHome} title="Home">
                <span className="control-icon">🏠</span>
              </div>
            </div>
          </div>
          
          <div className="map-container-new">
            <div 
              ref={mapRef}
              className="leaflet-map-container" 
              style={{
                width: '100%',
                height: '600px',
                minHeight: '600px',
                borderRadius: '12px',
                backgroundColor: '#f0f8ff',
                position: 'relative',
                display: 'block',
                zIndex: 1,
                overflow: 'hidden'
              }}
            />
            
            {/* Historical Periods Legend */}
            {isHistoricalLegendOpen && (
              <div className="historical-legend">
                <div className="legend-header">
                  <h4>Historical Periods</h4>
                  <button 
                    className="close-legend-btn"
                    onClick={() => setIsHistoricalLegendOpen(false)}
                    title="Close"
                  >
                    ✕
                  </button>
                </div>
                <div className="legend-items">
                  {period === 'All Periods' ? (
                    // Show all periods when "All Periods" is selected
                    historicalPeriods.slice(1).map((periodItem) => {
                      const cssClass = periodItem.key.replace('_', '').toLowerCase()
                      return (
                        <div key={periodItem.key} className="legend-item">
                          <span 
                            className={`legend-dot ${cssClass}`}
                            style={{ backgroundColor: periodItem.color }}
                          ></span>
                          <span>{periodItem.name}</span>
                        </div>
                      )
                    })
                  ) : (
                    // Show only the selected period
                    (() => {
                      const selectedPeriodName = period.split(' (')[0]
                      const selectedPeriodData = historicalPeriods.find(p => p.name === selectedPeriodName)
                      return selectedPeriodData ? (
                        <div className="legend-item selected">
                          <span 
                            className="legend-dot"
                            style={{ backgroundColor: selectedPeriodData.color }}
                          ></span>
                          <span>{selectedPeriodData.name}</span>
                        </div>
                      ) : null
                    })()
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Middle Column - Location Details */}
        <div className="location-panel">
          {selectedLocation ? (
            <>
              <div className="panel-header">
                <div className="panel-title">
                  <span className="panel-icon">📍</span>
                  <span>{selectedLocation.name}</span>
                </div>
              </div>
              
              <div className="location-details-new">
                <div className="detail-section">
                  <h4>Modern Location</h4>
                  <p>{selectedLocation.modern_name || 'Unknown modern location'}, {selectedLocation.region || 'Middle East'}</p>
                </div>
                
                <div className="detail-section">
                  <h4>Historical Period</h4>
                  <div className="period-tag exodus">Exodus Period</div>
                </div>
                
                <div className="detail-section">
                  <h4>Biblical Events</h4>
                  <div className="biblical-events">
                    <div className="event-item">
                      <span className="event-icon">🔥</span>
                      <span>Moses encounters the burning bush</span>
                    </div>
                    <div className="event-item">
                      <span className="event-icon">📜</span>
                      <span>God gives the Ten Commandments</span>
                    </div>
                    <div className="event-item">
                      <span className="event-icon">⚡</span>
                      <span>The golden calf incident</span>
                    </div>
                  </div>
                </div>
                
                <div className="detail-section">
                  <h4>Cross References</h4>
                  <div className="cross-references">
                    <div className="reference">Exodus 3:1-6</div>
                    <div className="reference">"Moses and the burning bush at Mount Horeb"</div>
                    <div className="reference">Exodus 19:18-20</div>
                    <div className="reference">"God descends on Mount Sinai in fire"</div>
                  </div>
                </div>
                
                {showDetailedAnalysis && (
                  <button 
                    className="toggle-analysis-btn"
                    onClick={() => setShowDetailedAnalysis(false)}
                  >
                    📊 Hide Detailed Analysis
                  </button>
                )}
              </div>
            </>
          ) : (
            <div className="location-placeholder-new">
              <div className="panel-header">
                <div className="panel-title">
                  <span className="panel-icon">📍</span>
                  <span>Location Details</span>
                </div>
              </div>
              <div className="placeholder-content">
                <div className="placeholder-icon">🗺️</div>
                <p>Select a location on the map to see detailed information</p>
              </div>
            </div>
          )}
          
          {/* Quick Access */}
          <div className="quick-access">
            <h4>Quick Access - {period === 'All Periods' ? 'All Periods' : period.split(' (')[0]}</h4>
            <div className="quick-location-list">
              {getQuickAccessForPeriod(period).map((location, index) => (
                <div 
                  key={index}
                  className={`quick-location ${selectedLocation?.name === location.name ? 'selected' : ''}`} 
                  onClick={() => selectLocationByName(location.name)}
                >
                  <span className="location-icon">{location.icon}</span>
                  <span>{location.name}</span>
                  <span className="location-subtext">{location.subtext}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column - AI Assistant */}
        <div className="ai-panel">
          <div className="panel-header">
            <div className="panel-title">
              <span className="panel-icon">🤖</span>
              <span>Geography AI Assistant</span>
              <span className="panel-badge">Atlas Chat</span>
            </div>
          </div>
          
          <div className="chat-container">
            <div className="chat-messages">
              <div className="ai-message">
                <div className="message-avatar">AI</div>
                <div className="message-content">
                  <div className="message-text">
                    What archaeological evidence supports the existence of ancient Jerusalem?
                  </div>
                  <div className="message-time">2:30 PM</div>
                </div>
              </div>
              
              <div className="ai-message">
                <div className="message-avatar">AI</div>
                <div className="message-content">
                  <div className="message-text detailed">
                    Archaeological evidence for ancient Jerusalem is extensive. Key discoveries include the City of David excavations from David's time, the Western Wall tunnels showing Herodian-period construction, and numerous artifacts confirming the city's biblical significance.
                  </div>
                  <div className="message-sources">
                    <span className="source-tag">Israeli Antiquities Authority</span>
                    <span className="source-tag">Biblical Archaeology Review</span>
                    <span className="source-tag">City of David Archives</span>
                  </div>
                  <div className="message-time">2:31 PM</div>
                </div>
              </div>
            </div>
            
            <div className="chat-input-area">
              <div className="chat-input-wrapper">
                <input
                  type="text"
                  value={chatMessage}
                  onChange={(e) => setChatMessage(e.target.value)}
                  placeholder="Ask about the selected location or any biblical geography topic..."
                  className="chat-input"
                />
                <button className="chat-send-btn">
                  <span className="send-icon">🎤</span>
                </button>
                <button className="chat-send-btn">
                  <span className="send-icon">➤</span>
                </button>
              </div>
              <div className="input-suggestion">
                Ask about the selected location or any biblical geography topic...
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default InteractiveMap