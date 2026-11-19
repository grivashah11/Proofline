import { useEffect, useState } from 'react'
import { AlertCircle, BarChart3, CheckCircle2, Clock3, LoaderCircle, RefreshCw, ShieldCheck } from 'lucide-react'
import { getGovernanceInsights, type GovernanceInsightsResponse } from '../lib/governance'
import './GovernanceInsightsPanel.css'

type Props = { workspaceId: string }

function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Date unavailable'
  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
  }).format(date)
}

function getErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'Unable to load governance insights.'
}

export default function GovernanceInsightsPanel({ workspaceId }: Props) {
  const [windowDays, setWindowDays] = useState(90)
  const [minSubmissions, setMinSubmissions] = useState(3)
  const [refreshVersion, setRefreshVersion] = useState(0)
  const [insights, setInsights] = useState<GovernanceInsightsResponse | null>(null)
  const [loadedKey, setLoadedKey] = useState('')
  const [error, setError] = useState('')

  const requestKey = `${workspaceId}:${windowDays}:${minSubmissions}:${refreshVersion}`
  const loading = loadedKey !== requestKey

  useEffect(() => {
    let active = true

    getGovernanceInsights(workspaceId, {
      windowDays,
      minDistinctSubmissions: minSubmissions,
      limit: 50,
    })
      .then((result) => {
        if (!active) return
        setInsights(result)
        setError('')
        setLoadedKey(requestKey)
      })
      .catch((err: unknown) => {
        if (!active) return
        setInsights(null)
        setError(getErrorMessage(err))
        setLoadedKey(requestKey)
      })

    return () => { active = false }
  }, [workspaceId, windowDays, minSubmissions, refreshVersion, requestKey])

  const hasCandidates = Boolean(
    insights && (
      insights.recurring_issues.length ||
      insights.candidate_guideline_gaps.length ||
      insights.evidence_gaps.length
    ),
  )

  return (
    <div className="governance-insights-page">
      <section className="governance-insights-toolbar">
        <div>
          <p className="eyebrow">WORKSPACE GOVERNANCE</p>
          <h2>Patterns across your reviews</h2>
          <p>See recurring issues, resolution trends and areas where existing guidance may need clarification.</p>
        </div>
        <div className="governance-insights-filters">
          <label>
            <span>Reporting window</span>
            <select value={windowDays} onChange={(event) => setWindowDays(Number(event.target.value))}>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
              <option value={180}>Last 180 days</option>
              <option value={365}>Last 365 days</option>
            </select>
          </label>
          <label>
            <span>Minimum submissions</span>
            <select value={minSubmissions} onChange={(event) => setMinSubmissions(Number(event.target.value))}>
              <option value={2}>2 or more</option>
              <option value={3}>3 or more</option>
              <option value={5}>5 or more</option>
              <option value={10}>10 or more</option>
            </select>
          </label>
          <button className="button button-secondary" type="button" onClick={() => setRefreshVersion((value) => value + 1)} disabled={loading}>
            {loading ? <LoaderCircle className="spin-icon" size={15} /> : <RefreshCw size={15} />}
            Refresh
          </button>
        </div>
      </section>

      {error && (
        <div className="workflow-alert workflow-alert--error" role="alert">
          <AlertCircle size={17} />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="workflow-loading workflow-panel governance-insights-loading">
          <LoaderCircle className="spin-icon" size={22} /> Loading workspace insights...
        </div>
      ) : insights ? (
        <>
          <section className="governance-summary-grid" aria-label="Finding resolution summary">
            <article className="governance-summary-card governance-summary-card--open">
              <span>Open finding threads</span>
              <strong>{insights.resolution_summary.open_threads}</strong>
              <small>Issues still appearing in at least one submission</small>
            </article>
            <article className="governance-summary-card governance-summary-card--resolved">
              <span>Resolved threads</span>
              <strong>{insights.resolution_summary.resolved_threads}</strong>
              <small>Issues absent from a complete later analysis</small>
            </article>
            <article className="governance-summary-card governance-summary-card--reappeared">
              <span>Reappeared threads</span>
              <strong>{insights.resolution_summary.reappeared_threads}</strong>
              <small>Previously resolved issues that returned</small>
            </article>
          </section>

          <section className="governance-insight-section">
            <div className="governance-section-heading">
              <div><p className="eyebrow">REPEATED ACROSS SUBMISSIONS</p><h3>Recurring issue patterns</h3></div>
              <span className="revision-tag">{insights.recurring_issues.length} patterns</span>
            </div>
            {insights.recurring_issues.length === 0 ? (
              <div className="governance-empty-state"><CheckCircle2 size={19} /><div><strong>No recurring patterns meet this threshold</strong><p>Try a longer reporting window or a lower minimum submission count. Findings are counted across distinct content submissions.</p></div></div>
            ) : (
              <div className="governance-pattern-list">
                {insights.recurring_issues.map((item) => (
                  <article className="governance-pattern-card" key={item.fingerprint}>
                    <div className="governance-pattern-top">
                      <div><span className="governance-source-label">{item.source.replaceAll('_', ' ')} · {item.category.replaceAll('_', ' ')}</span><h4>{item.title}</h4></div>
                      <span className="governance-count-pill">{item.distinct_submissions} submissions</span>
                    </div>
                    <div className="governance-pattern-metrics">
                      <span><strong>{item.total_occurrences}</strong> total occurrences</span>
                      <span><strong>{item.open_submissions}</strong> open</span>
                      <span><strong>{item.resolved_submissions}</strong> resolved</span>
                      <span><strong>{item.reappeared_submissions}</strong> reappeared</span>
                    </div>
                    <small className="governance-last-seen"><Clock3 size={12} /> Last seen {formatDate(item.last_seen_at)}</small>
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className="governance-insight-section">
            <div className="governance-section-heading">
              <div><p className="eyebrow">OWNER REVIEW REQUIRED</p><h3>Candidate guideline gaps</h3></div>
              <span className="revision-tag">{insights.candidate_guideline_gaps.length} candidates</span>
            </div>
            {insights.candidate_guideline_gaps.length === 0 ? (
              <div className="governance-empty-state"><ShieldCheck size={19} /><div><strong>No guideline-gap candidates found</strong><p>Repeated brand-rule findings that require review may appear here after enough distinct submissions.</p></div></div>
            ) : (
              <div className="governance-candidate-list">
                {insights.candidate_guideline_gaps.map((item) => (
                  <article className="governance-candidate-card" key={item.fingerprint}>
                    <div className="governance-candidate-heading"><div><span className="governance-source-label">{item.category.replaceAll('_', ' ')}</span><h4>{item.current_guideline_title}</h4></div><span className="governance-owner-badge">Owner confirmation</span></div>
                    <p>{item.suggested_clarification}</p>
                    <small>Observed in {item.distinct_submissions} submissions · {item.total_occurrences} occurrences</small>
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className="governance-insight-section">
            <div className="governance-section-heading">
              <div><p className="eyebrow">CLAIM EVIDENCE COVERAGE</p><h3>Candidate evidence gaps</h3></div>
              <span className="revision-tag">{insights.evidence_gaps.length} candidates</span>
            </div>
            {insights.evidence_gaps.length === 0 ? (
              <div className="governance-empty-state"><BarChart3 size={19} /><div><strong>No recurring evidence gaps found</strong><p>Recurring unverified claims across separate submissions may appear here.</p></div></div>
            ) : (
              <div className="governance-candidate-list">
                {insights.evidence_gaps.map((item) => (
                  <article className="governance-candidate-card" key={item.fingerprint}>
                    <div className="governance-candidate-heading"><div><span className="governance-source-label">{item.subject || 'Unspecified subject'}</span><h4>{item.attribute || 'Claim evidence not specified'}</h4></div><span className="governance-owner-badge">Owner confirmation</span></div>
                    <p>{item.suggested_action}</p>
                    <small>Observed in {item.distinct_submissions} submissions · {item.total_occurrences} occurrences</small>
                  </article>
                ))}
              </div>
            )}
          </section>

          <div className="governance-disclaimer">
            <ShieldCheck size={17} />
            <div><strong>Recommendations, not automatic changes</strong><p>These patterns are derived from finding history. They do not edit brand rules, activate Claim Passports or change review decisions. A Brand Owner must inspect each candidate and decide whether to update guidance or evidence.</p></div>
          </div>
          <p className="governance-generated-at">Generated {formatDate(insights.generated_at)} · {insights.window_days}-day window · Minimum {insights.min_distinct_submissions} distinct submissions</p>
          {!hasCandidates && <p className="governance-first-run-note">Finding lifecycle tracking starts with analyses run after the governance migration. Older findings are not backfilled into lifecycle threads.</p>}
        </>
      ) : error ? null : (
        <div className="workflow-empty-small"><BarChart3 size={24} /><strong>No governance data available</strong><span>Run content analyses to begin building finding lifecycle history.</span></div>
      )}
    </div>
  )
}
