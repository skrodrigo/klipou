"use client"

import { useRouter } from "next/navigation"
import { useQuery, useMutation } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowLeft02Icon } from "@hugeicons/core-free-icons"
import { getSession, updateProfile, type UpdateProfilePayload } from "@/infra/auth/auth"

export default function ProfilePage() {
  const router = useRouter()
  const [email, setEmail] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)

  const { data: user, isLoading } = useQuery({
    queryKey: ["auth-session"],
    queryFn: getSession,
  })

  const { mutate: updateUserProfile } = useMutation({
    mutationFn: (payload: UpdateProfilePayload) => updateProfile(payload),
    onSuccess: () => {
      toast.success("Perfil atualizado com sucesso!")
      setIsSubmitting(false)
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Erro ao atualizar perfil")
      setIsSubmitting(false)
    },
  })

  const handleSaveChanges = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || isSubmitting) return

    setIsSubmitting(true)
    updateUserProfile({ email })
  }

  if (isLoading) {
    return <div className="w-full flex items-center justify-center p-6 h-screen">Carregando...</div>
  }

  const userInitials = user?.email?.split("@")[0]?.substring(0, 2).toUpperCase() || "U"

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
          <div className="flex flex-wrap gap-2 rounded-md">
            <h1 className="text-2xl mb-8 text-foreground">Perfil</h1>
          </div>

          <div className="grid gap-6 rounded-3xl lg:grid-cols-2">
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <Avatar className="size-16">
                  <AvatarImage src="" alt={user?.email} />
                  <AvatarFallback>{userInitials}</AvatarFallback>
                </Avatar>
                <div>
                  <p className="text-xl font-semibold">{user?.email}</p>
                  <p className="text-muted-foreground">Usuário KlipAI</p>
                </div>
              </div>
              <Separator />
              <form onSubmit={handleSaveChanges} className="space-y-4">
                <div className="grid gap-2">
                  <label className="text-sm text-muted-foreground">Email</label>
                  <Input
                    type="email"
                    value={email || user?.email || ""}
                    onChange={(e) => setEmail(e.target.value)}
                    className="h-11 rounded-md"
                  />
                </div>
                <div className="flex gap-3">
                  <Button type="submit" disabled={isSubmitting} className="rounded-md">
                    {isSubmitting ? "Salvando..." : "Salvar alterações"}
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
