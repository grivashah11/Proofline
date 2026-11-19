import { supabase } from './supabase'

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
).replace(/\/+$/, '')

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function getErrorMessage(payload: unknown, fallback: string): string {
  if (typeof payload === 'string' && payload.trim()) {
    return payload
  }

  if (payload && typeof payload === 'object' && 'detail' in payload) {
    const detail = (payload as { detail?: unknown }).detail

    if (typeof detail === 'string') return detail
    if (detail !== undefined) return JSON.stringify(detail)
  }

  return fallback
}

async function authenticatedFetch(
  path: string,
  options: RequestInit,
  accept: string,
): Promise<Response> {
  const headers = new Headers(options.headers)
  headers.set('Accept', accept)

  // Let the browser set the multipart boundary for FormData uploads.
  if (
    options.body &&
    !(typeof FormData !== 'undefined' && options.body instanceof FormData) &&
    !headers.has('Content-Type')
  ) {
    headers.set('Content-Type', 'application/json')
  }

  if (supabase) {
    const { data, error } = await supabase.auth.getSession()

    if (error) {
      throw new Error(`Unable to read sign-in session: ${error.message}`)
    }

    const accessToken = data.session?.access_token

    if (accessToken) {
      headers.set('Authorization', `Bearer ${accessToken}`)
    }
  }

  const normalizedPath = path.startsWith('/') ? path : `/${path}`

  try {
    return await fetch(`${API_BASE_URL}${normalizedPath}`, {
      ...options,
      headers,
    })
  } catch {
    throw new Error(
      'Could not reach the Proofline backend. Check that the API server is running.',
    )
  }
}

async function readErrorResponse(
  response: Response,
  fallback: string,
): Promise<ApiError> {
  const contentType = response.headers.get('content-type') ?? ''
  const payload: unknown = contentType.includes('application/json')
    ? await response.json()
    : await response.text()

  return new ApiError(
    getErrorMessage(payload, `${fallback} (${response.status}).`),
    response.status,
  )
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await authenticatedFetch(
    path,
    options,
    'application/json',
  )

  if (response.status === 204) {
    return undefined as T
  }

  const contentType = response.headers.get('content-type') ?? ''
  const payload: unknown = contentType.includes('application/json')
    ? await response.json()
    : await response.text()

  if (!response.ok) {
    throw new ApiError(
      getErrorMessage(
        payload,
        `The request failed with status ${response.status}.`,
      ),
      response.status,
    )
  }

  return payload as T
}

export async function apiRequestBlob(path: string): Promise<Blob> {
  const response = await authenticatedFetch(path, {}, 'image/*')

  if (!response.ok) {
    throw await readErrorResponse(response, 'The image request failed')
  }

  return response.blob()
}

export async function apiRequestFile(path: string): Promise<Blob> {
  const response = await authenticatedFetch(
    path,
    {},
    'application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document, application/octet-stream',
  )

  if (!response.ok) {
    throw await readErrorResponse(response, 'The document request failed')
  }

  return response.blob()
}
