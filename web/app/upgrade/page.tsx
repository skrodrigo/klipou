"use client"

import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { IconArrowLeft } from "@tabler/icons-react"

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

export default function UpgradePage() {
  const router = useRouter()

  return (
    <div className="w-full flex flex-col p-6">
      <button
        className="flex items-center gap-2 text-sm font-medium text-foreground transition-colors hover:text-foreground mb-8 w-fit"
        onClick={() => router.back()}
      >
        <IconArrowLeft className="size-4" /> Voltar
      </button>

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
                className={`rounded-3xl border p-6 ${plan.highlight ? "border-primary" : "border-border"
                  }`}
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xl font-semibold">{plan.name}</h3>
                    {plan.tag ? (
                      <span className="rounded-lg bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                        {plan.tag}
                      </span>
                    ) : null}
                  </div>
                  <div className="space-x-2 text-3xl font-bold">
                    {plan.oldPrice ? (
                      <span className="text-muted-foreground line-through text-lg">
                        {plan.oldPrice}
                      </span>
                    ) : null}
                    <span>{plan.price}</span>
                    <span className="text-base font-medium text-muted-foreground">/mês</span>
                  </div>
                  <p className="text-sm text-muted-foreground">{plan.cadence}</p>
                </div>
                <Button
                  className={`mt-6 w-full rounded-lg ${plan.highlight ? "bg-primary text-primary-foreground" : "bg-secondary"
                    }`}
                  variant={plan.highlight ? "default" : "secondary"}
                >
                  {plan.cta}
                </Button>
                <div className="mt-6 space-y-3 text-sm text-muted-foreground">
                  {plan.perks.map((perk) => (
                    <div key={perk} className="flex items-center gap-3">
                      <span className="text-primary">•</span>
                      <span>{perk}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
