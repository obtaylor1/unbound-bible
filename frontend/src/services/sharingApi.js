import { api } from '../api/client'

export const createShare = (payload) => api.post('/shares', payload)
export const updateShare = (shareId, visibility) => api.patch(`/shares/${encodeURIComponent(shareId)}`, { visibility })
export const getShare = (shareId) => api.get(`/shares/${encodeURIComponent(shareId)}`)
export const revokeShare = (shareId) => api.post(`/shares/${encodeURIComponent(shareId)}/revoke`, {})
