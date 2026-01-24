"use client"

import { format, isValid, parseISO, setHours, setMinutes, startOfDay } from "date-fns"
import * as React from "react"

import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"

type TimeSlot = {
  available: boolean
  time: string
}

function buildDefaultTimeSlots(): TimeSlot[] {
  const slots: TimeSlot[] = []
  for (let hour = 9; hour <= 17; hour++) {
    for (const minute of [0, 30]) {
      if (hour === 17 && minute === 30) {
        slots.push({ available: true, time: "17:30" })
        continue
      }
      if (hour === 17 && minute === 0) {
        slots.push({ available: true, time: "17:00" })
        continue
      }
      if (hour === 17 && minute === 30) continue

      const h = String(hour).padStart(2, "0")
      const m = String(minute).padStart(2, "0")
      slots.push({ available: true, time: `${h}:${m}` })
    }
  }
  return slots
}

function parseDateTimeLocal(value: string): Date | null {
  if (!value) return null

  // Accept ISO or datetime-local
  const parsedIso = parseISO(value)
  if (isValid(parsedIso)) return parsedIso

  return null
}

function toDateTimeLocalString(date: Date): string {
  return format(date, "yyyy-MM-dd'T'HH:mm")
}

type SchedulePickerProps = {
  value: string
  onChange: (value: string) => void
  className?: string
  placeholder?: string
  disabled?: boolean
  timeSlots?: TimeSlot[]
}

function SchedulePicker({
  value,
  onChange,
  className,
  placeholder = "Agendar",
  disabled,
  timeSlots = buildDefaultTimeSlots(),
}: SchedulePickerProps) {
  const today = React.useMemo(() => startOfDay(new Date()), [])

  const initialDate = React.useMemo(() => {
    const parsed = parseDateTimeLocal(value)
    return parsed ?? today
  }, [today, value])

  const initialTime = React.useMemo(() => {
    const parsed = parseDateTimeLocal(value)
    if (!parsed) return null
    return format(parsed, "HH:mm")
  }, [value])

  const [open, setOpen] = React.useState(false)
  const [date, setDate] = React.useState<Date>(initialDate)
  const [time, setTime] = React.useState<string | null>(initialTime)

  React.useEffect(() => {
    const parsed = parseDateTimeLocal(value)
    if (!parsed) return

    setDate(parsed)
    setTime(format(parsed, "HH:mm"))
  }, [value])

  const displayValue = React.useMemo(() => {
    const parsed = parseDateTimeLocal(value)
    if (!parsed) return ""
    return format(parsed, "dd/MM/yyyy HH:mm")
  }, [value])

  const applyTime = (newDate: Date, timeValue: string) => {
    const [h, m] = timeValue.split(":")
    const next = setMinutes(setHours(startOfDay(newDate), Number(h)), Number(m))
    onChange(toDateTimeLocalString(next))
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          disabled={disabled}
          className={cn(
            "bg-input/30 border-input/30 text-muted-foreground hover:text-foreground inline-flex h-10 items-center justify-between gap-2 rounded-lg border px-3 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50",
            displayValue && "text-foreground",
            className
          )}
        >
          <span className={cn(!displayValue && "text-muted-foreground")}>{displayValue || placeholder}</span>
        </button>
      </PopoverTrigger>

      <PopoverContent align="end" className="w-auto p-0">
        <div className="rounded-md border">
          <div className="flex max-sm:flex-col">
            <Calendar
              className="p-2 sm:pe-5"
              disabled={[{ before: today }]}
              mode="single"
              selected={date}
              onSelect={(newDate) => {
                if (!newDate) return
                setDate(newDate)
                setTime(null)
              }}
            />

            <div className="relative w-full max-sm:h-48 sm:w-40">
              <div className="absolute inset-0 py-4 max-sm:border-t">
                <ScrollArea className="h-full sm:border-s">
                  <div className="space-y-3">
                    <div className="flex h-5 shrink-0 items-center px-5">
                      <p className="font-medium text-sm">{format(date, "EEEE, d")}</p>
                    </div>
                    <div className="grid gap-1.5 px-5 max-sm:grid-cols-2">
                      {timeSlots.map(({ time: timeSlot, available }) => (
                        <Button
                          className="w-full"
                          disabled={!available}
                          key={timeSlot}
                          onClick={() => {
                            setTime(timeSlot)
                            applyTime(date, timeSlot)
                            setOpen(false)
                          }}
                          size="sm"
                          variant={time === timeSlot ? "default" : "outline"}
                        >
                          {timeSlot}
                        </Button>
                      ))}
                    </div>
                  </div>
                </ScrollArea>
              </div>
            </div>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}

export { SchedulePicker }
