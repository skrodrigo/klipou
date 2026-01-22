"use client"

import * as React from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { createOrganization } from "@/infra/auth/auth"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { toast } from "sonner"

interface CreateOrganizationDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

const colorMap: Record<string, string> = {
  blue: "#3b82f6",
  indigo: "#6366f1",
  pink: "#ec4899",
  red: "#ef4444",
  orange: "#f97316",
  amber: "#f59e0b",
  emerald: "#10b981",
}

export function CreateOrganizationDialog({ open, onOpenChange }: CreateOrganizationDialogProps) {
  const queryClient = useQueryClient()
  const [name, setName] = React.useState("")
  const [color, setColor] = React.useState<string>(colorMap.blue)

  const { mutate: createOrg, isPending } = useMutation({
    mutationFn: createOrganization,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auth-session"] })
      queryClient.invalidateQueries({ queryKey: ["organizations"] })
      toast.success("Organization created successfully")
      onOpenChange(false)
    },
    onError: () => {
      toast.error("Failed to create organization")
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (name.trim()) {
      createOrg({ name: name.trim(), color })
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create Organization</DialogTitle>
          <DialogDescription>
            Enter a name for your new organization.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="name" className="text-right">
                Name
              </Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="col-span-3"
                placeholder="Acme Inc."
              />
            </div>

            <div className="grid grid-cols-4 items-center gap-4">
              <Label className="text-right">Color</Label>
              <RadioGroup
                value={Object.keys(colorMap).find((key) => colorMap[key] === color) || "blue"}
                onValueChange={(value) => setColor(colorMap[value as keyof typeof colorMap] || color)}
                className="col-span-3 flex gap-2"
              >
                {Object.entries(colorMap).map(([key, hex]) => (
                  <div key={key} className="flex items-center">
                    <RadioGroupItem
                      value={key}
                      id={`create-org-color-${key}`}
                      aria-label={key}
                      className="size-6 border-2 shadow-none data-[state=checked]:ring-2 data-[state=checked]:ring-offset-2 data-[state=checked]:ring-foreground"
                      indicatorClassName="text-foreground"
                      style={{
                        backgroundColor: hex,
                        borderColor: hex,
                      }}
                    />
                  </div>
                ))}
              </RadioGroup>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isPending || !name.trim()}>
              {isPending ? "Creating..." : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
