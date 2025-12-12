import { AuthRegisterForm } from "@/components/forms/auth-register-form";
import Image from "next/image";
import Link from "next/link";

export default function RegisterPage() {
  return (
    <main className="h-screen max-w-md flex flex-col justify-center items-center mx-auto p-8 ">
      <Image src='/logos/klipou.svg' alt="logo" width={100} height={100} className="mb-10 w-20" priority quality={100} />
      <AuthRegisterForm />
      <span className="mt-4 text-foreground">Tem conta? <Link href='/auth/login' className="underline text-blue-400">Login</Link></span>
    </main>
  );
}
