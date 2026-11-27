import { apiGet, apiPost } from './client'

/** The signed-in staff member (data-model.md#currentuser, contracts/auth-api.md). */
export interface CurrentUser {
  id: number
  username: string
  first_name: string
  last_name: string
  display_name: string
  is_superuser: boolean
  /** `"app_label.codename"` strings; UI hints only, the server remains authoritative. */
  permissions: string[]
}

export const authApi = {
  /** Ensures the `csrftoken` cookie is set. */
  async csrf(): Promise<void> {
    await apiGet<void>('/auth/csrf/')
  },
  login(username: string, password: string): Promise<CurrentUser> {
    return apiPost<CurrentUser>('/auth/login/', { username, password })
  },
  async logout(): Promise<void> {
    await apiPost<void>('/auth/logout/')
  },
  me(): Promise<CurrentUser> {
    return apiGet<CurrentUser>('/auth/me/')
  },
}
