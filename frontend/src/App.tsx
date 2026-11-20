import { lazy, Suspense, useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  Activity,
  ArrowRight,
  ArrowLeft,
  ArrowUpRight,
  BadgeCheck,
  BarChart3,
  BookOpenCheck,
  CheckCircle2,
  Clipboard,
  ChevronDown,
  ChevronRight,
  Eye,
  EyeOff,
  FileCheck2,
  LayoutDashboard,
  Image as ImageIcon,
  LoaderCircle,
  LogOut,
  Menu,
  MessageSquareText,
  ShieldCheck,
  RefreshCw,
  Sparkles,
  UsersRound,
  X,
  type LucideIcon,
} from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import {
  BrowserRouter,
  Link,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom'
import { ApiError, apiRequest } from './lib/api'
import { listContents, statusLabel, type ContentRecord } from './lib/content'
import { AuthProvider } from './lib/auth'
import GettingStarted from './features/GettingStarted'
import { useAuth } from './lib/auth-context'
import {
  createWorkspace,
  getWorkspaces,
  makeWorkspaceSlug,
  roleLabel,
  type WorkspaceListItem,
  type WorkspaceRecord,
  type WorkspaceRole,
} from './lib/workspaces'
import './App.css'
import './Auth.css'
import './JudgeUsability.css'

const BrandKnowledgePage = lazy(() => import('./features/BrandKnowledgePage'))
const ClaimPassportsPage = lazy(() => import('./features/ClaimPassportsPage'))
const ContentReviewsPage = lazy(() => import('./features/ContentReviewsPage'))
const ReviewQueuePage = lazy(() => import('./features/ReviewQueuePage'))
const TeamPage = lazy(() => import('./features/TeamPage'))
const ImagesPage = lazy(() => import('./features/ImagesPage'))
const GovernanceInsightsPage = lazy(() => import('./features/GovernanceInsightsPage'))


type ApiState = 'checking' | 'online' | 'offline'

type NavItem = {
  label: string
  to: string
  icon: LucideIcon
  group: 'start' | 'setup' | 'review' | 'manage'
}

const navItems: NavItem[] = [
  { label: 'Overview', to: '/', icon: LayoutDashboard, group: 'start' },
  { label: 'Brand rules', to: '/brand-rules', icon: BookOpenCheck, group: 'setup' },
  { label: 'Terminology', to: '/terminology', icon: MessageSquareText, group: 'setup' },
  { label: 'Claim Passports', to: '/claim-passports', icon: BadgeCheck, group: 'setup' },
  { label: 'Content reviews', to: '/content', icon: FileCheck2, group: 'review' },
  { label: 'Review queue', to: '/reviews', icon: UsersRound, group: 'review' },
  { label: 'Governance insights', to: '/governance', icon: BarChart3, group: 'review' },
  { label: 'Team members', to: '/team', icon: UsersRound, group: 'manage' },
  { label: 'Images & assets', to: '/images', icon: ImageIcon, group: 'manage' },
]

const navGroups: { key: NavItem['group']; label: string }[] = [
  { key: 'start', label: 'START HERE' },
  { key: 'setup', label: 'BRAND SETUP' },
  { key: 'review', label: 'REVIEW WORKFLOW' },
  { key: 'manage', label: 'TEAM & ASSETS' },
]

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AuthenticatedApp />
      </AuthProvider>
    </BrowserRouter>
  )
}

function AuthenticatedApp() {
  const { session, loading } = useAuth()

  if (loading) return <LoadingScreen label="Checking your session" />
  if (!session) return <AuthScreen />

  return <WorkspaceGate />
}

function LoadingScreen({ label }: { label: string }) {
  return (
    <div className="auth-loading">
      <div className="auth-loading-mark">
        <ShieldCheck size={28} />
      </div>
      <LoaderCircle className="spin-icon" size={19} />
      <p>{label}</p>
    </div>
  )
}

function RouteLoadingFallback() {
  return (
    <div className="route-loading-state" role="status" aria-live="polite">
      <LoaderCircle className="spin-icon" size={22} />
      <span>Loading this section…</span>
    </div>
  )
}

