const HASH_TO_PAGE = {
  home: 'home',
  aistudy: 'chat',
  chat: 'chat',
  sermon: 'sermon',
  scriptures: 'apocrypha',
  apocrypha: 'apocrypha',
  compare: 'textual',
  textual: 'textual',
  canon: 'canon-compare',
  'canon-compare': 'canon-compare',
  'race-misuse': 'race-misuse',
  'bias-explorer': 'bias-explorer',
  factbook: 'factbook',
  research: 'research',
  media: 'media',
  map: 'map',
  library: 'notes',
  notes: 'notes',
  community: 'forum',
  forum: 'forum',
  'admin-scripture-verification': 'scripture-verification-admin'
}

const PAGE_TO_HASH = {
  home: '#home',
  chat: '#aistudy',
  sermon: '#sermon',
  apocrypha: '#scriptures',
  textual: '#compare',
  'canon-compare': '#canon',
  'race-misuse': '#race-misuse',
  'bias-explorer': '#bias-explorer',
  factbook: '#factbook',
  research: '#research',
  media: '#media',
  map: '#map',
  notes: '#library',
  forum: '#community',
  'scripture-verification-admin': '#admin-scripture-verification'
}

export const pageFromHash = (hash = '') => {
  return pageFromKnownHash(hash) ?? 'home'
}

export const pageFromKnownHash = (hash = '') => {
  const route = hash.replace(/^#/, '').split('?')[0].toLowerCase()
  return HASH_TO_PAGE[route] ?? null
}
export const hashForPage = (page) => PAGE_TO_HASH[page] ?? '#home'
export const shareIdFromPath = (path = '') => /^\/share\/([A-Za-z0-9_-]+)\/?$/.exec(path)?.[1] ?? null

const PAGE_TITLES = {
  home: 'The Unbound Bible',
  chat: 'Scripture Research AI',
  sermon: 'Sermon Analysis',
  apocrypha: 'Scripture Reader',
  textual: 'Compare Scripture',
  'canon-compare': 'Canon Comparison',
  'race-misuse': 'Race and Scripture Misuse',
  'bias-explorer': 'Translation Bias Explorer',
  factbook: 'Biblical Factbook',
  research: 'Research Hub',
  media: 'Interactive Media',
  map: 'Biblical Map',
  notes: 'My Library',
  forum: 'Community',
  'scripture-verification-admin': 'Scripture source verification'
}

export const titleForPage = (page) => PAGE_TITLES[page] ?? 'The Unbound Bible'
