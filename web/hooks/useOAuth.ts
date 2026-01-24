import { useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'

interface SocialAccount {
  social_account_id: string
  platform: string
  username: string
  display_name: string
  profile_picture: string
  connected_at: string
  last_used_at: string | null
  token_expired: boolean
}

interface UseOAuthReturn {
  initiateOAuth: (platform: string) => Promise<void>
  disconnectAccount: (platform: string) => Promise<void>
  listAccounts: () => Promise<SocialAccount[]>
  loading: boolean
  error: string | null
}

export const useOAuth = (): UseOAuthReturn => {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const router = useRouter()

  const mapPlatformToOAuthProvider = (platform: string) => {
    if (platform === 'instagram') return 'facebook'
    return platform
  }

  const getAuthToken = () => {
    return localStorage.getItem('access_token')
  }

  const initiateOAuth = useCallback(async (platform: string) => {
    setLoading(true)
    setError(null)

    try {
      const token = getAuthToken()
      if (!token) {
        throw new Error('Not authenticated')
      }

      const userId = localStorage.getItem('user_id')
      if (!userId) {
        throw new Error('User ID not found')
      }

      const oauthProvider = mapPlatformToOAuthProvider(platform)

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/auth/oauth/authorize/${oauthProvider}/`,
        {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      )

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || `Failed to initiate ${platform} OAuth`)
      }

      // Store state for verification after callback
      sessionStorage.setItem(`oauth_state_${oauthProvider}`, data.state)
      sessionStorage.setItem(`oauth_user_id_${oauthProvider}`, userId)

      // Redirect to OAuth provider with user_id parameter
      const authUrl = new URL(data.authorization_url)
      authUrl.searchParams.append('user_id', userId)

      window.location.href = authUrl.toString()
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error'
      setError(errorMessage)
      console.error(`OAuth error for ${platform}:`, errorMessage)
    } finally {
      setLoading(false)
    }
  }, [])

  const disconnectAccount = useCallback(async (platform: string) => {
    setLoading(true)
    setError(null)

    try {
      const token = getAuthToken()
      if (!token) {
        throw new Error('Not authenticated')
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/auth/social-accounts/${platform}/disconnect/`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      )

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || `Failed to disconnect ${platform}`)
      }

      // Refresh the page to update the UI
      router.refresh()
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error'
      setError(errorMessage)
      console.error(`Disconnect error for ${platform}:`, errorMessage)
    } finally {
      setLoading(false)
    }
  }, [router])

  const listAccounts = useCallback(async (): Promise<SocialAccount[]> => {
    setLoading(true)
    setError(null)

    try {
      const token = getAuthToken()
      if (!token) {
        throw new Error('Not authenticated')
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/auth/social-accounts/`,
        {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      )

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Failed to list social accounts')
      }

      return data.accounts || []
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error'
      setError(errorMessage)
      console.error('List accounts error:', errorMessage)
      return []
    } finally {
      setLoading(false)
    }
  }, [])

  return {
    initiateOAuth,
    disconnectAccount,
    listAccounts,
    loading,
    error,
  }
}