function AuthScreen() {
  const { signIn, signUp } = useAuth()
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [confirmationEmail, setConfirmationEmail] = useState('')

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setBusy(true)

    try {
      if (mode === 'login') {
        await signIn(email, password)
      } else {
        const needsConfirmation = await signUp(email, password)

        if (needsConfirmation) {
          setConfirmationEmail(email.trim())
        }
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Something went wrong. Please try again.',
      )
    } finally {
      setBusy(false)
    }
  }

  function changeMode(nextMode: 'login' | 'signup') {
    setMode(nextMode)
    setError('')
    setConfirmationEmail('')
    setPassword('')
  }

  return (
    <div className="auth-page">
      <div className="auth-background-glow auth-glow-one" />
      <div className="auth-background-glow auth-glow-two" />

      <div className="auth-top-brand">
        <span className="auth-brand-mark">
          <ShieldCheck size={23} />
        </span>
        <span>
          <strong>proofline</strong>
          <small>Brand governance, made clear.</small>
        </span>
      </div>

      <div className="auth-main">
        <motion.div
          className="auth-pitch"
          initial={{ opacity: 0, x: -14 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.45 }}
        >
          <div className="auth-pitch-badge">
            <Sparkles size={14} />
            PRE-PUBLICATION BRAND REVIEW
          </div>
          <h1>
            Make every
            <br />
            message <span>mean it.</span>
          </h1>
          <p>
            Check content against your brand rules, connect claims to
            evidence and keep people in control of the final approval.
          </p>

          <div className="auth-benefits">
            <div>
              <CheckCircle2 size={17} />
              <span>Consistent brand messaging</span>
            </div>
            <div>
              <CheckCircle2 size={17} />
              <span>Evidence-backed claims</span>
            </div>
            <div>
              <CheckCircle2 size={17} />
              <span>Human-led approval workflow</span>
            </div>
          </div>

          <div className="auth-principle">
            <ShieldCheck size={19} />
            <span>AI assists. People decide.</span>
          </div>
        </motion.div>

        <motion.section
          className="auth-card"
          initial={{ opacity: 0, y: 13 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.08 }}
        >
          {confirmationEmail ? (
            <div className="confirmation-state">
              <div className="confirmation-icon">
                <CheckCircle2 size={29} />
              </div>
              <p className="auth-eyebrow">ONE LAST STEP</p>
              <h2>Check your inbox.</h2>
              <p>
                We sent a confirmation link to <strong>{confirmationEmail}</strong>.
                Verify your email, then come back here to sign in.
              </p>
              <button
                className="auth-primary-button"
                type="button"
                onClick={() => changeMode('login')}
              >
                Back to sign in <ArrowRight size={17} />
              </button>
            </div>
          ) : (
            <>
              <div className="auth-card-heading">
                <p className="auth-eyebrow">
                  {mode === 'login' ? 'WELCOME BACK' : 'GET STARTED'}
                </p>
                <h2>
                  {mode === 'login' ? 'Sign in to Proofline' : 'Create your account'}
                </h2>
                <p>
                  {mode === 'login'
                    ? 'First time here? Create an account, choose Brand Owner and set up a workspace. A Creator can join from a separate account.'
                    : 'Create an account to set up a brand workspace or join one as a Creator.'}
                </p>
              </div>

              <div className="auth-mode-switch">
                <button
                  type="button"
                  className={mode === 'login' ? 'active' : ''}
                  onClick={() => changeMode('login')}
                >
                  Sign in
                </button>
                <button
                  type="button"
                  className={mode === 'signup' ? 'active' : ''}
                  onClick={() => changeMode('signup')}
                >
                  Create account
                </button>
              </div>

              <form className="auth-form" onSubmit={handleSubmit}>
                <label htmlFor="auth-email">Email address</label>
                <input
                  id="auth-email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@company.com"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                />

                <div className="password-label-row">
                  <label htmlFor="auth-password">Password</label>
                  {mode === 'signup' && (
                    <span className="password-hint">At least 8 characters</span>
                  )}
                </div>
                <div className="password-input-wrap">
                  <input
                    id="auth-password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete={
                      mode === 'login' ? 'current-password' : 'new-password'
                    }
                    placeholder="Enter your password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    minLength={mode === 'signup' ? 8 : undefined}
                    required
                  />
                  <button
                    type="button"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    onClick={() => setShowPassword((value) => !value)}
                  >
                    {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                  </button>
                </div>

                {error && (
                  <div className="auth-error" role="alert">
                    {error}
                  </div>
                )}

                <button
                  className="auth-primary-button"
                  type="submit"
                  disabled={busy}
                >
                  {busy ? (
                    <>
                      <LoaderCircle className="spin-icon" size={17} />
                      Please wait...
                    </>
                  ) : (
                    <>
                      {mode === 'login' ? 'Sign in' : 'Create account'}
                      <ArrowRight size={17} />
                    </>
                  )}
                </button>
              </form>

              <p className="auth-switch-copy">
                {mode === 'login' ? "New to Proofline? " : 'Already have an account? '}
                <button
                  type="button"
                  onClick={() =>
                    changeMode(mode === 'login' ? 'signup' : 'login')
                  }
                >
                  {mode === 'login' ? 'Create an account' : 'Sign in'}
                </button>
              </p>
            </>
          )}

          <div className="auth-card-footer">
            <ShieldCheck size={14} />
            Your workspace and content stay access-controlled.
          </div>
        </motion.section>
      </div>

      <div className="auth-bottom-line">
        <span>PROOFLINE</span>
        <span>Brand clarity. Evidence. Human approval.</span>
      </div>
    </div>
  )
}

