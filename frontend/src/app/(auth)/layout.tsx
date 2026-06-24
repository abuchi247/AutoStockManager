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
    <div className="flex min-h-screen items-center justify-center bg-page px-4 py-12 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-6 animate-fade-in">
        {/* Branding */}
        <div className="text-center">
          <h1 className="text-2xl font-bold tracking-tight text-[#333]">
            AutoStockManager
          </h1>
          <p className="mt-1 text-sm text-[#666]">
            Spare Parts ERP System
          </p>
        </div>

        {/* Card */}
        <div className="rounded-xl bg-white px-5 py-6 sm:px-8 sm:py-8 shadow-[0_20px_60px_rgba(0,0,0,0.1)]">
          {children}
        </div>
      </div>
    </div>
  );
}
