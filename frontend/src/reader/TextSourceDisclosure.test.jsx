import { readFileSync } from 'node:fs'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import TextSourceDisclosure from './TextSourceDisclosure'
import { sourceVerificationLabel } from './sourceVerification'

const readerCss = readFileSync('src/reader/readerTokens.css', 'utf8')

const completeSource = {
  sourceKey: 'webbe-deuterocanon',
  sourceLabel: 'World English Bible British Edition with Deuterocanon',
  translator: 'World English Bible contributors',
  sourceLanguage: 'Greek and Hebrew',
  sourceTradition: 'Septuagint and Masoretic',
  publishedYear: 2024,
  license: 'Public Domain',
  attribution: 'World English Bible British Edition.',
  provenanceUrl: 'https://ebible.org/details.php?id=eng-webbe',
  rightsUrl: 'https://ebible.org/engwmb/copyright.htm',
  rightsJurisdiction: 'Worldwide dedication; naming condition applies',
  sourceEdition: 'August 2022 stable text',
  sourceRevision: 'engwmb source 2026-07-24',
  fallback: true,
  modified: true,
  modificationNote: 'Book names were standardized for this reader.',
  transformations: ['Unicode NFC', 'Line endings normalized'],
  verificationStatus: 'in_progress',
  verifiedAt: null,
  canonScope: 'ethio81',
}

