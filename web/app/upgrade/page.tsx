"use client"

import { useRouter } from "next/navigation"
import { useQuery, useMutation } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowLeft02Icon } from "@hugeicons/core-free-icons"
import { listPlans, upgradePlan, type ListPlansResponse } from "@/infra/billing/billing"
import { getSession } from "@/infra/auth/auth"

export default function UpgradePage() {
  const router = useRouter()
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null)
  const [isUpgrading, setIsUpgrading] = useState(false)

  const { data: user } = useQuery({
    queryKey: ["auth-session"],
    queryFn: getSession,
  })

  const { data: plansData, isLoading } = useQuery({
    queryKey: ["billing-plans"],
    queryFn: listPlans,
  })

  const { mutate: upgrade } = useMutation({
    mutationFn: (planName: string) =>
      upgradePlan(user?.organization_id || "", { new_plan: planName }),
    onSuccess: () => {
      toast.success("Plano atualizado com sucesso!")
      setIsUpgrading(false)
      router.push("/dashboard")
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Erro ao atualizar plano")
      setIsUpgrading(false)
    },
  })

  const handleUpgrade = (planName: string) => {
    if (!user?.organization_id) {
      toast.error("Usuário não autenticado")
      return
    }
    setSelectedPlan(planName)
    setIsUpgrading(true)
    upgrade(planName)
  }

  if (isLoading) {
    return <div className="w-full flex items-center justify-center p-6 h-screen">Carregando planos...</div>
  }

  const plans = plansData?.plans || []

  return (
    <div className="w-full flex flex-col p-6">
      <Button
        variant='ghost'
        className="flex items-center gap-2 text-sm font-medium text-foreground transition-colors hover:text-foreground mb-8 w-fit"
        onClick={() => router.back()}
      >
        <HugeiconsIcon icon={ArrowLeft02Icon} strokeWidth={2} />
        Voltar
      </Button>

      <div className="flex-1 flex flex-col">
        <div className="mx-auto flex max-w-5xl flex-col gap-8 w-full">
          <div className="space-y-3">
            <h1 className="text-4xl font-semibold">Atualize para desbloquear mais poder</h1>
            <p className="text-muted-foreground">
              Escolha o plano que acompanha seu crescimento: créditos extras, exportação 4K, automações e time colaborativo.
            </p>
          </div>
          <div className="flex flex-col gap-4 md:grid md:grid-cols-3">
            {plans.map((plan) => (
              <div
                key={plan.name}
                className={`rounded-3xl border p-6 ${plan.name === "Creator" ? "border-primary" : "border-border"}`}
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xl font-semibold">{plan.name}</h3>
                    {plan.name === "Creator" ? (
                      <span className="rounded-lg bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                        Mais popular
                      </span>
                    ) : null}
                  </div>
                  <div className="space-x-2 text-3xl font-bold">
                    <span>${plan.price_usd}</span>
                    <span className="text-base font-medium text-muted-foreground">/mês</span>
                  </div>
                  <p className="text-sm text-muted-foreground">{plan.credits_monthly} créditos/mês</p>
                </div>
                <Button
                  onClick={() => handleUpgrade(plan.name)}
                  disabled={isUpgrading && selectedPlan === plan.name}
                  className={`mt-6 w-full rounded-lg ${plan.name === "Creator" ? "bg-primary text-primary-foreground" : "bg-secondary"}`}
                  variant={plan.name === "Creator" ? "default" : "secondary"}
                >
                  {isUpgrading && selectedPlan === plan.name ? "Atualizando..." : "Assinar"}
                </Button>
                <div className="mt-6 space-y-3 text-sm text-muted-foreground">
                  <div className="flex items-center gap-3">
                    <span className="text-primary">•</span>
                    <span>Workspace privado</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-primary">•</span>
                    <span>{plan.credits_monthly} créditos mensais</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-primary">•</span>
                    <span>Suporte prioritário</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
