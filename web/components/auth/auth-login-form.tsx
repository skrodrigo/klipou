"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useRouter } from "next/navigation";
import { login, type LoginPayload } from "@/infra/auth/auth";
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

const loginSchema = z.object({
  email: z.string().email("Email inválido"),
  password: z.string().min(1, "Senha é obrigatória"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export function AuthLoginForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const { mutate, isPending } = useMutation({
    mutationFn: (values: LoginFormValues) =>
      login({
        email: values.email,
        password: values.password,
      }),
    onSuccess: () => {
      toast.success("Login realizado com sucesso!");
      queryClient.invalidateQueries({ queryKey: ["auth-session"] });
      router.push("/dashboard");
    },
    onError: (error) => {
      const errorMessage = error instanceof Error ? error.message : "Erro ao fazer login";

      let friendlyMessage = "Erro ao fazer login. Por favor, tente novamente.";

      if (errorMessage.includes("401") || errorMessage.includes("Unauthorized")) {
        friendlyMessage = "Email ou senha incorretos. Verifique seus dados e tente novamente.";
      } else if (errorMessage.includes("404") || errorMessage.includes("not found")) {
        friendlyMessage = "Usuário não encontrado. Verifique seu email e tente novamente.";
      } else if (errorMessage.includes("network") || errorMessage.includes("Failed to fetch")) {
        friendlyMessage = "Erro de conexão. Verifique sua internet e tente novamente.";
      } else if (errorMessage.includes("timeout")) {
        friendlyMessage = "Conexão expirou. Por favor, tente novamente.";
      }

      toast.error(friendlyMessage);
    },
  });

  async function onSubmit(values: LoginFormValues) {
    mutate(values);
  }

  return (
    <Form {...form}>

      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 w-full max-w-xs mx-auto">
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
        <Button type="submit" disabled={isPending} className="w-full">
          {isPending ? <Spinner /> : "Entrar"}
        </Button>

        <div className="space-y-3 mt-10">
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
      </form>


    </Form>
  );
}
