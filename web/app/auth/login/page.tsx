import { AuthLoginForm } from "@/components/auth/auth-login-form";
import Image from "next/image";
import Link from "next/link";

export default function LoginPage() {
  return (
    <main className="max-w-md h-screen flex flex-col justify-center items-center mx-auto p-8">
      <Image
        src='/logos/klipai.svg'
        alt="logo"
        width={40}
        height={40}
        className="ml-1 mb-3 rounded-md"
        priority
        quality={100} />
      <AuthLoginForm />
      <span className="mt-4 text-foreground">Não tem conta? <Link href='/auth/register' className="underline text-muted-foreground">Registre-se</Link></span>
    </main>
  );
}
