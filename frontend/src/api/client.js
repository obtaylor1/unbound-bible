const API_ROOT = '/api/v1'
const REFRESH_KEY = 'unbound.refreshToken'

let accessToken = null
let refreshPromise = null

export const credentials = {
  get accessToken() { return accessToken },
  get refreshToken() { return sessionStorage.getItem(REFRESH_KEY) },
  get hasSession() { return Boolean(sessionStorage.getItem(REFRESH_KEY)) },
  set(tokens) {
    accessToken = tokens.access_token
    if (tokens.refresh_token) sessionStorage.setItem(REFRESH_KEY, tokens.refresh_token)
  },
  clear() {
    accessToken = null
    sessionStorage.removeItem(REFRESH_KEY)
  }
}

async function parse(response) {
  if (response.status === 204) return null
  const type = response.headers.get('Content-Type') || ''
  return type.includes('json') || !type ? response.json() : response.text()
}

function normalizedError(response, data) {
  const validation = Array.isArray(data?.detail) ? data.detail : null
  const message = validation ? validation.map((item) => item.msg || 'Invalid value').join('. ') : data?.detail || data?.message || `Request failed (${response.status})`
  const error = new Error(typeof message === 'string' ? message : `Request failed (${response.status})`)
  error.status = response.status
  error.code = data?.code || 'request_failed'
  error.fieldErrors = data?.field_errors || (validation ? Object.fromEntries(validation.map((item) => [item.loc?.at(-1) || 'form', item.msg])) : null)
  return error
}

async function refreshCredentials() {
  if (!credentials.refreshToken) throw new Error('No active session')
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_ROOT}/auth/refresh`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: credentials.refreshToken })
    }).then(async (response) => {
      const data = await parse(response)
      if (!response.ok) throw normalizedError(response, data)
      credentials.set(data)
      return data
    }).catch((error) => {
      credentials.clear()
      throw error
    }).finally(() => { refreshPromise = null })
  }
  return refreshPromise
}

async function request(path, { method = 'GET', body, signal, retry = true } = {}) {
  const tokenUsed = credentials.accessToken
  const headers = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (credentials.accessToken) headers.Authorization = `Bearer ${credentials.accessToken}`
  const response = await fetch(`${API_ROOT}${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), signal })
  if (response.status === 401 && retry && credentials.refreshToken && path !== '/auth/refresh') {
    if (!tokenUsed || tokenUsed === credentials.accessToken) await refreshCredentials()
    return request(path, { method, body, signal, retry: false })
  }
  const data = await parse(response)
  if (!response.ok) throw normalizedError(response, data)
  return data
}

export const api = {
  get: (path, options) => request(path, options),
  post: (path, body, options = {}) => request(path, { ...options, method: 'POST', body }),
  put: (path, body, options = {}) => request(path, { ...options, method: 'PUT', body }),
  patch: (path, body, options = {}) => request(path, { ...options, method: 'PATCH', body }),
  delete: (path, options = {}) => request(path, { ...options, method: 'DELETE' })
}
