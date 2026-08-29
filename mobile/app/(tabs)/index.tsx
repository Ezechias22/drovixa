import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { PageHeader } from '@/components/PageHeader';
import { EmptyState, ErrorState, LoadingState } from '@/components/ScreenStates';
import { getDiscover, getEpisodes } from '@/features/catalog/api';
import type { ContentCardData } from '@/features/catalog/types';
import { useI18n } from '@/i18n';
import { colors } from '@/theme';
import { usePlaybackStore } from '@/stores/playback-store';

type Feed = 'popular' | 'new' | 'series';

function PosterCard({ item }: { item: ContentCardData }) {
  const { t } = useI18n();
  const router = useRouter();
  const [opening, setOpening] = useState(false);
  const open = async () => {
    if (opening) return;
    setOpening(true);
    try {
      if (item.type === 'movie' && item.movie_id) {
        router.push({ pathname: '/watch/[id]', params: { id: item.movie_id, target: 'movie' } });
        return;
      }
      if (item.type === 'series' && item.series_id) {
        const episodes = await getEpisodes(item.series_id);
        const remembered = usePlaybackStore.getState().lastEpisodeBySeries[item.series_id];
        const selected = episodes.find((episode) => episode.id === remembered) ?? episodes[0];
        if (selected) {
          router.push({ pathname: '/watch/[id]', params: { id: selected.id, target: 'episode' } });
          return;
        }
      }
      router.push({ pathname: item.type === 'series' ? '/series/[slug]' : '/movie/[slug]', params: { slug: item.slug } });
    } finally {
      setOpening(false);
    }
  };
  return (
    <Pressable disabled={opening} onPress={() => void open()} style={({ pressed }) => [styles.card, (pressed || opening) && styles.pressed]}>
      <View style={styles.poster}>
        {item.poster_url ? <Image source={{ uri: item.poster_url }} resizeMode="cover" style={styles.posterImage} /> : (
          <View style={styles.fallback}><Text style={styles.fallbackLetter}>D</Text><Text style={styles.fallbackName}>DROVIXA</Text></View>
        )}
        {item.premium ? <Text style={styles.premium}>VIP</Text> : null}
        <View style={styles.posterShade} />
      </View>
      <Text numberOfLines={1} style={styles.cardTitle}>{item.title}</Text>
      <Text numberOfLines={1} style={styles.cardMeta}>{item.type === 'series' ? t('content.episodeCount', { count: item.total_episodes ?? 0 }) : t('content.movie')}</Text>
    </Pressable>
  );
}

export default function Home() {
  const { t } = useI18n();
  const inset = useSafeAreaInsets();
  const [feed, setFeed] = useState<Feed>('popular');
  const catalog = useQuery({
    queryKey: ['home-poster-grid', feed],
    queryFn: () => getDiscover({
      sort: feed === 'new' ? 'new' : 'popular',
      type: feed === 'series' ? 'series' : undefined,
      limit: 40,
    }),
  });
  const labels: Record<Feed, string> = {
    popular: t('discover.popular'), new: t('discover.new'), series: t('home.series'),
  };
  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <View style={{ paddingTop: inset.top }}><PageHeader /></View>
      <View style={styles.heading}><Text style={styles.eyebrow}>DROVIXA</Text><Text style={styles.title}>{t('home.catalog')}</Text></View>
      <View style={styles.tabs}>{(['popular', 'new', 'series'] as Feed[]).map((item) => <Pressable key={item} onPress={() => setFeed(item)} style={[styles.tab, feed === item && styles.activeTab]}><Text style={[styles.tabText, feed === item && styles.activeTabText]}>{labels[item]}</Text></Pressable>)}</View>
      {catalog.isPending ? <LoadingState /> : null}
      {catalog.isError ? <ErrorState retry={() => void catalog.refetch()} /> : null}
      {catalog.data?.data.length ? <View style={styles.grid}>{catalog.data.data.map((item) => <PosterCard item={item} key={item.id} />)}</View> : null}
      {catalog.data && !catalog.data.data.length ? <EmptyState title={t('home.emptyTitle')} body={t('home.emptyBody')} /> : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background }, content: { paddingBottom: 38 },
  heading: { paddingHorizontal: 16, paddingTop: 10, paddingBottom: 14 }, eyebrow: { color: colors.accent, fontSize: 11, fontWeight: '900', letterSpacing: 2.5 }, title: { color: colors.text, fontSize: 30, lineHeight: 36, fontWeight: '900', marginTop: 4 },
  tabs: { flexDirection: 'row', gap: 8, paddingHorizontal: 16, paddingBottom: 18 }, tab: { flex: 1, alignItems: 'center', paddingVertical: 10, borderRadius: 99, backgroundColor: colors.card }, activeTab: { backgroundColor: colors.text }, tabText: { color: colors.muted, fontSize: 12, fontWeight: '900' }, activeTabText: { color: colors.background },
  grid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', rowGap: 20, paddingHorizontal: 14 }, card: { width: '48.4%', gap: 5 }, pressed: { opacity: 0.78, transform: [{ scale: 0.985 }] },
  poster: { width: '100%', aspectRatio: 2 / 3, overflow: 'hidden', borderRadius: 15, backgroundColor: colors.card, borderWidth: 1, borderColor: '#ffffff12' }, posterImage: { width: '100%', height: '100%' }, posterShade: { position: 'absolute', left: 0, right: 0, bottom: 0, height: '22%', backgroundColor: '#00000022' },
  fallback: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#17131d' }, fallbackLetter: { color: colors.accent, fontSize: 52, fontWeight: '900' }, fallbackName: { color: colors.muted, fontSize: 8, fontWeight: '900', letterSpacing: 2 }, premium: { position: 'absolute', right: 7, top: 7, color: '#fff', backgroundColor: colors.accent, borderRadius: 8, paddingHorizontal: 7, paddingVertical: 4, fontSize: 8, fontWeight: '900', overflow: 'hidden' },
  cardTitle: { color: colors.text, fontSize: 13, fontWeight: '900', paddingHorizontal: 2 }, cardMeta: { color: colors.muted, fontSize: 10, paddingHorizontal: 2 },
});
