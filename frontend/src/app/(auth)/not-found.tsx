import NotFoundView from '@/components/NotFoundView';

export default function AuthNotFound() {
  return <NotFoundView routeSegment="authentication" homeHref="/login" />;
}
