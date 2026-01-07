"use client"

import React, { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import Image from "next/image"
import { Cancel01FreeIcons, CheckmarkCircleFreeIcons, AlertCircleFreeIcons } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import { useOAuth } from "@/hooks/useOAuth"

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

const PLATFORMS = [
  { id: "tiktok", name: "TikTok", icon: "/social/tiktok.svg", desc: "Feed ou Inbox" },
  { id: "instagram", name: "Instagram", icon: "/social/instagram.svg", desc: "Feed" },
  { id: "youtube", name: "YouTube", icon: "/social/shorts.svg", desc: "Feed" },
  { id: "facebook", name: "Facebook", icon: "/social/facebook.svg", desc: "Feed" },
  { id: "linkedin", name: "LinkedIn", icon: "/social/linkedin.svg", desc: "Feed" },
  { id: "twitter", name: "X", icon: "/social/x.svg", desc: "Feed" },
]

export default function AccountsPage() {
  const [showModal, setShowModal] = useState(false)
  const [connectedAccounts, setConnectedAccounts] = useState<SocialAccount[]>([])
  const [selectedPlatform, setSelectedPlatform] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const { initiateOAuth, disconnectAccount, listAccounts, loading, error } = useOAuth()

  // Load connected accounts on mount
  useEffect(() => {
    loadAccounts()
  }, [])

  // Check for OAuth callback
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('connected') === 'true') {
      loadAccounts()
      // Clear URL params
      window.history.replaceState({}, document.title, window.location.pathname)
    }
  }, [])

  const loadAccounts = async () => {
    setIsLoading(true)
    const accounts = await listAccounts()
    setConnectedAccounts(accounts)
    setIsLoading(false)
  }

  const isConnected = (platformId: string) => {
    return connectedAccounts.some(acc => acc.platform === platformId)
  }

  const getConnectedAccount = (platformId: string) => {
    return connectedAccounts.find(acc => acc.platform === platformId)
  }

  const handleConnect = async (platformId: string) => {
    setSelectedPlatform(platformId)
    await initiateOAuth(platformId)
  }

  const handleDisconnect = async (platformId: string) => {
    if (confirm(`Tem certeza que deseja desconectar ${platformId}?`)) {
      await disconnectAccount(platformId)
      await loadAccounts()
    }
  }

  return (
    <div className="flex-1 p-12 flex flex-col">
      <div className="mb-8">
        <h1 className="text-2xl text-foreground mb-2">Contas</h1>
      </div>


      <div className="flex flex-wrap gap-6">
        {PLATFORMS.map((platform) => {
          const connected = isConnected(platform.id)
          const account = getConnectedAccount(platform.id)

          return (
            <div
              key={platform.id}
              className={`rounded-lg border w-60 h-60 p-4 flex flex-col h-full transition-all ${connected
                ? "bg-card border-green-500/20 shadow-sm"
                : "bg-card border-border hover:border-border/80"
                }`}
            >
              <div className="flex items-start justify-between mb-4">
                <Image
                  src={platform.icon}
                  alt={platform.name}
                  width={32}
                  height={32}
                  className="h-8 w-8"
                />
                {connected && (
                  <HugeiconsIcon icon={CheckmarkCircleFreeIcons} className="w-5 h-5 text-green-500" />
                )}
              </div>

              <h3 className="text-lg font-semibold text-foreground mb-1">{platform.name}</h3>
              <p className="text-muted-foreground text-sm mb-4">{platform.desc}</p>

              <div className="mt-auto space-y-2">
                {!connected ? (
                  <Button
                    onClick={() => handleConnect(platform.id)}
                    disabled={loading && selectedPlatform === platform.id}
                    className="w-full"
                  >
                    {loading && selectedPlatform === platform.id ? "Conectando..." : "Conectar"}
                  </Button>
                ) : (
                  <>
                    <Button variant="outline" className="w-full" disabled>
                      Conectado
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      className="w-full"
                      onClick={() => handleDisconnect(platform.id)}
                      disabled={loading}
                    >
                      Desconectar
                    </Button>
                  </>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
