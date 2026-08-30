// Frontend mirror of the reviewed inventories in backend verification/registry.py
// and the composite manifest. Membership changes require source-review approval
// and coordinated backend, data, and frontend contract updates.
const WMB_WORK_IDS = Object.freeze([
  'genesis', 'exodus', 'leviticus', 'numbers', 'deuteronomy', 'joshua',
  'judges', 'ruth', '1-samuel', '2-samuel', '1-kings', '2-kings',
  '1-chronicles', '2-chronicles', 'ezra', 'nehemiah', 'esther', 'job',
  'psalms', 'proverbs', 'ecclesiastes', 'song-of-solomon', 'isaiah',
  'jeremiah', 'lamentations', 'ezekiel', 'daniel', 'hosea', 'joel',
  'amos', 'obadiah', 'jonah', 'micah', 'nahum', 'habakkuk', 'zephaniah',
  'haggai', 'zechariah', 'malachi',
])

const MURDOCK_WORK_IDS = Object.freeze([
  'matthew', 'mark', 'luke', 'john', 'acts', 'romans', '1-corinthians',
  '2-corinthians', 'galatians', 'ephesians', 'philippians', 'colossians',
  '1-thessalonians', '2-thessalonians', '1-timothy', '2-timothy', 'titus',
  'philemon', 'hebrews', 'james', '1-peter', '2-peter', '1-john',
  '2-john', '3-john', 'jude', 'revelation',
])

const KJV_FALLBACK_WORK_IDS = Object.freeze([
  'baruch', 'letter-of-jeremiah', 'prayer-of-azariah', 'susanna',
  'bel-and-the-dragon', 'prayer-of-manasseh',
])

const ALREADY_PROVENANCED_WORKS = Object.freeze({
  '1-enoch': 'rh-charles-ethiopic',
  '1-meqabyan': 'wikisource-meqabyan-geez',
  '2-meqabyan': 'wikisource-meqabyan-geez',
  '3-meqabyan': 'wikisource-meqabyan-geez',
  'ezra-sutuel': 'world-english-bible-apocrypha',
  'judith': 'world-english-bible-apocrypha',
  'second-ezra': 'world-english-bible-apocrypha',
  'sirach': 'world-english-bible-apocrypha',
  'tobit': 'world-english-bible-apocrypha',
  'wisdom-of-solomon': 'world-english-bible-apocrypha',
})

export const SCRIPTURE_VERIFICATION_GROUPS = Object.freeze([
  Object.freeze({ id: 'world-messianic-bible', sourceKey: 'world-messianic-bible', affected: true, workIds: WMB_WORK_IDS }),
  Object.freeze({ id: 'murdock-peshitta-1852', sourceKey: 'murdock-peshitta-1852', affected: true, workIds: MURDOCK_WORK_IDS }),
  Object.freeze({ id: 'kjv-1611-fallback', sourceKey: 'kjv-1611-fallback', affected: true, workIds: KJV_FALLBACK_WORK_IDS }),
  Object.freeze({ id: 'rh-charles-jubilees-1902', sourceKey: 'rh-charles-ethiopic', affected: true, workIds: Object.freeze(['jubilees']) }),
  Object.freeze({ id: 'already-provenanced', sourceKey: null, affected: false, workIds: Object.freeze(Object.keys(ALREADY_PROVENANCED_WORKS)) }),
])

export const APPROVED_WORK_CONTRACT = Object.freeze(Object.assign(Object.create(null),
  ...SCRIPTURE_VERIFICATION_GROUPS.flatMap((group) => group.workIds.map((workId) => ({
    [workId]: Object.freeze({
      groupId: group.id,
      sourceKey: group.sourceKey ?? ALREADY_PROVENANCED_WORKS[workId],
      affected: group.affected,
    }),
  }))),
))

export const EXPECTED_SOURCE_KEY_TOTALS = Object.freeze({
  'kjv-1611-fallback': 6,
  'murdock-peshitta-1852': 27,
  'rh-charles-ethiopic': 2,
  'wikisource-meqabyan-geez': 3,
  'world-english-bible-apocrypha': 6,
  'world-messianic-bible': 39,
})

export const EXPECTED_SCRIPTURE_WORK_COUNT = 83
