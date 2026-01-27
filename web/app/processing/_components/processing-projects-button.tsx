"use client"

import { Button } from "@/components/ui/button"
import { LogoutSquare02Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"

type Props = {
  onClick: () => void
}

export function ProcessingProjectsButton({ onClick }: Props) {
  return (
    <Button
      onClick={onClick}
      className=" bg-foreground text-background rounded-md hover:bg-foreground/90 transition-colors"
    >
      <HugeiconsIcon size={16} icon={LogoutSquare02Icon} strokeWidth={2} className="text-background" />
      Ir para Projetos
    </Button>
  )
}
