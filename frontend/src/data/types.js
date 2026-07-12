/**
 * Data Models and Types for The Unbound Bible Research Platform
 * These define the standard structures for user notes, AI responses,
 * sermon claims, research topics, and interactive media.
 */

/**
 * @typedef {Object} BibleTranslation
 * @property {string} code - e.g., 'KJV', 'ERV', 'NLT'
 * @property {string} name - e.g., 'King James Version'
 * @property {string} description - Brief historical/theological background
 * @property {string} language - e.g., 'English', 'Ge'ez'
 * @property {number} yearPublished - Year published or standardized
 * @property {string} tradition - e.g., 'Protestant Standard', 'Roman Catholic', 'Ethiopian Orthodox'
 */

/**
 * @typedef {Object} BibleCanon
 * @property {string} code - e.g., 'PROT66', 'CATH73', 'ETHIO81', 'BROADER'
 * @property {string} name - e.g., 'Protestant Canon', 'Ethiopian Orthodox Canon'
 * @property {number} bookCount - Total books in this tradition
 * @property {string} description - Historical setting and scope
 */

/**
 * @typedef {Object} SourceReference
 * @property {string} title - Title of the source (e.g. "Commentary on Genesis")
 * @property {string} excerpt - Pertinent snippet supporting the AI response
 * @property {string} citation - Standard academic citation format
 * @property {string} [url] - Optional link to source text
 * @property {'scripture'|'commentary'|'translation'|'historical'|'original-language'|'map'} type - Source classification
 * @property {number} confidenceScore - Trust/reliability indicator (0.0 to 1.0)
 */

/**
 * @typedef {Object} AIResponse
 * @property {string} answer - Main structured markdown response
 * @property {SourceReference[]} sources - Verified citations grounding this answer
 * @property {string[]} followUps - Pre-computed or dynamic follow-up prompts
 * @property {number} [confidenceRating] - Overall confidence index (e.g., 94%)
 * @property {boolean} isStudyAidDisclaimerVisible - Must be true for all AI outputs
 */

/**
 * @typedef {Object} ResearchTopic
 * @property {string} slug - Unique URL slug (e.g., 'moses', 'jerusalem', 'covenant')
 * @property {string} name - Display name (e.g., 'Moses')
 * @property {'person'|'place'|'doctrine'|'book'|'theme'} type - Topic classification
 * @property {string} summary - Structured dictionary/encyclopedia summary
 * @property {string[]} scriptureReferences - Scripture hooks
 * @property {Array<{year: string, event: string}>} timelineEvents - Key historical points
 * @property {Array<{name: string, description: string, lat: number, lng: number}>} geographicalMaps - Map references
 * @property {string[]} relatedPeople - Connected biblical figures
 * @property {string[]} relatedPlaces - Connected locations
 * @property {string[]} themes - Associated theological themes
 * @property {Array<{word: string, lang: string, strong: string, def: string}>} originalWords - Key lexicons
 * @property {string[]} commentarySummaries - Commentary excerpts
 * @property {Array<{title: string, type: 'video'|'chart'|'map'|'image', url: string}>} mediaResources - Visual study aids
 * @property {string[]} suggestedQuestions - Prompt helpers
 */

/**
 * @typedef {Object} SermonClaim
 * @property {string} statement - The exact statement made in the sermon
 * @property {string} timestamp - Audio timestamp (e.g., '04:12')
 * @property {'strongly_supported'|'supported_context'|'partially_supported'|'debated'|'unsupported'} severity - Verification category
 * @property {string} issueType - Label (e.g. "Linguistic Mismatch", "Historical Shift", "Accurate Quote")
 * @property {string} explanation - Detailed scholarly audit of the claim
 * @property {string} correction - Verified scriptural or historical correction
 * @property {string[]} references - Supporting verses
 */

/**
 * @typedef {Object} SermonAnalysisReport
 * @property {string} topic - Overall subject
 * @property {string} theme - Theological category
 * @property {number} accuracyScore - Overall scripture agreement (0-100)
 * @property {number} scriptureUsageScore - Scripture saturation (0-100)
 * @property {number} contextScore - Contextual preservation (0-100)
 * @property {number} theologyConsistencyScore - Consistency with historical consensus (0-100)
 * @property {number} confidenceLevel - Factbook search verification rate (0-100)
 * @property {string} shortSummary - 2-sentence summary
 * @property {string} detailedSummary - Full analysis summary
 * @property {string[]} keyPoints - List of main arguments
 * @property {string} conclusion - Synthesized review
 * @property {SermonClaim[]} claims - Audited statements
 * @property {Array<{timestamp: string, text: string}>} transcriptSegments - Full timestamp transcript
 * @property {string[]} furtherStudy - Reading recommendations
 * @property {number} processingTime - Time taken to run audit in seconds
 */

/**
 * @typedef {Object} UserNote
 * @property {string} id - Unique note ID
 * @property {string} [book] - Associated Bible book
 * @property {number} [chapter] - Associated Bible chapter
 * @property {number} [verse] - Associated Bible verse
 * @property {string} text - User inputted content
 * @property {string[]} tags - Categorization tags
 * @property {string} timestamp - ISO timestamp string
 */
