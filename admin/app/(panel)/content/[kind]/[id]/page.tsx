import { ContentStudio } from '@/features/content-studio';

export default async function ContentStudioPage({
  params,
}: {
  params: Promise<{ kind: string; id: string }>;
}) {
  const { kind, id } = await params;

  if (kind !== 'series' && kind !== 'movies') {
    return <div className="page"><div className="notice">Unknown content type.</div></div>;
  }

  return <ContentStudio kind={kind} contentId={id} />;
}
