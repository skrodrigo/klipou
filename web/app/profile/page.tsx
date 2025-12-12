"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { IconArrowLeft } from "@tabler/icons-react"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"


export default function ProfilePage() {
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
          <div className="flex flex-wrap gap-2 rounded-md">
            <h1 className="text-2xl mb-8 text-foreground">Perfil</h1>
          </div>

          <div className="grid gap-6 rounded-3xl lg:grid-cols-2">
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
                  <Input defaultValue="Rodrigo Carvalho" className="h-11 rounded-md" />
                </div>
                <div className="grid gap-2">
                  <label className="text-sm text-muted-foreground">Email</label>
                  <Input type="email" defaultValue="rodrigoa0987@gmail.com" className="h-11 rounded-md" />
                </div>
                <div className="flex gap-3">
                  <Button className="rounded-md">Salvar alterações</Button>
                  <Button variant="outline" className="rounded-md">
                    Atualizar senha
                  </Button>
                </div>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
