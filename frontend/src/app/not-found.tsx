import NotFoundView from '@/components/NotFoundView';

export default function RootNotFound() {
  return <NotFoundView routeSegment="application" homeHref="/dashboard" />;
}
