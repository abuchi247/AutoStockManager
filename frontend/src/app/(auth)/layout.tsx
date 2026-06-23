/**
 * Auth Layout
 *
 * Centered card layout with glassmorphism design.
 * Used for login, password reset, and other unauthenticated pages.
 */

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="relative flex min-h-screen items-center justify-center px-4 py-12 sm:px-6 lg:px-8 overflow-hidden">
      {/* Background gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-indigo-100 via-purple-50 to-pink-100" />
      
      {/* Decorative blobs */}
      <div className="absolute top-0 -left-40 h-80 w-80 rounded-full bg-purple-300/30 blur-3xl" />
      <div className="absolute bottom-0 -right-40 h-80 w-80 rounded-full bg-indigo-300/30 blur-3xl" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-96 w-96 rounded-full bg-pink-200/20 blur-3xl" />

      <div className="relative z-10 w-full max-w-md space-y-8 animate-fade-in">
        <div className="text-center">
          <div className="flex items-center justify-center gap-3 mb-3">
            <svg className="h-10 w-10 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-gradient">
            AutoStockManager
          </h1>
          <p className="mt-2 text-sm text-gray-500">
            Spare Parts ERP System
          </p>
        </div>
        <div className="glass-card px-8 py-10">
          {children}
        </div>
      </div>
    </div>
  );
}
