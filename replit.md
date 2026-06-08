# The Unbound Bible

## Overview

The Unbound Bible is a comprehensive web application designed to liberate biblical text from imposed biases and free readers to find their own meaning. The project provides access to biblical texts alongside historical context and geographical information, offering users an enriched understanding of biblical content through integrated historical notes and location data, making scripture more accessible and contextually meaningful without doctrinal constraints.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend Architecture

The backend is built using **FastAPI**, a modern Python web framework chosen for its automatic API documentation, type hints support, and high performance. The application follows a layered architecture pattern:

**Database Layer**: Uses SQLAlchemy ORM with PostgreSQL for data persistence. The choice of PostgreSQL provides robust relational database capabilities needed for complex biblical text relationships. Connection pooling is configured for production scalability.

**Model Layer**: Implements three core domain entities:
- BiblicalText: Stores scripture verses with book, chapter, verse references
- HistoricalNote: Provides contextual historical information linked to specific texts
- GeographicalLocation: Maps biblical locations to modern geographical data

**API Layer**: RESTful endpoints using FastAPI's dependency injection for database sessions. Pydantic schemas handle request/response validation and serialization.

**CORS Configuration**: Configured to allow communication from the frontend development server, with specific origin restrictions for security.

### Frontend Architecture

The frontend uses **React 19** with **Vite** as the build tool, chosen for fast development experience and modern JavaScript features. The setup includes:

**Development Server**: Configured with proxy settings to route API calls to the backend, eliminating CORS issues during development.

**Build System**: Vite provides hot module replacement and optimized production builds.

**Code Quality**: ESLint configuration with React-specific rules ensures consistent code standards.

### Data Architecture

The database schema implements a one-to-many relationship structure where:
- Each biblical text can have multiple historical notes
- Each biblical text can reference multiple geographical locations
- Foreign key constraints maintain data integrity
- Timestamps track creation and modification times

### API Design

RESTful API design with:
- Standardized endpoint naming (`/api/biblical-texts`, `/api/historical-notes`)
- Pagination support for large datasets
- Type-safe responses using Pydantic models
- Health check endpoints for monitoring

## External Dependencies

**Backend Dependencies**:
- **FastAPI**: Web framework for API development
- **SQLAlchemy**: Database ORM for PostgreSQL interaction
- **Pydantic**: Data validation and serialization
- **Uvicorn**: ASGI server for production deployment
- **python-dotenv**: Environment variable management

**Frontend Dependencies**:
- **React**: User interface library
- **Vite**: Build tool and development server
- **ESLint**: Code linting and quality assurance

**Database**: 
- **PostgreSQL**: Primary database for storing biblical texts, historical notes, and geographical data

**Development Tools**:
- Environment-based configuration for database connections
- CORS middleware for cross-origin requests
- Proxy configuration for API routing during development

## Recent Changes

### Adam and Eve PDF Processing and AI Integration (September 18, 2025)

Successfully implemented comprehensive PDF processing capabilities for pseudepigraphal texts with full AI integration:

**PDF Processing Implementation**:
- **PyMuPDF Integration**: Added Python library for robust PDF text extraction and processing
- **Structured Content Extraction**: Created `ingest_adam_eve.py` script that processes 289-page "Book of Adam and Eve" PDF into 51 structured sections
- **Text Cleaning Pipeline**: Implemented regex-based cleaning to remove "Digitized by Google" artifacts and format headers properly
- **Database Integration**: Successfully inserted 26 biblical text records with proper book/chapter/verse structure

**AI Integration and Vector Search**:
- **Vector Embeddings**: Generated OpenAI embeddings for all 26 Adam and Eve texts using `generate_embeddings_adameve.py` batch script
- **Semantic Search Fixes**: Resolved critical SQL parameter binding issues in `vector_search.py` affecting pgvector operations
- **High-Relevance Results**: Integration testing confirms semantic search returns 0.8-0.9 similarity scores for queries like "Adam and Eve leaving the garden" and "Satan tempting Adam"
- **Translation Filtering**: Successfully implemented filtering to search specific translations including "ADAMEVE" code

