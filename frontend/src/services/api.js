import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30_000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export const authApi = {
  login: (credentials) => api.post('/auth/login', credentials),
  logout: () => api.post('/auth/logout'),
  me: () => api.get('/auth/me'),
}

export const dashboardApi = {
  stats: () => api.get('/dashboard/stats'),
  activityChart: (period, serverId) =>
    api.get('/dashboard/activity-chart', { params: { period, server_id: serverId } }),
  riskDistribution: (params) => api.get('/dashboard/risk-distribution', { params }),
}

export const commandLogsApi = {
  list: (params) => api.get('/command-logs/', { params }),
  export: (format, params) =>
    api.get(`/command-logs/export/${format}`, { params, responseType: 'blob' }),
}

export const sessionsApi = {
  active: (params) => api.get('/sessions/active', { params }),
  history: (params) => api.get('/sessions/history', { params }),
  exportHistory: (format, params) =>
    api.get(`/sessions/history/export/${format}`, { params, responseType: 'blob' }),
  killSession: (data) => api.post('/sessions/kill', data),
  actionStatus: (actionId) => api.get(`/sessions/action/${actionId}/status`),
}

export const alertsApi = {
  list: (params) => api.get('/alerts/', { params }),
  unreadCount: () => api.get('/alerts/unread-count'),
  acknowledge: (id, note) => api.post(`/alerts/${id}/acknowledge`, { note }),
  acknowledgeBulk: (ids) => api.post('/alerts/acknowledge-bulk', ids),
}

export const serversApi = {
  list: () => api.get('/servers/'),
  get: (id) => api.get(`/servers/${id}`),
  create: (data) => api.post('/servers/', data),
  update: (id, data) => api.put(`/servers/${id}`, data),
  delete: (id) => api.delete(`/servers/${id}`),
  rotateToken: (id) => api.post(`/servers/${id}/rotate-token`),
}

export const usersApi = {
  list: () => api.get('/users/'),
  get: (id) => api.get(`/users/${id}`),
  create: (data) => api.post('/users/', data),
  update: (id, data) => api.put(`/users/${id}`, data),
  delete: (id) => api.delete(`/users/${id}`),
}

export default api
