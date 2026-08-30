import { dashboardClient as client } from './client'

export interface AuthUser {
  id: number
  email: string
  name: string
  role: string
  totp_enabled?: boolean
}

export interface LoginResponse {
  token: string
  user: AuthUser
}

export interface OtpChallenge {
  otp_required: true
  user_id: number
  demo_otp: string
  is_totp?: boolean
}

export interface TotpSetupResponse {
  secret: string
  provisioning_uri: string
  qr_base64: string
}

export async function login(email: string, password: string): Promise<LoginResponse | OtpChallenge> {
  const { data } = await client.post<LoginResponse | OtpChallenge>('/api/auth/login', { email, password })
  return data
}

export async function verifyOtp(userId: number, code: string): Promise<LoginResponse> {
  const { data } = await client.post<LoginResponse>('/api/auth/verify-otp', { user_id: userId, code })
  return data
}

export async function enable2FA(token: string): Promise<AuthUser> {
  const { data } = await client.post<AuthUser>('/api/auth/enable-2fa', null, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return data
}

export async function disable2FA(token: string): Promise<AuthUser> {
  const { data } = await client.post<AuthUser>('/api/auth/disable-2fa', null, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return data
}

export async function setupTotp(token: string): Promise<TotpSetupResponse> {
  const { data } = await client.post<TotpSetupResponse>('/api/auth/setup-totp', null, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return data
}

export async function confirmTotp(token: string, code: string): Promise<AuthUser> {
  const { data } = await client.post<AuthUser>('/api/auth/confirm-totp', { code }, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return data
}

export async function disableTotp(token: string): Promise<AuthUser> {
  const { data } = await client.post<AuthUser>('/api/auth/disable-totp', null, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return data
}

export async function requestPasswordReset(email: string): Promise<{ status: string; demo_code?: string }> {
  const { data } = await client.post<{ status: string; demo_code?: string }>('/api/dashboard/auth/request-password-reset', { email })
  return data
}

export async function resetPassword(email: string, code: string, password: string): Promise<{ status: string }> {
  const { data } = await client.post<{ status: string }>('/api/dashboard/auth/reset-password', { email, code, password })
  return data
}

export async function me(token: string): Promise<AuthUser> {
  const { data } = await client.get<AuthUser>('/api/auth/me', {
    headers: { Authorization: `Bearer ${token}` },
  })
  return data
}
