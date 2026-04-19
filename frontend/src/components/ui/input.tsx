import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string | null;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, id, className, ...rest }, ref) => (
    <div>
      {label && (
        <label htmlFor={id} className="label">
          {label}
        </label>
      )}
      <input
        ref={ref}
        id={id}
        className={cn("input", error && "border-brand-500", className)}
        aria-invalid={!!error}
        {...rest}
      />
      {error && <p className="mt-1 text-xs text-brand-700">{error}</p>}
    </div>
  )
);
Input.displayName = "Input";
