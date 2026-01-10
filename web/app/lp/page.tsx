"use client"

import Image from "next/image"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useRef, useState } from "react"

import { AttachmentIcon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"

import { Button } from "@/components/ui/button"
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { useVideoStore } from "@/lib/store/video-store"
import { cn } from "@/lib/utils"

const navLinks = [
  { label: "Blog", href: "/blog" },
  { label: "Pricing", href: "/pricing" },
  { label: "Use cases", href: "#use-cases" },
  { label: "Tools", href: "#tools" },
  { label: "Affiliates", href: "/affiliates" },
]

export default function LandingPage() {
  const [files, setFiles] = useState<File[]>([])
  const [isDragging, setIsDragging] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [sourceUrl, setSourceUrl] = useState("")
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const router = useRouter()
  const { setVideoFile, clearVideo } = useVideoStore()

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files ?? [])
    const videoFiles = selected.filter((f) => f.type.startsWith("video"))
    if (videoFiles.length > 0) {
      setFiles([videoFiles[0]])
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const droppedFiles = Array.from(e.dataTransfer.files ?? [])
    const videoFiles = droppedFiles.filter((f) => f.type.startsWith("video"))
    if (videoFiles.length > 0) {
      setFiles([videoFiles[0]])
    }
  }

  const handleContinue = async () => {
    if (isSubmitting) return

    setIsSubmitting(true)
    try {
      const file = files[0]
      const trimmedUrl = sourceUrl.trim()

      if (file) {
        clearVideo()
        setVideoFile(file)
        router.push("/dashboard")
        return
      }

      if (trimmedUrl) {
        clearVideo()
        router.push(`/dashboard?sourceUrl=${encodeURIComponent(trimmedUrl)}`)
        return
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-dvh bg-background text-foreground">
      <header className="fixed left-0 right-0 top-0 z-50 bg-gradient-to-b from-background via-background to-transparent">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
          <div className="flex items-center gap-8">
            <Link href="/" className="flex items-center gap-2 font-semibold">
              <Image
                src="/logos/klipai.svg"
                alt="Klip AI"
                width={32}
                height={32}
                className="rounded-md"
              />
              <span>Klip AI</span>
            </Link>
          </div>

          <nav className="hidden items-center gap-6 text-sm text-muted-foreground md:flex">
            {navLinks.map((l) => (
              <Link
                key={l.label}
                href={l.href}
                className="hover:text-foreground transition-colors"
              >
                {l.label}
              </Link>
            ))}
          </nav>
          <div className="hidden items-center gap-2 md:flex">
            <Button asChild variant="ghost" size="sm">
              <Link href="/login">Login</Link>
            </Button>
            <Button asChild size="sm">
              <Link href="/signup">Cadastro</Link>
            </Button>
          </div>

          <div className="md:hidden">
            <Button
              className="group"
              variant="outline"
              size="icon"
              onClick={() => setMobileMenuOpen((prev) => !prev)}
              aria-expanded={mobileMenuOpen}
              aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
            >
              <svg
                className="pointer-events-none"
                width={16}
                height={16}
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M4 12L20 12"
                  className="origin-center -translate-y-[7px] transition-all duration-300 [transition-timing-function:cubic-bezier(.5,.85,.25,1.1)] group-aria-expanded:translate-x-0 group-aria-expanded:translate-y-0 group-aria-expanded:rotate-[315deg]"
                />
                <path
                  d="M4 12H20"
                  className="origin-center transition-all duration-300 [transition-timing-function:cubic-bezier(.5,.85,.25,1.8)] group-aria-expanded:rotate-45"
                />
                <path
                  d="M4 12H20"
                  className="origin-center translate-y-[7px] transition-all duration-300 [transition-timing-function:cubic-bezier(.5,.85,.25,1.1)] group-aria-expanded:translate-y-0 group-aria-expanded:rotate-[135deg]"
                />
              </svg>
            </Button>

            <Drawer open={mobileMenuOpen} onOpenChange={setMobileMenuOpen} direction="bottom">
              <DrawerContent>
                <DrawerHeader>
                  <DrawerTitle>Navegação</DrawerTitle>
                </DrawerHeader>

                <div className="px-4 pb-4">
                  <div className="flex flex-col gap-2">
                    {navLinks.map((l) => (
                      <DrawerClose key={l.label} asChild>
                        <Link
                          href={l.href}
                          className="hover:bg-muted flex items-center rounded-md px-3 py-2 text-sm"
                        >
                          {l.label}
                        </Link>
                      </DrawerClose>
                    ))}
                  </div>
                </div>

                <DrawerFooter>
                  <DrawerClose asChild>
                    <Button asChild variant="outline" className="w-full">
                      <Link href="/login">Login</Link>
                    </Button>
                  </DrawerClose>
                  <DrawerClose asChild>
                    <Button asChild className="w-full">
                      <Link href="/signup">Cadastro</Link>
                    </Button>
                  </DrawerClose>
                </DrawerFooter>
              </DrawerContent>
            </Drawer>
          </div>
        </div>
      </header>

      <main>
        <section className="relative overflow-hidden">
          <div className="mx-auto max-w-6xl px-4 py-16 md:py-24">
            <div className="mx-auto flex max-w-3xl flex-col items-center text-center">
              <h1 className="mt-4 text-balance font-dm-sans text-5xl tracking-tight md:text-6xl">
                1 video, 10 clips. Crie e escale 10x mais rápido.
              </h1>
              <div className="mt-10 relative flex w-full flex-col gap-3 sm:flex-row sm:items-center">
                <div className="pointer-events-none absolute -inset-6 -z-10 rounded-2xl bg-primary/25 blur-3xl" />

                <div
                  className={cn(
                    "relative rounded-md transition-all flex-1 bg-card",
                    isDragging ? "" : "border-border"
                  )}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                >
                  <div className="flex w-full items-center gap-3 border border-border rounded-md">
                    <input
                      hidden
                      onChange={handleFileChange}
                      ref={fileInputRef}
                      type="file"
                      accept="video/*"
                      multiple
                    />
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="text-muted-foreground p-3 border-border hover:text-foreground transition-colors"
                    >
                      <HugeiconsIcon icon={AttachmentIcon} size={16} />
                    </button>
                    <Input
                      placeholder="Paste link or drag your video here"
                      className="h-12 flex-1 min-w-0 focus-visible:ring-0 focus-visible:ring-offset-0 placeholder:text-muted-foreground !bg-transparent"
                      value={sourceUrl}
                      onChange={(e) => setSourceUrl(e.target.value)}
                    />
                  </div>
                </div>

                <Button
                  className="h-12 w-full rounded-md font-semibold sm:w-auto"
                  disabled={(!files.length && !sourceUrl.trim()) || isSubmitting}
                  onClick={handleContinue}
                >
                  {isSubmitting ? <Spinner /> : "Continue"}
                </Button>
              </div>
            </div>
          </div>
        </section>
      </main>

    </div>
  )
}