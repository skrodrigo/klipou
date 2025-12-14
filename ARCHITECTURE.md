# Arquitetura completa – Klipai 

## Stack fixa

- **Front-end**: Next.js
- **API**: Django REST
- **Banco**: PostgreSQL
- **Fila**: RabbitMQ
- **Workers**: Celery
- **IA local**: Whisper
- **IA externa**: Gemini API (análise semântica + embeddings)
- **Mídia**: FFmpeg
- **Storage**: Cloudflare R2
- **Entrega**: SSE (Webhooks depois)

## Visão geral do fluxo

Arquitetura assíncrona, batch, orientada a jobs, com upload direto ao storage e processamento desacoplado.

Suporta múltiplas fontes de vídeo: upload local, download de redes sociais (YouTube, TikTok, Instagram, etc).

---

## Fluxo ponta a ponta (passo a passo)

### 1. Ingestion (Ingestão)

**Múltiplas fontes:**
- Upload direto da máquina do usuário
- Download de redes sociais (YouTube, TikTok, Instagram, etc)
- Link externo

**Front solicita URL assinada** (apenas para upload local).

**Upload direto para R2** (ou download automático para redes sociais).

**Front envia para API:**
- `video_id`
- `source_type` (upload | youtube | tiktok | instagram | url)
- `source_url` (se aplicável)

**Status → ingestion**

---

### 2. Criação do Job

API cria registro com:
- `user_id`
- `organization_id`
- `video_id`
- `status = queued`
- **Configurações do usuário:**
  - `language` (idioma do vídeo: pt-BR, en, es, etc)
  - `target_ratios` (proporções desejadas: 9:16, 1:1, 16:9, etc)
  - `max_clip_duration` (duração máxima de cada clip em segundos)
  - `num_clips` (número de clips a gerar: padrão 5)
  - `auto_schedule` (ativar agendamento automático: true/false)

Publica job no RabbitMQ.

**Status → queued**

---

### 3. Download (Worker)

Baixa vídeo do R2 ou da fonte externa (stream).

Valida:
- duração
- tamanho
- codec
- resolução

**Status → downloading**

---

### 4. Normalização

Converte vídeo para formato padrão (codec, resolução, frame rate).

Garante compatibilidade com etapas seguintes.

**Status → normalizing**

---

### 5. Transcrição (Whisper)

Executa Whisper local.

Gera:
- **transcrição completa** (texto bruto com timestamps)
- **timestamps por segmento** (início/fim de cada frase)
- **timestamps por palavra** (para legendagem ASS e karaoke)

Salva:
- JSON bruto (estruturado com timestamps por palavra)
- SRT (para compatibilidade)

**Retorna para exibição:**
- Transcrição completa exibida na página de clipes
- Permite usuário visualizar o que foi transcrito
- Reutilizável para legendagem e análise

Upload no R2.

**Status → transcribing**

**Regra:**
- Sem pós-processamento caro
- Timestamps por palavra são obrigatórios (necessários para ASS/karaoke)

---

### 6. Análise Semântica (Gemini)

Envia apenas **texto da transcrição** (nunca vídeo).

**Gemini retorna:**
- **Título do vídeo** (título sugerido para o vídeo original)
- **Descrição** (descrição para publicação)
- **Trechos candidatos** (segmentos com timestamps)
- **Score de engajamento** (0-10 para cada trecho)
- **Possíveis hooks/títulos** (para cada clip)
- **Análise de tom/emoção**

**Status → analyzing**

**Regra:**
- Gemini nunca recebe vídeo
- Retry controlado
- Fallback: heurística local

---

### 7. Embedding e Classificação (Gemini)

Usa **Gemini API para gerar embeddings** do texto dos trechos candidatos.

Compara embeddings com:
- padrões internos (embeddings de bons clips históricos)
- histórico de bons clips (feedback do usuário)

Ajusta score final combinando:
- score Gemini (análise semântica)
- similaridade vetorial (embeddings)
- score de engajamento

**Status → embedding/classifying**

**Regra:**
- Usa Gemini API para embeddings (custo controlado)
- Não treina modelo customizado
- Só similaridade vetorial (sem IA generativa)
- Feature incremental (melhora com histórico)

---

### 8. Seleção de Clips

Combinação de:
- score Gemini
- score embedding
- regras fixas:
  - duração mínima/máxima (respeitando `max_clip_duration`)
  - densidade de fala
  - presença de emoção/palavras-chave
  - proporções desejadas (`target_ratios`)

Seleciona Top N clips (respeitando `num_clips`).

**Status → selecting**

---

### 9. Reenquadramento Automático

Detecta rosto/frame dominante.

Define crop automático para proporções desejadas (9:16, 1:1, 16:9).

Aplica tracking simples para manter foco no rosto/elemento principal.

**Status → reframing**

**Regra:**
- Visão computacional clássica
- Disponível apenas em Pro e Business (Starter não tem reenquadramento)
- Respeita proporções do usuário

---

### 10. Captioning (Legendagem Avançada)

Etapa fixa e determinística que gera legendas profissionais 

**Entrada:**
- Transcrição com timestamps por palavra (do Whisper)
- Clips selecionados com timestamps
- Proporção do vídeo (9:16, 1:1, 16:9)

**Processamento:**

1. **Geração de ASS (Advanced SubStation Alpha)**
   - Usa exclusivamente Whisper com timestamps por palavra
   - Gera arquivo ASS por clip
   - Estilo visual:
     - Fonte: Bold
     - Texto: CAIXA ALTA
     - Posição: Centralizado na parte inferior
     - Máximo: 2 linhas por frame
     - Destaque dinâmico: Karaoke (palavra falada em destaque)

2. **Queimação no vídeo (FFmpeg)**
   - Aplica ASS diretamente no vídeo usando FFmpeg
   - Sem IA para design ou animação
   - Resultado: MP4 com legendas queimadas
   - Compatível 100% com redes sociais

3. **Armazenamento**
   - Salva ASS original no R2 (reutilizável)
   - Salva vídeo final com legendas no R2

**Características:**
- Determinístico (mesmo input = mesmo output)
- Barato (100% local, sem APIs)
- Reutilizável (ASS pode ser regenerado)
- Compatível com todas as redes sociais
- Sem dependências de IA para design

**Status → captioning**

---

### 11. Geração dos Clips (FFmpeg)

Corta vídeo original nos timestamps selecionados.

Aplica:
- reenquadramento (se ativo)
- legenda ASS queimada (já aplicada na etapa anterior)
- normalização de áudio
- exporta formatos sociais (mp4, webm)

Upload para R2.

**Status → clipping**

---

### 12. Finalização

Gera URLs assinadas para cada clip.

Atualiza status → done.

Envia resultado via SSE com:
- lista de clips gerados
- URLs assinadas
- títulos sugeridos (do Gemini)
- descrição do vídeo original
- transcrição completa (para exibição)

