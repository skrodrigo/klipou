"use client"

import { useRouter } from "next/navigation"
import { createContext, useContext, useMemo } from "react"

type UpgradeDialogContextValue = {
  open: boolean
  openDialog: () => void
  closeDialog: () => void
}

const UpgradeDialogContext = createContext<UpgradeDialogContextValue | null>(null)

const plans = [
  {
    name: "Free",
    price: "$0",
    cadence: "60 credits/mês",
    cta: "Plano atual",
    highlight: false,
    perks: [
      "Workspace privado",
      "1 conta social gerenciada",
      "Clipes gerados por IA",
      "Exportação em 720p",
    ],
  },
  {
    name: "Creator",
    tag: "Mais popular",
    price: "$11.6",
    oldPrice: "$29",
    cadence: "7.200 créditos/ano",
    cta: "Assinar",
    highlight: true,
    perks: [
      "Workspace privado",
      "6 contas sociais",
      "Sem marca d'água",
      "Exportação em 4K",
      "Agendamento de posts",
    ],
  },
  {
    name: "Business",
    price: "$15.6",
    oldPrice: "$39",
    cadence: "7.200 créditos/ano",
    cta: "Assinar",
    highlight: false,
    perks: [
      "Workspace compartilhado",
      "20 contas sociais",
      "Convide time (+$5/assento)",
      "Brand kit",
      "Biblioteca compartilhada",
    ],
  },
]

export function UpgradeDialogProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter()

  const value = useMemo(
    () => ({
      open: false,
      openDialog: () => router.push("/upgrade"),
      closeDialog: () => router.back(),
    }),
    [router]
  )

  return (
    <UpgradeDialogContext.Provider value={value}>{children}</UpgradeDialogContext.Provider>
  )
}

export function useUpgradeDialog() {
  const context = useContext(UpgradeDialogContext)
  if (!context) {
    throw new Error("useUpgradeDialog deve ser usado dentro do UpgradeDialogProvider")
  }
  return context
}
