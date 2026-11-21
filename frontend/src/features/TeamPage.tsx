import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  AlertCircle,
  Check,
  Clipboard,
  Copy,
  LoaderCircle,
  Pencil,
  Save,
  ShieldCheck,
  UserPlus,
  UsersRound,
  UserX,
} from 'lucide-react'
import { useAuth } from '../lib/auth-context'
import WorkflowNextStep from './WorkflowNextStep'
import {
  addWorkspaceMember,
  listWorkspaceMembers,
  removeWorkspaceMember,
  updateWorkspaceMemberDisplayName,
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
  // Older deployed APIs omit this field. Hide the editor until the database
  // migration and matching backend endpoint are available together.
  const supportsDisplayNames = members.length > 0 && members.every((member) =>
    Object.prototype.hasOwnProperty.call(member, 'display_name'),
  )
  const [busy, setBusy] = useState(false)
  const [removingId, setRemovingId] = useState('')
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [editingMemberId, setEditingMemberId] = useState('')
  const [displayNameDraft, setDisplayNameDraft] = useState('')
  const [savingDisplayNameFor, setSavingDisplayNameFor] = useState('')

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

  function beginEditDisplayName(member: WorkspaceMember) {
    setEditingMemberId(member.user_id)
    setDisplayNameDraft(member.display_name ?? '')
    setError('')
    setSuccess('')
  }

  async function saveDisplayName(event: FormEvent<HTMLFormElement>, member: WorkspaceMember) {
    event.preventDefault()
    const normalizedName = displayNameDraft.trim().replace(/\s+/g, ' ')
    if (normalizedName.length < 2 || normalizedName.length > 80) {
      setError('Display names must be between 2 and 80 characters.')
      return
    }
    setError('')
    setSuccess('')
    setSavingDisplayNameFor(member.user_id)
    try {
      const updated = await updateWorkspaceMemberDisplayName(workspaceId, member.user_id, normalizedName)
      setMembers((current) => current.map((item) => item.user_id === member.user_id ? updated : item))
      setEditingMemberId('')
      setDisplayNameDraft('')
      setSuccess('Member display name updated.')
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSavingDisplayNameFor('')
    }
  }

  async function handleRemoveMember(member: WorkspaceMember) {
    if (role !== 'brand_owner' || member.user_id === user?.id) return
    if (!window.confirm(`Remove ${member.display_name || `member ${member.user_id.slice(0, 8)}`} from this workspace?`)) return
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
        <div><p className="eyebrow">WORKSPACE ACCESS</p><h1>Team members</h1><p className="workflow-subtitle">Manage workspace access. Brand Owners can set display names so review activity is easy to recognise.</p></div>
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
        {role === 'brand_owner' && members.length > 0 && !supportsDisplayNames && (
          <p className="workflow-muted-copy member-name-rollout-note">
            Display-name editing will appear after the matching workspace database and backend update is deployed.
          </p>
        )}
        <div className="workflow-panel-heading"><div><p className="eyebrow">CURRENT ACCESS</p><h2>Workspace members</h2></div><span className="revision-tag">{members.length} MEMBERS</span></div>
        {loading ? <div className="workflow-loading"><LoaderCircle className="spin-icon" size={21} />Loading members...</div> : members.length === 0 ? <div className="workflow-empty-small"><UsersRound size={23} /><strong>No members found</strong><span>Refresh the workspace member list or check access.</span></div> : <div className="member-list">{members.map((member) => {
          const isCurrentUser = member.user_id === user?.id
          const memberLabel = member.display_name || (isCurrentUser ? 'You — display name not set' : `Member ${member.user_id.slice(0, 8)}`)
          const isEditing = editingMemberId === member.user_id
          return (
            <article className="member-row" key={member.user_id}>
              <div className="member-avatar"><UsersRound size={16} /></div>
              <div className="member-detail">
                <strong>{memberLabel}</strong>
                <small>Account ID: {member.user_id}</small>
                <small>Joined {new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(member.joined_at))}</small>
                {isEditing && (
                  <form className="member-display-name-form" onSubmit={(event) => void saveDisplayName(event, member)}>
                    <label>
                      <span>Display name (2–80 characters)</span>
                      <input
                        value={displayNameDraft}
                        onChange={(event) => setDisplayNameDraft(event.target.value)}
                        placeholder="e.g. Griva Shah"
                        minLength={2}
                        maxLength={80}
                        autoFocus
                        required
                      />
                    </label>
                    <button className="button button-primary" type="submit" disabled={savingDisplayNameFor === member.user_id}>
                      {savingDisplayNameFor === member.user_id ? <LoaderCircle className="spin-icon" size={14} /> : <Save size={14} />}
                      Save name
                    </button>
                    <button className="button button-secondary" type="button" onClick={() => { setEditingMemberId(''); setDisplayNameDraft('') }} disabled={savingDisplayNameFor === member.user_id}>Cancel</button>
                  </form>
                )}
              </div>
              <span className={`role-badge ${member.role === 'brand_owner' ? 'role-badge--owner' : 'role-badge--creator'}`}>{member.role === 'brand_owner' ? 'Brand Owner' : 'Creator'}</span>
              {role === 'brand_owner' && supportsDisplayNames && !isEditing && <button className="icon-button" type="button" title={member.display_name ? 'Edit display name' : 'Set display name'} aria-label={`${member.display_name ? 'Edit' : 'Set'} display name for ${memberLabel}`} onClick={() => beginEditDisplayName(member)}><Pencil size={15} /></button>}
              {role === 'brand_owner' && !isCurrentUser && !isEditing && <button className="icon-button icon-button--danger" type="button" title="Remove member" aria-label={`Remove member ${member.user_id.slice(0, 8)}`} onClick={() => void handleRemoveMember(member)} disabled={removingId === member.user_id}>{removingId === member.user_id ? <LoaderCircle className="spin-icon" size={16} /> : <UserX size={16} />}</button>}
            </article>
          )
        })}</div>}
      </section>

      <WorkflowNextStep
        title={role === 'brand_owner' ? 'Review incoming submissions' : 'Create your first content submission'}
        description={role === 'brand_owner' ? 'Once your Creator sends a draft, inspect its findings and record the human review decision.' : 'Choose the content type, add the product and channel context, then run checks before sending it for review.'}
        action={role === 'brand_owner' ? 'Open review queue' : 'Open content reviews'}
        to={role === 'brand_owner' ? '/reviews' : '/content'}
      />
    </div>
  )
}