**Opcional:** Se `auto_schedule = true`, agenda posts no calendário do usuário.

**Status → done**

---

## Estados do Job

```
→ ingestion
→ queued
→ downloading
→ normalizing
→ transcribing
→ analyzing
→ embedding/classifying
→ selecting
→ reframing (opcional)
→ clipping
→ captioning
→ done | failed
```
 
---

## Jobs / Filas (RabbitMQ)

**Filas por Etapa (com prioridade por plano):**
- `video.ingestion` (prioridade: starter/pro/business)
- `video.download.starter | .pro | .business`
- `video.normalize.starter | .pro | .business`
- `video.transcribe.starter | .pro | .business`
- `video.analyze.starter | .pro | .business`
- `video.classify.starter | .pro | .business`
- `video.select.starter | .pro | .business`
- `video.reframe.pro | .business` (Starter não tem)
- `video.clip.starter | .pro | .business`
- `video.caption.starter | .pro | .business`

Cada etapa é idempotente.

---

# Camadas Obrigatórias de Operação, Segurança e Resiliência

## 1. Segurança, Limites e Anti-Abuso

**Rate Limiting:**
- Rate limit por usuário (ex: 10 jobs/hora para Starter, ilimitado para Pro/Business)
- Rate limit por IP (ex: 100 requisições/minuto)
- Throttling progressivo para IPs suspeitos

**Validação de URLs Externas:**
- Proteção contra SSRF (Server-Side Request Forgery)
- Lista explícita de domínios permitidos:
  - YouTube (youtube.com, youtu.be)
  - TikTok (tiktok.com, vm.tiktok.com)
  - Instagram (instagram.com, instagr.am)
- Timeout máximo de download (ex: 30 minutos)

**Validação de Mídia:**
- Tamanho máximo: 2GB (configurável por plano)
- Duração máxima: 120 minutos (configurável por plano)
- Formatos permitidos: MP4, WebM, MOV, MKV
- Resolução mínima: 480p
- Codec de áudio obrigatório

**Limites de Concorrência:**
- Máximo de jobs simultâneos por usuário (ex: 3 para Starter, 10 para Pro/Business)
- Máximo de jobs simultâneos globais (ex: 100)
- Kill automático de jobs que excederem tempo máximo por etapa (ex: 30 min por etapa)

---

## 2. Gerenciamento de Falhas e Retentativas

**Política de Execução Resiliente:**

Cada etapa implementa retry com backoff exponencial:
- Tentativa 1: imediato
- Tentativa 2: 30 segundos
- Tentativa 3: 2 minutos
- Tentativa 4: 10 minutos
- Tentativa 5: 30 minutos
- Máximo: 5 tentativas (configurável por etapa)

**Persistência de Estado:**
- Salva último checkpoint bem-sucedido em banco de dados
- Permite retomada automática a partir da última etapa válida
- Evita reprocessamento de etapas já concluídas

**Marcação de Falha Definitiva:**
- Após esgotar retries, marca job como `failed`
- Registra motivo da falha (último erro técnico)
- Permite reprocessamento manual pelo usuário

**Idempotência Garantida:**
- Cada etapa pode ser executada múltiplas vezes com mesmo resultado
- Evita duplicação de clips, legendas ou arquivos no storage

---

## 3. Erros Amigáveis (Frontend-safe)

**Princípio Fundamental:**
Nunca expor ao usuário:
- Nome de modelos (Whisper, Gemini, etc)
- Nome de serviços internos (RabbitMQ, Celery, etc)
- Detalhes de infraestrutura (workers, GPUs, etc)
- Stack traces ou erros técnicos

**Padrão Obrigatório de Erro:**

Toda resposta de erro deve conter:
```json
{
  "error_code": "PROCESSING_ERROR",
  "message": "Não foi possível processar o áudio do vídeo.",
  "user_action": "Tente novamente mais tarde ou entre em contato com o suporte.",
  "job_id": "uuid-do-job"
}
```

**Códigos de Erro Permitidos (Frontend):**
- `INGESTION_ERROR` → "Não foi possível carregar o vídeo."
- `AUDIO_ERROR` → "Não foi possível processar o áudio do vídeo."
- `ANALYSIS_ERROR` → "Ocorreu um problema ao analisar o conteúdo."
- `SELECTION_ERROR` → "Não foi possível selecionar os melhores trechos."
- `GENERATION_ERROR` → "Não foi possível gerar os clips."
- `TIMEOUT_ERROR` → "O processamento levou muito tempo. Tente novamente."
- `RATE_LIMIT_ERROR` → "Você atingiu o limite de processamentos. Tente novamente em X minutos."
- `VALIDATION_ERROR` → "O vídeo não atende aos requisitos mínimos."
- `STORAGE_ERROR` → "Erro ao salvar os resultados. Tente novamente."

**Logs Técnicos Detalhados:**
- Existem apenas no backend
- Associados a `job_id` para rastreamento
- Incluem stack traces, nomes de modelos, detalhes de infraestrutura
- Acessíveis apenas para administradores

---

## 4. Modelo de Dados Conceitual

**Entidades Principais:**

### Video
- `video_id` (UUID)
- `user_id` (FK)
- `source_type` (upload | youtube | tiktok | instagram | url)
- `source_url` (se aplicável)
- `original_filename`
- `duration` (segundos)
- `resolution` (1920x1080)
- `file_size` (bytes)
- `storage_path` (R2)
- `created_at`
- `version` (para reprocessamento)

### Job
- `job_id` (UUID)
- `user_id` (FK) - quem criou o job
- `organization_id` (FK) - quem possui o recurso
- `video_id` (FK)
- `status` (ingestion | queued | downloading | ... | done | failed)
- `current_step` (etapa atual)
- `last_successful_step` (para retomada)
- `configuration` (language, target_ratios, max_clip_duration, num_clips, etc)
- `error_code` (se failed)
- `error_message` (técnico, apenas backend)
- `credits_consumed` (créditos deduzidos)
- `retry_count` (por etapa)
- `created_at`
- `started_at`
- `completed_at`
- `version` (para rastreamento de reprocessamento)

### Clip
- `clip_id` (UUID)
- `job_id` (FK)
- `video_id` (FK)
- `start_time` (ms)
- `end_time` (ms)
- `duration` (ms)
- `ratio` (9:16 | 1:1 | 16:9)
- `engagement_score` (0-100)
- `title` (sugerido por Gemini)
- `storage_path` (R2)
- `file_size` (bytes)
- `created_at`
- `version`

### Transcript
- `transcript_id` (UUID)
- `video_id` (FK)
- `full_text` (transcrição completa)
- `segments` (JSON com timestamps por palavra)
- `language` (pt-BR, en, es, etc)
- `confidence_score` (0-100)
- `storage_path` (R2)
- `created_at`
- `version`

