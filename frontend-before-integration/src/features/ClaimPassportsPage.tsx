import { useEffect, useState, type FormEvent } from 'react'
import {
  AlertCircle,
  BadgeCheck,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ClipboardCheck,
  Clock3,
  ExternalLink,
  FileText,
  History,
  LoaderCircle,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  X,
  type LucideIcon,
} from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { ApiError, apiRequest } from '../lib/api'
import type { WorkspaceRole } from '../lib/workspaces'
import './ClaimPassports.css'

type ClaimKind = 'factual' | 'promotional'
type PassportState = 'draft' | 'active' | 'review_due' | 'retired'
type VersionState = 'draft' | 'active' | 'superseded' | 'withdrawn'

type ClaimPassportRecord = {
  id: string
  workspace_id: string
  passport_code: string
  subject: string
  claim_type: ClaimKind
  summary: string | null
  status: PassportState
  current_version_id: string | null
  created_by: string
  created_at: string
  updated_at: string
}

type PassportVersionRecord = {
  id: string
  workspace_id: string
  claim_passport_id: string
  version_number: number
  approved_wording: string
  subject: string
  attribute: string
  permitted_value: string | null
  numeric_value: string | null
  unit: string | null
  qualifier: string | null
  required_conditions: string | null
  product_scope: string | null
  channel_scope: string | null
  market_scope: string | null
  valid_from: string | null
  valid_until: string | null
  evidence_source_title: string | null
  evidence_source_url: string | null
  evidence_reference: string | null
  evidence_excerpt: string | null
  evidence_source_version: string | null
  owner_id: string
  verified_by: string | null
  verified_at: string | null
  review_by: string | null
  status: VersionState
  created_by: string
  created_at: string
  updated_at: string
}

type PassportDraft = {
  passport_code: string
  subject: string
  claim_type: ClaimKind
  summary: string
}

type VersionDraft = {
  approved_wording: string
  subject: string
  attribute: string
  permitted_value: string
  numeric_value: string
  unit: string
  qualifier: string
  required_conditions: string
  product_scope: string
  channel_scope: string
  market_scope: string
  valid_from: string
  valid_until: string
  evidence_source_title: string
  evidence_source_url: string
  evidence_reference: string
  evidence_excerpt: string
  evidence_source_version: string
  review_by: string
}

type Props = {
  workspaceId: string
  role: WorkspaceRole
}

const initialPassportDraft = (): PassportDraft => ({
  passport_code: '',
  subject: '',
  claim_type: 'factual',
  summary: '',
})

const initialVersionDraft = (): VersionDraft => ({
  approved_wording: '',
  subject: '',
  attribute: '',
  permitted_value: '',
  numeric_value: '',
  unit: '',
  qualifier: '',
  required_conditions: '',
  product_scope: '',
  channel_scope: '',
  market_scope: '',
  valid_from: '',
  valid_until: '',
  evidence_source_title: '',
  evidence_source_url: '',
  evidence_reference: '',
  evidence_excerpt: '',
  evidence_source_version: '',
  review_by: '',
})

const passportLabels: Record<PassportState, string> = {
  draft: 'Draft',
  active: 'Active',
  review_due: 'Review due',
  retired: 'Retired',
}

const versionLabels: Record<VersionState, string> = {
  draft: 'Draft',
  active: 'Active',
  superseded: 'Superseded',
  withdrawn: 'Withdrawn',
}

const passportBase = (workspaceId: string) =>
  `/api/v1/workspaces/${workspaceId}/claim-passports`

const versionPath = (workspaceId: string, passportId: string) =>
  `${passportBase(workspaceId)}/${passportId}/versions`

function errorMessage(error: unknown) {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Something went wrong. Please try again.'
}