function WorkspaceGate() {
  const { user, signOut } = useAuth()
  const [workspaces, setWorkspaces] = useState<WorkspaceListItem[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true

    getWorkspaces()
      .then((items) => {
        if (!active) return
        setWorkspaces(items)
        setSelectedId(items[0]?.workspace.id ?? '')
        setError('')
      })
      .catch((err: unknown) => {
        if (!active) return
        setError(
          err instanceof Error
            ? err.message
            : 'Unable to load your workspaces.',
        )
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [user?.id])

  const handleWorkspaceCreated = useCallback(async () => {
    const items = await getWorkspaces()
    setWorkspaces(items)
    setSelectedId(items[0]?.workspace.id ?? '')
    setError('')
    return items.length
  }, [])

  if (loading) return <LoadingScreen label="Loading your workspace" />

  if (error) {
    return (
      <div className="auth-loading">
        <div className="auth-loading-mark">
          <Activity size={27} />
        </div>
        <h2>We couldn't load your workspace.</h2>
        <p>{error}</p>
        <button
          className="auth-primary-button retry-button"
          type="button"
          onClick={() => window.location.reload()}
        >
          Try again <ArrowRight size={17} />
        </button>
      </div>
    )
  }

  if (workspaces.length === 0) {
    return <WorkspaceOnboarding onCreated={handleWorkspaceCreated} onSignOut={signOut} userId={user?.id ?? ''} />
  }

  const selected =
    workspaces.find((item) => item.workspace.id === selectedId) ??
    workspaces[0]

  return (
    <AppLayout
      workspaces={workspaces}
      selected={selected}
      onSelect={setSelectedId}
    />
  )
}

function WorkspaceOnboarding({
  onCreated,
  onSignOut,
  userId,
}: {
  onCreated: () => Promise<number>
  onSignOut: () => Promise<void>
  userId: string
}) {
  const [selectedPath, setSelectedPath] = useState<'choose' | 'owner' | 'creator'>('choose')
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [slugTouched, setSlugTouched] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [accessMessage, setAccessMessage] = useState('')
  const [copiedId, setCopiedId] = useState(false)
  const [signingOut, setSigningOut] = useState(false)
  const [signOutError, setSignOutError] = useState('')

  async function copyAccountId() {
    try {
      await navigator.clipboard.writeText(userId)
      setCopiedId(true)
      setAccessMessage('Creator ID copied. Share it with your Brand Owner.')
    } catch {
      setCopiedId(false)
      setAccessMessage(
        'Clipboard access is unavailable. Select and copy your Creator ID manually.',
      )
    }
  }

  async function handleBackToAuth() {
    setSigningOut(true)
    setSignOutError('')

    try {
      await onSignOut()
    } catch (err) {
      setSignOutError(
        err instanceof Error
          ? err.message
          : 'Unable to sign out. Please try again.',
      )
    } finally {
      setSigningOut(false)
    }
  }

  async function refreshWorkspaceAccess() {
    setAccessMessage('')
    setCopiedId(false)

    try {
      const count = await onCreated()
      if (count === 0) {
        setAccessMessage(
          'No workspace membership found yet. Ask the Brand Owner to add your Creator ID, then refresh again.',
        )
      }
    } catch (err) {
      setAccessMessage(
        err instanceof Error
          ? err.message
          : 'Unable to refresh workspace access.',
      )
    }
  }

  function updateName(value: string) {
    setName(value)

    if (!slugTouched) {
      setSlug(makeWorkspaceSlug(value))
    }
  }

  function selectPath(path: 'owner' | 'creator') {
    setError('')
    setAccessMessage('')
    setCopiedId(false)
    setSelectedPath(path)
  }

  function backToRoleChoices() {
    setError('')
    setAccessMessage('')
    setSelectedPath('choose')
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')

    const normalizedName = name.trim()
    const normalizedSlug = makeWorkspaceSlug(slug)

    if (normalizedName.length < 2) {
      setError('Workspace name must contain at least 2 characters.')
      return
    }

    if (normalizedSlug.length < 2) {
      setError('Please enter a valid workspace URL name.')
      return
    }

    setBusy(true)

    try {
      await createWorkspace({
        name: normalizedName,
        slug: normalizedSlug,
      })
      await onCreated()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'Unable to create your workspace.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="onboarding-page">
      <div className="onboarding-glow" />
      <div className="onboarding-brand">
        <span className="auth-brand-mark">
          <ShieldCheck size={23} />
        </span>
        <strong>proofline</strong>
      </div>

      <AnimatePresence mode="wait">
        {selectedPath === 'choose' && (
          <motion.section
            key="role-choice"
            className="onboarding-card onboarding-role-card"
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.18 }}
          >
            <div className="onboarding-role-heading">
              <div className="onboarding-icon">
                <Sparkles size={25} />
              </div>
              <p className="auth-eyebrow">WELCOME TO PROOFLINE</p>
              <h1>How would you like to use Proofline?</h1>
              <p className="onboarding-description">
                Choose the option that best describes your role. You can
                continue in just one step.
              </p>
            </div>

            <div className="onboarding-role-grid">
              <button
                className="onboarding-role-option"
                type="button"
                onClick={() => selectPath('owner')}
              >
                <span className="onboarding-role-icon">
                  <ShieldCheck size={23} />
                </span>
                <span className="onboarding-role-label">FOR BRAND TEAMS</span>
                <strong>I'm a Brand Owner</strong>
                <span className="onboarding-role-description">
                  Create a workspace to manage your brand rules, approved
                  claims, team and content reviews.
                </span>
                <span className="onboarding-role-action">
                  Create a workspace <ArrowRight size={16} />
                </span>
              </button>

              <button
                className="onboarding-role-option"
                type="button"
                onClick={() => selectPath('creator')}
              >
                <span className="onboarding-role-icon">
                  <UsersRound size={23} />
                </span>
                <span className="onboarding-role-label">FOR CONTRIBUTORS</span>
                <strong>I'm a Creator</strong>
                <span className="onboarding-role-description">
                  Join a brand workspace you're already working with and
                  submit content for review.
                </span>
                <span className="onboarding-role-action">
                  Join a workspace <ArrowRight size={16} />
                </span>
              </button>
            </div>

            <p className="onboarding-role-footnote">
              Not sure? Choose Brand Owner only if you are setting up a new
              workspace. Choose Creator if a brand team will add you.
            </p>
          </motion.section>
        )}

        {selectedPath === 'owner' && (
          <motion.section
            key="brand-owner"
            className="onboarding-card onboarding-detail-card"
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.18 }}
          >
            <button
              className="onboarding-back-link"
              type="button"
              onClick={backToRoleChoices}
            >
              <ArrowLeft size={15} /> Change role
            </button>

            <div className="onboarding-icon">
              <ShieldCheck size={25} />
            </div>
            <p className="auth-eyebrow">BRAND OWNER · CREATE A WORKSPACE</p>
            <h1>Create your brand workspace.</h1>
            <p className="onboarding-description">
              Set up a shared place to manage brand rules, verify important
              claims and review content before it gets published.
            </p>

            <form className="onboarding-form" onSubmit={handleCreate}>
              <label htmlFor="workspace-name">
                What is your brand or workspace called?
              </label>
              <input
                id="workspace-name"
                value={name}
                onChange={(event) => updateName(event.target.value)}
                placeholder="e.g. Acme Studio"
                maxLength={120}
                required
              />

              <label htmlFor="workspace-slug">Workspace URL name</label>
              <div className="slug-input">
                <span>proofline.app/</span>
                <input
                  id="workspace-slug"
                  value={slug}
                  onChange={(event) => {
                    setSlugTouched(true)
                    setSlug(event.target.value)
                  }}
                  placeholder="acme-studio"
                  maxLength={63}
                  required
                />
              </div>
              <p className="field-help">
                Lowercase letters, numbers and hyphens only.
              </p>

              {error && (
                <div className="auth-error" role="alert">
                  {error}
                </div>
              )}

              <button
                className="auth-primary-button"
                type="submit"
                disabled={busy}
              >
                {busy ? (
                  <>
                    <LoaderCircle className="spin-icon" size={17} />
                    Creating workspace...
                  </>
                ) : (
                  <>
                    Create my workspace <ArrowRight size={17} />
                  </>
                )}
              </button>
            </form>

            <div className="owner-note">
              <ShieldCheck size={16} />
              <span>
                You'll become the <strong>Brand Owner</strong> and manage
                this workspace's rules, Claim Passports and team access.
              </span>
            </div>
          </motion.section>
        )}

        {selectedPath === 'creator' && (
          <motion.section
            key="creator"
            className="onboarding-card onboarding-detail-card onboarding-creator-card"
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.18 }}
          >
            <button
              className="onboarding-back-link"
              type="button"
              onClick={backToRoleChoices}
            >
              <ArrowLeft size={15} /> Change role
            </button>

            <div className="onboarding-icon">
              <UsersRound size={25} />
            </div>
            <p className="auth-eyebrow">CREATOR · JOIN A WORKSPACE</p>
            <h1>Join your brand's workspace.</h1>
            <p className="onboarding-description">
              Share your Creator ID with the Brand Owner. They'll add your
              existing account to their workspace.
            </p>

            <div className="onboarding-creator-id-panel">
              <div className="onboarding-creator-id-copy">
                <span className="onboarding-field-label">
                  YOUR CREATOR ACCOUNT ID
                </span>
                <code>{userId}</code>
              </div>
              <button
                className="button button-secondary onboarding-copy-id-button"
                type="button"
                onClick={() => void copyAccountId()}
              >
                <Clipboard size={15} />
                {copiedId ? 'Copied' : 'Copy ID'}
              </button>
            </div>

            <ol className="onboarding-creator-steps">
              <li>
                <span>1</span>
                <p>
                  <strong>Copy your Creator ID</strong>
                  <small>Use the button above.</small>
                </p>
              </li>
              <li>
                <span>2</span>
                <p>
                  <strong>Send it to your Brand Owner</strong>
                  <small>
                    They can add you from their Team Members page.
                  </small>
                </p>
              </li>
              <li>
                <span>3</span>
                <p>
                  <strong>Return here after you've been added</strong>
                  <small>Refresh your access to open the workspace.</small>
                </p>
              </li>
            </ol>

            {accessMessage && (
              <p className="onboarding-access-message" role="status">
                {accessMessage}
              </p>
            )}

            <button
              className="auth-primary-button onboarding-refresh-button"
              type="button"
              onClick={() => void refreshWorkspaceAccess()}
            >
              <RefreshCw size={16} />
              I've been added — refresh access
            </button>

            <p className="onboarding-creator-note">
              You don't need to create a workspace to join an existing brand.
            </p>
          </motion.section>
        )}
      </AnimatePresence>

      <div className="onboarding-signout-area">
        <button
          className="button button-secondary onboarding-signout-button"
          type="button"
          onClick={() => void handleBackToAuth()}
          disabled={signingOut}
        >
          {signingOut ? (
            <LoaderCircle size={15} className="spin-icon" />
          ) : (
            <LogOut size={15} />
          )}
          {signingOut ? 'Signing out...' : 'Back to Sign in / Create Account'}
        </button>

        {signOutError && (
          <p className="onboarding-signout-error" role="alert">
            {signOutError}
          </p>
        )}
      </div>

      <p className="onboarding-footer">YOUR BRAND. YOUR RULES. YOUR PROOF.</p>
    </div>
  )
}

