import { apiRequest, apiRequestBlob } from './api'

export type PaletteColor = {
  hex: string
  percentage: number
}

export type ImageFinding = {
  code: string
  severity: 'info' | 'warning'
  title: string
  message: string
  recommended_action: string
}

export type BrandAsset = {
  id: string
  workspace_id: string
  asset_name: string
  description: string | null
  original_filename: string
  mime_type: string
  file_size_bytes: number
  sha256_hash: string
  image_format: 'JPEG' | 'PNG' | 'WEBP'
  width: number
  height: number
  dominant_colors: PaletteColor[]
  is_active: boolean
  created_by: string
  created_at: string
  updated_at: string
}

export type BrandAssetUpdate = {
  asset_name?: string
  description?: string | null
  is_active?: boolean
}

export type ImageCheckAnalysis = {
  asset_match_status: 'exact_match' | 'no_exact_match'
  matched_asset: {
    id: string
    asset_name: string
    description: string | null
  } | null
  dominant_colors: PaletteColor[]
  alt_text_status: 'provided' | 'missing'
  findings: ImageFinding[]
  limitations: string[]
}

export type ImageCheckRecord = {
  id: string
  workspace_id: string
  original_filename: string
  mime_type: string
  file_size_bytes: number
  sha256_hash: string
  image_format: 'JPEG' | 'PNG' | 'WEBP'
  width: number
  height: number
  alt_text: string | null
  analysis: ImageCheckAnalysis
  created_by: string
  created_at: string
}

const workspacePath = (workspaceId: string) =>
  `/api/v1/workspaces/${workspaceId}`

export function listBrandAssets(workspaceId: string) {
  return apiRequest<BrandAsset[]>(`${workspacePath(workspaceId)}/brand-assets`)
}

export function createBrandAsset(
  workspaceId: string,
  input: { file: File; assetName: string; description: string },
) {
  const formData = new FormData()
  formData.append('file', input.file)
  formData.append('asset_name', input.assetName.trim())
  if (input.description.trim()) {
    formData.append('description', input.description.trim())
  }

  return apiRequest<BrandAsset>(`${workspacePath(workspaceId)}/brand-assets`, {
    method: 'POST',
    body: formData,
  })
}

export function updateBrandAsset(
  workspaceId: string,
  assetId: string,
  updates: BrandAssetUpdate,
) {
  return apiRequest<BrandAsset>(
    `${workspacePath(workspaceId)}/brand-assets/${assetId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(updates),
    },
  )
}

export function archiveBrandAsset(workspaceId: string, assetId: string) {
  return apiRequest<void>(
    `${workspacePath(workspaceId)}/brand-assets/${assetId}`,
    { method: 'DELETE' },
  )
}

export function getBrandAssetFile(workspaceId: string, assetId: string) {
  return apiRequestBlob(
    `${workspacePath(workspaceId)}/brand-assets/${assetId}/file`,
  )
}

export function listImageChecks(workspaceId: string) {
  return apiRequest<ImageCheckRecord[]>(
    `${workspacePath(workspaceId)}/image-checks`,
  )
}

export function createImageCheck(
  workspaceId: string,
  input: { file: File; altText: string },
) {
  const formData = new FormData()
  formData.append('file', input.file)
  if (input.altText.trim()) {
    formData.append('alt_text', input.altText.trim())
  }

  return apiRequest<ImageCheckRecord>(
    `${workspacePath(workspaceId)}/image-checks`,
    {
      method: 'POST',
      body: formData,
    },
  )
}

export function getImageCheck(workspaceId: string, imageCheckId: string) {
  return apiRequest<ImageCheckRecord>(
    `${workspacePath(workspaceId)}/image-checks/${imageCheckId}`,
  )
}

export function getImageCheckFile(workspaceId: string, imageCheckId: string) {
  return apiRequestBlob(
    `${workspacePath(workspaceId)}/image-checks/${imageCheckId}/file`,
  )
}
