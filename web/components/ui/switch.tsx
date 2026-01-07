"use client"

import { Switch as SwitchPrimitive } from "@base-ui/react/switch"
import { cn } from "@/lib/utils"

function Switch({
  className,
  size = "default",
  ...props
}: SwitchPrimitive.Root.Props & {
  size?: "sm" | "default"
}) {
  return (
    <SwitchPrimitive.Root
      data-slot="switch"
      data-size={size}
      className={cn(
        `
        data-checked:bg-primary
        data-unchecked:bg-input
        focus-visible:border-ring
        focus-visible:ring-ring/50
        aria-invalid:ring-destructive/20
        dark:aria-invalid:ring-destructive/40
        aria-invalid:border-destructive
        dark:aria-invalid:border-destructive/50
        dark:data-unchecked:bg-input/80
        shrink-0
        rounded-full
        border
        border-transparent
        focus-visible:ring-[3px]
        aria-invalid:ring-[3px]
        data-[size=default]:h-[20px]
        data-[size=default]:w-[64px]
        data-[size=sm]:h-[16px]
        data-[size=sm]:w-[32px]
        peer
        group/switch
        relative
        inline-flex
        items-center
        transition-all
        outline-none
        after:absolute
        after:-inset-x-3
        after:-inset-y-2
        data-disabled:cursor-not-allowed
        data-disabled:opacity-50
        `,
        className
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb
        data-slot="switch-thumb"
        className="
          bg-background
          dark:data-unchecked:bg-foreground
          dark:data-checked:bg-primary-foreground
          rounded-full
          group-data-[size=default]/switch:h-4
          group-data-[size=default]/switch:w-8
          group-data-[size=sm]/switch:h-3
          group-data-[size=sm]/switch:w-6
          group-data-[size=default]/switch:data-checked:translate-x-[calc(100%-3px)]
          group-data-[size=sm]/switch:data-checked:translate-x-[calc(100%-3px)]
          group-data-[size=default]/switch:data-unchecked:translate-x-[3px]
          group-data-[size=sm]/switch:data-unchecked:translate-x-[3px]
          pointer-events-none
          block
          ring-0
          transition-transform
        "
      />
    </SwitchPrimitive.Root>
  )
}

export { Switch }
