import { api } from '../api/client'
import {
  boundedPublicText,
  normalizedVerifiedAt,
  safePublicSourceUrl,
  sourceVerificationLabel,
} from '../reader/sourceVerification'
import {
  APPROVED_WORK_CONTRACT,
  EXPECTED_SCRIPTURE_WORK_COUNT,
  EXPECTED_SOURCE_KEY_TOTALS,
} from './scriptureVerificationContract'

const IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$/u
const SHA256 = /^[0-9a-f]{64}$/u
const KNOWN_STATUSES = new Set([
  'in_progress',
  'verified_exact',
  'verified_formatting',
  'verified_rebuilt',
  'review_required',
])
const COMPARISON_FIELDS = ['exact', 'formatting', 'missing', 'extra', 'wording']

function identifier(value) {
  return typeof value === 'string' && IDENTIFIER.test(value) ? value : null
}

function checksum(value) {
  return typeof value === 'string' && SHA256.test(value) ? value : null
}

function count(value) {
  return Number.isSafeInteger(value) && value >= 0 ? value : 0
}

function normalizeComparison(value) {
  const source = value && typeof value === 'object' ? value : {}
  return Object.fromEntries(COMPARISON_FIELDS.map((field) => [field, count(source[field])]))
}

function normalizeWork(value) {
  if (!value || typeof value !== 'object') return null
  const workId = identifier(value.work_id)
  if (!workId) return null
  const status = KNOWN_STATUSES.has(value.verification?.status)
    ? value.verification.status
    : 'unknown'
  const approved = APPROVED_WORK_CONTRACT[workId]
  return {
    workId,
    workName: boundedPublicText(value.work_name, 200) ?? 'Not disclosed',
    sourceKey: identifier(value.source_key) ?? 'unknown-source',
    groupId: approved?.groupId ?? 'unclassified-source',
    sourceLabel: boundedPublicText(value.source_label, 200) ?? 'Not disclosed',
    sourceEdition: boundedPublicText(value.source_edition, 200),
    sourceRevision: boundedPublicText(value.source_revision, 200),
    provenanceUrl: safePublicSourceUrl(value.provenance_url),
    rightsUrl: safePublicSourceUrl(value.rights_url),
    license: boundedPublicText(value.license, 100) ?? 'Not disclosed',
    fallback: value.fallback === true,
    canonScope: value.canon_scope === 'supplemental' ? 'supplemental' : 'ethio81',
    artifactSha256: checksum(value.artifact_sha256),
    comparisonReportSha256: checksum(value.comparison_report_sha256),
    comparison: normalizeComparison(value.comparison),
    reviewer: boundedPublicText(value.reviewer, 200),
    reviewedAt: normalizedVerifiedAt(value.reviewed_at),
    verifiedAt: normalizedVerifiedAt(value.verification?.verified_at),
    status,
    statusLabel: sourceVerificationLabel(status),
  }
}

function normalizeFamilyTotals(value) {
  if (!Array.isArray(value)) return []
  return value.slice(0, 20).map((entry) => ({
    sourceKey: identifier(entry?.source_key),
    count: count(entry?.count),
  }))
}

function normalizeStatusTotals(value) {
  if (!Array.isArray(value)) return []
  return value.slice(0, 5).map((entry) => {
    const status = KNOWN_STATUSES.has(entry?.status) ? entry.status : 'unknown'
    return {
      status,
      label: boundedPublicText(entry?.label, 200),
      count: count(entry?.count),
    }
  })
}

function totalsMap(entries, key) {
  const result = new Map()
  let duplicate = false
  entries.forEach((entry) => {
    const identity = entry[key]
    if (!identity || result.has(identity)) duplicate = true
    else result.set(identity, entry.count)
  })
  return { duplicate, result }
}

function sameCounts(actual, expected) {
  const expectedEntries = Object.entries(expected)
  return actual.size === expectedEntries.length
    && expectedEntries.every(([key, value]) => actual.get(key) === value)
}

