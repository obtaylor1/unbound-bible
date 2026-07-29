import { useEffect, useLayoutEffect, useRef } from 'react'

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button',
  'input:not([type="hidden"])',
  'select',
  'textarea',
  'details > summary:first-of-type',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

let scrollLockCount = 0
let originalBodyOverflow = ''
const dialogStack = []
const handledKeyEvents = new WeakSet()

function topDialog() {
  return dialogStack[dialogStack.length - 1]
}

function isDisabledByFieldset(element) {
  let fieldset = element.closest('fieldset[disabled]')

  while (fieldset) {
    const firstLegend = [...fieldset.children].find(
      (child) => child.tagName === 'LEGEND',
    )
    if (!firstLegend?.contains(element)) return true
    fieldset = fieldset.parentElement?.closest('fieldset[disabled]')
  }

  return false
}

function isHiddenByClosedDetails(element) {
  let details = element.closest('details:not([open])')

  while (details) {
    const visibleSummary = [...details.children].find(
      (child) => child.tagName === 'SUMMARY',
    )
    if (element !== visibleSummary && !visibleSummary?.contains(element)) return true
    details = details.parentElement?.closest('details:not([open])')
  }

  return false
}

function isEligibleFocusable(element, container) {
  if (
    !(element instanceof HTMLElement)
    || !(container instanceof HTMLElement)
    || !container.contains(element)
    || !element.matches(FOCUSABLE_SELECTOR)
    || element.tabIndex < 0
    || element.matches(':disabled')
    || element.getAttribute('aria-disabled') === 'true'
    || element.closest('[aria-disabled="true"]')
    || element.closest('[inert]')
    || isDisabledByFieldset(element)
    || isHiddenByClosedDetails(element)
  ) return false

  let current = element

  while (current instanceof HTMLElement) {
    if (current.hidden || current.getAttribute('aria-hidden') === 'true') return false
    const style = window.getComputedStyle(current)
    if (style.display === 'none' || style.visibility === 'hidden') return false
    current = current.parentElement
  }

  return true
}

function focusableElements(container) {
  if (!(container instanceof HTMLElement)) return []
  return [...container.querySelectorAll(FOCUSABLE_SELECTOR)]
    .filter((element) => isEligibleFocusable(element, container))
}

function lockBackgroundScroll() {
  if (scrollLockCount === 0) {
    originalBodyOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
  }
  scrollLockCount += 1
}

function unlockBackgroundScroll() {
  scrollLockCount = Math.max(0, scrollLockCount - 1)
  if (scrollLockCount === 0) {
    document.body.style.overflow = originalBodyOverflow
  }
}

function stablePageTarget() {
  const target = document.querySelector('main, .scripture-reader')
  if (!(target instanceof HTMLElement) || !target.isConnected) return null
  if (!target.hasAttribute('tabindex')) target.tabIndex = -1
  return target
}

export default function useDialogFocus({
  open,
  containerRef,
  initialRef,
  onClose,
  restoreRef,
}) {
  const onCloseRef = useRef(onClose)

  useLayoutEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  useEffect(() => {
    if (!open) return undefined

    const parentToken = topDialog()
    const opener = document.activeElement
    const token = {
      containerRef,
      opener,
      parent: parentToken,
      restoreChain: [
        opener,
        ...(parentToken?.restoreChain ?? []),
      ],
      restoreRef,
      restoreSnapshot: restoreRef?.current,
    }
    let active = true
    const initialWasUnavailable = !initialRef?.current
    dialogStack.push(token)
    lockBackgroundScroll()

    const focusInitialControl = () => {
      const container = containerRef.current
      if (!(container instanceof HTMLElement)) return

      const initialControl = initialRef?.current
      const target = isEligibleFocusable(initialControl, container)
        ? initialControl
        : (focusableElements(container)[0] ?? container)
      target.focus()
    }

    focusInitialControl()
    if (initialWasUnavailable) {
      queueMicrotask(() => {
        if (active) focusInitialControl()
      })
    }

    const handleKeyDown = (event) => {
      if (topDialog() !== token || handledKeyEvents.has(event)) return

      if (event.key === 'Escape') {
        handledKeyEvents.add(event)
        event.preventDefault()
        if (typeof onCloseRef.current === 'function') onCloseRef.current()
        return
      }

      if (event.key !== 'Tab') return
      handledKeyEvents.add(event)

      const container = containerRef.current
      if (!container) return

      const focusable = focusableElements(container)
      if (focusable.length === 0) {
        event.preventDefault()
        container.focus()
        return
      }

      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      const activeElement = document.activeElement

      if (
        event.shiftKey
        && (activeElement === first || !container.contains(activeElement))
      ) {
        event.preventDefault()
        last.focus()
      } else if (
        !event.shiftKey
        && (activeElement === last || !container.contains(activeElement))
      ) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)

    return () => {
      active = false
      document.removeEventListener('keydown', handleKeyDown)
      unlockBackgroundScroll()

      const tokenIndex = dialogStack.indexOf(token)
      const wasTopDialog = tokenIndex === dialogStack.length - 1
      if (tokenIndex >= 0) dialogStack.splice(tokenIndex, 1)

      dialogStack.forEach((activeToken) => {
        if (activeToken.parent === token) activeToken.parent = token.parent
      })

      if (!wasTopDialog) {
        token.containerRef = null
        token.opener = null
        token.parent = null
        token.restoreChain = []
        token.restoreRef = null
        token.restoreSnapshot = null
        return
      }

      const lowerDialog = topDialog()?.containerRef.current
      if (lowerDialog instanceof HTMLElement && lowerDialog.isConnected) {
        if (
          token.opener instanceof HTMLElement
          && token.opener.isConnected
          && lowerDialog.contains(token.opener)
        ) {
          token.opener.focus()
        } else {
          const lowerTarget = focusableElements(lowerDialog)[0] ?? lowerDialog
          lowerTarget.focus()
        }
      } else {
        const ancestryTarget = token.restoreChain.find(
          (candidate) => candidate instanceof HTMLElement && candidate.isConnected,
        )
        const liveRestoreTarget = token.restoreRef?.current
        const fallback = ancestryTarget
          ?? (
            liveRestoreTarget instanceof HTMLElement && liveRestoreTarget.isConnected
              ? liveRestoreTarget
              : null
          )
          ?? (
            token.restoreSnapshot instanceof HTMLElement && token.restoreSnapshot.isConnected
              ? token.restoreSnapshot
              : null
          )
          ?? stablePageTarget()
        fallback?.focus()
      }

      token.containerRef = null
      token.opener = null
      token.parent = null
      token.restoreChain = []
      token.restoreRef = null
      token.restoreSnapshot = null
    }
  }, [containerRef, initialRef, open, restoreRef])
}