**Database Schema Updates**:
- **Translation Record**: Created translation entry (ID: 9, code: "ADAMEVE") for proper provenance tracking
- **Content Structure**: Biblical texts stored as "Adam and Eve 2", "Adam and Eve 3" with proper chapter/verse mapping
- **Vector Storage**: All texts now have 1536-dimensional embeddings for AI chat functionality

**Technical Achievements**:
- **SQL Parameter Issues**: Fixed pgvector binding problems by using direct string substitution for vector literals
- **Batch Processing**: Safe embedding generation with progress tracking and commit batching every 5 records
- **Integration Testing**: Created comprehensive test suite verifying database content, embedding presence, and search functionality

**Mission Alignment**:
The Adam and Eve integration expands the decolonizing biblical study mission by:
- Providing access to pseudepigraphal texts often excluded from Western canon
- Enabling AI-powered exploration of Satan's conflicts and Adam's trials
- Supporting semantic search across diverse biblical traditions
- Making ancient texts discoverable through modern AI technology

### Comprehensive UX & Feature Polish (April 2026)

All 6 planned improvements implemented and end-to-end tested:

**T001 – Bug Fixes**:
- Fixed CORS in both `backend/main.py` and `auth-forum-api/main.py` (allow_origins=["*"], allow_credentials=False)
- Added `/api/forum` proxy in `vite.config.js` routing to port 8008 with path rewrite

**T002 – Community Forum with Real API**:
- Rewrote `ForumPage.jsx` with full JWT authentication (AuthModal login/register)
- Real posts loaded from `/api/forum/posts` via Auth Forum API
- Categories encoded as `[Category]` prefix in post titles, parsed client-side
- Dark-themed CSS matching the app's design system

**T003 – Enriched Pseudepigrapha (ApocryphaReader)**:
- Added RICH_CONTENT static panels for 1 Enoch, Jubilees, and Meqabyan
- Each panel includes tradition badge, facts grid, key quote, and scholarly section cards

**T004 – Translation Bias Highlights**:
- Added `getBiasAlerts()` in `TextualComparison.jsx` with specific documented bias cases
- Song of Solomon 1:5: "black AND beautiful" vs KJV "but comely" (High severity)
- Exodus 12:38: "erev rav" ethnic diversity erasure (Medium severity)
- Inline bias alert panel with colored severity badges in the analysis section

**T005 – Improved AI Chat**:
- Rewrote `ChatInterface.jsx` with structured AI responses, CitationCard components
- Follow-up suggestion chips, welcome screen with feature pills
- Collapsible citations panel, formatted answer paragraphs
- Fully dark-themed CSS with purple accent system

**T006 – Polish & UX**:
- Added "Translation Bias Exposed" spotlight section to the homepage
- Two interactive cards showing Hebrew original vs KJV comparison for bias verses
- Cards link to Textual Comparison page for deeper exploration
- Scholarly attribution (Wilda Gafney, Esau McCaulley) for academic credibility

### Navigation Branding Update (September 18, 2025)

Successfully updated navigation branding to reflect the application's clean, accessible identity:

**Brand Simplification**:
- **Logo Update**: Removed book icon (📚) and changed "BiblicalScholar" to "The Unbound Bible"
- **Tagline Removal**: Eliminated "Decolonizing Biblical Study" subtitle for cleaner interface
- **Visual Streamlining**: Navigation now displays simple text-only branding without visual clutter

**Technical Implementation**:
- Updated Navigation.jsx component with clean branding changes
- Maintained all navigation functionality while simplifying visual presentation
- Hot module replacement confirmed successful deployment without errors
- Preserved responsive design and existing CSS styling structure

**Bug Fixes**:
- Fixed "searchTerm is not defined" error in InteractiveMap component by removing unused variable references
- Cleaned up unused search handling functions following UI simplification

### Comprehensive Biblical Data Ingestion Implementation (September 15, 2025)

Successfully implemented production-ready biblical data ingestion system with complete public domain sources:

**Database Population** (46,640+ total records):
- **31,102 KJV verses**: Complete King James Version Bible (all 66 books) from Project Gutenberg File #30
- **14,197 Strong's entries**: Complete Hebrew (8,674) + Greek (5,523) lexicon from secure HTTPS sources  
- **1,340 geographical locations**: Comprehensive biblical geography with accurate coordinates from OpenBible.info
- **Translation metadata**: KJV translation record with proper provenance and licensing