describe('TextSourceDisclosure', () => {
  it.each(['toString', 'constructor', '__proto__', 'future_status'])(
    'uses the exact fallback for prototype-like or unknown status %s',
    (status) => {
      expect(sourceVerificationLabel(status)).toBe('Source status unavailable')
      render(<TextSourceDisclosure source={{ ...completeSource, verificationStatus: status }} />)
      expect(screen.getByText('Source status unavailable')).toBeVisible()
    },
  )

  it('identifies fallback and in-progress records with visible words', () => {
    render(<TextSourceDisclosure source={completeSource} />)

    const region = screen.getByRole('region', { name: 'Text source' })
    expect(region).toHaveTextContent(completeSource.sourceLabel)
    expect(within(region).getByText('KJV fallback')).toBeVisible()
    expect(within(region).getByText('Source verification in progress')).toBeVisible()
    expect(within(region).getByText('About this text')).toBeVisible()
  })

  it('reveals every available reader-facing source detail and a safe provenance link', async () => {
    const user = userEvent.setup()
    render(<TextSourceDisclosure source={completeSource} />)

    await user.click(screen.getByText('About this text'))
    const region = screen.getByRole('region', { name: 'Text source' })
    for (const text of [
      'World English Bible contributors',
      'Greek and Hebrew',
      'Septuagint and Masoretic',
      '2024',
      'Public Domain',
      'World English Bible British Edition.',
      'Book names were standardized for this reader.',
      'August 2022 stable text',
      'engwmb source 2026-07-24',
      'Worldwide dedication; naming condition applies',
      'Unicode NFC',
      'Line endings normalized',
      'Ethiopian 81-book canon',
      'Source verification in progress',
    ]) expect(within(region).getByText(text)).toBeVisible()

    const link = within(region).getByRole('link', { name: /view source record/i })
    expect(link).toHaveAttribute('href', completeSource.provenanceUrl)
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', expect.stringMatching(/noopener/))
    expect(link).toHaveAttribute('rel', expect.stringMatching(/noreferrer/))
    expect(within(region).getByRole('link', { name: /view rights record/i }))
      .toHaveAttribute('href', completeSource.rightsUrl)
  })

  it.each([
    ['in_progress', 'Source verification in progress'],
    ['verified_exact', 'Source verified'],
    ['verified_formatting', 'Verified with documented formatting changes'],
    ['verified_rebuilt', 'Rebuilt from verified source'],
    ['review_required', 'Source review required'],
  ])('renders %s as plain language while preserving the fallback warning', (status, label) => {
    render(<TextSourceDisclosure source={{ ...completeSource, verificationStatus: status }} />)
    const region = screen.getByRole('region', { name: 'Text source' })
    expect(within(region).getByText(label)).toBeVisible()
    expect(within(region).getByText('KJV fallback')).toBeVisible()
  })

  it.each([undefined, null, '', 'future_status'])(
    'uses the honest unavailable label for missing or unknown status %s',
    (verificationStatus) => {
      render(<TextSourceDisclosure source={{ ...completeSource, verificationStatus }} />)
      expect(screen.getByText('Source status unavailable')).toBeVisible()
    },
  )

  it('announces a changed status but does not expose static status as a live region', () => {
    const { rerender } = render(<TextSourceDisclosure source={completeSource} />)
    expect(screen.getByText('Source verification in progress')).not.toHaveAttribute('role', 'status')

    rerender(<TextSourceDisclosure source={{ ...completeSource, verificationStatus: 'verified_exact' }} />)
    expect(screen.getByText('Source verified')).toHaveAttribute('role', 'status')
  })

  it.each([
    ['in_progress', false],
    ['verified_exact', true],
    ['verified_formatting', true],
    ['verified_rebuilt', true],
    ['review_required', false],
    ['future_status', false],
    [undefined, false],
  ])('shows a verified date for %s only when the status is verified', async (status, shouldShow) => {
    const user = userEvent.setup()
    render(<TextSourceDisclosure source={{
      ...completeSource,
      verificationStatus: status,
      verifiedAt: '2026-08-17T13:00:00Z',
    }} />)
    await user.click(screen.getByText('About this text'))

    if (shouldShow) expect(screen.getByText('Aug 17, 2026')).toBeVisible()
    else expect(screen.queryByText('Aug 17, 2026')).not.toBeInTheDocument()
  })

  it.each([
    '2026-02-29T13:00:00Z',
    '2024-02-30T13:00:00Z',
    '2026-04-31T13:00:00Z',
    '2026-13-01T13:00:00Z',
    '2026-01-01T24:00:00Z',
    '2026-01-01T13:60:00Z',
    '2026-01-01T13:00:60Z',
    '2026-01-01T13:00:00+01:00',
  ])('does not display impossible or non-UTC verified date %s', async (verifiedAt) => {
    const user = userEvent.setup()
    render(<TextSourceDisclosure source={{
      ...completeSource,
      verificationStatus: 'verified_exact',
      verifiedAt,
    }} />)
    await user.click(screen.getByText('About this text'))
    expect(screen.queryByText('Verified')).not.toBeInTheDocument()
  })

  it('displays a valid leap-day verification date', async () => {
    const user = userEvent.setup()
    render(<TextSourceDisclosure source={{
      ...completeSource,
      verificationStatus: 'verified_exact',
      verifiedAt: '2024-02-29T13:00:00Z',
    }} />)
    await user.click(screen.getByText('About this text'))
    expect(screen.getByText('Feb 29, 2024')).toBeVisible()
  })

  it('makes evidence details keyboard reachable with a native semantic disclosure control', async () => {
    const user = userEvent.setup()
    render(<TextSourceDisclosure source={{
      ...completeSource,
      verificationStatus: 'verified_exact',
      verifiedAt: '2026-08-17T13:00:00Z',
    }} />)

    const summary = screen.getByText('About this text')
    summary.focus()
    expect(summary).toHaveFocus()
    expect(summary.tagName).toBe('SUMMARY')
    await user.click(summary)
    expect(summary.closest('details')).toHaveAttribute('open')
    expect(screen.getByText('Aug 17, 2026')).toBeVisible()
  })

  it('omits empty optional details and unsafe links without empty labels', async () => {
    const user = userEvent.setup()
    render(<TextSourceDisclosure source={{
      sourceLabel: 'Archive source',
      provenanceUrl: 'javascript:alert(1)',
      rightsUrl: 'file:///private/source/rights.txt',
      fallback: false,
      modified: false,
      verificationStatus: 'verified_exact',
      transformations: [],
      artifactFilename: '/private/source/archive.zip',
      artifactSha256: 'a'.repeat(64),
    }} />)

    await user.click(screen.getByText('About this text'))
    expect(screen.queryByText('Translator')).not.toBeInTheDocument()
    expect(screen.queryByText('Modification note')).not.toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.queryByText('KJV fallback')).not.toBeInTheDocument()
    expect(screen.queryByText('/private/source/archive.zip')).not.toBeInTheDocument()
    expect(screen.queryByText('a'.repeat(64))).not.toBeInTheDocument()
  })

  it.each([
    'data:text/html,unsafe',
    'file:///private/source.txt',
    'https://example.org/%0d%0aHeader:value',
    'https://user:secret@example.org/source',
    'https://example.org/\u202Esource',
  ])('rejects unsafe or suspicious evidence URL %s', async (url) => {
    const user = userEvent.setup()
    render(<TextSourceDisclosure source={{ ...completeSource, provenanceUrl: url, rightsUrl: url }} />)
    await user.click(screen.getByText('About this text'))
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('redacts unsafe direct-render evidence while preserving normal Bible prose', async () => {
    const user = userEvent.setup()
    const secret = `ghp_${'A'.repeat(36)}`
    render(<TextSourceDisclosure source={{
      ...completeSource,
      sourceLabel: '/Users/obie/private/source.txt',
      translator: secret,
      sourceTradition: 'C:\\Users\\obie\\source.txt',
      modificationNote: 'clientSecret=do-not-disclose',
      sourceEdition: '/workspace/edition.txt',
      transformations: [
        'Psalm 23/1 retains Hebrew/Aramaic chapter/verse markers.',
        '/private/review.txt',
      ],
    }} />)
    await user.click(screen.getByText('About this text'))

    expect(screen.getByText('Source details unavailable')).toBeVisible()
    expect(screen.getByText('Psalm 23/1 retains Hebrew/Aramaic chapter/verse markers.')).toBeVisible()
    for (const unsafe of [secret, 'C:\\Users\\obie\\source.txt', 'clientSecret=do-not-disclose', '/workspace/edition.txt', '/private/review.txt']) {
      expect(screen.queryByText(unsafe)).not.toBeInTheDocument()
    }
  })

  it('adds edition-level context only for the normalized composite code', () => {
    const { rerender } = render(
      <TextSourceDisclosure
        source={completeSource}
        edition={{ code: ' eotc-composite-en ' }}
      />,
    )

    expect(screen.getByRole('button', { name: 'About this translation' })).toBeVisible()
    expect(screen.getByText('About this text')).toBeVisible()

    rerender(
      <TextSourceDisclosure
        source={completeSource}
        edition={{ code: 'WEB' }}
      />,
    )
    expect(screen.queryByRole('button', { name: 'About this translation' })).not.toBeInTheDocument()
    expect(screen.getByText('About this text')).toBeVisible()
  })

  it('uses a 44px disclosure target, strong focus treatment, responsive wrapping, and reduced motion', () => {
    expect(readerCss).toMatch(/\.text-source-disclosure summary\s*\{[^}]*min-height:\s*44px/s)
    expect(readerCss).toMatch(/\.text-source-disclosure summary:focus-visible\s*\{[^}]*outline:\s*3px solid var\(--reader-gold\)/s)
    expect(readerCss).toMatch(/\.text-source-disclosure__identity\s*\{[^}]*flex-wrap:\s*wrap/s)
    expect(readerCss).toMatch(/@media \(prefers-reduced-motion: reduce\)[\s\S]*\.text-source-disclosure/s)
  })
})
