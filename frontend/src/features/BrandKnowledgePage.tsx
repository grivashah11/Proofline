import { useEffect, useState, type FormEvent } from 'react'
import {
  AlertCircle,
  BookOpenCheck,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleDashed,
  FileText,
  LoaderCircle,
  MessageSquareText,
  Pencil,
  Plus,
  Power,
  Search,
  ShieldCheck,
  Trash2,
  X,
  type LucideIcon,
} from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { ApiError, apiRequest } from '../lib/api'
import type { WorkspaceRole } from '../lib/workspaces'
import './BrandKnowledge.css'

type BrandRuleKind =
  | 'brand_voice'
  | 'messaging'
  | 'channel_guidance'
  | 'other'

type BrandRuleState = 'active' | 'inactive'

type BrandRuleCheckType =
  | 'manual_review'
  | 'contains_phrase'
  | 'does_not_contain_phrase'
  | 'min_characters'
  | 'max_characters'

type TermEntryKind = 'preferred' | 'required' | 'restricted'

type BrandRuleRecord = {
  id: string
  workspace_id: string
  rule_kind: BrandRuleKind
  title: string
  description: string | null
  rule_text: string
  channel: string | null
  state: BrandRuleState
  check_type: BrandRuleCheckType
  check_value: string | null
  created_by: string
  created_at: string
  updated_at: string
}

type TermEntryRecord = {
  id: string
  workspace_id: string
  term_type: TermEntryKind
  term: string
  preferred_replacement: string | null
  explanation: string | null
  case_sensitive: boolean
  match_whole_word: boolean
  is_active: boolean
  created_by: string
  created_at: string
  updated_at: string
}

type RuleDraft = {
  rule_kind: BrandRuleKind
  title: string
  description: string
  rule_text: string
  channel: string
  check_type: BrandRuleCheckType
  check_value: string
}

type TermDraft = {
  term_type: TermEntryKind
  term: string
  preferred_replacement: string
  explanation: string
  case_sensitive: boolean
  match_whole_word: boolean
}

type Props = {
  section: 'brandRules' | 'terminology'
  workspaceId: string
  role: WorkspaceRole
}

const initialRuleDraft = (): RuleDraft => ({
  rule_kind: 'brand_voice',
  title: '',
  description: '',
  rule_text: '',
  channel: '',
  check_type: 'manual_review',
  check_value: '',
})

const initialTermDraft = (): TermDraft => ({
  term_type: 'preferred',
  term: '',
  preferred_replacement: '',
  explanation: '',
  case_sensitive: false,
  match_whole_word: true,
})

const ruleKindLabels: Record<BrandRuleKind, string> = {
  brand_voice: 'Brand voice',
  messaging: 'Messaging',
  channel_guidance: 'Channel guidance',
  other: 'Other',
}

const checkTypeLabels: Record<BrandRuleCheckType, string> = {
  manual_review: 'Manual review',
  contains_phrase: 'Must contain phrase',
  does_not_contain_phrase: 'Must not contain phrase',
  min_characters: 'Minimum characters',
  max_characters: 'Maximum characters',
}

const termKindLabels: Record<TermEntryKind, string> = {
  preferred: 'Preferred',
  required: 'Required',
  restricted: 'Restricted',
}

function getErrorMessage(error: unknown) {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Something went wrong. Please try again.'
}

function rulePath(workspaceId: string, ruleId?: string) {
  const base = `/api/v1/workspaces/${workspaceId}/brand-rules`
  return ruleId ? `${base}/${ruleId}` : base
}

function termPath(workspaceId: string, termId?: string) {
  const base = `/api/v1/workspaces/${workspaceId}/terminology`
  return termId ? `${base}/${termId}` : base
}

