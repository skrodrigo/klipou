import { AuthRegisterForm } from "@/components/auth/auth-register-form";
import Image from "next/image";
import Link from "next/link";

export default function RegisterPage() {
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
        <AuthRegisterForm />
        <div className="text-center text-xs font-light text-foreground mt-8">
          Ao continuar, você concorda com nossos <Link href='/terms' target="_blank" aria-label="Termos de Uso" about="Termos de Uso" className="underline text-muted-foreground">Termos de Uso</Link> e <Link href='/privacy' target="_blank" aria-label="Política de Privacidade" about="Política de Privacidade" className="underline text-muted-foreground">Política de Privacidade</Link>
        </div>
      </div>


    </main>
  );
}
