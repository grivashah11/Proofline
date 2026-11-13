import { useEffect, useState, type ReactNode } from 'react'
import type { Session } from '@supabase/supabase-js'
import { AuthContext } from './auth-context'
import { isSupabaseConfigured, supabase } from './supabase'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [initializing, setInitializing] = useState(isSupabaseConfigured)

  useEffect(() => {
    if (!supabase) return

    let active = true

    supabase.auth
      .getSession()
      .then(({ data, error }) => {
        if (!active) return

        if (!error) {
          setSession(data.session)
        }

        setInitializing(false)
      })
      .catch(() => {
        if (active) setInitializing(false)
      })

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession)
    })

    return () => {
      active = false
      subscription.unsubscribe()
    }
  }, [])

  async function signIn(email: string, password: string) {
    if (!supabase) {
      throw new Error('Supabase is not configured. Check your frontend environment.')
    }

    const { error } = await supabase.auth.signInWithPassword({
      email: email.trim(),
      password,
    })

    if (error) throw error
  }

  async function signUp(email: string, password: string) {
    if (!supabase) {
      throw new Error('Supabase is not configured. Check your frontend environment.')
    }

    const { data, error } = await supabase.auth.signUp({
      email: email.trim(),
      password,
      options: {
        emailRedirectTo: window.location.origin,
      },
    })

    if (error) throw error

    return !data.session
  }

  async function signOut() {
    if (!supabase) return

    const { error } = await supabase.auth.signOut()

    if (error) throw error
  }

  return (
    <AuthContext.Provider
      value={{
        session,
        user: session?.user ?? null,
        loading: isSupabaseConfigured ? initializing : false,
        signIn,
        signUp,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