### Caption
- `caption_id` (UUID)
- `clip_id` (FK)
- `format` (ASS)
- `content` (arquivo ASS)
- `storage_path` (R2)
- `style` (bold, uppercase, centered, karaoke)
- `created_at`
- `version`

### Schedule
- `schedule_id` (UUID)
- `clip_id` (FK)
- `user_id` (FK)
- `platform` (youtube | tiktok | instagram | etc)
- `scheduled_time` (datetime)
- `status` (scheduled | posted | failed)
- `post_url` (após publicação)
- `created_at`
- `version`

### Feedback (Futuro)
- `feedback_id` (UUID)
- `clip_id` (FK)
- `user_id` (FK)
- `rating` (1-5)
- `engagement_actual` (views, likes, shares)
- `created_at`

**Princípio de Versionamento:**
- Todas as entidades são versionáveis
- Permite reprocessamento sem duplicação
- Histórico completo para auditoria

---

## 5. Controle de Concorrência e Prioridade

**Limites por Organização:**
- Starter: máx 3 jobs simultâneos
- Pro: máx 10 jobs simultâneos
- Business: ilimitado

**Filas Separadas por Prioridade:**
- `video.download.starter` (prioridade normal)
- `video.download.pro` (prioridade alta)
- `video.download.business` (prioridade máxima)
- Mesmo padrão para todas as etapas

**Lock por Vídeo:**
- Evita processamento duplicado do mesmo vídeo
- Usa Redis para lock distribuído
- TTL: 24 horas (tempo máximo de processamento)
- Lock é liberado após job completar (sucesso ou falha)
- Permite reprocessamento manual após conclusão

**Fila Global:**
- Máximo de 100 jobs simultâneos em todo o sistema
- Overflow entra em fila de espera

---

## 6. Lifecycle e Limpeza de Dados

**Políticas de Retenção:**

| Recurso | Retenção | Política |
|---------|----------|----------|
| Vídeo original | 30 dias | Soft delete após 30 dias (ou sob demanda) |
| Clips gerados | Indefinido | Manter enquanto plano ativo |
| Legendas (ASS) | Indefinido | Manter para reutilização |
| Transcrição | Indefinido | Manter para análise futura |
| Jobs falhos | 7 dias | Soft delete após 7 dias |
| Logs | 30 dias | Arquivar após 30 dias |
| **Dados após cancelamento** | **90 dias** | **Soft delete 3 meses após cancelamento do plano** |

**Limpeza Automática:**
- Cron job diário para marcar recursos como deletados (soft delete)
- Dados nunca são removidos do banco (apenas marcados como deletados)
- Hard delete NUNCA ocorre (apenas soft delete permanente)
- Recuperação possível por admin se necessário

**Reprocessamento sem Duplicação:**
- Reutiliza vídeo original se ainda disponível
- Reutiliza transcrição se idioma igual
- Gera novos clips com novos IDs
- Mantém histórico de versões

---

## 7. Observabilidade Mínima

**Logs Estruturados:**
```json
{
  "timestamp": "2025-12-14T15:30:00Z",
  "job_id": "uuid-do-job",
  "user_id": "uuid-do-usuario",
  "step": "transcribing",
  "level": "INFO",
  "message": "Transcrição iniciada",
  "duration_ms": 1500,
  "status": "success"
}
```

**Métricas por Etapa:**
- Tempo médio de execução
- Taxa de sucesso/falha
- Número de retries
- Distribuição de duração

**Healthcheck dos Workers:**
- Heartbeat a cada 30 segundos
- Detecta workers mortos
- Auto-escalabilidade baseada em fila

**Dashboard Mínimo:**
- Jobs em processamento
- Taxa de sucesso por etapa
- Tempo médio por etapa
- Alertas de falhas críticas

---

## 8. SSE – Confiabilidade

**Suporte a Reconexão:**
- Cliente pode reconectar a qualquer momento
- Servidor mantém buffer de últimos 100 eventos por job
- Ao reconectar, envia estado completo atual

**Eventos SSE Padrão:**
```
event: job_status_update
data: {"job_id": "uuid", "status": "transcribing", "progress": 45}

event: job_completed
data: {"job_id": "uuid", "clips": [...], "transcript": "..."}

event: job_error
data: {"job_id": "uuid", "error_code": "AUDIO_ERROR", "message": "..."}
```

**Fonte da Verdade:**
- API REST é sempre a fonte da verdade
- SSE é apenas notificação em tempo real
- Cliente deve validar estado via GET /jobs/{job_id}

**Timeout e Keepalive:**
- Keepalive a cada 30 segundos (comentário vazio)
- Timeout de reconexão: 5 minutos

---

## 9. Multi-idioma Avançado

**Princípio:** Suporte robusto a múltiplos idiomas

### Funcionalidades

**Detecção Automática de Idioma**
- Whisper detecta idioma do áudio
- Compara com idioma configurado
- Usa idioma detectado se confiança > 90%

**Fallback para Idioma Configurado**
- Se detecção falhar, usa idioma do onboarding
- Sem bloqueio de processamento

**Persistência do Idioma Detectado**
- Registra idioma detectado no job
- Usa para análise semântica (Gemini)
- Histórico para análise

**Suporte a Vídeos Multilíngues**
- Detecta mudanças de idioma
- Registra timestamps de mudança
- Análise por segmento de idioma

### Modelo de Dados

```
TranscriptSegment (expandido)
├── segment_id (UUID)
├── transcript_id (FK)
├── text
├── start_time
├── end_time
├── language (pt-BR, en, es, etc)
├── confidence (0-100)
└── is_auto_detected
```

### Idiomas Suportados

- Português (Brasil, Portugal)
- Inglês (US, UK)
- Espanhol
- Francês
- Alemão
- Italiano
- Japonês
- Chinês (Simplificado, Tradicional)
- Outro

---

## 10. Normalização Técnica de Mídia

**Durante Ingestão:**
- Validar codec de áudio (AAC, MP3, OPUS)
- Validar codec de vídeo (H.264, H.265, VP9)
- Validar sample rate (16kHz, 44.1kHz, 48kHz)

**Durante Normalização:**
- Padronizar áudio: 48kHz, mono ou estéreo, -3dB (volume)
- Padronizar FPS: 30fps (converter de 24, 25, 60fps)
- Padronizar resolução: mínimo 480p, máximo 1080p
- Padronizar codec: H.264 para vídeo, AAC para áudio
- Resultado: arquivo intermediário no R2 para reutilização

**Garantias:**
- Qualidade mínima mantida
- Compatibilidade com FFmpeg
- Reutilizável para múltiplos clips

---

## 11. Ajuste Fino do Pipeline de Legendagem

**Ordem Corrigida do Pipeline:**

```
ingestion
→ queued
→ downloading
→ normalizing
→ transcribing
→ analyzing
→ embedding/classifying
→ selecting
→ reframing (opcional)
→ clipping
→ captioning
→ done | failed
```