function SectionHeader({
  section,
  canEdit,
  onAdd,
}: {
  section: 'brandRules' | 'terminology'
  canEdit: boolean
  onAdd: () => void
}) {
  const isRules = section === 'brandRules'
  const Icon = isRules ? BookOpenCheck : MessageSquareText

  return (
    <div className="bk-heading-row">
      <div className="bk-title-block">
        <div className="bk-heading-icon">
          <Icon size={23} />
        </div>
        <p className="bk-eyebrow">
          {isRules ? 'BRAND KNOWLEDGE' : 'BRAND LANGUAGE'}
        </p>
        <h1>{isRules ? 'Brand rules' : 'Terminology'}</h1>
        <p className="bk-description">
          {isRules
            ? 'Set the standards your content should follow. Proofline checks these rules before publication.'
            : 'Keep your brand language consistent. Define preferred words, required terms and phrases to avoid.'}
        </p>
      </div>

      {canEdit && (
        <button
          className="bk-button bk-button-primary"
          type="button"
          onClick={onAdd}
        >
          <Plus size={17} />
          {isRules ? 'Add a rule' : 'Add a term'}
        </button>
      )}
    </div>
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
    <div className="bk-stat-card">
      <div className={`bk-stat-icon bk-stat-icon--${tone}`}>
        <Icon size={19} />
      </div>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
      </div>
    </div>
  )
}

function StatusBadge({
  active,
  label,
}: {
  active: boolean
  label?: string
}) {
  return (
    <span className={`bk-status ${active ? 'bk-status--active' : 'bk-status--inactive'}`}>
      <span />
      {label ?? (active ? 'Active' : 'Inactive')}
    </span>
  )
}

