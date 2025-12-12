"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { IconArrowLeft } from "@tabler/icons-react"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"

const tabs = [
  { label: "Perfil", value: "profile" },
]

const seats = [
  {
    id: "owner",
    name: "Rodrigo Carvalho",
    email: "rodrigoa0987@gmail.com",
    role: "Owner",
    avatar: "https://avatars.githubusercontent.com/u/142619236?v=4",
  },
]

export default function ProfilePage() {
  const router = useRouter()
  const [activeTab, setActiveTab] = useState("profile")

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto flex max-w-7xl flex-col gap-8 p-6 md:p-10">
        <button
          className="flex items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
          onClick={() => router.back()}
        >
          <IconArrowLeft className="size-4" /> Voltar
        </button>


        <div className="flex flex-wrap gap-2 rounded-2xl">
          {tabs.map((tab) => (
            <Button
              key={tab.value}
              variant={activeTab === tab.value ? "default" : "ghost"}
              className="rounded-lg"
              onClick={() => setActiveTab(tab.value)}
            >
              {tab.label}
            </Button>
          ))}
        </div>

        {activeTab === "profile" && <ProfileInfo />}
      </div>
    </div>
  )
}

function ProfileInfo() {
  return (
    <div className="grid gap-6 rounded-3xl  lg:grid-cols-2">
      <div className="space-y-4">
        <div className="flex items-center gap-4">
          <Avatar className="size-16">
            <AvatarImage src="https://avatars.githubusercontent.com/u/142619236?v=4" alt="Rodrigo" />
            <AvatarFallback>RC</AvatarFallback>
          </Avatar>
          <div>
            <p className="text-xl font-semibold">Rodrigo Carvalho</p>
            <p className="text-muted-foreground">rodrigoa0987@gmail.com</p>
          </div>
        </div>
        <Separator />
        <form className="space-y-4">
          <div className="grid gap-2">
            <label className="text-sm text-muted-foreground">Nome</label>
            <Input defaultValue="Rodrigo Carvalho" className="h-11 rounded-2xl" />
          </div>
          <div className="grid gap-2">
            <label className="text-sm text-muted-foreground">Email</label>
            <Input type="email" defaultValue="rodrigoa0987@gmail.com" className="h-11 rounded-2xl" />
          </div>
          <div className="flex gap-3">
            <Button className="rounded-lg">Salvar alterações</Button>
            <Button variant="outline" className="rounded-lg">
              Atualizar senha
            </Button>
          </div>
        </form>
      </div>

    </div>
  )
}

