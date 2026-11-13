import { useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  Archive,
  Check,
  CheckCircle2,
  Clock3,
  FileImage,
  ImagePlus,
  LoaderCircle,
  Palette,
  RefreshCw,
  ShieldCheck,
  Upload,
  X,
  XCircle,
} from 'lucide-react'
import { ApiError } from '../lib/api'
import {
  archiveBrandAsset,
  createBrandAsset,
  createImageCheck,
  getImageCheckFile,
  listBrandAssets,
  listImageChecks,
  updateBrandAsset,
  type BrandAsset,
  type ImageCheckRecord,
  type PaletteColor,
} from '../lib/images'
import type { WorkspaceRole } from '../lib/workspaces'
import './ImagesPage.css'

type Props = {
  workspaceId: string
  role: WorkspaceRole
}

type Tab = 'assets' | 'checks'

function errorMessage(error: unknown) {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Something went wrong. Please try again.'
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function ColorSwatches({ colors }: { colors: PaletteColor[] }) {
  if (colors.length === 0) {
    return <span className="image-muted-copy">No palette data</span>
  }

  return (
    <div className="image-swatches" aria-label="Dominant colors">
      {colors.map((color) => (
        <span
          className="image-swatch"
          key={color.hex}
          title={`${color.hex} · ${color.percentage.toFixed(1)}%`}
          style={{ backgroundColor: color.hex }}
        />
      ))}
    </div>
  )
}

function UploadPreview({ file }: { file: File | null }) {
  const previewUrl = useMemo(
    () => (file ? URL.createObjectURL(file) : ''),
    [file],
  )

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    }
  }, [previewUrl])

  if (!file || !previewUrl) return null

  return (
    <div className="image-upload-preview">
      <img src={previewUrl} alt="Selected image preview" />
      <div>
        <strong>{file.name}</strong>
        <small>{formatBytes(file.size)}</small>
      </div>
    </div>
  )
}

function CheckedImagePreview({
  workspaceId,
  imageCheckId,
}: {
  workspaceId: string
  imageCheckId: string
}) {
  const [source, setSource] = useState('')
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let active = true
    let objectUrl = ''

    getImageCheckFile(workspaceId, imageCheckId)
      .then((blob) => {
        if (!active) return
        objectUrl = URL.createObjectURL(blob)
        setSource(objectUrl)
        setFailed(false)
      })
      .catch(() => {
        if (active) setFailed(true)
      })

    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [workspaceId, imageCheckId])

  if (failed) {
    return <div className="image-preview-placeholder">Private image preview unavailable</div>
  }

  if (!source) {
    return <div className="image-preview-placeholder"><LoaderCircle className="image-spin" size={20} /></div>
  }

  return <img className="image-result-preview" src={source} alt="Submitted image" />
}

function AssetCard({
  asset,
  canManage,
  busyId,
  onArchive,
  onReactivate,
}: {
  asset: BrandAsset
  canManage: boolean
  busyId: string
  onArchive: (asset: BrandAsset) => void
  onReactivate: (asset: BrandAsset) => void
}) {
  return (
    <article className={`image-asset-card ${asset.is_active ? '' : 'is-archived'}`}>
      <div className="image-asset-topline">
        <div className="image-file-icon"><FileImage size={20} /></div>
        <span className={`image-state ${asset.is_active ? 'is-active' : 'is-inactive'}`}>
          {asset.is_active ? 'Approved' : 'Archived'}
        </span>
      </div>
      <h3>{asset.asset_name}</h3>
      <p className="image-asset-description">{asset.description || 'No description provided.'}</p>
      <div className="image-asset-meta">
        <span>{asset.image_format}</span>
        <span>{asset.width} × {asset.height}</span>
        <span>{formatBytes(asset.file_size_bytes)}</span>
      </div>
      <div className="image-palette-row">
        <span>Dominant colors</span>
        <ColorSwatches colors={asset.dominant_colors} />
      </div>
      <p className="image-hash" title={asset.sha256_hash}>
        SHA-256 · {asset.sha256_hash.slice(0, 20)}…
      </p>
      <div className="image-asset-footer">
        <small>{formatDate(asset.created_at)}</small>
        {canManage && (asset.is_active ? (
          <button
            className="image-small-button image-small-button--danger"
            type="button"
            disabled={busyId === asset.id}
            onClick={() => onArchive(asset)}
          >
            {busyId === asset.id ? <LoaderCircle size={14} className="image-spin" /> : <Archive size={14} />}
            Archive
          </button>
        ) : (
          <button
            className="image-small-button"
            type="button"
            disabled={busyId === asset.id}
            onClick={() => onReactivate(asset)}
          >
            {busyId === asset.id ? <LoaderCircle size={14} className="image-spin" /> : <RefreshCw size={14} />}
            Reactivate
          </button>
        ))}
      </div>
    </article>
  )
}

