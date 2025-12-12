"use client"

import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { IconCalendar, IconHome, IconArchive, IconAsterisk, IconLogout, IconSearch, IconUser, IconSocial, IconFileAnalytics } from "@tabler/icons-react"
import Image from "next/image"

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
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useUpgradeDialog } from "@/contexts/upgrade-dialog-context"
import { sampleProjects } from "@/lib/sample-projects"

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
    icon: IconHome,
  },
  {
    title: "Projetos",
    url: "/dashboard/projects",
    icon: IconArchive,
  },
  {
    title: "Calendário",
    url: "/dashboard/calendar",
    icon: IconCalendar,
  },
  {
    title: "Accounts",
    url: "/dashboard/accounts",
    icon: IconSocial,
  },
  {
    title: "Analytics",
    url: "/dashboard/analytics",
    icon: IconFileAnalytics,
  },
]

export function AppSidebar() {
  const router = useRouter()
  const { openDialog } = useUpgradeDialog()
  const [commandOpen, setCommandOpen] = useState(false)
  const [query, setQuery] = useState("")

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
          <div className="flex justify-between items-center">
            <Image src='/logos/klipou.svg' alt="logo" width={100} height={100} className="mt-6 w-10" />
            <DropdownMenu >
              <DropdownMenuTrigger asChild className="flex pt-4 justify-end items-end">
                <div>
                  <Avatar className="cursor-pointer h-10 w-10">
                    <AvatarImage src="https://avatars.githubusercontent.com/u/142619236?v=4" alt="Rodrigo" />
                    <AvatarFallback>RC</AvatarFallback>
                  </Avatar>
                </div>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-56">
                <DropdownMenuItem onSelect={() => router.push("/profile")}>
                  <IconUser className="mr-2 h-4 w-4 text-muted-foreground" />
                  Account
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => router.push("/")} className="focus:bg-red-200 focus:text-red-800 transition-colors">
                  <IconLogout className="mr-2 h-4 w-4 focus:text-red-800 " />
                  Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          <TeamSwitcher />
          <div className="relative w-full">
            <IconSearch className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Buscar..."
              className="h-10 rounded-lg bg-transparent pl-10 text-sm"
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
              <SidebarMenu>
                {nav.map((item) => (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton asChild >
                      <a href={item.url} className="flex justify-start items-center">
                        <item.icon />
                        <span >{item.title}</span>
                      </a>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        <div className="border-t border-border p-4 space-y-4">
          <div className="border border-border rounded-lg px-3 gap-2 py-2 flex items-center text-sm">
            <IconAsterisk className="text-accent size-4" />
            <div className="flex-1">
              <p className="text-xs text-muted-foreground leading-none">Créditos</p>
              <p className="text-sm font-medium">60 restantes</p>
            </div>
            <Button size="sm" className="bg-primary text-white h-8" onClick={openDialog}>
              Upgrade
            </Button>
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