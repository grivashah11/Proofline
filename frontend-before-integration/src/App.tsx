import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  BadgeCheck,
  BookOpenCheck,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Eye,
  EyeOff,
  FileCheck2,
  LayoutDashboard,
  LoaderCircle,
  LogOut,
  Menu,
  MessageSquareText,
  ShieldCheck,
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
import { AuthProvider } from './lib/auth'
import BrandKnowledgePage from './features/BrandKnowledgePage'
import ClaimPassportsPage from './features/ClaimPassportsPage'
import { useAuth } from './lib/auth-context'
import {
  createWorkspace,
  getWorkspaces,
  makeWorkspaceSlug,
  roleLabel,
  type WorkspaceListItem,
  type WorkspaceRecord,
} from './lib/workspaces'
import './App.css'
import './Auth.css'

type ApiState = 'checking' | 'online' | 'offline'

type NavItem = {
  label: string
  to: string
  icon: LucideIcon
}

const navItems: NavItem[] = [
  { label: 'Overview', to: '/', icon: LayoutDashboard },
  { label: 'Brand rules', to: '/brand-rules', icon: BookOpenCheck },
  { label: 'Terminology', to: '/terminology', icon: MessageSquareText },
  { label: 'Claim Passports', to: '/claim-passports', icon: BadgeCheck },
  { label: 'Content reviews', to: '/content', icon: FileCheck2 },
  { label: 'Review queue', to: '/reviews', icon: UsersRound },
]

type SectionKey =
  | 'brandRules'
  | 'terminology'
  | 'passports'
  | 'content'
  | 'reviews'

const sectionContent: Record<
  SectionKey,
  {
    eyebrow: string
    title: string
    description: string
    icon: LucideIcon
    emptyTitle: string
    emptyDescription: string
    tasks: string[]
  }
> = {
  brandRules: {
    eyebrow: 'BRAND KNOWLEDGE',
    title: 'Brand rules',
    description:
      'Give your team clear, consistent guidance on how your brand should communicate.',
    icon: BookOpenCheck,
    emptyTitle: 'Your brand rules will live here',
    emptyDescription:
      'Add the messaging, tone and content requirements that Proofline should check before publication.',
    tasks: [
      'Define messaging and tone requirements',
      'Set words or phrases to use or avoid',
      'Apply consistent rules to every content review',
    ],
  },
  terminology: {
    eyebrow: 'BRAND KNOWLEDGE',
    title: 'Terminology',
    description:
      'Keep preferred terms and phrases consistent across every piece of content.',
    icon: MessageSquareText,
    emptyTitle: 'Your terminology list starts here',
    emptyDescription:
      'Add preferred terms, alternatives and words your team should avoid.',
    tasks: [
      'Add preferred brand terminology',
      'Record terms to avoid',
      'Help creators use consistent language',
    ],
  },
  passports: {
    eyebrow: 'VERIFIED EVIDENCE',
    title: 'Claim Passports',
    description:
      'Keep important brand claims connected to their evidence, scope and approval status.',
    icon: BadgeCheck,
    emptyTitle: 'No Claim Passports yet',
    emptyDescription:
      'Create a Passport for an important product claim and attach the evidence that supports it.',
    tasks: [
      'Record a claim and its product scope',
      'Attach evidence and supporting excerpts',
      'Activate an approved Passport version',
    ],
  },
  content: {
    eyebrow: 'CREATOR WORKSPACE',
    title: 'Content reviews',
    description:
      'Check drafts against brand rules and evidence before they are published.',
    icon: FileCheck2,
    emptyTitle: 'Ready for your first content review?',
    emptyDescription:
      'Start with a draft, choose its product and channel context, and let Proofline check it.',
    tasks: [
      'Create a content submission',
      'Run brand and claim checks',
      'Revise findings and submit for approval',
    ],
  },
  reviews: {
    eyebrow: 'BRAND OWNER WORKSPACE',
    title: 'Review queue',
    description:
      'Review submitted content and make the final publication decision.',
    icon: UsersRound,
    emptyTitle: 'Your review queue is clear',
    emptyDescription:
      'Content submitted by creators for approval will appear here.',
    tasks: [
      'Open the exact submitted revision',
      'Read findings and creator comments',
      'Approve, request changes or reject',
    ],
  },
}