function AppLayout({
  workspaces,
  selected,
  onSelect,
}: {
  workspaces: WorkspaceListItem[]
  selected: WorkspaceListItem
  onSelect: (id: string) => void
}) {
  const location = useLocation()
  const { user, signOut } = useAuth()
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [apiState, setApiState] = useState<ApiState>('checking')
  const [signingOut, setSigningOut] = useState(false)
  const [signOutError, setSignOutError] = useState('')

  const currentPage =
    navItems.find((item) => item.to === location.pathname) ??
    navItems.find(
      (item) =>
        item.to !== '/' && location.pathname.startsWith(item.to),
    ) ??
    navItems[0]

  useEffect(() => {
    let active = true

    apiRequest<unknown>('/api/v1/health')
      .then(() => {
        if (active) setApiState('online')
      })
      .catch(() => {
        if (active) setApiState('offline')
      })

    return () => {
      active = false
    }
  }, [])

  const handleSignOut = async () => {
    setSigningOut(true)
    setSignOutError('')

    try {
      await signOut()
    } catch (err) {
      setSignOutError(
        err instanceof Error ? err.message : 'Unable to sign out.',
      )
    } finally {
      setSigningOut(false)
    }
  }

  return (
    <div className="app-shell">
      {mobileNavOpen && (
        <button
          className="mobile-overlay"
          type="button"
          aria-label="Close navigation"
          onClick={() => setMobileNavOpen(false)}
        />
      )}

      <aside className={`sidebar ${mobileNavOpen ? 'sidebar--open' : ''}`}>
        <div className="sidebar-top">
          <Link
            className="brand"
            to="/"
            onClick={() => setMobileNavOpen(false)}
          >
            <span className="brand-mark">
              <ShieldCheck size={22} strokeWidth={2.1} />
            </span>
            <span className="brand-copy">
              <strong>proofline</strong>
              <small>Brand governance</small>
            </span>
          </Link>

          <button
            className="sidebar-close"
            type="button"
            aria-label="Close navigation"
            onClick={() => setMobileNavOpen(false)}
          >
            <X size={19} />
          </button>
        </div>

        <div
          className="workspace-select-wrap"
          title={selected.workspace.name}
        >
          <span className="workspace-avatar">
            {selected.workspace.name.slice(0, 1).toUpperCase()}
          </span>
          <div className="workspace-select-copy">
            <strong>{selected.workspace.name}</strong>
            <small>{roleLabel(selected.role)}</small>
          </div>
          <ChevronDown size={15} className="workspace-select-chevron" />
          <select
            className="workspace-select-overlay"
            aria-label="Switch workspace"
            value={selected.workspace.id}
            onChange={(event) => onSelect(event.target.value)}
          >
            {workspaces.map((item) => (
              <option
                value={item.workspace.id}
                key={item.workspace.id}
              >
                {item.workspace.name}
              </option>
            ))}
          </select>
        </div>

        <nav className="sidebar-nav" aria-label="Main navigation">
          {navGroups.map((group) => {
            const items = navItems.filter((item) =>
              item.group === group.key &&
              (!['/reviews', '/governance'].includes(item.to) || selected.role === 'brand_owner'),
            )

            if (items.length === 0) return null

            return (
              <section className="sidebar-nav-group" key={group.key}>
                <p className="nav-heading">{group.label}</p>
                {items.map((item) => {
                  const Icon = item.icon
                  const isActive = item.to === '/'
                    ? location.pathname === '/'
                    : location.pathname.startsWith(item.to)

                  return (
                    <Link
                      key={item.to}
                      to={item.to}
                      className={`nav-link ${isActive ? 'nav-link--active' : ''}`}
                      aria-current={isActive ? 'page' : undefined}
                      onClick={() => setMobileNavOpen(false)}
                    >
                      <Icon size={18} strokeWidth={1.85} />
                      <span>{item.label}</span>
                      {isActive && <span className="nav-active-dot" />}
                    </Link>
                  )
                })}
              </section>
            )
          })}
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-principle">
            <ShieldCheck size={17} />
            <div>
              <strong>AI assists. People decide.</strong>
              <p>Evidence informs the review. An authorised person makes the decision.</p>
            </div>
          </div>
          <div className="sidebar-version">PROOFLINE · ROUND 3</div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="mobile-menu"
              type="button"
              aria-label="Open navigation"
              onClick={() => setMobileNavOpen(true)}
            >
              <Menu size={21} />
            </button>
            <div className="breadcrumb">
              <span>{selected.workspace.name}</span>
              <ChevronRight size={15} />
              <strong>{currentPage.label}</strong>
            </div>
          </div>

          <div className="topbar-right">
            <ApiStatus state={apiState} />
            <div className="user-email" title={user?.email ?? ''}>
              {user?.email ?? 'Signed in'}
            </div>
            <button
              className="signout-button"
              type="button"
              onClick={handleSignOut}
              disabled={signingOut}
              title="Sign out"
            >
              {signingOut ? (
                <LoaderCircle size={16} className="spin-icon" />
              ) : (
                <LogOut size={16} />
              )}
              <span>Sign out</span>
            </button>
          </div>
        </header>

        {signOutError && (
          <div className="global-error" role="alert">
            {signOutError}
          </div>
        )}

        <div className="page-container">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={`${location.pathname}-${selected.workspace.id}`}
              className="page-transition"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
            >
              <Suspense fallback={<RouteLoadingFallback />}>
                <Routes location={location}>
                  <Route
                    path="/"
                    element={<DashboardPage workspace={selected.workspace} role={selected.role} />}
                  />
                  <Route
                    path="/brand-rules"
                    element={<BrandKnowledgePage section="brandRules" workspaceId={selected.workspace.id} role={selected.role} />}
                  />
                  <Route
                    path="/terminology"
                    element={<BrandKnowledgePage section="terminology" workspaceId={selected.workspace.id} role={selected.role} />}
                  />
                  <Route
                    path="/claim-passports"
                    element={<ClaimPassportsPage workspaceId={selected.workspace.id} role={selected.role} />}
                  />
                  <Route
                    path="/content"
                    element={<ContentReviewsPage workspaceId={selected.workspace.id} role={selected.role} />}
                  />
                  <Route
                    path="/reviews"
                    element={<ReviewQueuePage workspaceId={selected.workspace.id} role={selected.role} />}
                  />
                  <Route
                    path="/governance"
                    element={<GovernanceInsightsPage workspaceId={selected.workspace.id} role={selected.role} />}
                  />
                  <Route
                    path="/team"
                    element={<TeamPage workspaceId={selected.workspace.id} role={selected.role} />}
                  />
                  <Route
                    path="/images"
                    element={<ImagesPage workspaceId={selected.workspace.id} role={selected.role} />}
                  />
                  <Route path="*" element={<NotFoundPage />} />
                </Routes>
              </Suspense>
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  )
}

