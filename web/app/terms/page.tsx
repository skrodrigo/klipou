import Image from "next/image"

export default function TermsPage() {
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

      <h1 className="mt-8 text-2xl font-semibold tracking-tight">Termos de Uso</h1>
      <p className="mt-2 text-sm text-muted-foreground">Última atualização: {new Date().toLocaleDateString("pt-BR")}</p>

      <div className="mt-8 space-y-4 font-light text-sm leading-relaxed text-foreground">
        <p>
          Ao acessar e usar o Klip AI, você concorda com estes Termos de Uso. Se você não concordar com algum
          item, recomendamos que não utilize o serviço.
        </p>

        <p>
          O Klip AI oferece ferramentas para envio e processamento de vídeos com o objetivo de gerar conteúdos e
          recortes. Você é responsável pelo conteúdo que envia, incluindo a conformidade com direitos autorais,
          permissões e leis aplicáveis.
        </p>

        <p>
          Você se compromete a não utilizar o serviço para publicar, compartilhar ou processar conteúdo ilegal,
          ofensivo, que viole direitos de terceiros ou que contenha informações sensíveis sem autorização.
        </p>

        <p>
          Podemos atualizar, alterar ou descontinuar funcionalidades do produto a qualquer momento. Também podemos
          suspender o acesso em caso de uso indevido, tentativa de fraude, abuso de recursos, ou violação destes
          termos.
        </p>

        <p>
          Na extensão máxima permitida por lei, o Klip AI não se responsabiliza por perdas indiretas, lucros
          cessantes, ou danos decorrentes do uso (ou impossibilidade de uso) da plataforma.
        </p>

        <p>
          Se tiver dúvidas sobre estes Termos de Uso, entre em contato com a gente pelo canal de suporte indicado
          na plataforma.
        </p>
      </div>
    </main>
  )
}
