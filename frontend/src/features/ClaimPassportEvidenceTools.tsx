import { useEffect, useRef, useState } from 'react'
import {
  AlertCircle,
  ArrowDownToLine,
  BookOpenText,
  CalendarClock,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock3,
  FileText,
  LoaderCircle,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Upload,
} from 'lucide-react'
import { ApiError, apiRequest, apiRequestFile } from '../lib/api'
import './ClaimPassportEvidenceTools.css'

type SourceDocumentFormat = 'PDF' | 'DOCX'
type SourceLocationType = 'page' | 'section' | 'table_row'
type ReminderStatus = 'due_soon' | 'overdue' | 'expired'

export type SourceDocumentRecord = {
  id: string
  workspace_id: string
  title: string
  original_filename: string
  mime_type: string
  document_format: SourceDocumentFormat
  file_size_bytes: number
  sha256_hash: string
  page_count: number | null
  segment_count: number
  extraction_warnings: string[]
  uploaded_by: string
  created_at: string
}

export type SourceDocumentSegmentRecord = {
  id: string
  workspace_id: string
  source_document_id: string
  segment_index: number
  location_type: SourceLocationType
  location_label: string
  page_number: number | null
  section_path: string | null
  paragraph_number: number | null
  text_content: string
  sha256_hash: string
  created_at: string
}

export type SourceEvidenceSelection = {
  source_document_id: string
  source_document_segment_id: string
  source_excerpt: string
  evidence_source_title: string
  evidence_reference: string
  evidence_source_version: string
}

type PassportReverificationReminder = {
  passport_id: string
  passport_code: string
  subject: string
  version_id: string
  version_number: number
  review_by: string | null
  valid_until: string | null
  status: ReminderStatus
  days_until_action: number
}

type ClaimPassportVersionSourceRecord = {
  id: string
  workspace_id: string
  claim_passport_id: string
  passport_version_id: string
  source_document_id: string
  source_document_segment_id: string
  excerpt: string
  location_label_snapshot: string
  source_document_title_snapshot: string
  source_document_sha256_snapshot: string
  created_by: string
  created_at: string
}

export function PassportSourceLinks({
  workspaceId,
  passportId,
  versionId,
}: {
  workspaceId: string
  passportId: string
  versionId: string
}) {
  const [sources, setSources] = useState<ClaimPassportVersionSourceRecord[]>([])
  const [loadedKey, setLoadedKey] = useState('')
  const [loadError, setLoadError] = useState('')
  const [actionError, setActionError] = useState('')
  const [retryKey, setRetryKey] = useState(0)
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const requestKey = `${workspaceId}:${passportId}:${versionId}:${retryKey}`
  const loading = loadedKey !== requestKey

  useEffect(() => {
    let active = true
    const effectRequestKey = `${workspaceId}:${passportId}:${versionId}:${retryKey}`
    apiRequest<ClaimPassportVersionSourceRecord[]>(
      `/api/v1/workspaces/${workspaceId}/claim-passports/${passportId}/versions/${versionId}/sources`,
    )
      .then((items) => {
        if (active) {
          setSources(items)
          setLoadError('')
          setLoadedKey(effectRequestKey)
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setLoadError(getErrorMessage(reason))
          setLoadedKey(effectRequestKey)
        }
      })

    return () => {
      active = false
    }
  }, [workspaceId, passportId, versionId, retryKey])

  async function downloadSource(source: ClaimPassportVersionSourceRecord) {
    setDownloadingId(source.id)
    setActionError('')
    try {
      const blob = await apiRequestFile(
        `/api/v1/workspaces/${workspaceId}/source-documents/${source.source_document_id}/file`,
      )
      triggerBlobDownload(
        blob,
        filenameFromTitle(source.source_document_title_snapshot, blob),
      )
    } catch (reason) {
      setActionError(getErrorMessage(reason))
    } finally {
      setDownloadingId(null)
    }
  }

  if (loading) return <div className="cpet-inline-state"><LoaderCircle className="cpet-spinner" size={14} /> Loading document provenance…</div>
  if (loadError) {
    return (
      <div className="cpet-inline-error" role="alert">
        <AlertCircle size={14} />
        <span>{loadError}</span>
        <button type="button" onClick={() => setRetryKey((value) => value + 1)} disabled={loading}>
          <RefreshCw size={13} /> Retry provenance
        </button>
      </div>
    )
  }
  if (sources.length === 0) return null

  return (
    <div className="cpet-source-links">
      <div className="cpet-source-links-heading"><BookOpenText size={14} /><strong>Verified document provenance</strong></div>
      {actionError && <div className="cpet-inline-error" role="alert"><AlertCircle size={14} />{actionError}</div>}
      {sources.map((source) => (
        <div className="cpet-source-link-card" key={source.id}>
          <div>
            <strong>{source.source_document_title_snapshot}</strong>
            <span>{source.location_label_snapshot}</span>
            <blockquote>{source.excerpt}</blockquote>
            <small>Source SHA-256: {source.source_document_sha256_snapshot.slice(0, 16)}…</small>
          </div>
          <button type="button" className="cpet-text-button" onClick={() => void downloadSource(source)} disabled={downloadingId === source.id}>
            {downloadingId === source.id ? <LoaderCircle className="cpet-spinner" size={13} /> : <ArrowDownToLine size={13} />}
            {downloadingId === source.id ? 'Preparing…' : 'Download original'}
          </button>
        </div>
      ))}
    </div>
  )
}

