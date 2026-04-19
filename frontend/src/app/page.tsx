import { redirect } from "next/navigation";

export default function Home() {
  // Server-side unauthenticated redirect — real gating happens in /dashboard via useAuth.
  redirect("/dashboard");
}
