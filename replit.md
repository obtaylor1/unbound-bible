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

### Scripture Ingestion Safety (August 2026)

Scripture is published only through the reviewed stage, validate, and confirmed-publish workflow.
Legacy direct writers, sample loaders, network downloaders, and embedding mutators are retired and
exit without touching the network or database. Their filenames remain only to direct operators to
the safe replacement.

Run the following commands from the `backend` directory and target the intended migrated database
explicitly on every command:

```text
python -m app.library.ingest.cli stage --manifest <reviewed-manifest> --database-url <migrated-database-url>
python -m app.library.ingest.cli validate --run-id <run-id> --database-url <migrated-database-url>
python -m app.library.ingest.cli publish --run-id <run-id> --confirm --database-url <migrated-database-url>
```

An explicitly set `DATABASE_URL` is supported, but `--database-url` is recommended so the target is
visible in each command. Do not publish unreviewed, sample, placeholder, or prose content as Scripture.
Adapters for KJV, public English editions, original-language texts, Ethiopian critical texts, and
Adam and Eve are not installed yet; those editions remain unavailable until their source manifests,
licensing, checksums, and adapters complete review.

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

### Historical Direct-Ingestion Work (September 2025)

Earlier direct-ingestion experiments are retained in project history, not as production procedures.
They did not meet the current requirements for reviewed manifests, deterministic validation,
transactional publication, provenance, and explicit database targeting. Do not run the legacy
filenames described in older notes or commits. Use the Scripture Ingestion Safety workflow above.

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
