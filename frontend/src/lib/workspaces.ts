import { apiRequest } from './api'

export type WorkspaceRole = 'brand_owner' | 'creator'

export type WorkspaceRecord = {
  id: string
  name: string
  slug: string
  created_by: string
  created_at: string
  updated_at: string
}

export type WorkspaceListItem = {
  workspace: WorkspaceRecord
  role: WorkspaceRole
  joined_at: string
}

export type WorkspaceCreateInput = {
  name: string
  slug: string
}

export function getWorkspaces() {
  return apiRequest<WorkspaceListItem[]>('/api/v1/workspaces')
}

export function createWorkspace(input: WorkspaceCreateInput) {
  return apiRequest<WorkspaceRecord>('/api/v1/workspaces', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function roleLabel(role: WorkspaceRole) {
  return role === 'brand_owner' ? 'Brand Owner' : 'Creator'
}

export function makeWorkspaceSlug(name: string) {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 63)
}
