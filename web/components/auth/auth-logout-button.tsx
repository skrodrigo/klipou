"use client";

import { useMutation } from "@tanstack/react-query";
import { logout } from "@/infra/auth/auth";

export function AuthLogoutButton() {
  const { mutateAsync, isPending } = useMutation({
    mutationKey: ["auth-logout"],
    mutationFn: () => logout(),
  });

  return (
    <button
      type="button"
      onClick={() => void mutateAsync()}
      disabled={isPending}
      className="px-3 py-1 rounded border border-border bg-secondary text-secondary-foreground disabled:opacity-50"
    >
      {isPending ? "Saindo..." : "Sair"}
    </button>
  );
}
