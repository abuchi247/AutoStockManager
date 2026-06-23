/**
 * Auth Layout
 *
 * Centered card layout without sidebar navigation.
 * Used for login, password reset, and other unauthenticated pages.
 */

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-100 px-4 py-12 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">
            AutoStockManager
          </h1>
          <p className="mt-2 text-sm text-gray-600">
            Spare Parts ERP System
          </p>
        </div>
        <div className="rounded-lg bg-white px-6 py-8 shadow-md sm:px-10">
          {children}
        </div>
      </div>
    </div>
  );
}