**Mudança Principal:**
- **Antes:** Captioning → Clipping
- **Depois:** Clipping → Captioning

**Justificativa:**
- Legendas são geradas com base na duração final de cada clip
- Cada clip tem duração diferente após corte
- ASS é gerado com timestamps específicos do clip final
- Evita reprocessamento de legendas

**Fluxo Detalhado:**
1. **Clipping**: Corta vídeo nos timestamps selecionados → gera clip final
2. **Captioning**: Gera ASS com base na duração do clip final → queima no vídeo

---

## Garantias do Sistema

✅ **Resiliente**: Retry automático, retomada de falhas, idempotência  
✅ **Seguro**: Rate limiting, validação rigorosa, proteção contra SSRF  
✅ **Profissional**: Erros amigáveis, sem vazamento técnico  
✅ **Observável**: Logs estruturados, métricas, healthcheck  
✅ **Escalável**: Filas por prioridade, controle de concorrência  
✅ **Reutilizável**: Versionamento, reprocessamento sem duplicação  
✅ **Compatível**: Padrões de mercado, pronto para MVP público  

---

# Camada Estratégica: Onboarding, Organizações, Integrações e Planos

## 1. Onboarding Estratégico (obrigatório)

**Momento:** Logo após confirmação de email  
**Duração:** 1–2 minutos  
**Objetivo:** Entender o usuário e personalizar o produto

### Perguntas Obrigatórias:

**1. Qual é o principal tipo de conteúdo?**
- Podcast
- Curso / Aula
- Conteúdo educacional curto
- Marketing / Ads
- Conteúdo pessoal / criador

**2. Onde você publica hoje? (multi-select)**
- TikTok
- Instagram Reels
- YouTube Shorts
- LinkedIn
- X (Twitter)

**3. Qual é o principal objetivo com os clips?**
- Alcance / viralização
- Leads / vendas
- Autoridade / marca pessoal
- Reaproveitamento de conteúdo

**4. Idioma principal do conteúdo**
- Português (Brasil)
- Inglês
- Espanhol
- Outro

**5. Frequência esperada de uso**
- Esporádico (1–2x/mês)
- Semanal (1–3x/semana)
- Diário (todos os dias)

### Dados Coletados Alimentam:

- **Análise Semântica**: Gemini ajusta contexto baseado em tipo de conteúdo
- **Score de Engajamento**: Ponderação diferente por plataforma e objetivo
- **Templates de Legenda**: Sugestões personalizadas por nicho
- **Roadmap do Produto**: Priorização de features por perfil de usuário
- **Recomendações**: Sugestões de plano baseadas em frequência

### Regras:

- Onboarding é editável depois (Configurações → Perfil)
- Dados persistem na organização
- Influencia comportamento do sistema, não restringe features
- Sem onboarding = comportamento padrão (genérico)

---

## 2. Sistema de Organizações

**Conceito:** Recursos (vídeos, clips, jobs) pertencem à organização, não ao usuário

### Papéis e Permissões:

| Ação | Membro | Co-líder | Líder |
|------|--------|----------|-------|
| Visualizar projetos | ✅ | ✅ | ✅ |
| Visualizar clips | ✅ | ✅ | ✅ | (todos da organização)
| Fazer download | ✅ | ✅ | ✅ |
| Postar conteúdo | ❌ | ✅ | ✅ |
| Agendar posts | ❌ | ✅ | ✅ |
| Convidar membros | ❌ | ✅ | ✅ |
| Remover membros | ❌ | ✅ | ✅ |
| Gerenciar organização | ❌ | ❌ | ✅ |
| Gerenciar planos | ❌ | ❌ | ✅ |
| Gerenciar créditos | ❌ | ❌ | ✅ |
| Gerenciar integrações | ❌ | ❌ | ✅ |

### Estrutura de Dados:

```
Organization
├── organization_id (UUID)
├── name
├── plan (starter | pro | business)
├── credits_monthly (renovável)
├── credits_available (saldo atual)
├── credits_purchased (acumulado)
├── billing_email
├── stripe_customer_id
├── created_at
├── members[]
├── integrations[]
└── videos[]
```

### Convites:

- Email com link seguro (token com TTL de 7 dias)
- Usuário pode aceitar ou rejeitar
- Um usuário pode participar de múltiplas organizações
- Cada organização tem seus próprios recursos

### Regras:

- Toda ação respeita permissões do papel
- Auditoria de ações por usuário
- Soft delete de membros (histórico)

---

## 3. Integrações com Redes Sociais

**Objetivo:** Postagem automática

### Redes Suportadas:

- TikTok
- Instagram
- Facebook
- YouTube Shorts
- LinkedIn
- X (Twitter)

### Fluxo de Integração:

1. **Autorização (OAuth 2.0)**
   - Usuário clica "Conectar"
   - Redireciona para login da rede
   - Permissão explícita: "Postar em seu nome"
   - Retorna token de acesso + refresh token

2. **Armazenamento Seguro**
   - Token criptografado no banco
   - Associado à organização
   - Refresh automático 1 dia antes de expiração

3. **Postagem**
   - Manual: usuário clica "Postar agora"
   - Agendada: usuário define data/hora (se plano permite)
   - Sistema enfileira job de postagem
   - Feedback em tempo real via SSE

### Configuração por Rede:

```
Integration
├── integration_id (UUID)
├── organization_id (FK)
├── platform (tiktok | instagram | etc)
├── account_name
├── token_encrypted
├── token_refresh_at
├── is_active
├── created_at
└── last_posted_at
```

### Regras:

- Integrações são por organização
- Um usuário pode ter múltiplas contas por rede
- Desconexão revoga token imediatamente
- Falha de postagem não afeta clip (apenas registra erro)
- Refresh token automático antes de expiração

---

## 4. Planos Pagos 

**Princípio:** Apenas planos pagos, focados em uso real

### Plano Starter

**Ideal para:** Criadores individuais  
**Preço:** $29/mês USD | R$ 145/mês BRL  
**Anual:** $290/ano USD (17% desconto) | R$ 1.450/ano BRL (17% desconto)

**Limites:**
- 300 créditos/mês (≈ 5 horas de vídeo)
- 3 jobs simultâneos
- Fila normal
- Sem reenquadramento automático
- Sem auto-scheduling

**Features:**
- Análise semântica básica
- Seleção de clips
- Legendagem ASS
- Postagem manual
- 1 organização

### Plano Pro

**Ideal para:** Criadores consistentes, pequenas equipes  
**Preço:** $79/mês USD | R$ 395/mês BRL  
**Anual:** $790/ano USD (17% desconto) | R$ 3.950/ano BRL (17% desconto)

**Limites:**
- 1000 créditos/mês (≈ 16 horas de vídeo)
- 10 jobs simultâneos
- Fila prioritária (média)
- Reenquadramento automático
- Auto-scheduling

