import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, credentials } from './client'


afterEach(() => { credentials.clear(); vi.restoreAllMocks() })

describe('authenticated API client', () => {
  it('refreshes once and retries the original request', async () => {
    credentials.set({ access_token: 'old', refresh_token: 'refresh' })
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response('{}', { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ access_token: 'new', refresh_token: 'new-refresh' }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    await expect(api.get('/protected')).resolves.toEqual({ ok: true })
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('shares a refresh request across concurrent 401 responses', async () => {
    credentials.set({ access_token: 'old', refresh_token: 'refresh' })
    let refreshes = 0
    let protectedRequests = 0
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      if (String(url).endsWith('/auth/refresh')) {
        refreshes += 1
        await Promise.resolve()
        return new Response(JSON.stringify({ access_token: 'new', refresh_token: 'new-refresh' }), { status: 200 })
      }
      protectedRequests += 1
      const authorized = protectedRequests > 2
      return new Response(JSON.stringify({ ok: authorized }), { status: authorized ? 200 : 401 })
    })
    await Promise.all([api.get('/one'), api.get('/two')])
    expect(refreshes).toBe(1)
  })
})
