import { ArrowLeft, BarChart3 } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { WorkspaceRole } from '../lib/workspaces'
import GovernanceInsightsPanel from './GovernanceInsightsPanel'
import './WorkflowPages.css'

type Props = { workspaceId: string; role: WorkspaceRole }

export default function GovernanceInsightsPage({ workspaceId, role }: Props) {
  if (role !== 'brand_owner') {
    return (
      <div className="workflow-page">
        <header className="workflow-header">
          <div>
            <p className="eyebrow">WORKSPACE INSIGHTS</p>
            <h1>Governance insights</h1>
            <p className="workflow-subtitle">These workspace-level patterns are available to the Brand Owner.</p>
          </div>
        </header>
        <div className="workflow-notice workflow-notice--warning">
          <BarChart3 size={18} />
          Your current role is Creator. You can review your own submissions in <Link to="/content">Content reviews</Link>.
        </div>
      </div>
    )
  }

  return (
    <div className="workflow-page">
      <header className="workflow-header">
        <div>
          <p className="eyebrow">BRAND OWNER WORKSPACE</p>
          <h1>Governance insights</h1>
          <p className="workflow-subtitle">Spot repeated issues across distinct submissions, track finding resolution and identify where brand guidance or evidence may need attention.</p>
        </div>
        <Link className="button button-secondary" to="/reviews">
          <ArrowLeft size={15} /> Back to review queue
        </Link>
      </header>
      <GovernanceInsightsPanel workspaceId={workspaceId} />
    </div>
  )
}