function inventoryIntegrity({ raw, editionCode, totalWorks, works, familyTotals, statusTotals }) {
  const issues = new Set()
  const rawWorks = Array.isArray(raw?.works) ? raw.works : []
  if (editionCode !== 'EOTC-COMPOSITE-EN') issues.add('edition-contract')
  if (totalWorks !== EXPECTED_SCRIPTURE_WORK_COUNT || rawWorks.length !== EXPECTED_SCRIPTURE_WORK_COUNT) issues.add('work-total')
  if (works.length !== rawWorks.length) issues.add('invalid-work-row')

  const seen = new Set()
  const actualFamilyCounts = Object.create(null)
  const actualStatusCounts = Object.fromEntries([...KNOWN_STATUSES].map((status) => [status, 0]))
  works.forEach((work) => {
    if (seen.has(work.workId)) issues.add('duplicate-work')
    seen.add(work.workId)
    const approved = APPROVED_WORK_CONTRACT[work.workId]
    if (!approved) issues.add('unknown-work')
    else if (approved.sourceKey !== work.sourceKey) issues.add('work-family-contract')
    if (work.status === 'unknown') issues.add('work-status-contract')
    else actualStatusCounts[work.status] += 1
    actualFamilyCounts[work.sourceKey] = (actualFamilyCounts[work.sourceKey] ?? 0) + 1
    if ((approved?.groupId === 'kjv-1611-fallback') !== work.fallback) issues.add('fallback-contract')
  })
  if (seen.size !== EXPECTED_SCRIPTURE_WORK_COUNT) issues.add('work-membership')
  Object.keys(APPROVED_WORK_CONTRACT).forEach((workId) => {
    if (!seen.has(workId)) issues.add('work-membership')
  })
  if (!sameCounts(new Map(Object.entries(actualFamilyCounts)), EXPECTED_SOURCE_KEY_TOTALS)) issues.add('work-family-totals')

  const declaredFamilies = totalsMap(familyTotals, 'sourceKey')
  const rawFamilyTotals = Array.isArray(raw.family_totals) ? raw.family_totals : []
  const validRawFamilyTotals = rawFamilyTotals.length === Object.keys(EXPECTED_SOURCE_KEY_TOTALS).length
    && rawFamilyTotals.every((entry) => (
      entry && typeof entry === 'object'
      && identifier(entry.source_key) !== null
      && Number.isSafeInteger(entry.count) && entry.count >= 0
    ))
  if (
    !validRawFamilyTotals
    || declaredFamilies.duplicate
    || !sameCounts(declaredFamilies.result, EXPECTED_SOURCE_KEY_TOTALS)
  ) issues.add('declared-family-totals')

  const declaredStatuses = totalsMap(statusTotals, 'status')
  const rawStatusTotals = Array.isArray(raw.status_totals) ? raw.status_totals : []
  const validRawStatusTotals = rawStatusTotals.length === KNOWN_STATUSES.size
    && rawStatusTotals.every((entry) => (
      entry && typeof entry === 'object'
      && KNOWN_STATUSES.has(entry.status)
      && Number.isSafeInteger(entry.count) && entry.count >= 0
      && boundedPublicText(entry.label, 200) === sourceVerificationLabel(entry.status)
    ))
  if (
    !validRawStatusTotals
    || declaredStatuses.duplicate
    || declaredStatuses.result.size !== KNOWN_STATUSES.size
    || ![...KNOWN_STATUSES].every((status) => declaredStatuses.result.get(status) === actualStatusCounts[status])
    || statusTotals.some((entry) => entry.label !== sourceVerificationLabel(entry.status))
  ) issues.add('declared-status-totals')

  return { valid: issues.size === 0, issues: [...issues].sort() }
}

export function normalizeScriptureVerificationInventory(value) {
  if (!value || typeof value !== 'object') {
    return {
      editionCode: null,
      totalWorks: null,
      familyTotals: [],
      statusTotals: [],
      works: [],
      integrity: { valid: false, issues: ['invalid-response'] },
    }
  }
  const rawWorks = Array.isArray(value.works) ? value.works.slice(0, 100) : []
  const normalized = {
    editionCode: identifier(value.edition_code),
    totalWorks: Number.isSafeInteger(value.total_works) && value.total_works >= 0
      ? value.total_works
      : null,
    familyTotals: normalizeFamilyTotals(value.family_totals),
    statusTotals: normalizeStatusTotals(value.status_totals),
    works: rawWorks.map(normalizeWork).filter(Boolean),
  }
  normalized.integrity = inventoryIntegrity({ raw: value, ...normalized })
  return normalized
}

export async function fetchScriptureVerificationInventory({ signal } = {}) {
  const response = await api.get('/library/admin/scripture-verification', { signal })
  return normalizeScriptureVerificationInventory(response)
}
