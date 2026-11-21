import { CheckCircle2, CircleAlert, MinusCircle } from 'lucide-react'
import type { AnalysisFinding, NormalizedClaim } from '../lib/content'
import './ClaimMatchConfidence.css'

type Props = { finding: AnalysisFinding }

type DetailRow = { label: string; value: string | null | undefined }

function displayValue(value: string | null | undefined) {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

function formatNormalizedValue(
  numericValue: string | null,
  unit: string | null,
  unitDimension: string | null,
  fallbackText: string | null,
) {
  if (!numericValue) return fallbackText

  const numeric = Number(numericValue)
  const normalizedUnit = unit?.trim().toLowerCase()
  if (
    Number.isFinite(numeric) &&
    unitDimension?.trim().toLowerCase() === 'time' &&
    (normalizedUnit === 'second' || normalizedUnit === 'seconds' || normalizedUnit === 's')
  ) {
    const formattedSeconds = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(numeric)
    if (numeric >= 3600 && numeric % 3600 === 0) {
      const hours = numeric / 3600
      return `${hours} ${hours === 1 ? 'hour' : 'hours'} (${formattedSeconds} seconds)`
    }
    if (numeric >= 60 && numeric % 60 === 0) {
      const minutes = numeric / 60
      return `${minutes} ${minutes === 1 ? 'minute' : 'minutes'} (${formattedSeconds} seconds)`
    }
  }

  return [numericValue, unit].filter(Boolean).join(' ') || fallbackText
}

function normalizedRows(claim: NormalizedClaim): DetailRow[] {
  const numericValue = displayValue(claim.numeric_value)
  const textualValue = displayValue(claim.value_text)
  const unit = displayValue(claim.unit)
  const combinedValue = formatNormalizedValue(
    numericValue,
    unit,
    displayValue(claim.unit_dimension),
    textualValue,
  )

  return [
    { label: 'Subject', value: displayValue(claim.subject) },
    { label: 'Attribute', value: displayValue(claim.attribute) },
    { label: 'Claim type', value: displayValue(claim.claim_kind) },
    { label: 'Normalized value', value: combinedValue || textualValue },
    { label: 'Unit dimension', value: displayValue(claim.unit_dimension) },
    { label: 'Model year(s)', value: claim.model_years?.length ? claim.model_years.join(', ') : null },
    { label: 'Qualifier', value: displayValue(claim.qualifier) },
    { label: 'Conditions', value: displayValue(claim.conditions) },
    { label: 'Product scope', value: displayValue(claim.product_scope) },
    { label: 'Channel scope', value: displayValue(claim.channel_scope) },
    { label: 'Market scope', value: displayValue(claim.market_scope) },
  ].filter((row) => row.value !== null)
}

function FactorStatus({ applicable, matched }: { applicable: boolean; matched: boolean | null }) {
  if (!applicable) {
    return <span className="match-factor-status match-factor-status--neutral"><MinusCircle size={12} /> Not applicable</span>
  }
  if (matched === true) {
    return <span className="match-factor-status match-factor-status--matched"><CheckCircle2 size={12} /> Matched</span>
  }
  if (matched === false) {
    return <span className="match-factor-status match-factor-status--different"><CircleAlert size={12} /> Difference</span>
  }
  return <span className="match-factor-status match-factor-status--neutral"><MinusCircle size={12} /> Not compared</span>
}

export default function ClaimMatchConfidence({ finding }: Props) {
  if (finding.source !== 'claim_passport' && finding.source !== 'ai_claim') return null

  const score = typeof finding.match_confidence === 'number'
    ? Math.max(0, Math.min(1, finding.match_confidence))
    : null
  const band = finding.match_confidence_band ?? null
  const factors = finding.match_confidence_factors ?? []
  const normalized = finding.normalized_claim ?? null
  const rows = normalized ? normalizedRows(normalized) : []
  const hasMetadata = score !== null || band !== null || factors.length > 0 || rows.length > 0

  return (
    <section className="match-confidence-panel" aria-label="Claim matching confidence details">
      <div className="match-confidence-heading">
        <div>
          <span className="match-confidence-eyebrow">IMPROVEMENT 2 · CLAIM MATCHING</span>
          <h4>Claim field comparison</h4>
        </div>
        {hasMetadata && band && (
          <span className={`match-confidence-band match-confidence-band--${band}`}>
            {band.charAt(0).toUpperCase() + band.slice(1)} confidence
          </span>
        )}
      </div>

      {!hasMetadata ? (
        <div className="match-confidence-missing">
          <CircleAlert size={15} />
          Confidence details were not recorded for this historical finding. Run a new analysis to calculate the comparison metadata.
        </div>
      ) : (
        <>
          {score !== null && (
            <div className="match-confidence-score-row">
              <strong>{Math.round(score * 100)}%</strong>
              <span>field comparability · not claim accuracy</span>
              <div
                className="match-confidence-track"
                role="meter"
                aria-label="Comparison confidence score"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Math.round(score * 100)}
              >
                <span style={{ width: `${score * 100}%` }} />
              </div>
            </div>
          )}

          {rows.length > 0 && (
            <div className="normalized-claim-block">
              <h5>Normalized claim fields</h5>
              <dl className="normalized-claim-grid">
                {rows.map((row) => (
                  <div key={row.label}>
                    <dt>{row.label}</dt>
                    <dd>{row.value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          {factors.length > 0 && (
            <details className="match-confidence-factors">
              <summary>Why this comparison received this score ({factors.length} factors)</summary>
              <div className="match-factor-list">
                {factors.map((factor) => (
                  <article className="match-factor-item" key={factor.name}>
                    <div className="match-factor-topline">
                      <strong>{factor.label}</strong>
                      <FactorStatus applicable={factor.applicable} matched={factor.matched} />
                    </div>
                    <p>{factor.explanation}</p>
                    <small>Comparison weight: {Math.round(factor.weight * 100)}%</small>
                  </article>
                ))}
              </div>
            </details>
          )}
        </>
      )}

      <p className="match-confidence-disclaimer">
        This is a deterministic measure of how consistently the available claim fields could be compared. It is not a probability that the claim is true, does not independently verify the source, and never replaces human approval.
      </p>
    </section>
  )
}