function ImageCheckResult({
  workspaceId,
  check,
}: {
  workspaceId: string
  check: ImageCheckRecord
}) {
  const exactMatch = check.analysis.asset_match_status === 'exact_match'
  const altProvided = check.analysis.alt_text_status === 'provided'

  return (
    <section className="image-result-panel">
      <div className="image-result-heading">
        <div>
          <p className="image-eyebrow">CHECK RESULT</p>
          <h2>{check.original_filename}</h2>
          <p className="image-muted-copy">Checked {formatDate(check.created_at)}</p>
        </div>
        <span className={`image-state ${exactMatch ? 'is-active' : 'is-warning'}`}>
          {exactMatch ? 'Exact approved match' : 'Review required'}
        </span>
      </div>

      <div className="image-result-overview">
        <CheckedImagePreview workspaceId={workspaceId} imageCheckId={check.id} />
        <div className="image-result-facts">
          <div className={`image-fact ${exactMatch ? 'is-good' : 'is-warning'}`}>
            {exactMatch ? <CheckCircle2 size={18} /> : <XCircle size={18} />}
            <div>
              <small>Approved asset match</small>
              <strong>{exactMatch ? check.analysis.matched_asset?.asset_name ?? 'Exact match' : 'No exact match'}</strong>
            </div>
          </div>
          <div className={`image-fact ${altProvided ? 'is-good' : 'is-warning'}`}>
            {altProvided ? <CheckCircle2 size={18} /> : <XCircle size={18} />}
            <div>
              <small>Alternative text</small>
              <strong>{altProvided ? 'Provided' : 'Missing'}</strong>
            </div>
          </div>
          <div className="image-result-dimensions">
            <span>{check.image_format}</span>
            <span>{check.width} × {check.height}px</span>
            <span>{formatBytes(check.file_size_bytes)}</span>
          </div>
          {check.alt_text && <p className="image-alt-text"><strong>Alt text:</strong> {check.alt_text}</p>}
        </div>
      </div>

      <div className="image-result-section">
        <div className="image-section-title"><Palette size={16} /><h3>Detected dominant colors</h3></div>
        <div className="image-color-list">
          {check.analysis.dominant_colors.map((color) => (
            <div className="image-color-item" key={color.hex}>
              <span className="image-color-chip" style={{ backgroundColor: color.hex }} />
              <strong>{color.hex}</strong>
              <span>{color.percentage.toFixed(1)}%</span>
            </div>
          ))}
        </div>
      </div>

      <div className="image-result-section">
        <div className="image-section-title"><ShieldCheck size={16} /><h3>Findings and recommended actions</h3></div>
        <div className="image-findings-list">
          {check.analysis.findings.map((finding) => (
            <article className={`image-finding image-finding--${finding.severity}`} key={finding.code}>
              <div>
                <span className="image-finding-label">{finding.severity === 'warning' ? 'REVIEW' : 'INFORMATION'}</span>
                <h4>{finding.title}</h4>
                <p>{finding.message}</p>
                <small><strong>Next action:</strong> {finding.recommended_action}</small>
              </div>
            </article>
          ))}
        </div>
      </div>

      <div className="image-limitations">
        <strong>What this check does not verify</strong>
        <ul>
          {check.analysis.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}
        </ul>
      </div>
    </section>
  )
}

