import type { QueryClient } from '@tanstack/react-query';
import { createRootRouteWithContext, Outlet } from '@tanstack/react-router';

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()(
  {
    component: RootLayout,
  },
);

function RootLayout() {
  return (
    <div className="min-h-screen bg-neutral-50 text-neutral-900">
      <header className="border-b border-neutral-200 px-6 py-4">
        <span className="font-semibold tracking-tight">Joby</span>
      </header>
      <main className="px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
