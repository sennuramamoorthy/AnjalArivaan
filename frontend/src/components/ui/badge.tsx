import { cn } from "@/lib/cn";

export function Badge({
  tone = "muted",
  children,
  className,
}: {
  tone?: "urgent" | "muted";
  children: React.ReactNode;
  className?: string;
}) {
  return <span className={cn(tone === "urgent" ? "badge-urgent" : "badge-muted", className)}>{children}</span>;
}