export default function ImagesPage({ workspaceId, role }: Props) {
  const canManage = role === 'brand_owner'
  const [tab, setTab] = useState<Tab>('assets')
  const [assets, setAssets] = useState<BrandAsset[]>([])
  const [checks, setChecks] = useState<ImageCheckRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [assetName, setAssetName] = useState('')
  const [assetDescription, setAssetDescription] = useState('')
  const [assetFile, setAssetFile] = useState<File | null>(null)
  const [assetBusy, setAssetBusy] = useState(false)
  const [busyAssetId, setBusyAssetId] = useState('')
  const [checkFile, setCheckFile] = useState<File | null>(null)
  const [altText, setAltText] = useState('')
  const [checkBusy, setCheckBusy] = useState(false)
  const [selectedCheck, setSelectedCheck] = useState<ImageCheckRecord | null>(null)

  useEffect(() => {
    let active = true

    Promise.all([listBrandAssets(workspaceId), listImageChecks(workspaceId)])
      .then(([assetRecords, checkRecords]) => {
        if (!active) return
        setAssets(assetRecords)
        setChecks(checkRecords)
        setSelectedCheck(checkRecords[0] ?? null)
        setError('')
      })
      .catch((err: unknown) => {
        if (active) setError(errorMessage(err))
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [workspaceId])

  async function refreshData() {
    const [assetRecords, checkRecords] = await Promise.all([
      listBrandAssets(workspaceId),
      listImageChecks(workspaceId),
    ])
    setAssets(assetRecords)
    setChecks(checkRecords)
    return checkRecords
  }

  async function handleAssetSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setNotice('')

    if (!assetFile) {
      setError('Choose a PNG, JPEG or WebP image to upload.')
      return
    }
    if (assetName.trim().length < 2) {
      setError('Asset name must contain at least two characters.')
      return
    }

    setAssetBusy(true)
    try {
      const created = await createBrandAsset(workspaceId, {
        file: assetFile,
        assetName,
        description: assetDescription,
      })
      setAssetName('')
      setAssetDescription('')
      setAssetFile(null)
      await refreshData()
      setNotice(`“${created.asset_name}” is now registered as an approved asset.`)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setAssetBusy(false)
    }
  }

  async function handleArchive(asset: BrandAsset) {
    setError('')
    setNotice('')
    setBusyAssetId(asset.id)
    try {
      await archiveBrandAsset(workspaceId, asset.id)
      await refreshData()
      setNotice(`“${asset.asset_name}” has been archived. Its stored file and history are retained.`)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusyAssetId('')
    }
  }

  async function handleReactivate(asset: BrandAsset) {
    setError('')
    setNotice('')
    setBusyAssetId(asset.id)
    try {
      await updateBrandAsset(workspaceId, asset.id, { is_active: true })
      await refreshData()
      setNotice(`“${asset.asset_name}” is active again.`)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusyAssetId('')
    }
  }

  async function handleImageCheckSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setNotice('')

    if (!checkFile) {
      setError('Choose a PNG, JPEG or WebP image to check.')
      return
    }

    setCheckBusy(true)
    try {
      const result = await createImageCheck(workspaceId, {
        file: checkFile,
        altText,
      })
      setSelectedCheck(result)
      setCheckFile(null)
      setAltText('')
      const checkRecords = await refreshData()
      setSelectedCheck(checkRecords.find((item) => item.id === result.id) ?? result)
      setNotice('Image check completed and saved to workspace history.')
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setCheckBusy(false)
    }
  }

  const activeAssets = assets.filter((asset) => asset.is_active)
  const archivedAssets = assets.filter((asset) => !asset.is_active)

  return (
    <div className="images-page">
      <div className="images-page-heading">
        <div>
          <div className="images-heading-icon"><ImagePlus size={22} /></div>
          <p className="image-eyebrow">VISUAL BRAND GOVERNANCE</p>
          <h1>Images &amp; assets</h1>
          <p className="images-page-description">
            Register approved brand imagery and check submitted visuals before they are used in content.
          </p>
        </div>
        <div className="images-header-summary">
          <div><strong>{activeAssets.length}</strong><span>Active assets</span></div>
          <div><strong>{checks.length}</strong><span>Image checks</span></div>
        </div>
      </div>

      <div className="images-tabs" role="tablist" aria-label="Image tools">
        <button className={tab === 'assets' ? 'is-selected' : ''} type="button" role="tab" aria-selected={tab === 'assets'} onClick={() => setTab('assets')}>
          <ShieldCheck size={16} /> Approved assets <span>{activeAssets.length}</span>
        </button>
        <button className={tab === 'checks' ? 'is-selected' : ''} type="button" role="tab" aria-selected={tab === 'checks'} onClick={() => setTab('checks')}>
          <FileImage size={16} /> Check an image <span>{checks.length}</span>
        </button>
      </div>

      {error && <div className="images-alert images-alert--error" role="alert"><XCircle size={17} /><span>{error}</span><button type="button" onClick={() => setError('')} aria-label="Dismiss error"><X size={15} /></button></div>}
      {notice && <div className="images-alert images-alert--success" role="status"><CheckCircle2 size={17} /><span>{notice}</span><button type="button" onClick={() => setNotice('')} aria-label="Dismiss notice"><X size={15} /></button></div>}

      {loading ? (
        <div className="images-loading"><LoaderCircle className="image-spin" size={22} /><span>Loading image workspace…</span></div>
      ) : tab === 'assets' ? (
        <>
          {canManage ? (
            <section className="images-panel image-register-panel">
              <div className="images-panel-heading">
                <div><p className="image-eyebrow">BRAND OWNER</p><h2>Register an approved asset</h2><p>Upload the original image your team is allowed to reuse.</p></div>
                <div className="images-panel-icon"><Upload size={19} /></div>
              </div>
              <form className="image-register-form" onSubmit={handleAssetSubmit}>
                <label className="image-field"><span>Asset name</span><input value={assetName} onChange={(event) => setAssetName(event.target.value)} placeholder="e.g. Primary product logo" minLength={2} maxLength={120} required /></label>
                <label className="image-field"><span>Description <small>Optional</small></span><input value={assetDescription} onChange={(event) => setAssetDescription(event.target.value)} placeholder="Where or how this image may be used" maxLength={2000} /></label>
                <label className="image-file-drop"><input type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => setAssetFile(event.target.files?.[0] ?? null)} /><Upload size={18} /><strong>{assetFile ? 'Change selected image' : 'Choose an image'}</strong><span>PNG, JPEG or WebP · Up to 8 MB</span></label>
                <UploadPreview file={assetFile} />
                <div className="image-form-footer"><span>Exact file duplicates in this workspace are rejected.</span><button className="image-primary-button" type="submit" disabled={assetBusy}>{assetBusy ? <LoaderCircle size={16} className="image-spin" /> : <Upload size={16} />}{assetBusy ? 'Registering…' : 'Register approved asset'}</button></div>
              </form>
            </section>
          ) : (
            <div className="images-readonly-note"><ShieldCheck size={17} /><span>Approved assets are managed by your Brand Owner. You can view active assets and use them during image checks.</span></div>
          )}

          <section className="images-section">
            <div className="images-section-heading"><div><p className="image-eyebrow">WORKSPACE LIBRARY</p><h2>Approved brand assets</h2></div><span>{activeAssets.length} active</span></div>
            {activeAssets.length === 0 ? (
              <div className="images-empty"><div><FileImage size={23} /></div><strong>No approved images yet</strong><p>{canManage ? 'Register a logo, product image or campaign visual to start building your approved asset library.' : 'Your Brand Owner has not registered any active assets yet.'}</p></div>
            ) : (
              <div className="image-assets-grid">{activeAssets.map((asset) => <AssetCard key={asset.id} asset={asset} canManage={canManage} busyId={busyAssetId} onArchive={(item) => void handleArchive(item)} onReactivate={(item) => void handleReactivate(item)} />)}</div>
            )}
          </section>

          {canManage && archivedAssets.length > 0 && (
            <section className="images-section images-archived-section">
              <div className="images-section-heading"><div><p className="image-eyebrow">RETAINED RECORDS</p><h2>Archived assets</h2></div><span>{archivedAssets.length} archived</span></div>
              <div className="image-assets-grid">{archivedAssets.map((asset) => <AssetCard key={asset.id} asset={asset} canManage={canManage} busyId={busyAssetId} onArchive={(item) => void handleArchive(item)} onReactivate={(item) => void handleReactivate(item)} />)}</div>
            </section>
          )}
        </>
      ) : (
        <div className="image-check-layout">
          <div className="image-check-main">
            <section className="images-panel">
              <div className="images-panel-heading">
                <div><p className="image-eyebrow">STATIC IMAGE REVIEW</p><h2>Check an image</h2><p>Compare the uploaded file with active approved assets and inspect metadata and alt-text presence.</p></div>
                <div className="images-panel-icon"><Palette size={19} /></div>
              </div>
              <form className="image-check-form" onSubmit={handleImageCheckSubmit}>
                <label className="image-file-drop image-file-drop--large"><input type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => setCheckFile(event.target.files?.[0] ?? null)} /><ImagePlus size={21} /><strong>{checkFile ? 'Choose a different image' : 'Select an image to review'}</strong><span>PNG, JPEG or WebP · Up to 8 MB</span></label>
                <UploadPreview file={checkFile} />
                <label className="image-field"><span>Alternative text <small>Optional · Up to 1,000 characters</small></span><textarea value={altText} onChange={(event) => setAltText(event.target.value)} placeholder="Describe the purpose or relevant content of this image…" maxLength={1000} rows={3} /></label>
                <div className="image-form-footer"><span>Creators and Brand Owners can run checks.</span><button className="image-primary-button" type="submit" disabled={checkBusy}>{checkBusy ? <LoaderCircle size={16} className="image-spin" /> : <Check size={16} />}{checkBusy ? 'Checking image…' : 'Run image check'}</button></div>
              </form>
            </section>

            {selectedCheck && <ImageCheckResult workspaceId={workspaceId} check={selectedCheck} />}
          </div>

          <aside className="image-history-panel">
            <div className="image-history-heading"><div><p className="image-eyebrow">RECENT ACTIVITY</p><h2>Image checks</h2></div><Clock3 size={17} /></div>
            {checks.length === 0 ? (
              <div className="image-history-empty">Your completed image checks will appear here.</div>
            ) : (
              <div className="image-history-list">{checks.map((check) => {
                const match = check.analysis.asset_match_status === 'exact_match'
                return (
                  <button className={`image-history-item ${selectedCheck?.id === check.id ? 'is-selected' : ''}`} type="button" key={check.id} onClick={() => setSelectedCheck(check)}>
                    <span className={`image-history-icon ${match ? 'is-good' : 'is-warning'}`}>{match ? <CheckCircle2 size={16} /> : <FileImage size={16} />}</span>
                    <span className="image-history-copy"><strong>{check.original_filename}</strong><small>{match ? 'Exact approved match' : 'No exact match'} · {formatDate(check.created_at)}</small></span>
                  </button>
                )
              })}</div>
            )}
            <div className="image-history-note">Results are saved to this workspace and remain available to its members.</div>
          </aside>
        </div>
      )}

      <div className="images-disclaimer"><ShieldCheck size={15} /><span>Image checks are advisory. Exact hash matching does not identify resized or visually similar images, and color or alt-text quality still requires human review.</span></div>
    </div>
  )
}
