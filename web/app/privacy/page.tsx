import Image from "next/image"

export default function PrivacyPage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-2xl flex-col px-6 py-10">
      <div className="flex items-center gap-3">
        <Image
          src="/logos/klipai.svg"
          alt="Klip AI"
          width={32}
          height={32}
          className="rounded-md"
          priority
          quality={100}
        />
        <span className="text-sm font-medium">Klip AI</span>
      </div>

      <h1 className="mt-8 text-2xl font-semibold tracking-tight">Política de Privacidade</h1>
      <p className="mt-2 text-sm text-muted-foreground">Última atualização: {new Date().toLocaleDateString("pt-BR")}</p>

      <div className="mt-8 space-y-4 font-light text-sm leading-relaxed text-foreground">
        <p>
          Esta Política de Privacidade descreve, de forma simples, como coletamos e usamos informações quando você
          utiliza o Klip AI.
        </p>

        <p>
          Podemos coletar informações fornecidas por você (por exemplo, e-mail e dados de conta) e dados necessários
          para o funcionamento do serviço (como identificadores técnicos e informações de sessão).
        </p>

        <p>
          Ao enviar vídeos ou links para processamento, podemos armazenar temporariamente arquivos e metadados para
          executar as etapas de upload, processamento e geração de resultados.
        </p>

        <p>
          Usamos essas informações para:

          melhorar o produto,

          operar a plataforma,

          fornecer suporte,

          e manter segurança e prevenção de abusos.
        </p>

        <p>
          Não vendemos seus dados pessoais. Podemos compartilhar informações apenas quando necessário para operar o
          serviço (por exemplo, provedores de infraestrutura) ou quando exigido por lei.
        </p>

        <p>
          Você pode solicitar esclarecimentos, correções ou remoção de dados conforme aplicável. Para isso, utilize
          o canal de suporte disponível na plataforma.
        </p>
      </div>
    </main>
  )
}
