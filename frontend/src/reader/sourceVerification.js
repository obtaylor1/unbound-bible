export const SOURCE_VERIFICATION_LABELS = Object.freeze(Object.assign(Object.create(null), {
  in_progress: 'Source verification in progress',
  verified_exact: 'Source verified',
  verified_formatting: 'Verified with documented formatting changes',
  verified_rebuilt: 'Rebuilt from verified source',
  review_required: 'Source review required',
}))

const VERIFIED_SOURCE_STATUSES = new Set([
  'verified_exact',
  'verified_formatting',
  'verified_rebuilt',
])
const MAXIMUM_DECODE_PASSES = 12
const URL_IN_TEXT = /\b[a-z][a-z0-9+.-]*:\/\//iu
const POTENTIAL_ASSIGNMENT = /(?:^|[^A-Za-z0-9_-])([A-Za-z][A-Za-z0-9_-]{0,80})\s*(?::|=)\s*\S+/gu
const CREDENTIAL_WORDS = new Set([
  'authorization', 'credential', 'credentials', 'passwd', 'password', 'secret', 'token',
])
const CREDENTIAL_SUFFIXES = ['credential', 'credentials', 'passwd', 'password', 'secret', 'token']
const CREDENTIAL_COMPOUNDS = new Set([
  'accesskey', 'apikey', 'clientkey', 'consumerkey', 'encryptionkey',
  'privatekey', 'publickey', 'secretkey', 'signingkey',
])
const BEARER_SECRET = /\bbearer\s+[A-Za-z0-9._~+/-]{6,}/iu
const STANDALONE_SECRET = /(?:^|[^A-Za-z0-9_])(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{20,255}|(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,255}|(?:AKIA|ASIA)[A-Z0-9]{16}|sk-[A-Za-z0-9_-]{20,255}|AIza[A-Za-z0-9_-]{35}|xox[baprs]-[A-Za-z0-9-]{20,255})(?:$|[^A-Za-z0-9_])/u
const JWT_SECRET = /(?:^|[^A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?:$|[^A-Za-z0-9_-])/u
const WINDOWS_DRIVE_PATH = /(?:^|[^A-Za-z0-9])[A-Z]:[\\/]/iu
const KNOWN_POSIX_PATH = /(?:^|[^A-Za-z0-9])\/(?:users|home|private|var|tmp|etc|opt|root|volumes|srv|data|mnt|app|workspace)(?:\/|\b)/iu
const GENERIC_ABSOLUTE_PATH = /(?:^|[^A-Za-z0-9:/])\/(?!\/|\s|[?#])[^/\s?#]+(?:\/[^\s?#]*)?/u
const HOME_PATH = /(?:^|[\s="'(?&])(?:~|\$HOME|\$\{HOME\}|%USERPROFILE%|%HOMEPATH%)[\\/]/iu
const TRAVERSAL_PATH = /(?:^|[^A-Za-z0-9])\.\.[\\/]/u
const NON_ASCII_SEPARATOR = /[\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]/u

export function sourceVerificationLabel(status) {
  return Object.hasOwn(SOURCE_VERIFICATION_LABELS, status)
    ? SOURCE_VERIFICATION_LABELS[status]
    : 'Source status unavailable'
}

export function isVerifiedSourceStatus(status) {
  return VERIFIED_SOURCE_STATUSES.has(status)
}

function decodedVariants(value) {
  const variants = [value.normalize('NFC')]
  for (let pass = 0; pass < MAXIMUM_DECODE_PASSES; pass += 1) {
    let invalidEncoding = false
    const decoded = variants.at(-1).replace(/(?:%[0-9A-Fa-f]{2})+/gu, (encoded) => {
      try {
        return decodeURIComponent(encoded)
      } catch {
        invalidEncoding = true
        return encoded
      }
    })
    if (invalidEncoding) return null
    if (decoded === variants.at(-1)) return variants
    variants.push(decoded)
  }
  const remainingEncoding = /(?:%[0-9A-Fa-f]{2})+/u.test(variants.at(-1))
  return remainingEncoding ? null : variants
}

function credentialKeyWords(key) {
  return key
    .replace(/([A-Z])([A-Z][a-z])/gu, '$1_$2')
    .replace(/([a-z0-9])([A-Z])/gu, '$1_$2')
    .toLocaleLowerCase()
    .split(/[_-]+/u)
    .filter(Boolean)
}

function isCredentialKey(key) {
  const words = credentialKeyWords(key)
  const collapsed = words.join('')
  return words.some((word) => CREDENTIAL_WORDS.has(word))
    || CREDENTIAL_SUFFIXES.some((suffix) => collapsed.endsWith(suffix))
    || [...CREDENTIAL_COMPOUNDS].some((compound) => collapsed.endsWith(compound))
    || words.some((word, index) => CREDENTIAL_COMPOUNDS.has(`${word}${words[index + 1] ?? ''}`))
}

function containsCredentialAssignment(value) {
  POTENTIAL_ASSIGNMENT.lastIndex = 0
  return [...value.matchAll(POTENTIAL_ASSIGNMENT)].some((match) => isCredentialKey(match[1]))
}

function containsHighConfidenceSecret(value) {
  return BEARER_SECRET.test(value) || STANDALONE_SECRET.test(value) || JWT_SECRET.test(value)
}

function looksLikeLocalPath(value, { genericAbsolute = false } = {}) {
  const lowered = value.toLocaleLowerCase()
  if (
    lowered.includes('file://')
    || value.includes('\\')
    || WINDOWS_DRIVE_PATH.test(value)
    || KNOWN_POSIX_PATH.test(value)
    || HOME_PATH.test(value)
    || TRAVERSAL_PATH.test(value)
  ) return true
  return genericAbsolute && GENERIC_ABSOLUTE_PATH.test(value)
}

function unsafeTextDisclosure(value) {
  const variants = decodedVariants(value)
  if (!variants) return true
  return variants.some((variant) => (
    /\p{C}/u.test(variant)
    || NON_ASCII_SEPARATOR.test(variant)
    || URL_IN_TEXT.test(variant)
    || containsCredentialAssignment(variant)
    || containsHighConfidenceSecret(variant)
    || looksLikeLocalPath(variant, { genericAbsolute: true })
  ))
}

export function boundedPublicText(value, maximumLength) {
  if (typeof value !== 'string') return null
  const text = value.trim()
  if (!text || text.length > maximumLength || unsafeTextDisclosure(text)) return null
  return text.replace(/\s+/gu, ' ')
}

function ipv4Value(hostname) {
  if (!/^\d{1,3}(?:\.\d{1,3}){3}$/u.test(hostname)) return null
  const parts = hostname.split('.').map(Number)
  if (parts.some((part) => part > 255)) return null
  return parts.reduce((value, part) => ((value * 256) + part) >>> 0, 0)
}

function ipv4InCidr(value, base, bits) {
  const baseValue = ipv4Value(base)
  const mask = bits === 0 ? 0 : (0xffffffff << (32 - bits)) >>> 0
  return baseValue !== null && (value & mask) === (baseValue & mask)
}

function unsafeIpv4(hostname) {
  const value = ipv4Value(hostname)
  if (value === null) return false
  if (['192.0.0.9', '192.0.0.10'].includes(hostname)) return false
  return [
    ['0.0.0.0', 8], ['10.0.0.0', 8], ['100.64.0.0', 10], ['127.0.0.0', 8],
    ['169.254.0.0', 16], ['172.16.0.0', 12], ['192.0.0.0', 24], ['192.0.2.0', 24],
    ['192.88.99.0', 24], ['192.168.0.0', 16], ['198.18.0.0', 15],
    ['198.51.100.0', 24], ['203.0.113.0', 24], ['224.0.0.0', 4], ['240.0.0.0', 4],
  ].some(([base, bits]) => ipv4InCidr(value, base, bits))
}

function ipv6Value(hostname) {
  const host = hostname.replace(/^\[|\]$/gu, '').toLocaleLowerCase()
  if (!host.includes(':') || host.includes('%')) return null
  const halves = host.split('::')
  if (halves.length > 2) return null
  const left = halves[0] ? halves[0].split(':') : []
  const right = halves.length === 2 && halves[1] ? halves[1].split(':') : []
  if ([...left, ...right].some((part) => !/^[0-9a-f]{1,4}$/u.test(part))) return null
  const missing = 8 - left.length - right.length
  if ((halves.length === 1 && missing !== 0) || (halves.length === 2 && missing < 1)) return null
  const parts = [...left, ...Array.from({ length: missing }, () => '0'), ...right]
  return parts.reduce((value, part) => (value << 16n) + BigInt(`0x${part}`), 0n)
}

function ipv6InCidr(value, base, bits) {
  const baseValue = ipv6Value(base)
  if (baseValue === null) return false
  const shift = 128n - BigInt(bits)
  return (value >> shift) === (baseValue >> shift)
}

function unsafeIpv6(hostname) {
  const value = ipv6Value(hostname)
  if (value === null) return false
  if (
    ipv6InCidr(value, '64:ff9b::', 96)
    || ipv6InCidr(value, '64:ff9b:1::', 48)
  ) return true
  const globallyRoutable = ipv6InCidr(value, '2000::', 3)
  if (!globallyRoutable) return true
  return [
    ['2001::', 32],
    ['2001:2::', 48],
    ['2001:10::', 28],
    ['2001:20::', 28],
    ['2001:db8::', 32],
    ['2002::', 16],
    ['3fff::', 20],
  ].some(([base, bits]) => ipv6InCidr(value, base, bits))
}

function unsafeHostname(hostname) {
  const host = hostname.toLocaleLowerCase().replace(/\.+$/u, '')
  return host === 'localhost'
    || host === 'localhost.localdomain'
    || host.endsWith('.local')
    || unsafeIpv4(host)
    || unsafeIpv6(host)
}

function unsafeUrlDisclosure(value) {
  const variants = decodedVariants(value)
  if (!variants) return true
  return variants.some((variant) => {
    if (
      /[\p{C}\\\s]/u.test(variant)
      || NON_ASCII_SEPARATOR.test(variant)
      || containsCredentialAssignment(variant)
      || containsHighConfidenceSecret(variant)
      || looksLikeLocalPath(variant)
    ) return true

    try {
      const parsed = new URL(variant)
      if (!['http:', 'https:'].includes(parsed.protocol)) return true
      if (!parsed.hostname || parsed.username || parsed.password || unsafeHostname(parsed.hostname)) return true
      for (const [key, queryValue] of parsed.searchParams.entries()) {
        if (
          isCredentialKey(key)
          || containsHighConfidenceSecret(queryValue)
          || containsCredentialAssignment(queryValue)
          || looksLikeLocalPath(queryValue, { genericAbsolute: true })
        ) return true
      }
      const fragment = parsed.hash.slice(1)
      return Boolean(fragment) && (
        containsCredentialAssignment(fragment)
        || containsHighConfidenceSecret(fragment)
        || looksLikeLocalPath(fragment, { genericAbsolute: true })
      )
    } catch {
      return true
    }
  })
}

export function safePublicSourceUrl(value) {
  if (typeof value !== 'string') return null
  const candidate = value.trim()
  if (!candidate || candidate.length > 2048 || unsafeUrlDisclosure(candidate)) return null
  try {
    return new URL(candidate).href
  } catch {
    return null
  }
}

export function normalizedVerifiedAt(value) {
  const timestamp = boundedPublicText(value, 32)
  const match = timestamp?.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?Z$/u)
  if (!match) return null
  const [, yearText, monthText, dayText, hourText, minuteText, secondText] = match
  const [year, month, day, hour, minute, second] = [
    yearText, monthText, dayText, hourText, minuteText, secondText,
  ].map(Number)
  const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)
  const daysInMonth = [31, leapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  if (
    year < 1
    || month < 1 || month > 12
    || day < 1 || day > daysInMonth[month - 1]
    || hour > 23 || minute > 59 || second > 59
  ) return null
  return Number.isNaN(Date.parse(timestamp)) ? null : timestamp
}

export function formatVerifiedDate(value) {
  const timestamp = normalizedVerifiedAt(value)
  if (!timestamp) return null
  return new Intl.DateTimeFormat('en-US', {
    day: 'numeric',
    month: 'short',
    timeZone: 'UTC',
    year: 'numeric',
  }).format(new Date(timestamp))
}

export function normalizedTransformations(value) {
  if (!Array.isArray(value)) return []
  return value
    .slice(0, 32)
    .map((item) => boundedPublicText(item, 300))
    .filter(Boolean)
    .slice(0, 8)
}
