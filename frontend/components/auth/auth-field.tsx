import { InputHTMLAttributes } from "react";

interface AuthFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
}

export function AuthField({ label, id, ...props }: AuthFieldProps) {
  return (
    <label className="grid gap-2 text-sm font-medium" htmlFor={id}>
      {label}
      <input
        id={id}
        className="min-h-11 rounded-md border border-border bg-background px-3 text-sm outline-none transition placeholder:text-muted-foreground focus:border-primary"
        {...props}
      />
    </label>
  );
}
