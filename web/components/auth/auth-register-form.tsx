"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useRouter } from "next/navigation";
import { register as registerUser, type RegisterPayload } from "@/infra/auth/auth";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Spinner } from "../ui/spinner";

const registerSchema = z.object({
  email: z.string().email("Email inválido"),
  password: z.string().min(6, "Senha deve ter pelo menos 6 caracteres"),
  confirmPassword: z.string(),
}).refine((data) => data.password === data.confirmPassword, {
  message: "As senhas não correspondem",
  path: ["confirmPassword"],
});

type RegisterFormValues = z.infer<typeof registerSchema>;

export function AuthRegisterForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const form = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      email: "",
      password: "",
      confirmPassword: "",
    },
  });

  const { mutate, isPending } = useMutation({
    mutationFn: (payload: RegisterPayload) => registerUser(payload),
    onSuccess: () => {
      toast.success("Registro realizado com sucesso!");
      queryClient.invalidateQueries({ queryKey: ["auth-session"] });
      router.push("/dashboard");
    },
    onError: (error) => {
      const errorMessage = error instanceof Error ? error.message : "Erro ao registrar";

      let friendlyMessage = "Erro ao registrar. Por favor, tente novamente.";

      if (errorMessage.includes("409") || errorMessage.includes("already exists") || errorMessage.includes("já existe")) {
        friendlyMessage = "Este email já está registrado. Faça login ou use outro email.";
      } else if (errorMessage.includes("400") || errorMessage.includes("Bad Request")) {
        friendlyMessage = "Dados inválidos. Verifique seu email e senha.";
      } else if (errorMessage.includes("network") || errorMessage.includes("Failed to fetch")) {
        friendlyMessage = "Erro de conexão. Verifique sua internet e tente novamente.";
      } else if (errorMessage.includes("timeout")) {
        friendlyMessage = "Conexão expirou. Por favor, tente novamente.";
      } else if (errorMessage.includes("password")) {
        friendlyMessage = "Senha inválida. Deve ter pelo menos 6 caracteres.";
      } else if (errorMessage.includes("email")) {
        friendlyMessage = "Email inválido. Verifique o formato.";
      }

      toast.error(friendlyMessage);
    },
  });

  async function onSubmit(values: RegisterFormValues) {
    const { confirmPassword, ...payload } = values;
    mutate(payload);
  }

  return (
    <Form {...form}>

      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 w-full max-w-xs mx-auto">
        <div className="space-y-3">
          <Button type="button" variant="default" className="w-full flex items-center justify-center gap-2 bg-foreground text-background">
            <img src="/logos/google.svg" alt="Google" className="w-5 h-5" />
            <span>Continuar com Google</span>
          </Button>
          <Button type="button" variant="default" className="w-full flex items-center justify-center gap-2 dark:bg-black bg-foreground dark:text-foreground">
            <img src="/logos/apple.svg" alt="Apple" className="w-5 h-5 dark:block hidden" />
            <img src="/logos/apple-black.svg" alt="Apple" className="w-5 h-5 dark:hidden block" />
            <span>Continuar com Apple</span>
          </Button>
        </div>
        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t dark:border-[#252525] border-[#EEF0F4]"></div>
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-2 bg-background text-foreground">OU</span>
          </div>
        </div>
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl>
                <Input type="email" placeholder="seu@email.com" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="password"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Senha</FormLabel>
              <FormControl>
                <Input type="password" placeholder="senha" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="confirmPassword"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Confirmar Senha</FormLabel>
              <FormControl>
                <Input type="password" placeholder="confirme sua senha" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit" disabled={isPending} className="w-full">
          {isPending ? <Spinner /> : "Registrar"}
        </Button>
      </form>
    </Form>
  );
}
