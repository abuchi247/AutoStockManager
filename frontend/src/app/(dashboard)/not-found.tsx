import NotFoundView from '@/components/NotFoundView';

export default function DashboardNotFound() {
  return <NotFoundView routeSegment="dashboard" homeHref="/dashboard" />;
}
