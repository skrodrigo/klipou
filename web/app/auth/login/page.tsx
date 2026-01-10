import { AuthLoginForm } from "@/components/auth/auth-login-form";
import Image from "next/image";
import Link from "next/link";

export default function LoginPage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col px-8 py-8">
      <div className="flex flex-1 flex-col items-center justify-center">
        <Image
          src='/logos/klipai.svg'
          alt="logo"
          width={40}
          height={40}
          className="ml-1 mb-10 rounded-md"
          priority
          quality={100} />
        <AuthLoginForm />
        <span className="mt-4 text-foreground font-light">Não tem conta? <Link href='/auth/register' className="underline text-muted-foreground">Registre-se</Link></span>
      </div>

      <div className="mt-auto pb-2 text-center text-xs font-light text-foreground">
        Ao continuar, você concorda com nossos <Link href='/terms' target="_blank" aria-label="Termos de Uso" about="Termos de Uso" className="underline text-muted-foreground">Termos de Uso</Link> e <Link href='/privacy' target="_blank" aria-label="Política de Privacidade" about="Política de Privacidade" className="underline text-muted-foreground">Política de Privacidade</Link>
      </div>
    </main>
  );
}
