export type ProjectStatus = "in-progress" | "completed" | "draft"

export interface ProjectSummary {
  id: string
  title: string
  description: string
  lastUpdated: string
  status: ProjectStatus
  duration: string
  platform: string
}

export const sampleProjects: ProjectSummary[] = [
  {
    id: "proj-1",
    title: "Podcast em cortes verticais",
    description: "Transformar episódio #142 em 8 clipes para Reels e TikTok",
    lastUpdated: "Há 2 horas",
    status: "in-progress",
    duration: "28 min",
    platform: "Instagram",
  },
  {
    id: "proj-2",
    title: "Lançamento do curso klipai",
    description: "Sequência de vídeos para funil pago e orgânico",
    lastUpdated: "Ontem",
    status: "completed",
    duration: "12 min",
    platform: "YouTube",
  },
  {
    id: "proj-3",
    title: "Highlights da live CTO",
    description: "Selecionar 5 melhores momentos da live de produto",
    lastUpdated: "Há 3 dias",
    status: "in-progress",
    duration: "45 min",
    platform: "LinkedIn",
  },
  {
    id: "proj-4",
    title: "Reels do cliente Vizard",
    description: "Gerar 15 clipes automáticos usando IA",
    lastUpdated: "Há 1 semana",
    status: "draft",
    duration: "15 min",
    platform: "Instagram",
  },
  {
    id: "proj-5",
    title: "Campanha Black Friday",
    description: "Editar compilado de depoimentos",
    lastUpdated: "Há 2 semanas",
    status: "completed",
    duration: "22 min",
    platform: "YouTube",
  },
]