function ApiStatus({ state }: { state: ApiState }) {
  const label = {
    checking: 'Checking backend',
    online: 'Backend connected',
    offline: 'Backend offline',
  }[state]

  return (
    <div className={`api-status api-status--${state}`}>
      <span className="api-status-dot" />
      <span>{label}</span>
    </div>
  )
}

function DashboardPage({ workspace, role }: { workspace: WorkspaceRecord; role: WorkspaceRole }) {
  const [recentSubmissions, setRecentSubmissions] = useState<ContentRecord[]>([])
  const [recentLoadedForWorkspace, setRecentLoadedForWorkspace] = useState('')
  const recentLoading = recentLoadedForWorkspace !== workspace.id
  const [recentError, setRecentError] = useState('')

  useEffect(() => {
    let active = true
    listContents(workspace.id)
      .then((records) => {
        if (active) {
          setRecentSubmissions(records.slice(0, 4))
          setRecentError('')
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setRecentSubmissions([])
          setRecentError(err instanceof Error ? err.message : 'Unable to load recent submissions.')
        }
      })
      .finally(() => { if (active) setRecentLoadedForWorkspace(workspace.id) })
    return () => { active = false }
  }, [workspace.id])

  return (
    <div className="dashboard-page">
      <section className="welcome-row">
        <div>
          <p className="eyebrow">YOUR BRAND WORKSPACE</p>
          <h1>Welcome to {workspace.name}</h1>
          <p className="welcome-description">
            {role === 'brand_owner'
              ? 'Start with brand rules and approved claims, then invite a Creator and review their draft.'
              : 'Submit a draft, review the findings, make corrections and send your revision to the Brand Owner.'}
          </p>
        </div>
        {role === 'brand_owner' ? (
          <a className="button button-primary welcome-button" href="#getting-started-panel">
            <Sparkles size={17} />
            Follow setup steps
            <ArrowRight size={17} />
          </a>
        ) : (
          <Link className="button button-primary welcome-button" to="/content">
            <FileCheck2 size={17} />
            Submit content
            <ArrowRight size={17} />
          </Link>
        )}
      </section>

      <GettingStarted workspaceId={workspace.id} role={role} />

      <details className="workflow-overview-panel">
        <summary className="workflow-overview-summary">
          <span>
            <span className="eyebrow">HOW PROOFLINE WORKS</span>
            <strong>See the three-step review journey</strong>
            <small>Brand setup → content checks → human decision</small>
          </span>
          <span className="workflow-overview-summary-action">
            <span>View steps</span>
            <ChevronDown size={17} />
          </span>
        </summary>
        <div className="workflow-overview-content">
          <div className="workflow-overview-heading">
            <div>
              <h2 id="workflow-overview-title">One clear path from draft to decision</h2>
            </div>
            <p>Evidence stays visible. People stay in control.</p>
          </div>
          <div className="workflow-overview-steps">
            <div className="workflow-overview-step">
              <span className="workflow-overview-number">1</span>
              <div><strong>Prepare the brand</strong><small>Set brand rules, terminology and approved Claim Passports.</small></div>
            </div>
            <div className="workflow-overview-step">
              <span className="workflow-overview-number">2</span>
              <div><strong>Check a draft</strong><small>Submit content and review evidence-linked findings and suggestions.</small></div>
            </div>
            <div className="workflow-overview-step">
              <span className="workflow-overview-number">3</span>
              <div><strong>Review and decide</strong><small>An authorised Brand Owner reviews the exact submitted revision.</small></div>
            </div>
          </div>
        </div>
      </details>

      <section className="bottom-grid">
        <div className="recent-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">YOUR WORK</p>
              <h2>Recent submissions</h2>
            </div>
            <Link to="/content" className="subtle-link">
              View all <ArrowRight size={15} />
            </Link>
          </div>

          {recentLoading ? (
            <div className="empty-activity">
              <div className="empty-icon"><LoaderCircle className="spin-icon" size={21} /></div>
              <div><strong>Loading submissions</strong><p>Your latest content activity is being retrieved.</p></div>
            </div>
          ) : recentError ? (
            <div className="empty-activity">
              <div className="empty-icon"><Activity size={21} /></div>
              <div><strong>Recent activity unavailable</strong><p>{recentError}</p></div>
            </div>
          ) : recentSubmissions.length === 0 ? (
            <div className="empty-activity">
              <div className="empty-icon"><FileCheck2 size={23} /></div>
              <div><strong>No submissions yet</strong><p>Your content reviews and their latest decisions will appear here.</p></div>
            </div>
          ) : (
            <div className="dashboard-recent-list">
              {recentSubmissions.map((item) => (
                <Link to="/content" className="dashboard-recent-item" key={item.id}>
                  <span className="dashboard-recent-icon"><FileCheck2 size={16} /></span>
                  <span className="dashboard-recent-copy"><strong>{item.title}</strong><small>{item.product_context || item.channel || 'Content submission'}</small></span>
                  <span className={`status-pill status-${item.status}`}>{statusLabel(item.status)}</span>
                  <ArrowUpRight size={14} />
                </Link>
              ))}
            </div>
          )}
        </div>

        <div className="principle-panel">
          <div className="principle-icon">
            <ShieldCheck size={21} />
          </div>
          <p className="eyebrow">THE PROOFLINE PRINCIPLE</p>
          <h3>AI assists. People decide.</h3>
          <p>
            Proofline helps identify issues and connect claims to
            evidence. An authorised reviewer makes the final decision.
          </p>
          <div className="principle-foot">
            <CheckCircle2 size={15} />
            Human approval stays in control
          </div>
        </div>
      </section>
      <p className="dashboard-workspace-caption">
        Current workspace: <strong>{workspace.name}</strong>
      </p>
    </div>
  )
}

function NotFoundPage() {
  return (
    <div className="not-found">
      <div className="empty-large-icon">
        <Activity size={27} />
      </div>
      <h1>Page not found</h1>
      <p>The page you're looking for doesn't exist.</p>
      <Link to="/" className="button button-primary">
        Back to overview
      </Link>
    </div>
  )
}

export default App
