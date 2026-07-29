import { useEffect, useRef } from 'react'

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

function isEligibleFocusable(element, container) {
  if (
    !(element instanceof HTMLElement)
    || !(container instanceof HTMLElement)
    || !container.contains(element)
    || !element.matches(FOCUSABLE_SELECTOR)
    || element.matches(':disabled')
    || element.getAttribute('aria-disabled') === 'true'
    || element.closest('[aria-disabled="true"]')
    || element.closest('[inert]')
    || isDisabledByFieldset(element)
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

export default function useDialogFocus({
  open,
  containerRef,
  initialRef,
  onClose,
}) {
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  useEffect(() => {
    if (!open) return undefined

    const opener = document.activeElement
    let active = true
    const initialWasUnavailable = !initialRef?.current
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
      if (event.key === 'Escape') {
        event.preventDefault()
        if (typeof onCloseRef.current === 'function') onCloseRef.current()
        return
      }

      if (event.key !== 'Tab') return

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

      if (opener instanceof HTMLElement && opener.isConnected) {
        opener.focus()
      }
    }
  }, [containerRef, initialRef, open])
}
