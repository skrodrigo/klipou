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
      toast.error(error instanceof Error ? error.message : "Erro ao fazer login");
    },
  });

  async function onSubmit(values: LoginFormValues) {
    mutate(values);
  }

  return (
    <Form {...form}>

      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 w-full max-w-xs mx-auto">
        <div className="space-y-3">
          <Button type="button" variant="default" className="w-full flex items-center justify-center gap-2 bg-[#EEF0F4] dark:bg-white text-background">
            <img src="/logos/google.svg" alt="Google" className="w-5 h-5" />
            <span>Continuar com Google</span>
          </Button>
          <Button type="button" variant="default" className="w-full flex items-center justify-center gap-2 dark:bg-black bg-[#EEF0F4] dark:text-white text-foreground">
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
            <span className="px-2 dark:bg-[#121212] bg-[#F9FAFB] dark:text-white text-[#101010] ">OU</span>
          </div>
        </div>
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel className="text">Email</FormLabel>
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
      </form>
    </Form>
  );
}