**Features:**
- Tudo do Starter
- Análise semântica avançada
- Embeddings com Gemini
- Auto-scheduling com calendário
- Reenquadramento 9:16, 1:1, 16:9
- Até 5 membros
- Múltiplas organizações

### Plano Business

**Ideal para:** Equipes, agências  
**Preço:** $199/mês USD | R$ 995/mês BRL  
**Anual:** $1990/ano USD (17% desconto) | R$ 9.950/ano BRL (17% desconto)

**Limites:**
- 5000 créditos/mês (≈ 83 horas de vídeo)
- Ilimitado jobs simultâneos
- Fila prioritária (alta)
- Reenquadramento automático
- Auto-scheduling

**Features:**
- Tudo do Pro
- Todas as features liberadas
- Até 50 membros
- Múltiplas organizações
- Suporte prioritário
- Webhooks (futuro)
- API customizada (futuro)

### Tabela Comparativa:

| Feature | Starter | Pro | Business |
|---------|---------|-----|----------|
| Créditos/mês | 300 | 1000 | 5000 |
| Jobs simultâneos | 3 | 10 | Ilimitado |
| Reenquadramento | ❌ | ✅ | ✅ |
| Auto-scheduling | ❌ | ✅ | ✅ |
| Membros | 1 | 5 | 50 |
| Organizações | 1 | Múltiplas | Múltiplas |
| Fila | Normal | Prioritária | Prioritária |
| Preço | $29/mês USD | $79/mês USD | $199/mês USD |

---

## 5. Sistema de Créditos

**Modelo:** 1 crédito = 1 minuto de vídeo bruto analisado

### Consumo:

- **Quando:** Após validação de duração, antes de downloading
- **Quanto:** Duração do vídeo em minutos (arredondado para cima)
- **Validação:** Se vídeo inválido, créditos NÃO são deduzidos
- **Sem créditos:** Job é rejeitado com erro amigável (INSUFFICIENT_CREDITS)

### Exemplo:

- Vídeo de 15 minutos = 15 créditos
- Vídeo de 15:30 = 16 créditos
- Plano Starter (300 créditos) = até 5 horas/mês

### Regras:

- Créditos pertencem à organização, não ao usuário
- Falha no processamento → estorno automático IMEDIATAMENTE
- Reprocessamento não consome novos créditos (reutiliza checkpoint)
- Créditos não expiram (acumulam indefinidamente)
- Sem limite de clips gerados (apenas limite de vídeo bruto)

### Fluxo de Consumo:

```
1. Usuário envia vídeo (15 min)
2. Sistema valida: 15 créditos disponíveis?
3. SIM → Deduz 15 créditos, inicia job
4. Job falha → Estorna 15 créditos
5. Job sucesso → Créditos permanecem deduzidos
```

---

## 6. Compra de Créditos

### Pacotes Avulsos:

| Pacote | Créditos | Preço | Preço/Crédito |
|--------|----------|-------|---------------|
| Pequeno | 100 | $9 | $0.09 |
| Médio | 500 | $39 | $0.078 |
| Grande | 1000 | $69 | $0.069 |
| Mega | 5000 | $299 | $0.0598 |

### Regras:

- Pacotes associados à organização
- Disponíveis imediatamente após pagamento
- Acumulam com créditos mensais
- Sem expiração (créditos acumulam indefinidamente)
- Reembolso: 30 dias se não utilizado

### Fluxo de Compra:

```
1. Usuário clica "Comprar créditos"
2. Seleciona pacote
3. Redireciona para pagamento
4. Pagamento bem-sucedido
5. Créditos creditados imediatamente
6. Email de confirmação
```

---

## 7. Integração com Pipeline de Processamento

### Validação de Créditos:

```
Job Creation (step 2)
├── Validar créditos disponíveis
├── Calcular consumo (duração do vídeo)
├── Créditos >= consumo?
│   ├── SIM → Deduzir créditos, continuar
│   └── NÃO → Rejeitar com INSUFFICIENT_CREDITS
└── Registrar consumo no Job
```

### Estorno Automático:

```
Job Failure (any step)
├── Se job falhou após consumo de créditos
├── Estornar créditos IMEDIATAMENTE à organização
├── Registrar no histórico com motivo (error_code)
├── Notificar usuário com mensagem amigável
├── Marcar job como failed com erro técnico
```

### Reprocessamento:

```
Job Reprocessing
├── Verificar se créditos já foram consumidos
├── SIM → Não deduzir novamente
├── NÃO → Deduzir normalmente
└── Reutilizar checkpoints anteriores
```

---

## 8. Modelo de Dados Expandido

### User (expandido)

```
User
├── user_id (UUID)
├── email
├── password_hash
├── onboarding_completed (boolean)
├── onboarding_data (JSON)
│   ├── content_type
│   ├── platforms
│   ├── objective
│   ├── language
│   └── frequency
├── created_at
└── organizations[] (FK)
```

### Organization (novo)

```
Organization
├── organization_id (UUID)
├── name
├── plan (starter | pro | business)
├── credits_monthly (renovável)
├── credits_available (saldo atual)
├── credits_purchased (acumulado)
├── billing_email
├── stripe_customer_id
├── created_at
├── members[]
├── integrations[]
└── videos[]
```

### Integration (novo)

```
Integration
├── integration_id (UUID)
├── organization_id (FK)
├── platform (tiktok | instagram | etc)
├── account_name
├── token_encrypted
├── token_refresh_at
├── is_active
├── created_at
└── last_posted_at
```

### CreditTransaction (novo)

```
CreditTransaction
├── transaction_id (UUID)
├── organization_id (FK)
├── job_id (FK)
├── amount (positivo = dedução, negativo = estorno)
├── type (consumption | refund | purchase)
├── reason
├── created_at
└── balance_after
```

---

## 9. Fluxo Completo do Usuário

### 1. Signup

```
1. Usuário se registra
2. Confirma email
3. Onboarding (1–2 min)
   ├── Tipo de conteúdo
   ├── Plataformas
   ├── Objetivo
   ├── Idioma
   └── Frequência
4. Escolhe plano (Starter, Pro, Business)
5. Pagamento (Stripe)
6. Organização criada
7── Acesso ao dashboard
```

### 2. Primeiro Processamento

```
1. Usuário envia vídeo
2. Sistema valida créditos
3. Se insuficiente → "Compre créditos"
4. Se suficiente → Deduz créditos, inicia job
5. SSE com progresso
6. Job concluído → Clips prontos
```

### 3. Postagem Automática

```
1. Usuário clica "Conectar Instagram"
2. OAuth → Autoriza
3. Token armazenado
4. Usuário seleciona clips
5. Clica "Agendar para amanhã"
6. Sistema enfileira postagem
7. Amanhã → Publica automaticamente
8. Notificação ao usuário
```

---

## 10. Garantias da Camada Estratégica

