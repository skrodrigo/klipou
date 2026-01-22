"use client"

import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import Image from "next/image"
import { HugeiconsIcon } from "@hugeicons/react"
import { useQuery } from "@tanstack/react-query"
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import { TeamSwitcher } from "@/components/ui/team-switcher"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useUpgradeDialog } from "@/contexts/upgrade-dialog-context"
import { sampleProjects } from "@/lib/events/sample-projects"
import { Analytics01Icon, Archive03Icon, Calendar01Icon, FallingStarIcon, Home07Icon, LogoutSquare02Icon, Search01Icon, UserSquareIcon } from "@hugeicons/core-free-icons"
import { getSession } from "@/infra/auth/auth"
import { getOrganizationCredits } from "@/infra/videos/videos"

type CommandOption = {
  label: string
  value: string
  description?: string
}

const quickLinks: CommandOption[] = [
  { label: "Dashboard", value: "/dashboard" },
  { label: "Projetos", value: "/dashboard/projects" },
  { label: "Calendário", value: "/dashboard/calendar" },
  { label: "Perfil", value: "/profile" },
]

const nav = [
  {
    title: "Home",
    url: "/dashboard",
    icon: Home07Icon,
  },
  {
    title: "Projetos",
    url: "/dashboard/projects",
    icon: Archive03Icon,
  },
  {
    title: "Calendário",
    url: "/dashboard/calendar",
    icon: Calendar01Icon,
  },
  {
    title: "Accounts",
    url: "/dashboard/accounts",
    icon: UserSquareIcon,
  },
  {
    title: "Analytics",
    url: "/dashboard/analytics",
    icon: Analytics01Icon,
  },
]

export function AppSidebar() {
  const router = useRouter()
  const { openDialog } = useUpgradeDialog()
  const [commandOpen, setCommandOpen] = useState(false)
  const [query, setQuery] = useState("")

  const { data: user } = useQuery({
    queryKey: ["auth-session"],
    queryFn: getSession,
  })

  const { data: credits } = useQuery({
    queryKey: ["organization-credits", user?.organization_id],
    queryFn: () => getOrganizationCredits(user?.organization_id || ""),
    enabled: !!user?.organization_id,
  })

  const commandOptions = useMemo<CommandOption[]>(() => {
    const projectItems = sampleProjects.map((project) => ({
      label: project.title,
      description: project.description,
      value: `/dashboard/projects#${project.id}`,
    }))
    return [...quickLinks, ...projectItems]
  }, [])

  const filteredOptions = commandOptions.filter((option) =>
    option.label.toLowerCase().includes(query.toLowerCase())
  )

  const handleSelect = (value: string) => {
    setCommandOpen(false)
    setQuery("")
    router.push(value)
  }

  return (
    <>
      <Sidebar>
        <SidebarHeader className="space-y-4">
          <Image
            src='/logos/klipai.svg'
            alt="logo"
            width={32}
            height={32}
            className="ml-1 mt-3 rounded-md"
            priority
            quality={100} />
          <TeamSwitcher />
          <div className="relative w-full bg-card rounded-md">
            <HugeiconsIcon size={16} icon={Search01Icon} className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Buscar..."
              className="h-10 rounded-md bg-transparent pl-10 text-sm"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value)
                setCommandOpen(true)
              }}
              onFocus={() => setCommandOpen(true)}
            />
          </div>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu className="space-y-2">
                {nav.map((item) => (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton
                      onClick={() => router.push(item.url)}
                      className="flex justify-start gap-2 items-center w-full cursor-pointer"
                    >
                      <HugeiconsIcon size={16} icon={item.icon} className="size-4" />
                      <span>{item.title}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        <div className="border-t border-border flex  justify-center items-center py-4 gap-4 ">
          <div className="border border-border rounded-md px-3 gap-2 py-2 flex items-center text-sm">
            <HugeiconsIcon size={16} icon={FallingStarIcon} className="text-accent size-4" />
            <div className="flex-1">
              <p className="text-xs text-muted-foreground leading-none">Créditos</p>
              <p className="text-sm font-medium">
                {credits ? `${credits.credits_available} ` : "0"}
              </p>
            </div>
            <Button size="sm" className="bg-primary text-white h-8" onClick={openDialog}>
              Upgrade
            </Button>
          </div>
          <div className="flex justify-between items-center">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <div className="flex justify-end items-end cursor-pointer">
                  <Avatar className="h-10 w-10">
                    <AvatarImage src="https://avatars.githubusercontent.com/u/142619236?v=4" alt="Rodrigo" />
                    <AvatarFallback>RC</AvatarFallback>
                  </Avatar>
                </div>
              </DropdownMenuTrigger>

              <DropdownMenuContent align="start" className="w-56">
                <DropdownMenuItem onSelect={() => router.push("/profile")}>
                  <HugeiconsIcon size={16} icon={UserSquareIcon} className="mr-2 h-4 w-4 text-muted-foreground" />
                  Account
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => router.push("/")} className="focus:bg-destructive transition-colors">
                  <HugeiconsIcon size={16} icon={LogoutSquare02Icon} className="mr-2 h-4 w-4 focus:text-white" />
                  Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </Sidebar>

      <CommandDialog open={commandOpen} onOpenChange={setCommandOpen}>
        <CommandInput
          placeholder="Pesquise por rotas ou projetos"
          value={query}
          onValueChange={(value) => setQuery(value)}
        />
        <CommandList>
          <CommandEmpty>Nenhum resultado encontrado.</CommandEmpty>
          <CommandGroup heading="Resultados">
            {filteredOptions.map((option) => (
              <CommandItem key={option.value} value={option.value} onSelect={handleSelect}>
                <div className="flex flex-col">
                  <span className="font-medium">{option.label}</span>
                  {option.description ? (
                    <span className="text-xs text-muted-foreground">{option.description}</span>
                  ) : null}
                </div>
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </>
  )
}