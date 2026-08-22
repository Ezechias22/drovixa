import { ContentCard } from './content-card';
import type { HomeSection } from '@/features/catalog/types';
export function SectionRow({ section }: { section: HomeSection }) { return <section><h2 className="mb-5 text-2xl font-black tracking-tight">{section.title}</h2><div className="scrollbar-hidden flex gap-4 overflow-x-auto pb-3">{section.items.map((item, i) => <ContentCard key={'content' in item ? item.progress.id : item.id} item={item} rank={section.presentation === 'ranked' ? i + 1 : undefined} />)}</div></section>; }