✅ **Onboarding Guia Decisões**: Personaliza análise e UX  
✅ **Organizações Simples**: Papéis claros, permissões respeitadas  
✅ **Monetização Previsível**: Planos bem definidos, créditos transparentes  
✅ **Integrações Focadas**: Postagem automática, não login  
✅ **UX Profissional**: SaaS padrão, sem confusão  
✅ **Sem Impacto no Pipeline**: Camada estratégica é independente  

---

## Frontend - Views e UX

### View de Envio

Ao clicar em "Enviar", exibe progresso em tempo real via SSE com nomes amigáveis:

- **Next in queue** (aguardando processamento)
- **Criando seu projeto** (baixando/validando vídeo)
- **Gerando Clipes** (análise, seleção e reenquadramento)
- **Buscando melhores clipes** (análise semântica e embeddings)
- **Finalizando** (legendagem e exportação)
- **Done** (concluído)

**Mapeamento interno dos status:**
- ingestion → Next in queue
- queued → Next in queue
- downloading → Criando seu projeto
- normalizing → Criando seu projeto
- transcribing → Criando seu projeto
- analyzing → Buscando melhores clipes
- embedding/classifying → Buscando melhores clipes
- selecting → Gerando Clipes
- reframing → Gerando Clipes
- captioning → Finalizando
- clipping → Finalizando
- done → Done

### View de Clips

Exibe:
- Thumbnail de cada clip
- Duração
- Score de engajamento
- Título sugerido (do Gemini)
- Proporção (9:16, 1:1, 16:9)
- Botões: Download, Preview, Schedule, Delete

### Calendário

- **Visualização**: Mês/Semana/Dia
- **Funcionalidades:**
  - Ver clips agendados para postar
  - Ver clips já postados
  - Agendar novo post (data/hora)
  - Editar agendamento
  - Cancelar post agendado
  - Integração com redes sociais (futura)

---

## Regras de negócio principais

- Upload nunca passa pela API (direto para R2)
- Processamento sempre batch
- Suporte a múltiplas fontes de vídeo
- Limites por plano:
  - duração máxima de vídeo
  - nº máximo de clips
  - reenquadramento on/off
  - auto-scheduling on/off
- Retry com backoff
- Reprocessamento sem novo upload
- Custos sempre previsíveis

---

# Camada Operacional e Estratégica: Billing, Controle Técnico e Evolução

## 1. Billing & Assinatura (ciclo de vida completo)

**Princípio:** Stripe é a fonte de verdade de billing

### Upgrade de Plano

- Aplicação imediata
- Diferença cobrada pró-rata
- Créditos mensais aumentam imediatamente
- Limites técnicos atualizados em tempo real

**Exemplo:**
- Usuário em Starter ($29/mês, 300 créditos)
- Upgrade para Pro no dia 15 do ciclo
- Diferença: ($79 - $29) / 30 * 15 = $25 cobrado imediatamente
- Créditos aumentam de 300 para 1000 imediatamente

### Downgrade de Plano

- Aplicado apenas no próximo ciclo
- Não afeta créditos atuais
- Aviso claro ao usuário
- Créditos em excesso não são removidos

**Exemplo:**
- Usuário em Pro com 800 créditos restantes
- Downgrade para Starter
- Créditos permanecem até fim do ciclo
- Próximo ciclo: 300 créditos (Starter)

### Cancelamento

- Plano permanece ativo até o fim do ciclo
- Após expirar, bloqueia novos jobs
- Clips e downloads permanecem acessíveis indefinidamente
- Dados não são deletados

**Fluxo:**
```
1. Usuário clica "Cancelar assinatura"
2. Confirmação: "Seu plano expira em X dias"
3. Até data de expiração: acesso total
4. Após expiração: "Sem créditos. Assine para continuar"
5. Dados permanecem acessíveis
```

### Falha de Pagamento

- Grace period configurável (padrão: 3 dias)
- Bloqueio de criação de novos jobs após grace period
- Nenhuma exclusão de dados
- Email de aviso ao usuário
- Retry automático com backoff

**Fluxo:**
```
1. Pagamento falha
2. Email: "Falha no pagamento. Tente novamente."
3. Retry automático em 1, 3, 5 dias
4. Após 3 dias (grace period): bloqueio de novos jobs
5. Após 7 dias: aviso de cancelamento automático
6. Após 14 dias: cancelamento automático
```

### Renovação Mensal de Créditos

- Execução via cron mensal (no mesmo dia do mês em que plano foi ativado)
- Idempotência obrigatória (pode ser executado múltiplas vezes)
- Registro de histórico de crédito
- Notificação ao usuário

**Fluxo:**
```
1. Cron executa no dia do aniversário (mesmo dia do mês de ativação)
2. Verifica: plano ativo?
3. SIM → Adiciona créditos mensais
4. Registra transação (type: monthly_renewal)
5. Envia email: "Seus créditos foram renovados"
6. Idempotência: se executado 2x, apenas 1 renovação
```

### Modelo de Dados de Billing

```
Subscription
├── subscription_id (UUID)
├── organization_id (FK)
├── stripe_subscription_id
├── plan (starter | pro | business)
├── status (active | past_due | canceled | unpaid)
├── current_period_start
├── current_period_end
├── cancel_at (se cancelado)
├── created_at
└── updated_at

BillingEvent
├── event_id (UUID)
├── organization_id (FK)
├── type (upgrade | downgrade | renewal | payment_failed | etc)
├── old_plan
├── new_plan
├── amount
├── created_at
└── stripe_event_id
```

---

## 2. Quotas Técnicas por Recurso (anti-abuso)

**Princípio:** Além de créditos, aplicar limites técnicos claros

### Limites Configuráveis por Plano

| Recurso | Starter | Pro | Business |
|---------|---------|-----|----------|
| Storage | 100GB | 500GB | Ilimitado |
| Clips por job | 50 | 200 | 500 |
| Redes sociais conectadas | 2 | 6 | 20 |
| Integrações simultâneas | 1 | 5 | 20 |
| Membros da equipe | 1 | 5 | 50 |
| Projetos | 1 | 5 | Ilimitado |
| Templates visuais | Ilimitados | Ilimitados | Ilimitados |

### Comportamento ao Atingir Limite

- Erro explícito: `QUOTA_EXCEEDED`
- Bloqueio imediato da ação
- Nenhuma cobrança extra
- Mensagem amigável: "Você atingiu o limite de X. Atualize seu plano."

**Exemplo:**
```json
{
  "error_code": "QUOTA_EXCEEDED",
  "message": "Você atingiu o limite de 50 clips por job (plano Starter).",
  "user_action": "Atualize para Pro para até 200 clips.",
  "current": 50,
  "limit": 50,
  "quota_type": "clips_per_job"
}
```

### Monitoramento de Quotas

- Verificação em tempo real antes de ação
- Alertas quando atingir 80% do limite
- Dashboard mostrando uso atual vs limite

---