type SourceDocumentEvidencePickerProps = {
  workspaceId: string
  onSelectEvidence: (selection: SourceEvidenceSelection | null) => void
  selectedSourceDocumentId?: string | null
  selectedSegmentId?: string | null
}

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message
  return 'Something went wrong. Please try again.'
}

/**
 * Download an authenticated file response without navigating the current tab
 * to its blob URL. The download attribute is important for PDFs: without it,
 * Chrome opens its PDF viewer, which can fail later if the blob URL is revoked.
 */
function triggerBlobDownload(blob: Blob, filename: string): void {
  if (blob.size === 0) {
    throw new Error('The downloaded source document was empty.')
  }

  if (blob.type.toLowerCase().includes('application/json')) {
    throw new Error('The server returned JSON instead of the original document.')
  }

  const objectUrl = URL.createObjectURL(blob)
  const anchor = window.document.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename
  anchor.style.position = 'fixed'
  anchor.style.left = '-10000px'
  anchor.style.top = '0'
  anchor.setAttribute('aria-hidden', 'true')
  window.document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()

  // Chrome may start processing the download asynchronously. Keep the blob
  // URL alive long enough for the browser to finish reading it.
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
}

function filenameFromTitle(title: string, blob: Blob): string {
  const safeTitle = title
    .replace(/[\\/:*?"<>|]/g, '-')
    .split('')
    .filter((character) => {
      const code = character.charCodeAt(0)
      return code >= 0x20 && !(code >= 0x7f && code <= 0x9f)
    })
    .join('')
    .trim()
    .replace(/\.(pdf|docx)$/i, '')
  const mimeType = blob.type.toLowerCase()
  const extension = mimeType.includes('pdf')
    ? '.pdf'
    : mimeType.includes('wordprocessingml')
      ? '.docx'
      : ''
  return `${safeTitle || 'proofline-source-document'}${extension}`
}

function formatDate(value: string | null | undefined): string {
  if (!value) return 'Date not set'
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(parsed)
}

function fetchSourceDocuments(workspaceId: string): Promise<SourceDocumentRecord[]> {
  return apiRequest<SourceDocumentRecord[]>(
    `/api/v1/workspaces/${workspaceId}/source-documents?limit=100`,
  )
}

function formatBytes(value: number): string {
  if (value < 1024 * 1024) return `${Math.max(1, Math.round(value / 1024))} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

function reminderLabel(status: ReminderStatus): string {
  if (status === 'expired') return 'Expired'
  if (status === 'overdue') return 'Overdue'
  return 'Due soon'
}

function reminderDate(reminder: PassportReverificationReminder): string {
  if (reminder.status === 'expired') return formatDate(reminder.valid_until)
  return formatDate(reminder.review_by ?? reminder.valid_until)
}

export function PassportReverificationPanel({
  workspaceId,
  refreshKey = 0,
  onOpenPassport,
}: {
  workspaceId: string
  refreshKey?: number
  onOpenPassport: (passportId: string) => void
}) {
  const [reminders, setReminders] = useState<PassportReverificationReminder[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    let active = true
    apiRequest<PassportReverificationReminder[]>(
      `/api/v1/workspaces/${workspaceId}/claim-passports/reverification-reminders?within_days=30`,
    )
      .then((items) => {
        if (active) {
          setReminders(items)
          setError('')
        }
      })
      .catch((reason: unknown) => {
        if (active) setError(getErrorMessage(reason))
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [workspaceId, refreshKey, retryKey])

  return (
    <section className="cpet-reminders" aria-labelledby="cpet-reminders-title">
      <div className="cpet-section-heading">
        <div className="cpet-section-icon"><CalendarClock size={18} /></div>
        <div>
          <p className="cpet-eyebrow">PASSPORT LIFECYCLE</p>
          <h2 id="cpet-reminders-title">Re-verification reminders</h2>
          <p>Review active evidence before its review date or validity period ends.</p>
        </div>
        <span className="cpet-count">{loading ? '…' : reminders.length}</span>
      </div>

      {loading ? (
        <div className="cpet-inline-state"><LoaderCircle className="cpet-spinner" size={17} /> Loading reminders…</div>
      ) : error ? (
        <div className="cpet-inline-error" role="alert">
          <AlertCircle size={16} />
          <span>{error}</span>
          <button
            type="button"
            onClick={() => {
              setLoading(true)
              setRetryKey((current) => current + 1)
            }}
            disabled={loading}
          >
            <RefreshCw size={13} /> Retry
          </button>
        </div>
      ) : reminders.length === 0 ? (
        <div className="cpet-empty-reminders"><CheckCircle2 size={17} /> No active Passports need re-verification in the next 30 days.</div>
      ) : (
        <div className="cpet-reminder-list">
          {reminders.map((reminder) => (
            <article className="cpet-reminder-row" key={reminder.version_id}>
              <div className={`cpet-reminder-status cpet-reminder-status--${reminder.status}`}>
                {reminder.status === 'due_soon' ? <Clock3 size={15} /> : <ShieldAlert size={15} />}
              </div>
              <div className="cpet-reminder-copy">
                <strong>{reminder.passport_code} · {reminder.subject}</strong>
                <span>Version {reminder.version_number} · {reminderLabel(reminder.status)} · {reminderDate(reminder)}</span>
              </div>
              <button type="button" className="cpet-text-button" onClick={() => onOpenPassport(reminder.passport_id)}>
                View Passport <ChevronRight size={14} />
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

export function SourceDocumentEvidencePicker({
  workspaceId,
  onSelectEvidence,
  selectedSourceDocumentId = null,
  selectedSegmentId = null,
}: SourceDocumentEvidencePickerProps) {
  const [documents, setDocuments] = useState<SourceDocumentRecord[]>([])
  const [segments, setSegments] = useState<Record<string, SourceDocumentSegmentRecord[]>>({})
  const [hasMoreSegments, setHasMoreSegments] = useState<Record<string, boolean>>({})
  const [segmentErrors, setSegmentErrors] = useState<Record<string, string>>({})
  const [downloadErrors, setDownloadErrors] = useState<Record<string, string>>({})
  const [expandedDocumentId, setExpandedDocumentId] = useState<string | null>(null)
  const [loadedWorkspaceId, setLoadedWorkspaceId] = useState<string | null>(null)
  const [refreshingDocuments, setRefreshingDocuments] = useState(false)
  const [loadingSegments, setLoadingSegments] = useState<string | null>(null)
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const segmentRequestLock = useRef(new Set<string>())
  const downloadRequestLock = useRef(new Set<string>())
  const uploadRequestLock = useRef(false)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [documentListError, setDocumentListError] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [fileInputKey, setFileInputKey] = useState(0)
  const [documentTitle, setDocumentTitle] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  const loadingDocuments = loadedWorkspaceId !== workspaceId

  async function loadDocuments() {
    setRefreshingDocuments(true)
    setDocumentListError('')
    try {
      const result = await fetchSourceDocuments(workspaceId)
      setDocuments(result)
      setLoadedWorkspaceId(workspaceId)
    } catch (error) {
      setDocumentListError(getErrorMessage(error))
      setLoadedWorkspaceId(workspaceId)
    } finally {
      setRefreshingDocuments(false)
    }
  }

  useEffect(() => {
    let active = true

    fetchSourceDocuments(workspaceId)
      .then((result) => {
        if (!active) return
        setDocuments(result)
        setDocumentListError('')
        setLoadedWorkspaceId(workspaceId)
      })
      .catch((error: unknown) => {
        if (!active) return
        setDocuments([])
        setSegments({})
        setExpandedDocumentId(null)
        setDocumentListError(getErrorMessage(error))
        setLoadedWorkspaceId(workspaceId)
      })

    return () => {
      active = false
    }
  }, [workspaceId])

  function handleFileChange(file: File | null) {
    setSelectedFile(file)
    setUploadError('')
    setSuccessMessage('')
    if (file && !documentTitle.trim()) {
      setDocumentTitle(file.name.replace(/\.(pdf|docx)$/i, ''))
    }
  }

  async function uploadDocument() {
    if (uploadRequestLock.current) return
    setUploadError('')
    setSuccessMessage('')

    if (!selectedFile) {
      setUploadError('Choose a PDF or DOCX document first.')
      return
    }

    const extension = selectedFile.name.split('.').pop()?.toLowerCase()
    if (extension !== 'pdf' && extension !== 'docx') {
      setUploadError('Only PDF and DOCX documents are supported.')
      return
    }
    if (selectedFile.size <= 0 || selectedFile.size > 15 * 1024 * 1024) {
      setUploadError('Choose a document smaller than 15 MB.')
      return
    }

    uploadRequestLock.current = true
    setUploading(true)
    try {
      const form = new FormData()
      form.append('file', selectedFile)
      if (documentTitle.trim()) form.append('title', documentTitle.trim())

      const created = await apiRequest<SourceDocumentRecord>(
        `/api/v1/workspaces/${workspaceId}/source-documents`,
        { method: 'POST', body: form },
      )
      setDocuments((current) => [created, ...current.filter((item) => item.id !== created.id)])
      setExpandedDocumentId(created.id)
      setSelectedFile(null)
      setFileInputKey((current) => current + 1)
      setDocumentTitle('')
      setSuccessMessage(`Uploaded and extracted ${created.original_filename}. Inspect its passages below.`)
      await loadSegments(created.id)
    } catch (error) {
      setUploadError(getErrorMessage(error))
    } finally {
      uploadRequestLock.current = false
      setUploading(false)
    }
  }

  async function loadSegments(documentId: string, append = false) {
    if (segmentRequestLock.current.has(documentId)) return
    segmentRequestLock.current.add(documentId)
    setLoadingSegments(documentId)
    setSegmentErrors((current) => ({ ...current, [documentId]: '' }))

    const existing = segments[documentId] ?? []
    const offset = append ? existing.length : 0

    try {
      const result = await apiRequest<SourceDocumentSegmentRecord[]>(
        `/api/v1/workspaces/${workspaceId}/source-documents/${documentId}/segments?limit=100&offset=${offset}`,
      )
      setSegments((current) => {
        const currentItems = append ? (current[documentId] ?? []) : []
        const knownIds = new Set(currentItems.map((item) => item.id))
        const incoming = result.filter((item) => !knownIds.has(item.id))
        return { ...current, [documentId]: [...currentItems, ...incoming] }
      })
      setHasMoreSegments((current) => ({ ...current, [documentId]: result.length === 100 }))
      setSegmentErrors((current) => ({ ...current, [documentId]: '' }))
    } catch (error) {
      setSegmentErrors((current) => ({ ...current, [documentId]: getErrorMessage(error) }))
    } finally {
      segmentRequestLock.current.delete(documentId)
      setLoadingSegments((current) => current === documentId ? null : current)
    }
  }

  async function toggleDocument(documentId: string) {
    if (expandedDocumentId === documentId) {
      setExpandedDocumentId(null)
      return
    }
    setExpandedDocumentId(documentId)
    if (!segments[documentId] && !segmentErrors[documentId]) await loadSegments(documentId)
  }

  async function downloadDocument(documentRecord: SourceDocumentRecord) {
    if (downloadRequestLock.current.size > 0 || downloadRequestLock.current.has(documentRecord.id)) return
    downloadRequestLock.current.add(documentRecord.id)
    setDownloadingId(documentRecord.id)
    setDownloadErrors((current) => ({ ...current, [documentRecord.id]: '' }))
    try {
      const blob = await apiRequestFile(
        `/api/v1/workspaces/${workspaceId}/source-documents/${documentRecord.id}/file`,
      )
      triggerBlobDownload(blob, documentRecord.original_filename)
    } catch (error) {
      setDownloadErrors((current) => ({ ...current, [documentRecord.id]: getErrorMessage(error) }))
    } finally {
      downloadRequestLock.current.delete(documentRecord.id)
      setDownloadingId(null)
    }
  }

  function selectSegment(document: SourceDocumentRecord, segment: SourceDocumentSegmentRecord) {
    const exactExcerpt = segment.text_content.slice(0, 10000)
    onSelectEvidence({
      source_document_id: document.id,
      source_document_segment_id: segment.id,
      source_excerpt: exactExcerpt,
      evidence_source_title: document.title,
      evidence_reference: segment.location_label,
      evidence_source_version: `SHA-256 ${document.sha256_hash.slice(0, 16)}`,
    })
    setSuccessMessage(`Selected ${segment.location_label} from ${document.title}. The excerpt remains editable, but must stay an exact passage from this source.`)
  }

  return (
    <section className="cpet-picker" aria-labelledby="cpet-picker-title">
      <div className="cpet-section-heading">
        <div className="cpet-section-icon"><BookOpenText size={18} /></div>
        <div>
          <p className="cpet-eyebrow">DOCUMENT EVIDENCE</p>
          <h3 id="cpet-picker-title">Upload or choose a supporting document</h3>
          <p>Upload a text-readable PDF or DOCX, inspect extracted passages, then attach the exact evidence to this Passport version.</p>
        </div>
      </div>

      <div className="cpet-upload-form">
        <div className="cpet-upload-fields">
          <label className="cpet-file-field">
            <span>Supporting document</span>
            <input
              key={fileInputKey}
              type="file"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(event) => handleFileChange(event.target.files?.[0] ?? null)}
            />
            <small>{selectedFile ? `${selectedFile.name} · ${formatBytes(selectedFile.size)}` : 'PDF or DOCX · maximum 15 MB'}</small>
          </label>
          <label className="cpet-title-field">
            <span>Document title <em>Optional</em></span>
            <input
              value={documentTitle}
              onChange={(event) => setDocumentTitle(event.target.value)}
              placeholder="e.g. Official product specifications"
              maxLength={300}
            />
          </label>
        </div>
        <div className="cpet-upload-actions">
          <p>Scanned/image-only PDFs are not supported by text extraction. The original file is stored privately.</p>
          <button className="cp-button cp-button-primary" type="button" onClick={() => void uploadDocument()} disabled={uploading || !selectedFile}>
            {uploading ? <LoaderCircle className="cpet-spinner" size={15} /> : <Upload size={15} />}
            {uploading ? 'Uploading…' : 'Upload document'}
          </button>
        </div>
        {uploadError && <div className="cpet-inline-error" role="alert"><AlertCircle size={15} />{uploadError}</div>}
      </div>

      {successMessage && <div className="cpet-inline-success" role="status"><CheckCircle2 size={15} />{successMessage}</div>}
      {documentListError && <div className="cpet-inline-error" role="alert"><AlertCircle size={15} />{documentListError}<button type="button" onClick={() => void loadDocuments()} disabled={refreshingDocuments}><RefreshCw size={13} /> Retry document list</button></div>}

      <div className="cpet-documents-heading">
        <strong>Workspace source documents</strong>
        <button type="button" className="cpet-text-button" onClick={() => void loadDocuments()} disabled={loadingDocuments || refreshingDocuments}>
          {refreshingDocuments ? <LoaderCircle className="cpet-spinner" size={13} /> : <RefreshCw size={13} />} {refreshingDocuments ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {loadingDocuments ? (
        <div className="cpet-inline-state"><LoaderCircle className="cpet-spinner" size={16} /> Loading documents…</div>
      ) : documents.length === 0 ? (
        <div className="cpet-empty-documents">
          <FileText size={21} />
          <strong>No supporting documents uploaded yet</strong>
          <span>Upload the first approved source document above.</span>
        </div>
      ) : (
        <div className="cpet-document-list">
          {documents.map((documentRecord) => {
            const expanded = expandedDocumentId === documentRecord.id
            const selectedDocument = selectedSourceDocumentId === documentRecord.id
            return (
              <article className={`cpet-document-card ${selectedDocument ? 'is-selected' : ''}`} key={documentRecord.id}>
                <div className="cpet-document-row">
                  <div className="cpet-document-icon"><FileText size={18} /></div>
                  <div className="cpet-document-copy">
                    <strong>{documentRecord.title}</strong>
                    <span>{documentRecord.original_filename} · {documentRecord.document_format} · {formatBytes(documentRecord.file_size_bytes)}</span>
                    <small>{documentRecord.segment_count} extracted passages · Uploaded {formatDate(documentRecord.created_at)}</small>
                  </div>
                  <div className="cpet-document-actions">
                    <button type="button" className="cpet-icon-button" title="Download original document" aria-label={`Download ${documentRecord.original_filename}`} onClick={() => void downloadDocument(documentRecord)} disabled={downloadingId !== null}>
                      <ArrowDownToLine size={15} />
                    </button>
                    <button type="button" className="cpet-text-button" onClick={() => void toggleDocument(documentRecord.id)}>
                      {expanded ? 'Hide passages' : 'Inspect passages'}
                      <ChevronDown size={14} className={expanded ? 'is-expanded' : ''} />
                    </button>
                  </div>
                </div>
                {documentRecord.extraction_warnings.length > 0 && (
                  <div className="cpet-document-warning"><AlertCircle size={14} />{documentRecord.extraction_warnings.join(' ')}</div>
                )}
                {downloadErrors[documentRecord.id] && (
                  <div className="cpet-inline-error" role="alert">
                    <AlertCircle size={14} />
                    <span>{downloadErrors[documentRecord.id]}</span>
                    <button type="button" onClick={() => void downloadDocument(documentRecord)} disabled={downloadingId !== null}>
                      <RefreshCw size={13} /> Retry download
                    </button>
                  </div>
                )}
                {expanded && (
                  <div className="cpet-segments">
                    {loadingSegments === documentRecord.id && !(segments[documentRecord.id] ?? []).length ? (
                      <div className="cpet-inline-state"><LoaderCircle className="cpet-spinner" size={15} /> Loading extracted passages…</div>
                    ) : null}
                    {segmentErrors[documentRecord.id] && (
                      <div className="cpet-inline-error" role="alert">
                        <AlertCircle size={14} />
                        <span>{segmentErrors[documentRecord.id]}</span>
                        <button type="button" onClick={() => void loadSegments(documentRecord.id, (segments[documentRecord.id] ?? []).length > 0)} disabled={loadingSegments === documentRecord.id}>
                          <RefreshCw size={13} /> Retry passages
                        </button>
                      </div>
                    )}
                    {(segments[documentRecord.id] ?? []).map((segment) => {
                      const selected = selectedSegmentId === segment.id
                      return (
                        <article className={`cpet-segment-card ${selected ? 'is-selected' : ''}`} key={segment.id}>
                          <div className="cpet-segment-heading">
                            <span>{segment.location_label}</span>
                            {selected && <span className="cpet-selected-label"><CheckCircle2 size={12} /> Selected</span>}
                          </div>
                          <p>{segment.text_content}</p>
                          <div className="cpet-segment-footer">
                            <small>Passage {segment.segment_index} · {segment.text_content.length > 10000 ? 'First 10,000 characters can be attached; refine the excerpt if needed.' : `${segment.text_content.length.toLocaleString('en-IN')} characters`}</small>
                            <button type="button" className="cp-button cp-button-secondary" onClick={() => selectSegment(documentRecord, segment)}>
                              <Check size={14} /> Use this passage
                            </button>
                          </div>
                        </article>
                      )
                    })}
                    {!segmentErrors[documentRecord.id] && !loadingSegments && (segments[documentRecord.id] ?? []).length === 0 && (
                      <p className="cpet-no-segments">No extracted passages were returned for this document. Check its extraction warnings or upload a text-readable source.</p>
                    )}
                    {hasMoreSegments[documentRecord.id] && (
                      <div className="cpet-load-more-wrap">
                        <button type="button" className="cpet-text-button" onClick={() => void loadSegments(documentRecord.id, true)} disabled={loadingSegments === documentRecord.id}>
                          {loadingSegments === documentRecord.id ? <LoaderCircle className="cpet-spinner" size={13} /> : <ChevronDown size={13} />}
                          {loadingSegments === documentRecord.id ? 'Loading more passages…' : `Load more passages (${(segments[documentRecord.id] ?? []).length} loaded)`}
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </article>
            )
          })}
        </div>
      )}
      <div className="cpet-verification-note">
        <ShieldCheck size={15} />
        <span>Extracted text is a source-review aid, not approval. The Brand Owner must confirm that the selected passage supports the claim before activating this Passport version.</span>
      </div>
      {selectedSourceDocumentId && (
        <button type="button" className="cpet-clear-source" onClick={() => onSelectEvidence(null)}>
          Remove uploaded document link and use manual source details
        </button>
      )}
    </section>
  )
}
