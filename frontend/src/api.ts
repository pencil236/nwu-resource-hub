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
  resource_type: string
  college: string
  major: string
  teacher: string
  grade: string
  year?: number
  is_anonymous: boolean
  owner_name: string
  tags: string
  original_filename: string
  content_type: string
  size_bytes: number
  status: 'processing' | 'waiting_confirmation' | 'published' | 'failed' | 'hidden'
  ai_summary?: string
  ai_purpose?: string
  ai_audience?: string
  failure_reason?: string
  like_count: number
  dislike_count: number
  comment_count: number
  liked_by_me: boolean
  disliked_by_me: boolean
  created_at: string
}

export interface ResourceComment {
  id: number
  resource_id: string
  author_id: string
  author_name: string
  content: string
  created_at: string
}

export interface Engagement {
  liked_by_me: boolean
  disliked_by_me: boolean
  like_count: number
  dislike_count: number
  comment_count: number
}

export interface User {
  id: string
  email: string
  display_name: string
  is_admin: boolean
  onboarding_completed: boolean
}

export interface UserProfile {
  id: string
  display_name: string
  resource_count: number
  total_likes: number
}

export interface HelpRequest {
  id: number
  author_id: string
  author_name: string
  title: string
  description: string
  college: string
  major: string
  course: string
  heat_count: number
  supported_by_me: boolean
  created_at: string
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
