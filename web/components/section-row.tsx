import { ContentCard } from './content-card';
import type { HomeSection } from '@/features/catalog/types';
export function SectionRow({ section }: { section: HomeSection }) { return <section><h2 className="mb-5 text-2xl font-black tracking-tight">{section.title}</h2><div className="grid grid-cols-2 gap-x-4 gap-y-7 pb-3 sm:flex sm:gap-4 sm:overflow-x-auto">{section.items.map((item, i) => <ContentCard key={'content' in item ? item.progress.id : item.id} item={item} rank={section.presentation === 'ranked' ? i + 1 : undefined} />)}</div></section>; }
