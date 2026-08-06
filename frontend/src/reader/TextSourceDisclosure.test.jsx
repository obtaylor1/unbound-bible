import { readFileSync } from 'node:fs'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import TextSourceDisclosure from './TextSourceDisclosure'

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
  fallback: true,
  modified: true,
  modificationNote: 'Book names were standardized for this reader.',
  verificationStatus: 'provisional',
  canonScope: 'ethio81',
}

describe('TextSourceDisclosure', () => {
  it('identifies fallback and provisional records with visible words', () => {
    render(<TextSourceDisclosure source={completeSource} />)

    const region = screen.getByRole('region', { name: 'Text source' })
    expect(region).toHaveTextContent(completeSource.sourceLabel)
    expect(within(region).getByText('KJV fallback')).toBeVisible()
    expect(within(region).getByText('Provisional source record')).toBeVisible()
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
      'Ethiopian 81-book canon',
      'Provisional',
    ]) expect(within(region).getByText(text)).toBeVisible()

    const link = within(region).getByRole('link', { name: /view source record/i })
    expect(link).toHaveAttribute('href', completeSource.provenanceUrl)
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', expect.stringMatching(/noopener/))
    expect(link).toHaveAttribute('rel', expect.stringMatching(/noreferrer/))
  })

  it('omits empty optional details and unsafe links without empty labels', async () => {
    const user = userEvent.setup()
    render(<TextSourceDisclosure source={{
      sourceLabel: 'Archive source',
      provenanceUrl: 'javascript:alert(1)',
      fallback: false,
      modified: false,
      verificationStatus: 'verified',
    }} />)

    await user.click(screen.getByText('About this text'))
    expect(screen.queryByText('Translator')).not.toBeInTheDocument()
    expect(screen.queryByText('Modification note')).not.toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.queryByText('KJV fallback')).not.toBeInTheDocument()
    expect(screen.queryByText('Provisional source record')).not.toBeInTheDocument()
  })

  it('uses a 44px disclosure target, strong focus treatment, responsive wrapping, and reduced motion', () => {
    expect(readerCss).toMatch(/\.text-source-disclosure summary\s*\{[^}]*min-height:\s*44px/s)
    expect(readerCss).toMatch(/\.text-source-disclosure summary:focus-visible\s*\{[^}]*outline:\s*3px solid var\(--reader-gold\)/s)
    expect(readerCss).toMatch(/\.text-source-disclosure__identity\s*\{[^}]*flex-wrap:\s*wrap/s)
    expect(readerCss).toMatch(/@media \(prefers-reduced-motion: reduce\)[\s\S]*\.text-source-disclosure/s)
  })
})