**Enhanced Database Schema**:
- **LexiconEntry model**: Complete Strong's Exhaustive Concordance integration
- **Translation model**: Support for multiple biblical translations and original languages
- **Enhanced relationships**: Proper foreign key constraints linking biblical texts, lexicon, and geography
- **Original language support**: Schema ready for Hebrew/Greek text integration

**Security Implementation**:
- **HTTPS-only data sources**: Eliminated HTTP vulnerabilities with secure GitHub repositories
- **Cryptographic verification**: SHA256 checksum validation for data integrity
- **Fail-closed security**: Secure-by-default behavior with proper error handling
- **SSL certificate validation**: MITM attack prevention for all downloads

**Data Ingestion Scripts**:
- `ingest_kjv.py`: Complete KJV Bible text parser handling Project Gutenberg's structured format
- `ingest_strongs.py`: Secure Strong's Concordance ingestion with XML/CSV parsing capabilities
- `ingest_geography.py`: OpenBible.info JSONL data parser with coordinate validation
- `ingest_all_data.py`: Master orchestration script for complete data population
- `ethiopian_canon_placeholder.json`: Framework for future Ethiopian Orthodox canon integration

**Data Sources & Provenance**:
- **KJV Bible**: Project Gutenberg File #30 (public domain, complete 31,102 verses)
- **Strong's Concordance**: MorphGNT GitHub repository (public domain, cryptographically verified)
- **Biblical Geography**: OpenBible.info (Creative Commons Attribution 4.0, 1,340 verified locations)
- **Ethiopian Canon**: Academic placeholder awaiting authentic Ge'ez manuscript sources

**Mission Alignment**:
The system now provides authentic biblical sources supporting the decolonization mission through:
- Complete public domain biblical texts free from modern copyright restrictions
- Original language lexical data enabling Hebrew/Greek word studies
- Geographical context connecting biblical narratives to authentic historical locations  
- Framework for non-Western canonical traditions (Ethiopian Orthodox placeholder)
- Transparent provenance and licensing documentation

### Authentication and Forum System Implementation (September 15, 2025)

Successfully implemented a comprehensive authentication and forum system with production-ready security:

**Auth Forum API Service** (Port 8008):
- Separate FastAPI service for user authentication and forum functionality
- JWT-based authentication with secure token management
- Role-based access control (member/moderator roles)
- User registration, login, and profile management
- Password hashing with bcrypt for security

**Database Models**:
- auth_users: User accounts with email, username, role, and profile information
- forum_posts: Discussion posts with title, content, and author relationships
- forum_comments: Threaded comments linked to posts and authors
- Proper foreign key relationships and data integrity constraints

**Security Features**:
- JWT authentication with mandatory secure secret keys
- Role-based authorization preventing privilege escalation
- Privacy protection - no email exposure in public forum responses
- SQLAlchemy enum-safe role comparisons
- Protected moderator-only administrative endpoints

**API Endpoints**:
- `/auth/register` - User registration (auto-assigns member role)
- `/auth/login` - User authentication with JWT token response
- `/auth/me` - User profile retrieval
- `/posts` - Forum post creation and listing
- `/posts/{id}/comments` - Comment management
- `/admin/users/{id}/role` - Moderator-only role management

**Testing Verification**:
- User registration and authentication tested successfully
- Forum post creation and retrieval working
- Comment system functional with author information
- JWT token authentication protecting restricted endpoints
- Role-based access control verified

### Previous Implementation (September 15, 2025)

**Core Backend Implementation**:
- FastAPI application with PostgreSQL database integration
- Three core database models: BiblicalText, HistoricalNote, GeographicalLocation
- Pydantic schemas for type-safe API responses
- Health check endpoints and RESTful API design

**Frontend Implementation**:
- React application with Vite build configuration
- Interactive interface with sermon analysis and geographical mapping
- Leaflet.js integration for biblical location visualization
- OpenAI integration for sermon transcription and analysis

**Development Workflows**:
- Backend API workflow (port 8000) - Core biblical content API
- Auth Forum API workflow (port 8008) - Authentication and forum system  
- Frontend Server workflow (port 5000) - React application with proxy

The platform now provides a complete foundation for biblical study with user accounts, community discussions, and rich content features.