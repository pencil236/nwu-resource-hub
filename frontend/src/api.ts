import axios from 'axios'

export const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

let refreshPromise: Promise<string> | null = null
api.interceptors.response.use(undefined, async (error) => {
  const original = error.config
  const refreshToken = localStorage.getItem('refresh_token')
  if (error.response?.status !== 401 || original?._retried || !refreshToken || original?.url?.includes('/auth/')) {
    return Promise.reject(error)
  }
  original._retried = true
  refreshPromise ||= axios.post('/api/auth/refresh', { refresh_token: refreshToken })
    .then(({ data }) => {
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      return data.access_token as string
    })
    .finally(() => { refreshPromise = null })
  const token = await refreshPromise
  original.headers.Authorization = `Bearer ${token}`
  return api(original)
})

export interface Resource {
  id: string
  owner_id: string
  title: string
  description: string
  experience: string
  course?: string
  category?: string
  tags: string
  original_filename: string
  status: 'processing' | 'waiting_confirmation' | 'published' | 'failed' | 'hidden'
  ai_summary?: string
  ai_purpose?: string
  ai_audience?: string
  failure_reason?: string
}

export interface User {
  id: string
  email: string
  display_name: string
  is_admin: boolean
}

export interface Report {
  id: number
  resource_id: string
  reporter_id: string
  reason: string
  details: string
  status: 'pending' | 'resolved' | 'rejected'
  resolution?: string
  created_at: string
}

export interface SearchResult {
  resource: Resource
  score: number
  matched_excerpt?: string
}
