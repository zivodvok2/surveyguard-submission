import axios from 'axios'

// Same-origin by default so a clean Docker/API deployment is self-contained.
// A split Vercel frontend can point to its backend with VITE_QC_API_URL.
const qcBaseURL = import.meta.env.VITE_QC_API_URL ?? ''

export const qcClient = axios.create({
  baseURL: qcBaseURL,
  timeout: 120_000,
})

// Dashboard/auth client → this project's local backend (api.py)
// In dev: Vite proxies /api → http://localhost:8000 (empty baseURL = relative)
// In prod: set VITE_DASHBOARD_API_URL to the client's deployed backend URL
const dashboardBaseURL = import.meta.env.VITE_DASHBOARD_API_URL ?? ''

export const dashboardClient = axios.create({
  baseURL: dashboardBaseURL,
  timeout: 120_000,
})

// 401 on dashboard calls → log out and re-prompt login
dashboardClient.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      import('../store/appStore').then(({ useAppStore }) => {
        const { logoutUser, openLogin } = useAppStore.getState()
        logoutUser()
        openLogin('inline')
      })
    }
    const detail = err.response?.data?.detail
    const message =
      typeof detail === 'string'
        ? detail
        : typeof detail === 'object' && detail?.error
          ? detail.error
          : err.message
    return Promise.reject(Object.assign(new Error(message), { status: err.response?.status }))
  },
)

// `client` alias → qcClient (used by upload, qc, eda, interviewers, compare, ai)
export const client = qcClient
