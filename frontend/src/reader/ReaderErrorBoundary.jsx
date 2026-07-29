import { Component } from 'react'

function reloadReader() {
  window.location.reload()
}

export default class ReaderErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidUpdate(previousProps) {
    if (
      this.state.error
      && previousProps.resetKey !== this.props.resetKey
    ) {
      this.setState({ error: null })
    }
  }

  render() {
    if (!this.state.error) {
      return this.props.children
    }

    const onReload = this.props.onReload ?? reloadReader

    return (
      <section
        className="scripture-reader reader-fatal-error"
        role="alert"
        aria-labelledby="reader-fatal-error-heading"
      >
        <p className="reader-fatal-error__eyebrow">Reader unavailable</p>
        <h1 id="reader-fatal-error-heading">
          The Scripture Reader could not open
        </h1>
        <p>
          Your saved notes and preferences were unchanged. Reload the reader or
          return home to continue.
        </p>
        <div className="reader-fatal-error__actions">
          <button type="button" onClick={onReload}>
            Reload the reader
          </button>
          <a href="#home">Return home</a>
        </div>
      </section>
    )
  }
}