## 3. Backoffice / Admin (operação real)

**Acesso:** Restrito a admins do sistema (não usuários)

### Funcionalidades Obrigatórias

**Reprocessar Job Manualmente**
- Selecionar job por ID
- Escolher etapa inicial (ingestion, downloading, transcribing, etc)
- Reutilizar checkpoints anteriores
- Sem cobrar créditos novamente

**Cancelar Job Travado**
- Selecionar job
- Marcar como canceled
- Estornar créditos se aplicável
- Notificar usuário

**Ajustar Créditos de Organização**
- Adicionar/remover créditos manualmente
- Motivo obrigatório (refund, adjustment, etc)
- Auditoria completa
- Notificação ao usuário

**Visualizar Falhas por Etapa**
- Dashboard com taxa de falha por etapa
- Filtrar por período, usuário, organização
- Detalhes técnicos (stack trace, logs)
- Alertas automáticos para falhas críticas

**Bloquear/Desbloquear Usuário ou Organização**
- Bloqueio imediato de novos jobs
- Acesso a dados permanece
- Motivo obrigatório
- Auditoria

### Interface Admin

```
Dashboard Admin
├── Métricas
│   ├── Jobs processados hoje
│   ├── Taxa de sucesso
│   ├── Receita MRR
│   └── Usuários ativos
├── Operações
│   ├── Reprocessar job
│   ├── Cancelar job
│   ├── Ajustar créditos
│   └── Bloquear usuário
├── Análise
│   ├── Falhas por etapa
│   ├── Tempo médio por etapa
│   ├── Usuários com mais falhas
│   └── Alertas
└── Auditoria
    ├── Histórico de ações
    ├── Histórico de créditos
    └── Histórico de billing
```

---

## 4. Cold Start & Defaults


### Defaults Obrigatórios

```
DefaultConfig
├── language: "en-US"
├── target_ratios: ["9:16", "1:1", "16:9"]
├── max_clip_duration: 60 (segundos)
├── min_clip_duration: 10 (segundos)
├── max_clips_per_job: 20
├── default_clips_per_job: 5
├── min_engagement_score: 40 (0-100)
├── caption_style: "opus_pro" (bold, uppercase, centered, karaoke)
├── caption_position: "bottom"
├── caption_max_lines: 2
├── auto_schedule: false
├── reframing: false (Starter não tem)
└── transcript_display: true
```

### Fluxo de Cold Start

```
1. Usuário faz signup
2. Pula onboarding (opcional)
3. Envia primeiro vídeo
4. Sistema usa defaults
5. Clips gerados com defaults
6. Usuário pode ajustar depois
```

### Personalização Progressiva

- Usuário pode editar defaults em Configurações → Preferências de Processamento
- Defaults salvos por organização
- Herança de defaults em novos jobs
- Sem bloqueio de funcionalidade

---

## 5. Webhooks (além de SSE)


### Eventos Suportados

- `job_started` → Job iniciou processamento
- `job_completed` → Job completou com sucesso
- `job_failed` → Job falhou
- `clip_ready` → Clip individual pronto
- `post_published` → Post publicado em rede social

### Configuração

```
Webhook
├── webhook_id (UUID)
├── organization_id (FK)
├── url
├── events[] (job_started, job_completed, etc)
├── secret (para validação HMAC)
├── is_active
├── created_at
└── last_triggered_at
```

### Payload Padrão

```json
{
  "event": "job_completed",
  "timestamp": "2025-12-14T15:30:00Z",
  "organization_id": "uuid",
  "data": {
    "job_id": "uuid",
    "video_id": "uuid",
    "clips_count": 5,
    "duration_seconds": 900
  },
  "signature": "sha256=..."
}
```

### Regras

- Secret por organização: string aleatória de 32 caracteres, gerada no signup
- Validação: HMAC-SHA256
- Retry básico: 3 tentativas com backoff exponencial
- Timeout: 30 segundos
- Não bloqueia SSE (assíncrono)
- Integração totalmente opcional

---

## 6. Execução com GPU

### Características

- Execução com GPU (quando disponível)
- Custo otimizado (GPU local reduz latência)
- Tempo reduzido de processamento
- Opção padrão para produção
- Fallback automático para CPU se GPU indisponível

### Impacto no Pipeline

```
Transcrição (Whisper)
├── Com GPU: ~1-2 min para 1 hora de vídeo
├── Fallback CPU: ~5-10 min para 1 hora de vídeo
└── Ambos: mesmo output, mesma qualidade
```

---

## 7. Ranking por Feedback Real

**Princípio:** Feedback explícito do usuário melhora ranking futuro

### Funcionalidades

**Marcar Clip como Bom/Ruim**
- Usuário clica ⭐ (bom) ou 👎 (ruim)
- Feedback persistido no banco
- Sem treino de modelo

**Uso do Feedback**
- Ajuste de score futuro (ponderação)
- Reordenação de ranking
- Evolução incremental
- Feedback afeta apenas clips gerados em jobs futuros (não clips antigos)

### Modelo de Dados

```
ClipFeedback
├── feedback_id (UUID)
├── clip_id (FK)
├── user_id (FK)
├── rating (good | bad)
├── created_at
└── updated_at
```

### Algoritmo de Ajuste

```
feedback_score = (good_count - bad_count) / total_feedback * 100
final_score = (engagement_score * 0.7) + (feedback_score * 0.3)
```

### Fluxo

```
1. Usuário marca clip como bom
2. Feedback registrado
3. Score do clip ajustado
4. Próximo job: clips com bom feedback ranqueados mais alto
5. Sem retraining, apenas ponderação
```

---

## 8. Templates Visuais

**Princípio:** Sistema simples de templates aplicados via FFmpeg

### Tipos de Templates

- **Overlays**: Logos, marcas d'água
- **Barras**: Barra de título, barra inferior
- **Efeitos**: Transições, zoom, blur
- **Estilos de Texto**: Fontes, cores, sombras

### Configuração

```
Template
├── template_id (UUID)
├── name
├── type (overlay | bar | effect | text_style)
├── ffmpeg_filter (comando FFmpeg)
├── preview_url
├── is_active
├── created_at
└── version
```

### Aplicação

- Via FFmpeg durante clipping
- Versionável (histórico)
- Disponível para todos os planos (Starter, Pro, Business)
- Template padrão para Starter: "Minimal" (sem overlays, sem efeitos)
- Sem impacto no pipeline (aplicado no final)

### Exemplos de Templates

```
Template: "Pro Style"
├── Overlay: Logo no canto superior
├── Bar: Barra inferior com título
├── Text: Fonte bold, branca, sombra
└── Effect: Zoom suave no início

Template: "Minimal"
├── Overlay: Nenhum
├── Bar: Nenhuma
├── Text: Fonte simples, branca
└── Effect: Nenhum

Template: "Branded"
├── Overlay: Logo + marca d'água
├── Bar: Barra superior com nome do canal
├── Text: Fonte custom, cor da marca
└── Effect: Transição suave
```

