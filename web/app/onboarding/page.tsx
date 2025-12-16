'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery, useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import {
  Stepper,
  StepperIndicator,
  StepperItem,
  StepperSeparator,
  StepperTrigger,
} from '@/components/ui/stepper'
import { HugeiconsIcon } from '@hugeicons/react'
import { ArrowLeft02Icon } from '@hugeicons/core-free-icons'
import { getSession } from '@/infra/auth/auth'
import { completeOnboarding } from '@/infra/onboarding/onboarding'
import { Spinner } from '@/components/ui/spinner'

const steps = [1, 2, 3, 4]

const colorMap: Record<string, string> = {
  blue: '#3b82f6',
  indigo: '#6366f1',
  pink: '#ec4899',
  red: '#ef4444',
  orange: '#f97316',
  amber: '#f59e0b',
  emerald: '#10b981',
}

type OnboardingData = {
  organization_name: string
  segment: string
  color: string
  platforms: string[]
  objective: string
  content_type: string
}

export default function OnboardingPage() {
  const router = useRouter()
  const [currentStep, setCurrentStep] = useState(1)
  const [isLoading, setIsLoading] = useState(false)
  const [formData, setFormData] = useState<OnboardingData>({
    organization_name: '',
    segment: '',
    color: '#3b82f6',
    platforms: [],
    objective: '',
    content_type: '',
  })

  const { data: user } = useQuery({
    queryKey: ['auth-session'],
    queryFn: getSession,
  })

  const { mutate: submitOnboarding } = useMutation({
    mutationFn: () => completeOnboarding(formData),
    onSuccess: () => {
      toast.success('Onboarding concluído com sucesso!')
      router.push('/dashboard')
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Erro ao completar onboarding')
    },
  })

  const handleNextStep = () => {
    if (currentStep === 1 && (!formData.organization_name || !formData.segment)) {
      toast.error('Por favor, preencha o nome e segmento da organização')
      return
    }
    if (currentStep === 2 && formData.platforms.length === 0) {
      toast.error('Por favor, selecione pelo menos uma plataforma')
      return
    }
    if (currentStep === 3 && !formData.objective) {
      toast.error('Por favor, selecione um objetivo')
      return
    }
    if (currentStep === 4 && !formData.content_type) {
      toast.error('Por favor, selecione um tipo de conteúdo')
      return
    }
    if (currentStep === 5) {
      // Step 5 é a última etapa, pronto para concluir
    }

    setIsLoading(true)
    setTimeout(() => {
      if (currentStep < steps.length) {
        setCurrentStep((prev) => prev + 1)
      } else {
        submitOnboarding()
      }
      setIsLoading(false)
    }, 500)
  }

  const handlePrevStep = () => {
    if (currentStep > 1) {
      setCurrentStep((prev) => prev - 1)
    }
  }

  const togglePlatform = (platform: string) => {
    setFormData((prev) => ({
      ...prev,
      platforms: prev.platforms.includes(platform)
        ? prev.platforms.filter((p) => p !== platform)
        : [...prev.platforms, platform],
    }))
  }

  return (
    <div className="w-full flex flex-col p-6 h-screen bg-gradient-to-br from-background to-muted/30">
      <Button
        variant="ghost"
        onClick={() => router.back()}
        className="flex items-center gap-2 text-foreground hover:text-foreground text-sm mb-8 w-fit"
      >
        <HugeiconsIcon icon={ArrowLeft02Icon} strokeWidth={2} />
        Voltar
      </Button>

      <div className="flex-1 flex flex-col items-center justify-center">
        <div className="w-full max-w-md space-y-8">
          {/* Stepper */}
          <Stepper onValueChange={setCurrentStep} value={currentStep}>
            {steps.map((step) => (
              <StepperItem
                className="not-last:flex-1"
                key={step}
                loading={isLoading}
                step={step}
              >
                <StepperTrigger asChild>
                  <div className="relative flex items-center justify-center">
                    {currentStep === step && (
                      <div className="absolute inset-0 bg-primary/50 rounded-full animate-ping scale-110" />
                    )}
                    <StepperIndicator />
                  </div>
                </StepperTrigger>
                {step < steps.length && <StepperSeparator />}
              </StepperItem>
            ))}
          </Stepper>

          {/* Step Content */}
          <div className="space-y-6 mb-10">
            {/* Step 1: Organization */}
            {currentStep === 1 && (
              <div className="space-y-4 animate-in fade-in">
                <div>
                  <h2 className="text-2xl font-bold mb-2">Crie sua Organização</h2>
                  <p className="text-muted-foreground">
                    Vamos começar configurando sua organização.
                  </p>
                </div>

                <div className="space-y-3">
                  <div className="space-y-2">
                    <Label htmlFor="org-name">Nome da Organização</Label>
                    <Input
                      id="org-name"
                      placeholder="Ex: Minha Empresa"
                      value={formData.organization_name}
                      onChange={(e) =>
                        setFormData((prev) => ({
                          ...prev,
                          organization_name: e.target.value,
                        }))
                      }
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="segment">Segmento</Label>
                    <Input
                      id="segment"
                      placeholder="Ex: Tecnologia, Marketing, Educação"
                      value={formData.segment}
                      onChange={(e) =>
                        setFormData((prev) => ({
                          ...prev,
                          segment: e.target.value,
                        }))
                      }
                    />
                  </div>

                  <div className="space-y-3">
                    <Label>Cor da Organização</Label>
                    <RadioGroup
                      value={Object.keys(colorMap).find(key => colorMap[key] === formData.color) || 'blue'}
                      onValueChange={(value) =>
                        setFormData((prev) => ({
                          ...prev,
                          color: colorMap[value as keyof typeof colorMap] || formData.color,
                        }))
                      }
                      className="flex gap-2"
                    >
                      {Object.entries(colorMap).map(([name, hex]) => (
                        <div key={name} className="flex items-center">
                          <RadioGroupItem
                            value={name}
                            id={`color-${name}`}
                            aria-label={name.charAt(0).toUpperCase() + name.slice(1)}
                            className={`size-6 border-2 shadow-none data-[state=checked]:ring-2 data-[state=checked]:ring-offset-2 data-[state=checked]:ring-foreground`}
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
              </div>
            )}

            {/* Step 2: Platforms */}
            {currentStep === 2 && (
              <div className="space-y-4 animate-in fade-in">
                <div>
                  <h2 className="text-2xl font-bold mb-2">Onde você publica hoje?</h2>
                  <p className="text-muted-foreground">
                    Selecione uma ou mais plataformas.
                  </p>
                </div>

                <Label>Plataformas de Publicação</Label>
                <div className="space-y-2">
                  {['TikTok', 'Instagram Reels', 'YouTube Shorts', 'LinkedIn', 'X (Twitter)'].map(
                    (platform) => (
                      <label
                        key={platform}
                        className="flex items-center gap-3 p-3 rounded-lg border border-border hover:bg-muted/50 cursor-pointer transition-all"
                      >
                        <Checkbox
                          checked={formData.platforms.includes(platform)}
                          onCheckedChange={() => togglePlatform(platform)}
                        />
                        <span className="font-medium">{platform}</span>
                      </label>
                    )
                  )}
                </div>
              </div>
            )}

            {/* Step 3: Objective */}
            {currentStep === 3 && (
              <div className="space-y-4 animate-in fade-in">
                <div>
                  <h2 className="text-2xl font-bold mb-2">Qual é seu principal objetivo?</h2>
                  <p className="text-muted-foreground">
                    Isso influencia como selecionamos os melhores trechos.
                  </p>
                </div>

                <Label>Objetivo Principal</Label>
                <div className="space-y-2">
                  {['Alcance / viralização', 'Leads / vendas', 'Autoridade / marca pessoal', 'Reaproveitamento de conteúdo', 'Engajamento / comunidade'].map(
                    (objective) => (
                      <label
                        key={objective}
                        className="flex items-center gap-3 p-3 rounded-lg border border-border hover:bg-muted/50 cursor-pointer transition-all"
                      >
                        <Checkbox
                          checked={formData.objective === objective}
                          onCheckedChange={() =>
                            setFormData((prev) => ({
                              ...prev,
                              objective: formData.objective === objective ? '' : objective,
                            }))
                          }
                        />
                        <span className="font-medium">{objective}</span>
                      </label>
                    )
                  )}
                </div>
              </div>
            )}

            {/* Step 4: Content Type */}
            {currentStep === 4 && (
              <div className="space-y-4 animate-in fade-in">
                <div>
                  <h2 className="text-2xl font-bold mb-2">Qual é seu principal tipo de conteúdo?</h2>
                  <p className="text-muted-foreground">
                    Isso nos ajuda a personalizar a análise dos seus vídeos.
                  </p>
                </div>

                <Label>Tipo de Conteúdo</Label>
                <div className="space-y-2">
                  {['Podcast', 'Curso / Aula', 'Conteúdo educacional curto', 'Marketing / Ads', 'Conteúdo pessoal / criador'].map(
                    (type) => (
                      <label
                        key={type}
                        className="flex items-center gap-3 p-3 rounded-lg border border-border hover:bg-muted/50 cursor-pointer transition-all"
                      >
                        <Checkbox
                          checked={formData.content_type === type}
                          onCheckedChange={() =>
                            setFormData((prev) => ({
                              ...prev,
                              content_type: formData.content_type === type ? '' : type,
                            }))
                          }
                        />
                        <span className="font-medium">{type}</span>
                      </label>
                    )
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Navigation Buttons */}
          <div className="flex justify-between gap-4">
            <Button
              className="w-32"
              disabled={currentStep === 1}
              onClick={handlePrevStep}
              variant="outline"
            >
              Anterior
            </Button>

            <Button
              className="w-32"
              disabled={isLoading}
              onClick={handleNextStep}
              variant="default"
            >
              {isLoading ? <Spinner /> : currentStep === steps.length ? 'Concluir' : 'Próximo'}
            </Button>
          </div>

        </div>
      </div>
    </div>
  )
}
