"use client"

import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { useQuery } from "@tanstack/react-query"

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import { UnfoldMoreIcon, PlusSignIcon } from "@hugeicons/core-free-icons"
import { getSession } from "@/infra/auth/auth"

type Organization = {
  organization_id: string
  name: string
  color: string
  plan: "starter" | "pro" | "business"
  credits_available: number
}

export function TeamSwitcher() {
  const { isMobile } = useSidebar()
  const [activeOrganization, setActiveOrganization] = React.useState<Organization | null>(null)

  const { data: user } = useQuery({
    queryKey: ["auth-session"],
    queryFn: getSession,
  })

  React.useEffect(() => {
    if (user?.organization) {
      setActiveOrganization({
        organization_id: user.organization.organization_id,
        name: user.organization.name,
        color: user.organization.color,
        plan: user.organization.plan,
        credits_available: user.organization.credits_available,
      })
    }
  }, [user?.organization?.organization_id])

  if (!activeOrganization) {
    return null
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild className='w-full'>
            <SidebarMenuButton
              size="lg"
              className="data-[state=open]:bg-sidebar-accent border data-[state=open]:text-sidebar-accent-foreground"
            >
              <div
                className="border border-border text-white flex aspect-square size-8 items-center justify-center rounded-md"
                style={{ backgroundColor: activeOrganization.color }}
              >
                <span className="text-xs font-bold">{activeOrganization.name.charAt(0).toUpperCase()}</span>
              </div>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-medium">{activeOrganization.name}</span>
              </div>
              <HugeiconsIcon icon={UnfoldMoreIcon} className="ml-auto size-4" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-md"
            align="start"
            side={isMobile ? "bottom" : "right"}
            sideOffset={4}
          >
            <DropdownMenuGroup>
              <DropdownMenuLabel className="text-muted-foreground text-xs">
                Organização
              </DropdownMenuLabel>
              <DropdownMenuItem
                className="gap-2 p-2"
                disabled
              >
                <div
                  className="flex size-6 items-center justify-center rounded-md border text-white"
                  style={{ backgroundColor: activeOrganization.color }}
                >
                  <span className="text-xs font-bold">{activeOrganization.name.charAt(0).toUpperCase()}</span>
                </div>
                <div className="flex flex-col flex-1">
                  <span className="font-medium">{activeOrganization.name}</span>
                  <span className="text-xs text-muted-foreground">{activeOrganization.credits_available} créditos</span>
                </div>
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="gap-2 p-2">
              <div className="flex size-6 items-center justify-center rounded-md border bg-transparent">
                <HugeiconsIcon icon={PlusSignIcon} className="size-4" />
              </div>
              <div className="text-muted-foreground font-medium">Criar organização</div>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
