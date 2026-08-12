import { useEffect, useId, useRef, useState } from 'react'
import { isCompositeEnglishEdition } from './compositeEdition'
import useDialogFocus from './useDialogFocus'

const SOURCE_AUDIT_URL = 'https://github.com/obtaylor1/unbound-bible/blob/main/docs/operations/ethiopian-composite-release-audit.md'

export default function TranslationOverview({ edition }) {
  const [open, setOpen] = useState(false)
  const headingId = `translation-overview-heading-${useId()}`
  const triggerRef = useRef(null)
  const dialogRef = useRef(null)
  const closeRef = useRef(null)
  const compositeEdition = isCompositeEnglishEdition(edition)
  const dialogOpen = compositeEdition && open

  useDialogFocus({
    open: dialogOpen,
    containerRef: dialogRef,
    initialRef: closeRef,
    onClose: () => setOpen(false),
    restoreRef: triggerRef,
  })

  useEffect(() => {
    if (!compositeEdition) setOpen(false)
  }, [compositeEdition])

  if (!compositeEdition) return null

  return (
    <div className="translation-overview">
      <button
        ref={triggerRef}
        type="button"
        className="translation-overview__trigger"
        aria-haspopup="dialog"
        aria-expanded={dialogOpen}
        onClick={() => setOpen(true)}
      >
        About this translation
      </button>

      {dialogOpen ? (
        <div
          className="translation-overview__backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setOpen(false)
          }}
        >
          <div
            ref={dialogRef}
            className="translation-overview__dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby={headingId}
            tabIndex="-1"
          >
            <header className="translation-overview__header">
              <div>
                <p className="translation-overview__eyebrow">Edition guide</p>
                <h2 id={headingId}>About the Ethiopian Composite English edition</h2>
              </div>
              <button
                ref={closeRef}
                type="button"
                className="translation-overview__close"
                aria-label="Close translation information"
                onClick={() => setOpen(false)}
              >
                Close
              </button>
            </header>

            <div className="translation-overview__content">
              <section aria-labelledby={`${headingId}-what`}>
                <h3 id={`${headingId}-what`}>What this edition is</h3>
                <p>
                  This edition combines public-domain and openly licensed English sources
                  into one reading collection.
                </p>
                <p>
                  It is not one uniform Ethiopian Orthodox translation. Different works
                  come from different translation traditions and source languages.
                </p>
                <p className="translation-overview__scope">
                  It covers 83 works, 1,520 chapters, and 38,938 verses: 82 ETHIO81 works
                  plus one supplemental work.
                </p>
              </section>

              <section aria-labelledby={`${headingId}-sources`}>
                <h3 id={`${headingId}-sources`}>Where the English comes from</h3>
                <ul>
                  <li>Hebrew-based World Messianic Bible (WMB) Old Testament</li>
                  <li>Murdock Syriac Peshitta New Testament</li>
                  <li>World English Bible (WEB) deuterocanon</li>
                  <li>Ge’ez-sourced Meqabyan</li>
                  <li>R. H. Charles editions of Enoch and Jubilees</li>
                </ul>
                <p>
                  Six works use a clearly labeled KJV fallback; each affected book is
                  marked in its source disclosure.
                </p>
              </section>

              <section aria-labelledby={`${headingId}-records`}>
                <h3 id={`${headingId}-records`}>How to check a source</h3>
                <p>
                  All source records remain provisional pending more precise upstream
                  revision verification.
                </p>
                <p>
                  For the exact source used by the book you are reading, open its
                  per-book About this text disclosure.
                </p>
                <a
                  href={SOURCE_AUDIT_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Read the detailed source audit (opens in a new tab)
                </a>
              </section>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
