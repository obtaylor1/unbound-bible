export const COMPOSITE_ENGLISH_EDITION_CODE = 'EOTC-COMPOSITE-EN'

export function isCompositeEnglishEdition(edition) {
  return typeof edition?.code === 'string'
    && edition.code.trim().toUpperCase() === COMPOSITE_ENGLISH_EDITION_CODE
}