export default function BrandKnowledgePage({
  section,
  workspaceId,
  role,
}: Props) {
  const isRules = section === 'brandRules'
  const canEdit = role === 'brand_owner'

  const [rules, setRules] = useState<BrandRuleRecord[]>([])
  const [terms, setTerms] = useState<TermEntryRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [pageError, setPageError] = useState('')
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  const [refreshKey, setRefreshKey] = useState(0)

  const [modalOpen, setModalOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [modalError, setModalError] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [ruleDraft, setRuleDraft] = useState<RuleDraft>(initialRuleDraft)
  const [termDraft, setTermDraft] = useState<TermDraft>(initialTermDraft)

  useEffect(() => {
    let active = true

    async function load() {
      try {
        if (isRules) {
          const result = await apiRequest<BrandRuleRecord[]>(
            rulePath(workspaceId),
          )
          if (active) setRules(result)
        } else {
          const result = await apiRequest<TermEntryRecord[]>(
            termPath(workspaceId),
          )
          if (active) setTerms(result)
        }

        if (active) setPageError('')
      } catch (error) {
        if (active) setPageError(getErrorMessage(error))
      } finally {
        if (active) setLoading(false)
      }
    }

    void load()

    return () => {
      active = false
    }
  }, [workspaceId, isRules, refreshKey])

  const visibleRules = rules.filter((rule) => {
    const query = search.trim().toLowerCase()
    const searchable = [
      rule.title,
      rule.description ?? '',
      rule.rule_text,
      rule.channel ?? '',
      ruleKindLabels[rule.rule_kind],
    ]
      .join(' ')
      .toLowerCase()

    const matchesSearch = !query || searchable.includes(query)
    const matchesFilter =
      filter === 'all' || rule.state === filter

    return matchesSearch && matchesFilter
  })

  const visibleTerms = terms.filter((term) => {
    const query = search.trim().toLowerCase()
    const searchable = [
      term.term,
      term.preferred_replacement ?? '',
      term.explanation ?? '',
      termKindLabels[term.term_type],
    ]
      .join(' ')
      .toLowerCase()

    const matchesSearch = !query || searchable.includes(query)
    const matchesFilter =
      filter === 'all' ||
      (filter === 'active' && term.is_active) ||
      (filter === 'inactive' && !term.is_active) ||
      term.term_type === filter

    return matchesSearch && matchesFilter
  })

  function openCreate() {
    setEditingId(null)
    setRuleDraft(initialRuleDraft())
    setTermDraft(initialTermDraft())
    setModalError('')
    setModalOpen(true)
  }

  function openEditRule(rule: BrandRuleRecord) {
    setEditingId(rule.id)
    setRuleDraft({
      rule_kind: rule.rule_kind,
      title: rule.title,
      description: rule.description ?? '',
      rule_text: rule.rule_text,
      channel: rule.channel ?? '',
      check_type: rule.check_type,
      check_value: rule.check_value ?? '',
    })
    setModalError('')
    setModalOpen(true)
  }

  function openEditTerm(term: TermEntryRecord) {
    setEditingId(term.id)
    setTermDraft({
      term_type: term.term_type,
      term: term.term,
      preferred_replacement: term.preferred_replacement ?? '',
      explanation: term.explanation ?? '',
      case_sensitive: term.case_sensitive,
      match_whole_word: term.match_whole_word,
    })
    setModalError('')
    setModalOpen(true)
  }

  async function saveRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setModalError('')

    if (
      ruleDraft.check_type !== 'manual_review' &&
      !ruleDraft.check_value.trim()
    ) {
      setModalError('Enter the phrase or character limit for this automatic check.')
      return
    }

    if (
      ['min_characters', 'max_characters'].includes(ruleDraft.check_type) &&
      (!Number.isInteger(Number(ruleDraft.check_value)) ||
        Number(ruleDraft.check_value) < 1)
    ) {
      setModalError('Enter a whole number greater than zero for the character limit.')
      return
    }

    setSaving(true)

    const payload = {
      rule_kind: ruleDraft.rule_kind,
      title: ruleDraft.title.trim(),
      description: ruleDraft.description.trim() || null,
      rule_text: ruleDraft.rule_text.trim(),
      channel: ruleDraft.channel.trim() || null,
      check_type: ruleDraft.check_type,
      check_value: ruleDraft.check_value.trim() || null,
    }

    try {
      if (editingId) {
        await apiRequest<BrandRuleRecord>(
          rulePath(workspaceId, editingId),
          { method: 'PATCH', body: JSON.stringify(payload) },
        )
      } else {
        await apiRequest<BrandRuleRecord>(
          rulePath(workspaceId),
          { method: 'POST', body: JSON.stringify(payload) },
        )
      }

      setModalOpen(false)
      setRefreshKey((value) => value + 1)
    } catch (error) {
      setModalError(getErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  async function saveTerm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setModalError('')
    setSaving(true)

    const payload = {
      term_type: termDraft.term_type,
      term: termDraft.term.trim(),
      preferred_replacement:
        termDraft.preferred_replacement.trim() || null,
      explanation: termDraft.explanation.trim() || null,
      case_sensitive: termDraft.case_sensitive,
      match_whole_word: termDraft.match_whole_word,
    }

    try {
      if (editingId) {
        await apiRequest<TermEntryRecord>(
          termPath(workspaceId, editingId),
          { method: 'PATCH', body: JSON.stringify(payload) },
        )
      } else {
        await apiRequest<TermEntryRecord>(
          termPath(workspaceId),
          { method: 'POST', body: JSON.stringify(payload) },
        )
      }

      setModalOpen(false)
      setRefreshKey((value) => value + 1)
    } catch (error) {
      setModalError(getErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  async function deleteRule(rule: BrandRuleRecord) {
    if (!window.confirm(`Delete the rule "${rule.title}"?`)) return

    try {
      await apiRequest<void>(rulePath(workspaceId, rule.id), {
        method: 'DELETE',
      })
      setRefreshKey((value) => value + 1)
    } catch (error) {
      setPageError(getErrorMessage(error))
    }
  }

  async function deleteTerm(term: TermEntryRecord) {
    if (!window.confirm(`Delete the term "${term.term}"?`)) return

    try {
      await apiRequest<void>(termPath(workspaceId, term.id), {
        method: 'DELETE',
      })
      setRefreshKey((value) => value + 1)
    } catch (error) {
      setPageError(getErrorMessage(error))
    }
  }

  async function toggleRule(rule: BrandRuleRecord) {
    try {
      await apiRequest<BrandRuleRecord>(
        rulePath(workspaceId, rule.id),
        {
          method: 'PATCH',
          body: JSON.stringify({
            state: rule.state === 'active' ? 'inactive' : 'active',
          }),
        },
      )
      setRefreshKey((value) => value + 1)
    } catch (error) {
      setPageError(getErrorMessage(error))
    }
  }

  async function toggleTerm(term: TermEntryRecord) {
    try {
      await apiRequest<TermEntryRecord>(
        termPath(workspaceId, term.id),
        {
          method: 'PATCH',
          body: JSON.stringify({ is_active: !term.is_active }),
        },
      )
      setRefreshKey((value) => value + 1)
    } catch (error) {
      setPageError(getErrorMessage(error))
    }
  }

  const activeRules = rules.filter((rule) => rule.state === 'active').length
  const automaticRules = rules.filter(
    (rule) => rule.check_type !== 'manual_review',
  ).length

  const activeTerms = terms.filter((term) => term.is_active).length
  const requiredTerms = terms.filter(
    (term) => term.term_type === 'required',
  ).length

  return (
    <div className="bk-page">
      <SectionHeader
        section={section}
        canEdit={canEdit}
        onAdd={openCreate}
      />

      {!canEdit && (
        <div className="bk-readonly-note">
          <ShieldCheck size={16} />
          You have read-only access to this brand knowledge.
        </div>
      )}

      {pageError && (
        <div className="bk-error-banner" role="alert">
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

      <section className="bk-stats-grid">
        {isRules ? (
          <>
            <StatCard icon={BookOpenCheck} label="Total rules" value={rules.length} />
            <StatCard icon={CheckCircle2} label="Active rules" value={activeRules} tone="green" />
            <StatCard icon={CircleDashed} label="Automatic checks" value={automaticRules} tone="amber" />
          </>
        ) : (
          <>
            <StatCard icon={MessageSquareText} label="Total terms" value={terms.length} />
            <StatCard icon={CheckCircle2} label="Active terms" value={activeTerms} tone="green" />
            <StatCard icon={ShieldCheck} label="Required terms" value={requiredTerms} tone="amber" />
          </>
        )}
      </section>

      <section className="bk-list-panel">
        <div className="bk-list-heading">
          <div>
            <p className="bk-eyebrow">
              {isRules ? 'YOUR BRAND STANDARDS' : 'YOUR BRAND VOCABULARY'}
            </p>
            <h2>{isRules ? 'All brand rules' : 'All terminology'}</h2>
          </div>
          <span className="bk-count">
            {isRules ? rules.length : terms.length} total
          </span>
        </div>

        <div className="bk-toolbar">
          <div className="bk-search">
            <Search size={17} />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={isRules ? 'Search rules...' : 'Search terms...'}
              aria-label={isRules ? 'Search brand rules' : 'Search terminology'}
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

          <div className="bk-filter">
            <ChevronDown size={15} />
            <select
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
              aria-label="Filter items"
            >
              <option value="all">All items</option>
              {isRules ? (
                <>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </>
              ) : (
                <>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                  <option value="preferred">Preferred</option>
                  <option value="required">Required</option>
                  <option value="restricted">Restricted</option>
                </>
              )}
            </select>
          </div>
        </div>

        {loading ? (
          <div className="bk-loading">
            <LoaderCircle className="bk-spinner" size={22} />
            <span>Loading your {isRules ? 'brand rules' : 'terminology'}...</span>
          </div>
        ) : isRules ? (
          visibleRules.length === 0 ? (
            <EmptyState
              section="brandRules"
              hasSearch={Boolean(search) || filter !== 'all'}
              canEdit={canEdit}
              onAdd={openCreate}
            />
          ) : (
            <div className="bk-cards-grid">
              {visibleRules.map((rule) => (
                <motion.article
                  className="bk-item-card"
                  key={rule.id}
                  layout
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  whileHover={{ y: -2 }}
                >
                  <div className="bk-card-top">
                    <span className="bk-kind-pill">
                      {ruleKindLabels[rule.rule_kind]}
                    </span>
                    <StatusBadge active={rule.state === 'active'} />
                  </div>

                  <h3>{rule.title}</h3>
                  {rule.description && (
                    <p className="bk-card-description">{rule.description}</p>
                  )}

                  <div className="bk-rule-text">
                    <span>RULE</span>
                    <p>{rule.rule_text}</p>
                  </div>

                  <div className="bk-meta-row">
                    <span>
                      <CircleDashed size={14} />
                      {checkTypeLabels[rule.check_type]}
                    </span>
                    {rule.channel && (
                      <span>
                        <FileText size={14} />
                        {rule.channel}
                      </span>
                    )}
                  </div>

                  {rule.check_value && (
                    <div className="bk-check-value">
                      <span>CHECK VALUE</span>
                      <strong>{rule.check_value}</strong>
                    </div>
                  )}

                  {canEdit && (
                    <div className="bk-card-actions">
                      <button
                        type="button"
                        onClick={() => openEditRule(rule)}
                      >
                        <Pencil size={14} /> Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => void toggleRule(rule)}
                      >
                        <Power size={14} />
                        {rule.state === 'active' ? 'Deactivate' : 'Activate'}
                      </button>
                      <button
                        type="button"
                        className="bk-action-danger"
                        onClick={() => void deleteRule(rule)}
                        aria-label={`Delete ${rule.title}`}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  )}
                </motion.article>
              ))}
            </div>
          )
        ) : visibleTerms.length === 0 ? (
          <EmptyState
            section="terminology"
            hasSearch={Boolean(search) || filter !== 'all'}
            canEdit={canEdit}
            onAdd={openCreate}
          />
        ) : (
          <div className="bk-terms-list">
            {visibleTerms.map((term) => (
              <motion.article
                className="bk-term-row"
                key={term.id}
                layout
                initial={{ opacity: 0, y: 7 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <div className="bk-term-type-icon">
                  <MessageSquareText size={19} />
                </div>
                <div className="bk-term-main">
                  <div className="bk-term-title-row">
                    <h3>{term.term}</h3>
                    <span className={`bk-term-kind bk-term-kind--${term.term_type}`}>
                      {termKindLabels[term.term_type]}
                    </span>
                    <StatusBadge active={term.is_active} />
                  </div>

                  {term.preferred_replacement && (
                    <p className="bk-replacement">
                      <span>Use instead:</span> {term.preferred_replacement}
                    </p>
                  )}

                  {term.explanation && (
                    <p className="bk-card-description">{term.explanation}</p>
                  )}

                  <div className="bk-meta-row">
                    <span>
                      {term.case_sensitive ? 'Case-sensitive' : 'Case-insensitive'}
                    </span>
                    <span>
                      {term.match_whole_word ? 'Whole word' : 'Partial match'}
                    </span>
                  </div>
                </div>

                {canEdit && (
                  <div className="bk-term-actions">
                    <button
                      type="button"
                      aria-label={`Edit ${term.term}`}
                      onClick={() => openEditTerm(term)}
                    >
                      <Pencil size={15} />
                    </button>
                    <button
                      type="button"
                      aria-label={`${term.is_active ? 'Deactivate' : 'Activate'} ${term.term}`}
                      onClick={() => void toggleTerm(term)}
                    >
                      <Power size={15} />
                    </button>
                    <button
                      type="button"
                      className="bk-action-danger"
                      aria-label={`Delete ${term.term}`}
                      onClick={() => void deleteTerm(term)}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                )}
              </motion.article>
            ))}
          </div>
        )}

        {!loading && (
          <div className="bk-list-footer">
            <span>
              Showing {isRules ? visibleRules.length : visibleTerms.length} of{' '}
              {isRules ? rules.length : terms.length} items
            </span>
            {canEdit && (
              <span className="bk-footer-permission">
                <ShieldCheck size={14} />
                Brand Owner controls
              </span>
            )}
          </div>
        )}
      </section>

      <section className="bk-tip">
        <div className="bk-tip-icon">
          <ShieldCheck size={19} />
        </div>
        <div>
          <strong>
            {isRules
              ? 'A rule is a standard your content must follow.'
              : 'Terminology keeps your brand language consistent.'}
          </strong>
          <p>
            {isRules
              ? 'Use automatic checks for exact phrases and character limits. Use manual review for guidance that needs human judgement.'
              : 'Preferred terms suggest better wording, required terms must appear where applicable, and restricted terms flag language to avoid.'}
          </p>
        </div>
      </section>

      <AnimatePresence>
        {modalOpen && (
          <motion.div
            className="bk-modal-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) setModalOpen(false)
            }}
          >
            <motion.section
              className="bk-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="bk-modal-title"
              initial={{ opacity: 0, y: 14, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.98 }}
              transition={{ duration: 0.18 }}
            >
              <div className="bk-modal-heading">
                <div>
                  <p className="bk-eyebrow">
                    {isRules ? 'BRAND KNOWLEDGE' : 'BRAND LANGUAGE'}
                  </p>
                  <h2 id="bk-modal-title">
                    {editingId
                      ? isRules ? 'Edit brand rule' : 'Edit terminology'
                      : isRules ? 'Add a brand rule' : 'Add a term'}
                  </h2>
                  <p>
                    {isRules
                      ? 'Tell your team what to follow and how Proofline should check it.'
                      : 'Define how this word or phrase should be used in your brand content.'}
                  </p>
                </div>
                <button
                  className="bk-modal-close"
                  type="button"
                  aria-label="Close form"
                  onClick={() => setModalOpen(false)}
                >
                  <X size={19} />
                </button>
              </div>

              {isRules ? (
                <form className="bk-form" onSubmit={saveRule}>
                  <div className="bk-form-grid">
                    <label>
                      Rule title *
                      <input
                        value={ruleDraft.title}
                        onChange={(event) =>
                          setRuleDraft({ ...ruleDraft, title: event.target.value })
                        }
                        placeholder="e.g. Friendly brand voice"
                        maxLength={120}
                        required
                      />
                    </label>
                    <label>
                      Rule category *
                      <select
                        value={ruleDraft.rule_kind}
                        onChange={(event) =>
                          setRuleDraft({
                            ...ruleDraft,
                            rule_kind: event.target.value as BrandRuleKind,
                          })
                        }
                      >
                        {Object.entries(ruleKindLabels).map(([value, label]) => (
                          <option value={value} key={value}>{label}</option>
                        ))}
                      </select>
                    </label>
                  </div>

                  <label>
                    Description
                    <input
                      value={ruleDraft.description}
                      onChange={(event) =>
                        setRuleDraft({ ...ruleDraft, description: event.target.value })
                      }
                      placeholder="A short explanation of this rule"
                      maxLength={2000}
                    />
                  </label>

                  <label>
                    What should the content follow? *
                    <textarea
                      value={ruleDraft.rule_text}
                      onChange={(event) =>
                        setRuleDraft({ ...ruleDraft, rule_text: event.target.value })
                      }
                      placeholder="Describe the standard in plain language..."
                      rows={3}
                      maxLength={10000}
                      required
                    />
                  </label>

                  <div className="bk-form-grid">
                    <label>
                      Channel (optional)
                      <input
                        value={ruleDraft.channel}
                        onChange={(event) =>
                          setRuleDraft({ ...ruleDraft, channel: event.target.value })
                        }
                        placeholder="e.g. Instagram"
                        maxLength={80}
                      />
                    </label>
                    <label>
                      How should Proofline check it?
                      <select
                        value={ruleDraft.check_type}
                        onChange={(event) =>
                          setRuleDraft({
                            ...ruleDraft,
                            check_type: event.target.value as BrandRuleCheckType,
                            check_value: '',
                          })
                        }
                      >
                        {Object.entries(checkTypeLabels).map(([value, label]) => (
                          <option value={value} key={value}>{label}</option>
                        ))}
                      </select>
                    </label>
                  </div>

                  {ruleDraft.check_type !== 'manual_review' && (
                    <label>
                      {['min_characters', 'max_characters'].includes(ruleDraft.check_type)
                        ? 'Character limit *'
                        : 'Phrase to check *'}
                      <input
                        type={
                          ['min_characters', 'max_characters'].includes(ruleDraft.check_type)
                            ? 'number'
                            : 'text'
                        }
                        min={1}
                        value={ruleDraft.check_value}
                        onChange={(event) =>
                          setRuleDraft({ ...ruleDraft, check_value: event.target.value })
                        }
                        placeholder={
                          ['min_characters', 'max_characters'].includes(ruleDraft.check_type)
                            ? 'e.g. 100'
                            : 'Enter the exact phrase'
                        }
                        required
                      />
                    </label>
                  )}

                  {modalError && <div className="auth-error" role="alert">{modalError}</div>}

                  <div className="bk-modal-actions">
                    <button
                      className="bk-button bk-button-secondary"
                      type="button"
                      onClick={() => setModalOpen(false)}
                    >
                      Cancel
                    </button>
                    <button
                      className="bk-button bk-button-primary"
                      type="submit"
                      disabled={saving}
                    >
                      {saving ? <LoaderCircle className="bk-spinner" size={16} /> : <Check size={16} />}
                      {saving ? 'Saving...' : editingId ? 'Save changes' : 'Create rule'}
                    </button>
                  </div>
                </form>
              ) : (
                <form className="bk-form" onSubmit={saveTerm}>
                  <label>
                    Term or phrase *
                    <input
                      value={termDraft.term}
                      onChange={(event) =>
                        setTermDraft({ ...termDraft, term: event.target.value })
                      }
                      placeholder="e.g. best-in-class"
                      maxLength={200}
                      required
                    />
                  </label>

                  <label>
                    How should Proofline treat this term? *
                    <select
                      value={termDraft.term_type}
                      onChange={(event) =>
                        setTermDraft({
                          ...termDraft,
                          term_type: event.target.value as TermEntryKind,
                        })
                      }
                    >
                      <option value="preferred">Preferred — suggest this term</option>
                      <option value="required">Required — must be included</option>
                      <option value="restricted">Restricted — flag this term</option>
                    </select>
                  </label>

                  <label>
                    Preferred replacement (optional)
                    <input
                      value={termDraft.preferred_replacement}
                      onChange={(event) =>
                        setTermDraft({
                          ...termDraft,
                          preferred_replacement: event.target.value,
                        })
                      }
                      placeholder="What should be used instead?"
                      maxLength={200}
                    />
                  </label>

                  <label>
                    Explanation (optional)
                    <textarea
                      value={termDraft.explanation}
                      onChange={(event) =>
                        setTermDraft({ ...termDraft, explanation: event.target.value })
                      }
                      placeholder="Explain why this term is preferred, required or restricted."
                      rows={3}
                      maxLength={2000}
                    />
                  </label>

                  <div className="bk-checkbox-list">
                    <label className="bk-checkbox">
                      <input
                        type="checkbox"
                        checked={termDraft.case_sensitive}
                        onChange={(event) =>
                          setTermDraft({
                            ...termDraft,
                            case_sensitive: event.target.checked,
                          })
                        }
                      />
                      <span>
                        <strong>Case-sensitive matching</strong>
                        <small>Distinguish uppercase and lowercase letters.</small>
                      </span>
                    </label>
                    <label className="bk-checkbox">
                      <input
                        type="checkbox"
                        checked={termDraft.match_whole_word}
                        onChange={(event) =>
                          setTermDraft({
                            ...termDraft,
                            match_whole_word: event.target.checked,
                          })
                        }
                      />
                      <span>
                        <strong>Match whole word</strong>
                        <small>Avoid matching the term inside a longer word.</small>
                      </span>
                    </label>
                  </div>

                  {modalError && <div className="auth-error" role="alert">{modalError}</div>}

                  <div className="bk-modal-actions">
                    <button
                      className="bk-button bk-button-secondary"
                      type="button"
                      onClick={() => setModalOpen(false)}
                    >
                      Cancel
                    </button>
                    <button
                      className="bk-button bk-button-primary"
                      type="submit"
                      disabled={saving}
                    >
                      {saving ? <LoaderCircle className="bk-spinner" size={16} /> : <Check size={16} />}
                      {saving ? 'Saving...' : editingId ? 'Save changes' : 'Add term'}
                    </button>
                  </div>
                </form>
              )}
            </motion.section>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function EmptyState({
  section,
  hasSearch,
  canEdit,
  onAdd,
}: {
  section: 'brandRules' | 'terminology'
  hasSearch: boolean
  canEdit: boolean
  onAdd: () => void
}) {
  const isRules = section === 'brandRules'
  const Icon = isRules ? BookOpenCheck : MessageSquareText

  return (
    <div className="bk-empty-state">
      <div className="bk-empty-icon">
        <Icon size={27} />
      </div>
      <h3>
        {hasSearch
          ? 'No matching items'
          : isRules
            ? 'Your brand rules start here'
            : 'Your terminology starts here'}
      </h3>
      <p>
        {hasSearch
          ? 'Try a different search term or filter.'
          : isRules
            ? 'Add the first rule your team should follow when creating content.'
            : 'Add the words your brand prefers, requires or wants to avoid.'}
      </p>
      {canEdit && !hasSearch && (
        <button
          className="bk-button bk-button-primary"
          type="button"
          onClick={onAdd}
        >
          <Plus size={16} />
          {isRules ? 'Add your first rule' : 'Add your first term'}
        </button>
      )}
      {hasSearch && (
        <div className="bk-empty-hint">
          <Search size={14} /> Adjust your search and try again.
        </div>
      )}
    </div>
  )
}
