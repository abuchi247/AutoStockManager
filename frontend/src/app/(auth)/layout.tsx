/**
 * Auth Layout
 *
 * Clean centered card layout for authentication pages.
 * Used for login, password reset, and other unauthenticated pages.
 */

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 py-12 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-6 animate-fade-in">
        {/* Branding */}
        <div className="text-center">
          <div className="flex items-center justify-center gap-2.5 mb-2">
            <svg className="h-9 w-9 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            AutoStockManager
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Spare Parts ERP System
          </p>
        </div>

        {/* Card */}
        <div className="rounded-lg border border-gray-200 bg-white px-8 py-8 shadow-md">
          {children}
        </div>
      </div>
    </div>
  );
}
