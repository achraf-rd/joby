import { useQuery } from '@tanstack/react-query';
import { createFileRoute } from '@tanstack/react-router';
import { api } from '@/lib/api';

export const Route = createFileRoute('/')({
  component: Home,
});

function Home() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const { data, error, response } = await api.GET('/health');
      if (error || !response.ok)
        throw new Error(`API returned ${response.status}`);
      return data;
    },
  });

  return (
    <section className="max-w-xl space-y-2">
      <h1 className="text-2xl font-semibold">Joby</h1>
      <p className="text-neutral-600">
        Finds job offers, tailors your CV for each one, and applies once you
        approve.
      </p>
      <p className="text-sm" data-testid="api-status">
        API:{' '}
        {health.isPending ? 'checking…' : health.isError ? 'unreachable' : 'ok'}
      </p>
    </section>
  );
}
