"use client"

import React, { useState } from "react"
import { X } from "lucide-react"
import { Button } from "@/components/ui/button"
import Image from "next/image"

export default function AccountsPage() {
  const [showModal, setShowModal] = useState(false)

  const accounts = [
    { name: "TikTok", icon: "/social/tiktok.svg", status: "Conectar", desc: "Feed ou Inbox" },
    { name: "LinkedIn", icon: "/social/linkedin.svg", status: "Conectar", desc: "Feed" },
    { name: "YouTube", icon: "/social/shorts.svg", status: "Conectar", desc: "Feed" },
    { name: "Facebook", icon: "/social/facebook.svg", status: "Conectar", desc: "Feed" },
    { name: "Instagram", icon: "/social/instagram.svg", status: "Conectar", desc: "Feed" },
    { name: "X", icon: "/social/x.svg", status: "Desconectar", desc: "Feed", connected: true },
  ]

  return (
    <div className="flex-1 p-12">
      <h1 className="text-2xl mb-8 text-foreground">Contas</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {accounts.map((acc) => (
          <div key={acc.name} className="bg-card border border-border rounded-xl p-6 flex flex-col h-48">
            <Image src={acc.icon} alt={acc.name} width={30} height={30} className="h-[30px] mb-4" />
            <h3 className="text-lg font-semibold text-foreground">{acc.name}</h3>
            <p className="text-muted-foreground text-sm mb-auto">{acc.desc}</p>

            <Button
              variant={acc.connected ? "destructive" : "default"}
              className="w-full"
              onClick={() => !acc.connected && setShowModal(true)}
            >
              {acc.status}
            </Button>
          </div>
        ))}
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center">
          <div className="bg-card border border-border rounded-2xl p-8 w-full max-w-md relative">
            <button
              onClick={() => setShowModal(false)}
              className="absolute top-4 right-4 text-muted-foreground hover:text-foreground"
            >
              <X size={20} />
            </button>

            <div className="text-center">
              <h2 className="text-xl font-bold text-foreground mb-2">Conecte uma conta primeiro</h2>
              <p className="text-muted-foreground text-sm mb-8">
                Você só pode postar em redes se conectar pelo menos uma primeiro
              </p>

              <Button className="w-full h-12" onClick={() => setShowModal(false)}>
                Conectar Conta
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
