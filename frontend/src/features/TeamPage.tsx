import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  AlertCircle,
  Check,
  Clipboard,
  Copy,
  LoaderCircle,
  ShieldCheck,
  UserPlus,
  UsersRound,
  UserX,
} from 'lucide-react'
import { useAuth } from '../lib/auth-context'
import {
  addWorkspaceMember,
  listWorkspaceMembers,
  removeWorkspaceMember,
  type WorkspaceMember,
} from '../lib/content'
import type { WorkspaceRole } from '../lib/workspaces'
import './WorkflowPages.css'

type Props = { workspaceId: string; role: WorkspaceRole }

function getErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.'
}

export default function TeamPage({ workspaceId, role }: Props) {
  const { user } = useAuth()
  const [members, setMembers] = useState<WorkspaceMember[]>([])
  const [userIdInput, setUserIdInput] = useState('')
  const [loadedWorkspaceId, setLoadedWorkspaceId] = useState('')
  const loading = loadedWorkspaceId !== workspaceId
  const [busy, setBusy] = useState(false)
  const [removingId, setRemovingId] = useState('')
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const refresh = useCallback(async () => {
    const records = await listWorkspaceMembers(workspaceId)
    setMembers(records)
  }, [workspaceId])

  useEffect(() => {
    let active = true
    listWorkspaceMembers(workspaceId)
      .then((records) => {
        if (active) {
          setMembers(records)
          setError('')
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setMembers([])
          setError(getErrorMessage(err))
        }
      })
      .finally(() => { if (active) setLoadedWorkspaceId(workspaceId) })
    return () => { active = false }
  }, [workspaceId])

  async function copyAccountId() {
    if (!user?.id) return
    try {
      await navigator.clipboard.writeText(user.id)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      setError('Clipboard access is unavailable. Select and copy your account ID manually.')
    }
  }

  async function handleAddMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (role !== 'brand_owner') return
    const normalizedId = userIdInput.trim()
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(normalizedId)) {
      setError('Enter a valid registered user UUID.')
      return
    }
    if (normalizedId === user?.id) {
      setError('You are already a member of this workspace.')
      return
    }
    setError('')
    setSuccess('')
    setBusy(true)
    try {
      await addWorkspaceMember(workspaceId, { user_id: normalizedId, role: 'creator' })
      setUserIdInput('')
      await refresh()
      setSuccess('Creator added to this workspace.')
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleRemoveMember(member: WorkspaceMember) {
    if (role !== 'brand_owner' || member.user_id === user?.id) return
    if (!window.confirm(`Remove ${member.user_id.slice(0, 8)} from this workspace?`)) return
    setError('')
    setSuccess('')
    setRemovingId(member.user_id)
    try {
      await removeWorkspaceMember(workspaceId, member.user_id)
      setMembers((current) => current.filter((item) => item.user_id !== member.user_id))
      setSuccess('Workspace member removed.')
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setRemovingId('')
    }
  }

  return (
    <div className="workflow-page">
      <header className="workflow-header">
        <div><p className="eyebrow">WORKSPACE ACCESS</p><h1>Team members</h1><p className="workflow-subtitle">Manage who can work with this brand's rules, Claim Passports and content reviews.</p></div>
        <span className={`role-badge ${role === 'brand_owner' ? 'role-badge--owner' : 'role-badge--creator'}`}><ShieldCheck size={14} />{role === 'brand_owner' ? 'Brand Owner' : 'Creator'}</span>
      </header>

      {error && <div className="workflow-alert workflow-alert--error" role="alert"><AlertCircle size={17} />{error}</div>}
      {success && <div className="workflow-alert workflow-alert--success" role="status"><Check size={17} />{success}</div>}

      <section className="workflow-panel account-id-panel">
        <div className="account-id-icon"><Clipboard size={19} /></div>
        <div className="account-id-copy"><p className="eyebrow">YOUR REGISTERED ACCOUNT ID</p><h2>Share this ID to join a workspace</h2><p>A Creator must register first, then share this UUID with the Brand Owner so they can add the account to this workspace.</p><code>{user?.id ?? 'Account ID unavailable'}</code></div>
        <button className="button button-secondary" type="button" onClick={() => void copyAccountId()} disabled={!user?.id}>{copied ? <Check size={15} /> : <Copy size={15} />}{copied ? 'Copied' : 'Copy ID'}</button>
      </section>

      {role === 'brand_owner' && (
        <section className="workflow-panel add-member-panel">
          <div className="workflow-panel-heading"><div><p className="eyebrow">ADD AN EXISTING ACCOUNT</p><h2>Connect a Creator</h2></div><span className="workflow-step-pill">REGISTER FIRST</span></div>
          <p className="workflow-muted-copy">The backend currently adds an already registered user by UUID. It does not send email invitations. Ask the Creator to sign up in Proofline and share their account ID from this page.</p>
          <form className="add-member-form" onSubmit={handleAddMember}><label className="workflow-field"><span>Creator account UUID</span><input value={userIdInput} onChange={(event: { target: { value: string } }) => setUserIdInput(event.target.value)} placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" required /></label><button className="button button-primary" type="submit" disabled={busy}>{busy ? <LoaderCircle className="spin-icon" size={15} /> : <UserPlus size={15} />} Add Creator</button></form>
        </section>
      )}

      <section className="workflow-panel team-members-panel">
        <div className="workflow-panel-heading"><div><p className="eyebrow">CURRENT ACCESS</p><h2>Workspace members</h2></div><span className="revision-tag">{members.length} MEMBERS</span></div>
        {loading ? <div className="workflow-loading"><LoaderCircle className="spin-icon" size={21} />Loading members...</div> : members.length === 0 ? <div className="workflow-empty-small"><UsersRound size={23} /><strong>No members found</strong><span>Refresh the workspace member list or check access.</span></div> : <div className="member-list">{members.map((member) => <article className="member-row" key={member.user_id}><div className="member-avatar"><UsersRound size={16} /></div><div className="member-detail"><strong>{member.user_id === user?.id ? 'You' : `User ${member.user_id.slice(0, 8)}`}</strong><small>{member.user_id}</small><small>Joined {new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(member.joined_at))}</small></div><span className={`role-badge ${member.role === 'brand_owner' ? 'role-badge--owner' : 'role-badge--creator'}`}>{member.role === 'brand_owner' ? 'Brand Owner' : 'Creator'}</span>{role === 'brand_owner' && member.user_id !== user?.id && <button className="icon-button icon-button--danger" type="button" title="Remove member" aria-label={`Remove member ${member.user_id.slice(0, 8)}`} onClick={() => void handleRemoveMember(member)} disabled={removingId === member.user_id}>{removingId === member.user_id ? <LoaderCircle className="spin-icon" size={16} /> : <UserX size={16} />}</button>}</article>)}</div>}
      </section>
    </div>
  )
}