function formatDate(value: string | null) {
  if (!value) return 'Not specified'

  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`)

  if (Number.isNaN(parsed.getTime())) return value

  return new Intl.DateTimeFormat('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(parsed)
}

function formatDateTime(value: string | null) {
  if (!value) return 'Not verified'

  const parsed = new Date(value)

  if (Number.isNaN(parsed.getTime())) return value

  return new Intl.DateTimeFormat('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(parsed)
}

function PassportStatus({ status }: { status: PassportState }) {
  return (
    <span className={`cp-status cp-status--${status}`}>
      <span />
      {passportLabels[status]}
    </span>
  )
}

function VersionStatus({ status }: { status: VersionState }) {
  return (
    <span className={`cp-status cp-status--${status}`}>
      <span />
      {versionLabels[status]}
    </span>
  )
}

function StatCard({
  icon: Icon,
  label,
  value,
  tone = 'purple',
}: {
  icon: LucideIcon
  label: string
  value: number
  tone?: 'purple' | 'green' | 'amber'
}) {
  return (
    <div className="cp-stat-card">
      <div className={`cp-stat-icon cp-stat-icon--${tone}`}>
        <Icon size={19} />
      </div>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
      </div>
    </div>
  )
}

export default function ClaimPassportsPage({
  workspaceId,
  role,
}: Props) {
  const canEdit = role === 'brand_owner'

  const [passports, setPassports] = useState<ClaimPassportRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [pageError, setPageError] = useState('')
  const [actionError, setActionError] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [versions, setVersions] = useState<PassportVersionRecord[]>([])
  const [versionsLoading, setVersionsLoading] = useState(false)

  const [passportModalOpen, setPassportModalOpen] = useState(false)
  const [versionModalOpen, setVersionModalOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [modalError, setModalError] = useState('')

  const [passportDraft, setPassportDraft] =
    useState<PassportDraft>(initialPassportDraft)
  const [versionDraft, setVersionDraft] =
    useState<VersionDraft>(initialVersionDraft)

  useEffect(() => {
    let active = true

    apiRequest<ClaimPassportRecord[]>(passportBase(workspaceId))
      .then((items) => {
        if (!active) return

        setPassports(items)
        setPageError('')

        if (selectedId && !items.some((item) => item.id === selectedId)) {
          setSelectedId(null)
          setVersions([])
        }
      })
      .catch((error: unknown) => {
        if (active) setPageError(errorMessage(error))
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [workspaceId, refreshKey, selectedId])

  async function openPassport(passport: ClaimPassportRecord) {
    setSelectedId(passport.id)
    setVersions([])
    setVersionsLoading(true)
    setActionError('')

    try {
      const result = await apiRequest<PassportVersionRecord[]>(
        versionPath(workspaceId, passport.id),
      )
      setVersions(result)
    } catch (error) {
      setActionError(errorMessage(error))
    } finally {
      setVersionsLoading(false)
    }
  }

  function openCreatePassport() {
    setPassportDraft(initialPassportDraft())
    setModalError('')
    setPassportModalOpen(true)
  }

  function openCreateVersion() {
    if (!selectedPassport) return

    setVersionDraft({
      ...initialVersionDraft(),
      subject: selectedPassport.subject,
    })
    setModalError('')
    setVersionModalOpen(true)
  }

  async function createPassport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setModalError('')

    const code = passportDraft.passport_code.trim().toUpperCase()

    if (!/^[A-Z0-9][A-Z0-9._-]{0,63}$/.test(code)) {
      setModalError(
        'Use uppercase letters, numbers, dots, underscores or hyphens for the Passport code.',
      )
      return
    }

    setSaving(true)

    try {
      const created = await apiRequest<ClaimPassportRecord>(
        passportBase(workspaceId),
        {
          method: 'POST',
          body: JSON.stringify({
            passport_code: code,
            subject: passportDraft.subject.trim(),
            claim_type: passportDraft.claim_type,
            summary: passportDraft.summary.trim() || null,
          }),
        },
      )

      setPassportModalOpen(false)
      setRefreshKey((value) => value + 1)
      await openPassport(created)
    } catch (error) {
      setModalError(errorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  async function createVersion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!selectedPassport) return

    setModalError('')

    if (
      versionDraft.valid_from &&
      versionDraft.valid_until &&
      versionDraft.valid_until < versionDraft.valid_from
    ) {
      setModalError('The valid-until date cannot be earlier than the valid-from date.')
      return
    }

    if (
      versionDraft.review_by &&
      versionDraft.valid_until &&
      versionDraft.review_by > versionDraft.valid_until
    ) {
      setModalError('The review-by date should be on or before the valid-until date.')
      return
    }

    if (
      versionDraft.evidence_source_url &&
      !/^https?:\/\/.+/i.test(versionDraft.evidence_source_url.trim())
    ) {
      setModalError('Enter a valid HTTP or HTTPS evidence URL.')
      return
    }

    setSaving(true)

    const optional = (value: string) => value.trim() || null

    const payload = {
      approved_wording: versionDraft.approved_wording.trim(),
      subject: versionDraft.subject.trim(),
      attribute: versionDraft.attribute.trim(),
      permitted_value: optional(versionDraft.permitted_value),
      numeric_value: optional(versionDraft.numeric_value),
      unit: optional(versionDraft.unit),
      qualifier: optional(versionDraft.qualifier),
      required_conditions: optional(versionDraft.required_conditions),
      product_scope: optional(versionDraft.product_scope),
      channel_scope: optional(versionDraft.channel_scope),
      market_scope: optional(versionDraft.market_scope),
      valid_from: optional(versionDraft.valid_from),
      valid_until: optional(versionDraft.valid_until),
      evidence_source_title: optional(versionDraft.evidence_source_title),
      evidence_source_url: optional(versionDraft.evidence_source_url),
      evidence_reference: optional(versionDraft.evidence_reference),
      evidence_excerpt: optional(versionDraft.evidence_excerpt),
      evidence_source_version: optional(versionDraft.evidence_source_version),
      review_by: optional(versionDraft.review_by),
    }

    try {
      await apiRequest<PassportVersionRecord>(
        versionPath(workspaceId, selectedPassport.id),
        {
          method: 'POST',
          body: JSON.stringify(payload),
        },
      )

      setVersionModalOpen(false)
      await openPassport(selectedPassport)
      setRefreshKey((value) => value + 1)
    } catch (error) {
      setModalError(errorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  async function activateVersion(version: PassportVersionRecord) {
    if (!selectedPassport) return

    const confirmed = window.confirm(
      `Activate version ${version.version_number}?\n\nThe backend will verify its evidence and requirements before activation.`,
    )

    if (!confirmed) return

    setActionError('')

    try {
      await apiRequest<ClaimPassportRecord>(
        `${versionPath(workspaceId, selectedPassport.id)}/${version.id}/activate`,
        { method: 'POST' },
      )

      setRefreshKey((value) => value + 1)
      await openPassport(selectedPassport)
    } catch (error) {
      setActionError(
        `This version could not be activated: ${errorMessage(error)}`,
      )
    }
  }

  const query = search.trim().toLowerCase()

  const visiblePassports = passports.filter((passport) => {
    const searchable = [
      passport.passport_code,
      passport.subject,
      passport.summary ?? '',
      passport.claim_type,
    ]
      .join(' ')
      .toLowerCase()

    return (
      (!query || searchable.includes(query)) &&
      (filter === 'all' || passport.status === filter)
    )
  })

  const selectedPassport =
    passports.find((passport) => passport.id === selectedId) ?? null

  const activeCount = passports.filter((item) => item.status === 'active').length
  const draftCount = passports.filter((item) => item.status === 'draft').length
  const reviewDueCount = passports.filter(
    (item) => item.status === 'review_due',
  ).length

  return (
    <div className="cp-page">
      <div className="cp-heading-row">
        <div className="cp-title-block">
          <div className="cp-heading-icon">
            <BadgeCheck size={23} />
          </div>
          <p className="cp-eyebrow">VERIFIED BRAND EVIDENCE</p>
          <h1>Claim Passports</h1>
          <p className="cp-description">
            Store approved product claims with the evidence behind them.
            Every version keeps its own wording, scope and source.
          </p>
        </div>

        {canEdit && (
          <button
            className="cp-button cp-button-primary"
            type="button"
            onClick={openCreatePassport}
          >
            <Plus size={17} />
            Create a Passport
          </button>
        )}
      </div>

      {!canEdit && (
        <div className="cp-readonly-note">
          <ShieldCheck size={16} />
          You have read-only access to Claim Passports in this workspace.
        </div>
      )}

      {pageError && (
        <div className="cp-error-banner" role="alert">
          <AlertCircle size={17} />
          <span>{pageError}</span>
          <button
            type="button"
            onClick={() => setRefreshKey((value) => value + 1)}
          >
            Retry
          </button>
        </div>
      )}

      <section className="cp-stats-grid">
        <StatCard icon={FileText} label="Total Passports" value={passports.length} />
        <StatCard icon={CheckCircle2} label="Active Passports" value={activeCount} tone="green" />
        <StatCard icon={Clock3} label="Draft / Review due" value={draftCount + reviewDueCount} tone="amber" />
      </section>

      <section className="cp-library-panel">
        <div className="cp-library-heading">
          <div>
            <p className="cp-eyebrow">YOUR EVIDENCE LIBRARY</p>
            <h2>All Claim Passports</h2>
          </div>
          <span className="cp-total-pill">{passports.length} total</span>
        </div>

        <div className="cp-toolbar">
          <div className="cp-search">
            <Search size={17} />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search by Passport code, product or claim..."
              aria-label="Search Claim Passports"
            />
            {search && (
              <button
                type="button"
                aria-label="Clear search"
                onClick={() => setSearch('')}
              >
                <X size={15} />
              </button>
            )}
          </div>

          <div className="cp-filter">
            <ChevronDown size={15} />
            <select
              aria-label="Filter Claim Passports"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            >
              <option value="all">All statuses</option>
              <option value="active">Active</option>
              <option value="draft">Draft</option>
              <option value="review_due">Review due</option>
              <option value="retired">Retired</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div className="cp-loading">
            <LoaderCircle className="cp-spinner" size={23} />
            <span>Loading your Claim Passports...</span>
          </div>
        ) : visiblePassports.length === 0 ? (
          <div className="cp-empty-state">
            <div className="cp-empty-icon">
              <BadgeCheck size={28} />
            </div>
            <h3>
              {query || filter !== 'all'
                ? 'No matching Passports'
                : 'Your evidence library starts here'}
            </h3>
            <p>
              {query || filter !== 'all'
                ? 'Try a different search or select another status.'
                : 'Create a Passport for an important product claim and connect it to reliable supporting evidence.'}
            </p>
            {!query && filter === 'all' && canEdit && (
              <button
                className="cp-button cp-button-primary"
                type="button"
                onClick={openCreatePassport}
              >
                <Plus size={16} /> Create your first Passport
              </button>
            )}
          </div>
        ) : (
          <div className="cp-passport-grid">
            {visiblePassports.map((passport) => {
              const isSelected = passport.id === selectedId

              return (
                <motion.article
                  key={passport.id}
                  className={`cp-passport-card ${isSelected ? 'cp-passport-card--selected' : ''}`}
                  layout
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  whileHover={{ y: -3 }}
                >
                  <div className="cp-card-top">
                    <span className="cp-code">{passport.passport_code}</span>
                    <PassportStatus status={passport.status} />
                  </div>

                  <div className="cp-claim-type">
                    <ShieldCheck size={14} />
                    {passport.claim_type === 'factual'
                      ? 'Factual claim'
                      : 'Promotional claim'}
                  </div>

                  <h3>{passport.subject}</h3>
                  <p className="cp-card-summary">
                    {passport.summary || 'No summary added for this Passport.'}
                  </p>

                  <div className="cp-card-footer">
                    <span>
                      <Clock3 size={13} />
                      Updated {formatDate(passport.updated_at)}
                    </span>
                    <button
                      type="button"
                      className="cp-details-button"
                      onClick={() =>
                        isSelected
                          ? setSelectedId(null)
                          : void openPassport(passport)
                      }
                    >
                      {isSelected ? 'Close' : 'View versions'}
                      <ChevronRight
                        size={15}
                        className={isSelected ? 'cp-chevron-open' : ''}
                      />
                    </button>
                  </div>
                </motion.article>
              )
            })}
          </div>
        )}

        {!loading && (
          <div className="cp-list-footer">
            Showing {visiblePassports.length} of {passports.length} Passports
            <span>
              <ShieldCheck size={14} />
              Evidence-backed claim records
            </span>
          </div>
        )}
      </section>

      <AnimatePresence>
        {selectedPassport && (
          <motion.section
            className="cp-detail-panel"
            key={selectedPassport.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 6 }}
          >
            <div className="cp-detail-heading">
              <div>
                <p className="cp-eyebrow">PASSPORT DETAILS</p>
                <h2>{selectedPassport.passport_code}</h2>
                <p>{selectedPassport.subject}</p>
              </div>
              <div className="cp-detail-heading-actions">
                <PassportStatus status={selectedPassport.status} />
                {canEdit && (
                  <button
                    className="cp-button cp-button-primary"
                    type="button"
                    onClick={openCreateVersion}
                  >
                    <Plus size={16} /> New version
                  </button>
                )}
              </div>
            </div>

            <div className="cp-detail-summary">
              <div>
                <span>Claim type</span>
                <strong>
                  {selectedPassport.claim_type === 'factual'
                    ? 'Factual'
                    : 'Promotional'}
                </strong>
              </div>
              <div>
                <span>Passport status</span>
                <strong>{passportLabels[selectedPassport.status]}</strong>
              </div>
              <div>
                <span>Current version</span>
                <strong>
                  {selectedPassport.current_version_id
                    ? 'Version assigned'
                    : 'No active version'}
                </strong>
              </div>
            </div>

            {actionError && (
              <div className="cp-error-banner" role="alert">
                <AlertCircle size={17} />
                <span>{actionError}</span>
                <button type="button" onClick={() => setActionError('')}>
                  Dismiss
                </button>
              </div>
            )}

            <div className="cp-version-heading">
              <div>
                <p className="cp-eyebrow">VERSION HISTORY</p>
                <h3>Passport versions</h3>
              </div>
              <span className="cp-total-pill">{versions.length} versions</span>
            </div>

            {versionsLoading ? (
              <div className="cp-loading cp-loading-compact">
                <LoaderCircle className="cp-spinner" size={20} />
                <span>Loading version history...</span>
              </div>
            ) : versions.length === 0 ? (
              <div className="cp-no-version">
                <History size={21} />
                <div>
                  <strong>No versions created yet</strong>
                  <p>
                    Create the first version with approved wording and its
                    supporting source.
                  </p>
                </div>
                {canEdit && (
                  <button
                    className="cp-button cp-button-primary"
                    type="button"
                    onClick={openCreateVersion}
                  >
                    <Plus size={15} /> Add first version
                  </button>
                )}
              </div>
            ) : (
              <div className="cp-version-list">
                {versions.map((version) => (
                  <article className="cp-version-card" key={version.id}>
                    <div className="cp-version-top">
                      <div>
                        <span className="cp-version-number">
                          VERSION {version.version_number}
                        </span>
                        <VersionStatus status={version.status} />
                      </div>

                      {canEdit && version.status === 'draft' && (
                        <button
                          className="cp-button cp-button-primary cp-activate-button"
                          type="button"
                          onClick={() => void activateVersion(version)}
                        >
                          <ShieldCheck size={15} />
                          Verify & activate
                        </button>
                      )}
                    </div>

                    <h4>{version.approved_wording}</h4>

                    <div className="cp-version-attributes">
                      <div>
                        <span>Subject</span>
                        <strong>{version.subject}</strong>
                      </div>
                      <div>
                        <span>Attribute</span>
                        <strong>{version.attribute}</strong>
                      </div>
                      {version.permitted_value && (
                        <div>
                          <span>Permitted value</span>
                          <strong>{version.permitted_value}</strong>
                        </div>
                      )}
                      {version.numeric_value && (
                        <div>
                          <span>Numeric value</span>
                          <strong>
                            {version.numeric_value} {version.unit ?? ''}
                          </strong>
                        </div>
                      )}
                    </div>

                    {(version.product_scope ||
                      version.channel_scope ||
                      version.market_scope) && (
                      <div className="cp-scope-row">
                        {version.product_scope && (
                          <span>Product: {version.product_scope}</span>
                        )}
                        {version.channel_scope && (
                          <span>Channel: {version.channel_scope}</span>
                        )}
                        {version.market_scope && (
                          <span>Market: {version.market_scope}</span>
                        )}
                      </div>
                    )}

                    {(version.qualifier || version.required_conditions) && (
                      <div className="cp-condition-box">
                        {version.qualifier && (
                          <p>
                            <span>Qualifier:</span> {version.qualifier}
                          </p>
                        )}
                        {version.required_conditions && (
                          <p>
                            <span>Required conditions:</span>{' '}
                            {version.required_conditions}
                          </p>
                        )}
                      </div>
                    )}

                    <div className="cp-evidence-box">
                      <div className="cp-evidence-heading">
                        <FileText size={16} />
                        <strong>Supporting evidence</strong>
                      </div>

                      {version.evidence_source_title ? (
                        <p className="cp-evidence-title">
                          {version.evidence_source_title}
                        </p>
                      ) : (
                        <p className="cp-evidence-missing">
                          No evidence source title added.
                        </p>
                      )}

                      {version.evidence_source_url && (
                        <a
                          href={version.evidence_source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="cp-evidence-link"
                        >
                          Open source <ExternalLink size={13} />
                        </a>
                      )}

                      {version.evidence_reference && (
                        <p className="cp-evidence-reference">
                          Reference: {version.evidence_reference}
                        </p>
                      )}

                      {version.evidence_excerpt && (
                        <blockquote>
                          {version.evidence_excerpt}
                        </blockquote>
                      )}

                      {version.evidence_source_version && (
                        <p className="cp-evidence-reference">
                          Source version: {version.evidence_source_version}
                        </p>
                      )}
                    </div>

                    <div className="cp-version-dates">
                      <span>
                        <CalendarDays size={13} />
                        Valid from: {formatDate(version.valid_from)}
                      </span>
                      <span>
                        <CalendarDays size={13} />
                        Valid until: {formatDate(version.valid_until)}
                      </span>
                      <span>
                        <Clock3 size={13} />
                        Review by: {formatDate(version.review_by)}
                      </span>
                    </div>

                    {version.status === 'active' && (
                      <div className="cp-verified-note">
                        <CheckCircle2 size={15} />
                        Verified {formatDateTime(version.verified_at)}
                      </div>
                    )}
                  </article>
                ))}
              </div>
            )}
          </motion.section>
        )}
      </AnimatePresence>

      <section className="cp-tip">
        <div className="cp-tip-icon">
          <Sparkles size={19} />
        </div>
        <div>
          <strong>What makes a Claim Passport trustworthy?</strong>
          <p>
            Each version records exactly what can be claimed, for which
            product and context, and the source that supports it. Proofline
            checks the version before activation. Only an authorised human
            should decide which evidence is acceptable.
          </p>
        </div>
      </section>

      <AnimatePresence>
        {passportModalOpen && (
          <motion.div
            className="cp-modal-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) {
                setPassportModalOpen(false)
              }
            }}
          >
            <motion.section
              className="cp-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="cp-passport-modal-title"
              initial={{ opacity: 0, y: 14, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.98 }}
            >
              <div className="cp-modal-heading">
                <div>
                  <p className="cp-eyebrow">VERIFIED BRAND EVIDENCE</p>
                  <h2 id="cp-passport-modal-title">Create a Claim Passport</h2>
                  <p>
                    Start a record for a product or brand claim.
                    You'll add approved wording and evidence next.
                  </p>
                </div>
                <button
                  type="button"
                  className="cp-modal-close"
                  aria-label="Close"
                  onClick={() => setPassportModalOpen(false)}
                >
                  <X size={19} />
                </button>
              </div>

              <form className="cp-form" onSubmit={createPassport}>
                <label>
                  Passport code *
                  <input
                    value={passportDraft.passport_code}
                    onChange={(event) =>
                      setPassportDraft({
                        ...passportDraft,
                        passport_code: event.target.value.toUpperCase(),
                      })
                    }
                    placeholder="e.g. HYDRA-001"
                    maxLength={64}
                    required
                  />
                  <small>Unique identifier, such as HYDRA-001.</small>
                </label>

                <label>
                  Product or claim subject *
                  <input
                    value={passportDraft.subject}
                    onChange={(event) =>
                      setPassportDraft({
                        ...passportDraft,
                        subject: event.target.value,
                      })
                    }
                    placeholder="e.g. HydraLite Water Bottle"
                    maxLength={300}
                    required
                  />
                </label>

                <label>
                  Claim type *
                  <select
                    value={passportDraft.claim_type}
                    onChange={(event) =>
                      setPassportDraft({
                        ...passportDraft,
                        claim_type: event.target.value as ClaimKind,
                      })
                    }
                  >
                    <option value="factual">Factual claim</option>
                    <option value="promotional">Promotional claim</option>
                  </select>
                </label>

                <label>
                  Short summary
                  <textarea
                    rows={3}
                    value={passportDraft.summary}
                    onChange={(event) =>
                      setPassportDraft({
                        ...passportDraft,
                        summary: event.target.value,
                      })
                    }
                    placeholder="What does this Passport establish?"
                    maxLength={2000}
                  />
                </label>

                {modalError && (
                  <div className="cp-error-banner" role="alert">
                    <AlertCircle size={16} />
                    {modalError}
                  </div>
                )}

                <div className="cp-modal-actions">
                  <button
                    className="cp-button cp-button-secondary"
                    type="button"
                    onClick={() => setPassportModalOpen(false)}
                  >
                    Cancel
                  </button>
                  <button
                    className="cp-button cp-button-primary"
                    type="submit"
                    disabled={saving}
                  >
                    {saving ? (
                      <LoaderCircle className="cp-spinner" size={16} />
                    ) : (
                      <Check size={16} />
                    )}
                    {saving ? 'Creating...' : 'Create Passport'}
                  </button>
                </div>
              </form>
            </motion.section>
          </motion.div>
        )}

        {versionModalOpen && selectedPassport && (
          <motion.div
            className="cp-modal-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) {
                setVersionModalOpen(false)
              }
            }}
          >
            <motion.section
              className="cp-modal cp-modal-wide"
              role="dialog"
              aria-modal="true"
              aria-labelledby="cp-version-modal-title"
              initial={{ opacity: 0, y: 14, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.98 }}
            >
              <div className="cp-modal-heading">
                <div>
                  <p className="cp-eyebrow">
                    {selectedPassport.passport_code}
                  </p>
                  <h2 id="cp-version-modal-title">Add a Passport version</h2>
                  <p>
                    Define the approved wording and link the source that
                    supports this claim.
                  </p>
                </div>
                <button
                  type="button"
                  className="cp-modal-close"
                  aria-label="Close"
                  onClick={() => setVersionModalOpen(false)}
                >
                  <X size={19} />
                </button>
              </div>

              <form className="cp-form" onSubmit={createVersion}>
                <div className="cp-form-section-heading">
                  <span>01</span>
                  <div>
                    <strong>Approved claim</strong>
                    <small>Define exactly what the brand is allowed to say.</small>
                  </div>
                </div>

                <label>
                  Approved wording *
                  <textarea
                    rows={3}
                    value={versionDraft.approved_wording}
                    onChange={(event) =>
                      setVersionDraft({
                        ...versionDraft,
                        approved_wording: event.target.value,
                      })
                    }
                    placeholder="Write the exact claim that may be used in content..."
                    maxLength={3000}
                    required
                  />
                </label>

                <div className="cp-form-grid">
                  <label>
                    Subject *
                    <input
                      value={versionDraft.subject}
                      onChange={(event) =>
                        setVersionDraft({
                          ...versionDraft,
                          subject: event.target.value,
                        })
                      }
                      maxLength={300}
                      required
                    />
                  </label>
                  <label>
                    Attribute *
                    <input
                      value={versionDraft.attribute}
                      onChange={(event) =>
                        setVersionDraft({
                          ...versionDraft,
                          attribute: event.target.value,
                        })
                      }
                      placeholder="e.g. insulation duration"
                      maxLength={300}
                      required
                    />
                  </label>
                </div>

                <div className="cp-form-grid">
                  <label>
                    Permitted value
                    <input
                      value={versionDraft.permitted_value}
                      onChange={(event) =>
                        setVersionDraft({
                          ...versionDraft,
                          permitted_value: event.target.value,
                        })
                      }
                      placeholder="e.g. up to 24 hours"
                      maxLength={500}
                    />
                  </label>
                  <label>
                    Numeric value
                    <input
                      value={versionDraft.numeric_value}
                      onChange={(event) =>
                        setVersionDraft({
                          ...versionDraft,
                          numeric_value: event.target.value,
                        })
                      }
                      placeholder="e.g. 24"
                    />
                  </label>
                </div>

                <div className="cp-form-grid">
                  <label>
                    Unit
                    <input
                      value={versionDraft.unit}
                      onChange={(event) =>
                        setVersionDraft({
                          ...versionDraft,
                          unit: event.target.value,
                        })
                      }
                      placeholder="e.g. hours"
                      maxLength={80}
                    />
                  </label>
                  <label>
                    Qualifier
                    <input
                      value={versionDraft.qualifier}
                      onChange={(event) =>
                        setVersionDraft({
                          ...versionDraft,
                          qualifier: event.target.value,
                        })
                      }
                      placeholder="e.g. under controlled conditions"
                      maxLength={500}
                    />
                  </label>
                </div>

                <label>
                  Required conditions
                  <textarea
                    rows={2}
                    value={versionDraft.required_conditions}
                    onChange={(event) =>
                      setVersionDraft({
                        ...versionDraft,
                        required_conditions: event.target.value,
                      })
                    }
                    placeholder="Conditions that must accompany this claim..."
                    maxLength={3000}
                  />
                </label>

                <div className="cp-form-section-heading">
                  <span>02</span>
                  <div>
                    <strong>Where this claim applies</strong>
                    <small>Set the product, channel and market scope.</small>
                  </div>
                </div>

                <div className="cp-form-grid">
                  <label>
                    Product scope
                    <input
                      value={versionDraft.product_scope}
                      onChange={(event) =>
                        setVersionDraft({
                          ...versionDraft,
                          product_scope: event.target.value,
                        })
                      }
                      placeholder="e.g. HydraLite 750ml"
                      maxLength={300}
                    />
                  </label>
                  <label>
                    Channel scope
                    <input
                      value={versionDraft.channel_scope}
                      onChange={(event) =>
                        setVersionDraft({
                          ...versionDraft,
                          channel_scope: event.target.value,
                        })
                      }
                      placeholder="e.g. Website, Instagram"
                      maxLength={300}
                    />
                  </label>
                </div>

                <label>
                  Market scope
                  <input
                    value={versionDraft.market_scope}
                    onChange={(event) =>
                      setVersionDraft({
                        ...versionDraft,
                        market_scope: event.target.value,
                      })
                    }
                    placeholder="e.g. India"
                    maxLength={300}
                  />
                </label>

                <div className="cp-form-section-heading">
                  <span>03</span>
                  <div>
                    <strong>Supporting evidence</strong>
                    <small>
                      Connect the claim to the document or source that backs it.
                    </small>
                  </div>
                </div>

                <label>
                  Evidence source title
                  <input
                    value={versionDraft.evidence_source_title}
                    onChange={(event) =>
                      setVersionDraft({
                        ...versionDraft,
                        evidence_source_title: event.target.value,
                      })
                    }
                    placeholder="e.g. Independent insulation test report"
                    maxLength={500}
                  />
                </label>

                <label>
                  Evidence source URL
                  <input
                    type="url"
                    value={versionDraft.evidence_source_url}
                    onChange={(event) =>
                      setVersionDraft({
                        ...versionDraft,
                        evidence_source_url: event.target.value,
                      })
                    }
                    placeholder="https://example.com/evidence"
                  />
                </label>

                <label>
                  Supporting excerpt
                  <textarea
                    rows={3}
                    value={versionDraft.evidence_excerpt}
                    onChange={(event) =>
                      setVersionDraft({
                        ...versionDraft,
                        evidence_excerpt: event.target.value,
                      })
                    }
                    placeholder="Paste the exact passage that supports the claim..."
                    maxLength={10000}
                  />
                </label>

                <div className="cp-form-grid">
                  <label>
                    Evidence reference
                    <input
                      value={versionDraft.evidence_reference}
                      onChange={(event) =>
                        setVersionDraft({
                          ...versionDraft,
                          evidence_reference: event.target.value,
                        })
                      }
                      placeholder="e.g. Page 4, Table 2"
                      maxLength={1000}
                    />
                  </label>
                  <label>
                    Source version
                    <input
                      value={versionDraft.evidence_source_version}
                      onChange={(event) =>
                        setVersionDraft({
                          ...versionDraft,
                          evidence_source_version: event.target.value,
                        })
                      }
                      placeholder="e.g. Report v2"
                      maxLength={200}
                    />
                  </label>
                </div>

                <div className="cp-form-section-heading">
                  <span>04</span>
                  <div>
                    <strong>Validity and review dates</strong>
                    <small>Optional dates for managing evidence freshness.</small>
                  </div>
                </div>

                <div className="cp-form-grid cp-date-grid">
                  <label>
                    Valid from
                    <input
                      type="date"
                      value={versionDraft.valid_from}
                      onChange={(event) =>
                        setVersionDraft({
                          ...versionDraft,
                          valid_from: event.target.value,
                        })
                      }
                    />
                  </label>
                  <label>
                    Valid until
                    <input
                      type="date"
                      value={versionDraft.valid_until}
                      onChange={(event) =>
                        setVersionDraft({
                          ...versionDraft,
                          valid_until: event.target.value,
                        })
                      }
                    />
                  </label>
                  <label>
                    Review by
                    <input
                      type="date"
                      value={versionDraft.review_by}
                      onChange={(event) =>
                        setVersionDraft({
                          ...versionDraft,
                          review_by: event.target.value,
                        })
                      }
                    />
                  </label>
                </div>

                <div className="cp-evidence-reminder">
                  <ShieldCheck size={17} />
                  <p>
                    A saved version remains a draft. Proofline will verify
                    the required evidence and version details when you
                    choose to activate it.
                  </p>
                </div>

                {modalError && (
                  <div className="cp-error-banner" role="alert">
                    <AlertCircle size={16} />
                    {modalError}
                  </div>
                )}

                <div className="cp-modal-actions">
                  <button
                    className="cp-button cp-button-secondary"
                    type="button"
                    onClick={() => setVersionModalOpen(false)}
                  >
                    Cancel
                  </button>
                  <button
                    className="cp-button cp-button-primary"
                    type="submit"
                    disabled={saving}
                  >
                    {saving ? (
                      <LoaderCircle className="cp-spinner" size={16} />
                    ) : (
                      <Check size={16} />
                    )}
                    {saving ? 'Saving...' : 'Save draft version'}
                  </button>
                </div>
              </form>
            </motion.section>
          </motion.div>
        )}
      </AnimatePresence>

      <section className="cp-tip">
        <div className="cp-tip-icon">
          <ClipboardCheck size={19} />
        </div>
        <div>
          <strong>Evidence first. Approval second.</strong>
          <p>
            Every version preserves its approved wording, scope and evidence.
            Saving a draft does not activate it. The backend performs the
            verification before a version can become active.
          </p>
        </div>
      </section>
    </div>
  )
}