const quickLinks: {
  number: string
  title: string
  description: string
  to: string
  action: string
  icon: LucideIcon
}[] = [
  {
    number: '01',
    title: 'Set brand rules',
    description:
      'Define the messaging, tone and terminology your team should follow.',
    to: '/brand-rules',
    action: 'Set up brand knowledge',
    icon: BookOpenCheck,
  },
  {
    number: '02',
    title: 'Verify important claims',
    description:
      'Create evidence-backed Claim Passports for your products.',
    to: '/claim-passports',
    action: 'Manage Claim Passports',
    icon: BadgeCheck,
  },
  {
    number: '03',
    title: 'Review content',
    description:
      'Check a draft and resolve findings before it reaches a reviewer.',
    to: '/content',
    action: 'Start a content review',
    icon: FileCheck2,
  },
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
                    ? 'Pick up where your brand left off.'
                    : 'Start building a more trustworthy brand.'}
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
  const { user } = useAuth()
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
    return <WorkspaceOnboarding onCreated={handleWorkspaceCreated} />
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
}: {
  onCreated: () => Promise<void>
}) {
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [slugTouched, setSlugTouched] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  function updateName(value: string) {
    setName(value)

    if (!slugTouched) {
      setSlug(makeWorkspaceSlug(value))
    }
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

      <motion.section
        className="onboarding-card"
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="onboarding-step">YOUR FIRST STEP · 01 OF 01</div>
        <div className="onboarding-icon">
          <Sparkles size={25} />
        </div>
        <p className="auth-eyebrow">WELCOME TO PROOFLINE</p>
        <h1>Let's set up your brand workspace.</h1>
        <p className="onboarding-description">
          Give your team one place to manage brand rules, verify important
          claims and review content before it gets published.
        </p>

        <form className="onboarding-form" onSubmit={handleCreate}>
          <label htmlFor="workspace-name">What is your brand or workspace called?</label>
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

          <button className="auth-primary-button" type="submit" disabled={busy}>
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
            You'll become the <strong>Brand Owner</strong> and can invite
            registered team members as Creators.
          </span>
        </div>
      </motion.section>
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

        <div className="workspace-select-wrap">
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
          <p className="nav-heading">WORKSPACE</p>
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive =
              item.to === '/'
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
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-help-icon">
            <Sparkles size={17} />
          </div>
          <strong>Publish with confidence.</strong>
          <p>
            Keep your brand voice consistent and every important claim
            traceable.
          </p>
          <div className="sidebar-version">PROOFLINE · ROUND 2</div>
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
              <Routes location={location}>
                <Route
                  path="/"
                  element={<DashboardPage workspace={selected.workspace} />}
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
                  element={<FeaturePage section="content" />}
                />
                <Route
                  path="/reviews"
                  element={<FeaturePage section="reviews" />}
                />
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
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

function DashboardPage({ workspace }: { workspace: WorkspaceRecord }) {
  return (
    <div className="dashboard-page">
      <section className="welcome-row">
        <div>
          <p className="eyebrow">YOUR BRAND WORKSPACE</p>
          <h1>Your brand, in check.</h1>
          <p className="welcome-description">
            Keep every claim traceable and every message on-brand.
            Review content with confidence before it gets published.
          </p>
        </div>
        <Link className="button button-primary welcome-button" to="/content">
          <Sparkles size={17} />
          Start a content review
          <ArrowUpRight size={17} />
        </Link>
      </section>

      <section className="hero-panel">
        <div className="hero-glow hero-glow-one" />
        <div className="hero-glow hero-glow-two" />
        <div className="hero-content">
          <div className="hero-label">
            <span className="hero-label-dot" />
            PRE-PUBLICATION CONTENT CHECK
          </div>
          <h2>
            Publish with proof.
            <br />
            <span>Not guesswork.</span>
          </h2>
          <p>
            Proofline brings brand rules, verified claims and human
            approvals into one simple workflow.
          </p>
          <div className="hero-actions">
            <Link className="button button-light" to="/content">
              Review content <ArrowRight size={17} />
            </Link>
            <Link className="hero-text-link" to="/brand-rules">
              Set up brand knowledge <ArrowUpRight size={16} />
            </Link>
          </div>
        </div>

        <div className="hero-visual" aria-hidden="true">
          <div className="visual-orbit orbit-one" />
          <div className="visual-orbit orbit-two" />
          <div className="visual-core">
            <ShieldCheck size={54} strokeWidth={1.45} />
          </div>
          <div className="visual-chip visual-chip-top">
            <CheckCircle2 size={15} />
            <span>Evidence linked</span>
          </div>
          <div className="visual-chip visual-chip-bottom">
            <BadgeCheck size={15} />
            <span>Human approved</span>
          </div>
        </div>
      </section>

      <section className="section-heading">
        <div>
          <p className="eyebrow">THE PROOFLINE WORKFLOW</p>
          <h2>Everything you need, in three steps.</h2>
        </div>
        <span className="section-caption">A clear path from draft to approval</span>
      </section>

      <section className="quick-grid">
        {quickLinks.map((item) => {
          const Icon = item.icon

          return (
            <motion.div
              key={item.number}
              className="quick-card"
              whileHover={{ y: -4 }}
              transition={{ duration: 0.18 }}
            >
              <div className="quick-card-top">
                <span className="step-number">{item.number}</span>
                <span className="quick-card-icon">
                  <Icon size={19} />
                </span>
              </div>
              <h3>{item.title}</h3>
              <p>{item.description}</p>
              <Link className="card-link" to={item.to}>
                {item.action} <ArrowUpRight size={16} />
              </Link>
            </motion.div>
          )
        })}
      </section>

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

          <div className="empty-activity">
            <div className="empty-icon">
              <FileCheck2 size={23} />
            </div>
            <div>
              <strong>No submissions yet</strong>
              <p>
                Your content reviews and their latest decisions will
                appear here.
              </p>
            </div>
          </div>
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

function FeaturePage({ section }: { section: SectionKey }) {
  const page = sectionContent[section]
  const Icon = page.icon

  return (
    <div className="feature-page">
      <div className="feature-intro">
        <div className="feature-icon">
          <Icon size={23} />
        </div>
        <p className="eyebrow">{page.eyebrow}</p>
        <h1>{page.title}</h1>
        <p>{page.description}</p>
      </div>

      <div className="feature-content-grid">
        <section className="feature-empty-panel">
          <div className="empty-large-icon">
            <Icon size={27} />
          </div>
          <h2>{page.emptyTitle}</h2>
          <p>{page.emptyDescription}</p>
          <span className="feature-status">
            <span className="feature-status-dot" />
            Workspace setup
          </span>
        </section>

        <aside className="feature-guide-panel">
          <p className="eyebrow">WHAT YOU CAN DO HERE</p>
          <h2>Simple steps. Clear outcomes.</h2>
          <div className="guide-list">
            {page.tasks.map((task, index) => (
              <div className="guide-item" key={task}>
                <span className="guide-number">0{index + 1}</span>
                <span>{task}</span>
              </div>
            ))}
          </div>
          <Link to="/" className="subtle-link guide-back-link">
            Back to overview <ArrowRight size={15} />
          </Link>
        </aside>
      </div>
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
