import { AuthLoginForm } from "@/components/forms/auth-login-form";
import Image from "next/image";
import Link from "next/link";

export default function LoginPage() {
  return (
    <main className="max-w-md h-screen flex flex-col justify-center items-center mx-auto p-8">
      <Image src='/klipou.svg' alt="logo" width={100} height={100} className="mb-20" />
      <AuthLoginForm />
      <span className="mt-4">Não tem conta? <Link href='/auth/register' className="underline text-blue-400">Register</Link></span>
    </main>
  );
}
