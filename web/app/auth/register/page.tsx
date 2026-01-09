import { AuthRegisterForm } from "@/components/auth/auth-register-form";
import Image from "next/image";
import Link from "next/link";

export default function RegisterPage() {
  return (
    <main className="h-screen max-w-md flex flex-col justify-center items-center mx-auto p-8 ">
      <Image
        src='/logos/klipai.svg'
        alt="logo"
        width={40}
        height={40}
        className="ml-1 mb-3 rounded-md"
        priority
        quality={100} />
      <AuthRegisterForm />
      <span className="mt-4 text-foreground">Tem conta? <Link href='/auth/login' className="underline text-muted-foreground">Login</Link></span>
    </main>
  );
}