---

## 9. Multi-idioma Avançado

**Princípio:** Suporte robusto a múltiplos idiomas

### Funcionalidades

**Detecção Automática de Idioma**
- Whisper detecta idioma do áudio
- Compara com idioma configurado
- Usa idioma detectado se confiança > 90%

**Fallback para Idioma Configurado**
- Se detecção falhar, usa idioma do onboarding
- Sem bloqueio de processamento

**Persistência do Idioma Detectado**
- Registra idioma detectado no job
- Usa para análise semântica (Gemini)
- Histórico para análise

**Suporte a Vídeos Multilíngues**
- Detecta mudanças de idioma
- Registra timestamps de mudança
- Análise por segmento de idioma

### Modelo de Dados

```
TranscriptSegment (expandido)
├── segment_id (UUID)
├── transcript_id (FK)
├── text
├── start_time
├── end_time
├── language (pt-BR, en, es, etc)
├── confidence (0-100)
└── is_auto_detected
```

### Idiomas Suportados

- Português (Brasil, Portugal)
- Inglês (US, UK)
- Espanhol
- Francês
- Alemão
- Italiano
- Japonês
- Chinês (Simplificado, Tradicional)
- Outro

---

## 10. Analytics de Performance

**Princípio:** Métricas pós-publicação para ranking futuro

### Coleta de Dados

**Métricas por Rede Social**
- Views
- Likes / Reactions
- Shares / Reposts
- Comments
- Engagement rate

**Associação ao Clip**
```
ClipPerformance
├── performance_id (UUID)
├── clip_id (FK)
├── platform (tiktok | instagram | etc)
├── post_url
├── views
├── likes
├── shares
├── comments
├── engagement_rate
├── collected_at
└── updated_at
```

### Integração com Ranking

- Performance histórica influencia score futuro
- Clips com alta performance ranqueados mais alto
- Feedback loop: bom desempenho → melhor ranking

### Regras

- Coleta via webhooks de redes sociais (futuro)
- Não bloqueia MVP
- Opcional por organização
- Histórico completo para análise

### Fluxo

```
1. Clip publicado em TikTok
2. Webhook de TikTok: views, likes, shares
3. Dados persistidos em ClipPerformance
4. Score do clip ajustado
5. Próximo job: clips com alta performance ranqueados mais alto
```

---

## 11. Integração com Pipeline (sem impacto)

### Pontos de Integração

**Validação de Créditos**
- Verifica quotas técnicas também
- Rejeita se alguma quota atingida

**Job Creation**
- Aplica defaults se não especificado
- Registra onboarding_data para análise

**Transcrição**
- Detecta idioma automaticamente
- Persiste idioma detectado

**Análise Semântica**
- Usa idioma detectado para contexto
- Usa feedback histórico para ponderação

**Seleção de Clips**
- Considera feedback real do usuário
- Considera performance histórica
- Aplica defaults de score mínimo

**Clipping**
- Aplica templates visuais se configurado
- Sem impacto no tempo (FFmpeg paralelo)

**Postagem**
- Enfileira webhook se configurado
- Não bloqueia SSE

---

## 12. Monitoramento via Discord


### Eventos Monitorados

**Erros Críticos:**
- Job falhou após 5 retries
- Taxa de falha > 10% em uma etapa
- Timeout de worker detectado
- Erro de storage (R2)

**Assinaturas:**
- Novo usuário registrado
- Upgrade de plano
- Downgrade de plano
- Cancelamento de assinatura
- Falha de pagamento

**Logs Estruturados:**
- Erros de API
- Erros de integração
- Erros de autenticação
- Erros de validação

**Relatórios Diários:**
- Total de jobs processados
- Taxa de sucesso/falha
- Receita do dia (MRR)
- Usuários ativos
- Alertas críticos

### Configuração Discord

```
Webhook URL: https://discord.com/api/webhooks/[ID]/[TOKEN]
Canais:
├── #errors (erros críticos)
├── #subscriptions (eventos de assinatura)
├── #logs (logs estruturados)
└── #reports (relatórios diários)
```

### Formato de Mensagem

```json
{
  "event": "job_failed",
  "severity": "critical",
  "timestamp": "2025-12-14T15:30:00Z",
  "job_id": "uuid",
  "organization_id": "uuid",
  "error_code": "AUDIO_ERROR",
  "message": "Falha ao processar áudio após 5 tentativas",
  "retry_count": 5,
  "last_step": "transcribing"
}
```

---

## 13. Clean Code & SOLID Principles


### Clean Code Rules

**Nomenclatura Clara:**
- Variáveis: `user_id`, `job_status`, `clip_duration` (snake_case)
- Funções: `process_video()`, `validate_credits()` (verbos + substantivos)
- Classes: `VideoProcessor`, `ClipSelector` (PascalCase)
- Constantes: `MAX_RETRY_COUNT`, `DEFAULT_LANGUAGE` (UPPER_SNAKE_CASE)

**Funções Pequenas e Focadas:**
- Máximo 20 linhas por função
- Uma responsabilidade por função
- Nomes descritivos (evitar `process()`, `handle()`)
- Sem side effects inesperados

**Comentários Mínimos:**
- Código auto-explicativo é melhor que comentários
- Comentários apenas para "por quê", não "o quê"
- Manter comentários sincronizados com código

**DRY (Don't Repeat Yourself):**
- Extrair lógica comum em funções reutilizáveis
- Usar composição sobre duplicação
- Centralizar configurações

### SOLID Principles

**S - Single Responsibility Principle:**
- `VideoDownloader`: apenas download
- `VideoNormalizer`: apenas normalização
- `TranscriptionService`: apenas transcrição
- Cada classe tem uma razão para mudar

**O - Open/Closed Principle:**
- Aberto para extensão (novos processadores)
- Fechado para modificação (não quebrar existente)
- Usar interfaces e abstrações

**L - Liskov Substitution Principle:**
- Subclasses podem substituir superclasses
- Contrato respeitado em todas as implementações
- Sem surpresas no comportamento

**I - Interface Segregation Principle:**
- Interfaces pequenas e específicas
- Não forçar implementação de métodos não usados
- Exemplo: `IProcessor`, `IStorage`, `INotifier`

**D - Dependency Inversion Principle:**
- Depender de abstrações, não de implementações
- Injetar dependências (constructor injection)
- Facilita testes e manutenção

### Testing Standards

**Unit Tests:**
- Mínimo 80% de cobertura
- Testes para happy path e edge cases
- Mocks para dependências externas

**Integration Tests:**
- Testar fluxo completo de job
- Testar integração com banco de dados
- Testar integração com APIs externas

**Test Naming:**
- `test_process_video_with_valid_input()`
- `test_process_video_with_invalid_format()`
- `test_process_video_timeout_after_30_minutes()`