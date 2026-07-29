import { Component, useId } from 'react'

function reloadReader() {
  window.location.reload()
}

class ReaderErrorBoundaryClass extends Component {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidUpdate(previousProps) {
    if (
      this.state.hasError
      && previousProps.resetKey !== this.props.resetKey
    ) {
      this.setState({ hasError: false })
    }
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children
    }

    const onReload = this.props.onReload ?? reloadReader

    return (
      <section
        className="scripture-reader reader-fatal-error"
        role="alert"
        aria-labelledby={this.props.headingId}
      >
        <p className="reader-fatal-error__eyebrow">Reader unavailable</p>
        <h1 id={this.props.headingId}>
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

export default function ReaderErrorBoundary(props) {
  const headingId = useId()

  return <ReaderErrorBoundaryClass {...props} headingId={headingId} />
}
