import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'

type Props = {
  title: string
  description: string
  action: string
  to: string
}

export default function WorkflowNextStep({ title, description, action, to }: Props) {
  return (
    <section className="workflow-next-step" aria-label="Continue to the next step">
      <div className="workflow-next-step-copy">
        <span className="workflow-next-step-eyebrow">NEXT STEP</span>
        <strong>{title}</strong>
        <p>{description}</p>
      </div>
      <Link className="button button-primary workflow-next-step-action" to={to}>
        {action} <ArrowRight size={16} />
      </Link>
    </section>
  )
}
