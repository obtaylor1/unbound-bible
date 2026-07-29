import { useEffect, useRef } from 'react'

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  'details > summary:first-of-type',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

let scrollLockCount = 0
let originalBodyOverflow = ''

function isVisible(element) {
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
  return [...container.querySelectorAll(FOCUSABLE_SELECTOR)].filter(isVisible)
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

  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  useEffect(() => {
    if (!open) return undefined

    const opener = document.activeElement
    let active = true
    const initialWasUnavailable = !initialRef?.current
    lockBackgroundScroll()

    const focusInitialControl = () => {
      const container = containerRef.current
      const initialControl = initialRef?.current
      const target = initialControl && container?.contains(initialControl)
        ? initialControl
        : focusableElements(container ?? document.body)[0]
      target?.focus()
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
