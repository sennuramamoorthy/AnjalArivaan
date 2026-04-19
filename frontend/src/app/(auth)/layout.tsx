export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-brand-50 via-ink-50 to-white px-4">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="inline-flex items-center gap-2 text-brand-600 font-semibold text-xl">
            <span className="w-8 h-8 rounded-full bg-brand-500 text-white inline-flex items-center justify-center">
              அ
            </span>
            <span>AnjalArivaan</span>
          </div>
          <p className="text-ink-500 text-sm mt-1">Takshashila University</p>
        </div>
        {children}
      </div>
    </div>
  );
}
