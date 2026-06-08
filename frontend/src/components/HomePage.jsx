import { useState, useEffect } from 'react'
import './HomePage.css'
import heroImage from '../assets/images/garden-of-eden-hero.png'
import textualComparisonIcon from '../assets/images/textual-comparison-icon.png'

function HomePage({ onPageChange }) {
  const [searchQuery, setSearchQuery] = useState('')

  const handleSearch = (e) => {
    e.preventDefault()
    // Handle search functionality
    console.log('Searching for:', searchQuery)
  }

  const handleFeatureClick = (featurePage) => {
    if (onPageChange) {
      onPageChange(featurePage)
    }
  }

  return (
    <div className="homepage">
      {/* Garden of Eden Hero Section */}
      <section className="eden-hero-section">
        <div className="eden-hero-background">
          <img src={heroImage} alt="Garden of Eden" className="hero-image" />
          <div className="hero-overlay-top"></div>
          <div className="hero-overlay-bottom"></div>
        </div>
        
        <div className="eden-hero-content">
          <div className="hero-text-container">
            <h1 className="eden-hero-title">
              Unlocking Scripture Through Historical Context and Original Languages
            </h1>
            <p className="eden-hero-tagline">
              A world of harmony, spirit, and creation where biblical wisdom meets authentic understanding
            </p>
            
            <div className="eden-cta-buttons">
              <button 
                onClick={() => handleFeatureClick('textual')} 
                className="eden-primary-btn"
              >
                Begin the Journey
              </button>
              <button 
                onClick={() => handleFeatureClick('chat')} 
                className="eden-secondary-btn"
              >
                Learn More
              </button>
            </div>
          </div>
          
          <div className="floating-particles">
            <div className="particle particle-1"></div>
            <div className="particle particle-2"></div>
            <div className="particle particle-3"></div>
            <div className="particle particle-4"></div>
            <div className="particle particle-5"></div>
          </div>
        </div>
      </section>

      {/* Mission Statement */}
      <section className="mission-section">
        <div className="container">
          <h2 className="section-title">
            Moving beyond traditional religious methodics toward rigorous academic inquiry
          </h2>
          <p className="mission-description">
            The Unbound Bible provides a modern, evidence-based approach to scriptural study. Our platform enables scholars to 
            access historical context, original language texts, and peer-reviewed historical resources to deepen their 
            understanding of scripture.
          </p>
          <div className="mission-tags">
            <span className="tag">Historical Context</span>
            <span className="tag">Original Languages</span>
            <span className="tag">The Study</span>
            <span className="tag">Academic Resources</span>
          </div>
        </div>
      </section>

      {/* Translation Bias Spotlight */}
      <section className="bias-spotlight-section">
        <div className="container">
          <div className="bias-spotlight-header">
            <span className="bias-spotlight-label">DECOLONIZING SCRIPTURE</span>
            <h2 className="section-title">Translation Bias Exposed</h2>
            <p className="section-subtitle">
              The KJV was translated in 1611 by a committee shaped by European cultural assumptions.
              Here are two documented examples where translator bias shaped the text.
            </p>
          </div>
          <div className="bias-spotlight-grid">
            <div className="bias-spotlight-card" onClick={() => handleFeatureClick('textual')}>
              <div className="bias-card-tag red">🔴 High Severity</div>
              <div className="bias-card-verse">Song of Solomon 1:5</div>
              <div className="bias-comparison">
                <div className="bias-original-text">
                  <span className="lang-label">Hebrew Original</span>
                  <span className="lang-text">"I am black <strong>AND</strong> beautiful"</span>
                </div>
                <div className="bias-kjv-text">
                  <span className="lang-label">KJV Translation</span>
                  <span className="lang-text">"I am black <strong>BUT</strong> comely"</span>
                </div>
              </div>
              <p className="bias-card-note">The Hebrew conjunction "וְ" means "and" — not "but." The contrast was added by translators who could not conceive of blackness as inherently beautiful. — Scholar Wilda Gafney</p>
              <span className="explore-link">Explore this verse →</span>
            </div>
            <div className="bias-spotlight-card" onClick={() => handleFeatureClick('textual')}>
              <div className="bias-card-tag yellow">🟡 Medium Severity</div>
              <div className="bias-card-verse">Exodus 12:38</div>
              <div className="bias-comparison">
                <div className="bias-original-text">
                  <span className="lang-label">Hebrew Original</span>
                  <span className="lang-text">עֵרֶב רַב — "erev rav" <br /><em>(ethnically diverse multitude)</em></span>
                </div>
                <div className="bias-kjv-text">
                  <span className="lang-label">KJV Translation</span>
                  <span className="lang-text">"A mixed multitude"</span>
                </div>
              </div>
              <p className="bias-card-note">The phrase specifically emphasizes ethnic diversity — including Egyptians, Cushites, and Africans who left Egypt with the Israelites. The KJV's generic phrasing erases their presence. — Scholar Esau McCaulley</p>
              <span className="explore-link">Explore this verse →</span>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="stats-section">
        <div className="container">
          <h2 className="section-title">Trusted by the Academic Community</h2>
          <p className="stats-subtitle">Join thousands of scholars advancing biblical understanding</p>
          
          <div className="stats-grid">
            <div className="stat-item">
              <div className="stat-number">3k+</div>
              <div className="stat-label">Active Scholars</div>
            </div>
            <div className="stat-item">
              <div className="stat-number">2.5k+</div>
              <div className="stat-label">Research Papers</div>
            </div>
            <div className="stat-item">
              <div className="stat-number">450+</div>
              <div className="stat-label">Institutions</div>
            </div>
            <div className="stat-item">
              <div className="stat-icon">🎓</div>
              <div className="stat-label">Academic Excellence</div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="features-section">
        <div className="container">
          <h2 className="section-title">Scholarly Tools & Features</h2>
          <p className="section-subtitle">
            Comprehensive tools designed for the modern academic and theological researcher, built with 
            deep cultural perspectives and multilingual support
          </p>
          <p className="features-note">All features available in Plus tier</p>
          
          <div className="features-grid">
            <div className="feature-card">
              <div className="feature-icon">
                <img src={textualComparisonIcon} alt="Ancient Manuscripts" className="feature-icon-image" />
              </div>
              <h3>Textual Comparison</h3>
              <p>Compare multiple translations side-by-side with detailed original language analysis.</p>
              <ul className="feature-benefits">
                <li>All ISO 639-3 Supported Polyglotte Dictionary</li>
                <li>Textual Narrative Context and Historical Significance</li>
                <li>Cross-reference biblical passages</li>
                <li>Strong's concordance integration</li>
              </ul>
              <button className="feature-button" onClick={() => handleFeatureClick('textual')}>
                Get Started
              </button>
            </div>

            <div className="feature-card">
              <div className="feature-icon">🎤</div>
              <h3>Sermon Analysis</h3>
              <p>AI-powered sermon transcription and theological analysis for deeper understanding.</p>
              <ul className="feature-benefits">
                <li>Audio transcription and analysis</li>
                <li>Biblical theme identification</li>
                <li>Historical connection mapping</li>
                <li>Cultural significance assessment</li>
              </ul>
              <button className="feature-button" onClick={() => handleFeatureClick('sermon')}>
                Get Started
              </button>
            </div>

            <div className="feature-card">
              <div className="feature-icon">🗺️</div>
              <h3>Interactive Biblical Map</h3>
              <p>Explore biblical locations with historical and geographical context.</p>
              <ul className="feature-benefits">
                <li>Interactive maps with ancient toponyms</li>
                <li>Historical timeline integration</li>
                <li>Archaeological site information</li>
                <li>Cultural and historical narratives</li>
              </ul>
              <button className="feature-button" onClick={() => handleFeatureClick('map')}>
                Get Started
              </button>
            </div>

            <div className="feature-card">
              <div className="feature-icon">💬</div>
              <h3>Community Forum</h3>
              <p>Engage with scholars and theologians in meaningful academic discourse.</p>
              <ul className="feature-benefits">
                <li>Moderated scholarly discussions</li>
                <li>Peer review system</li>
                <li>Resource sharing platform</li>
                <li>Expert consultations available</li>
              </ul>
              <button className="feature-button" onClick={() => handleFeatureClick('forum')}>
                Get Started
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Who We Serve */}
      <section className="serve-section">
        <div className="container">
          <h2 className="section-title">Who The Unbound Bible Serves</h2>
          <p className="section-subtitle">
            Designed for everyone pursuing deeper biblical understanding, from academic researchers to 
            theological students and curious believers seeking comprehensive insights.
          </p>
          
          <div className="serve-grid">
            <div className="serve-card">
              <div className="serve-icon">👥</div>
              <h3>Scholars & Students</h3>
              <p>
                Academic researchers, theologians, and students seeking rigorous, evidence-based 
                biblical study resources with access to original languages and historical contexts.
              </p>
            </div>

            <div className="serve-card">
              <div className="serve-icon">⛪</div>
              <h3>Pastors & Theologians</h3>
              <p>
                Religious leaders seeking authentic scriptural understanding beyond colonial interpretations, 
                with tools for sermon preparation and theological development.
              </p>
            </div>

            <div className="serve-card">
              <div className="serve-icon">🔍</div>
              <h3>Curious Believers</h3>
              <p>
                Individuals passionate about understanding scripture in its original historical, 
                cultural, and linguistic contexts through accessible yet scholarly resources.
              </p>
            </div>
          </div>
          
          <div className="serve-grid-second">
            <div className="serve-card">
              <div className="serve-icon">👥</div>
              <h3>Scholars & Students</h3>
              <p>
                Advanced research tools, peer collaboration features, and access to comprehensive 
                databases for in-depth biblical scholarship and academic publication.
              </p>
            </div>

            <div className="serve-card">
              <div className="serve-icon">⛪</div>
              <h3>Pastors & Theologians</h3>
              <p>
                Contextual sermon preparation tools, historical accuracy verification, and 
                cross-cultural interpretation resources for authentic teaching.
              </p>
            </div>

            <div className="serve-card">
              <div className="serve-icon">🔍</div>
              <h3>Curious Believers</h3>
              <p>
                User-friendly interfaces, guided learning paths, and community support for 
                personal spiritual growth through scholarly biblical understanding.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="cta-section">
        <div className="container">
          <div className="cta-content">
            <h2 className="cta-title">Ready to Begin Your Scholarly Journey?</h2>
            <p className="cta-description">
              Join thousands of scholars, theologians, and students who are using The Unbound Bible to 
              deepen their understanding of biblical texts through rigorous academic analysis.
            </p>
            <div className="cta-buttons">
              <button className="cta-button primary" onClick={() => handleFeatureClick('textual')}>
                Start Free Research
              </button>
              <button className="cta-button secondary" onClick={() => handleFeatureClick('chat')}>
                Request Demo
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}

export default HomePage