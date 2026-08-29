import { useRouter } from 'expo-router';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { getEpisodes } from '@/features/catalog/api';
import type { ContentCardData, ContinueWatchingItem } from '@/features/catalog/types';
import { useI18n } from '@/i18n';
import { usePlaybackStore } from '@/stores/playback-store';
import { colors } from '@/theme';

function progress(item: ContentCardData | ContinueWatchingItem): item is ContinueWatchingItem { return 'content' in item; }

export function ContentCard({ item, rank }: { item: ContentCardData | ContinueWatchingItem; rank?: number }) {
  const { t } = useI18n();
  const router = useRouter();
  const content = progress(item) ? item.content : item;
  const open = async () => {
    if (progress(item) && item.episode) {
      router.push({ pathname: '/watch/[id]', params: { id: item.episode.id, target: 'episode' } });
      return;
    }
    if (content.type === 'movie' && content.movie_id) {
      router.push({ pathname: '/watch/[id]', params: { id: content.movie_id, target: 'movie' } });
      return;
    }
    if (content.type === 'series' && content.series_id) {
      const episodes = await getEpisodes(content.series_id);
      const remembered = usePlaybackStore.getState().lastEpisodeBySeries[content.series_id];
      const selected = episodes.find((episode) => episode.id === remembered) ?? episodes[0];
      if (selected) {
        router.push({ pathname: '/watch/[id]', params: { id: selected.id, target: 'episode' } });
        return;
      }
    }
    router.push({ pathname: content.type === 'series' ? '/series/[slug]' : '/movie/[slug]', params: { slug: content.slug } });
  };
  return <Pressable onPress={() => void open()} style={styles.wrap}><View style={styles.poster}>{content.poster_url ? <Image source={{ uri: content.poster_url }} style={styles.image} /> : <View style={styles.fallback}><Text style={styles.letter}>D</Text></View>}{content.premium ? <Text style={styles.badge}>PREMIUM</Text> : null}{rank ? <Text style={styles.rank}>{rank}</Text> : null}</View><Text numberOfLines={1} style={styles.title}>{content.title}</Text><Text style={styles.meta}>{content.type === 'series' ? t('content.episodeCount', { count: content.total_episodes ?? 0 }) : t('content.movie')}</Text></Pressable>;
}

const styles = StyleSheet.create({ wrap: { width: 132, gap: 5 }, poster: { width: 132, height: 198, overflow: 'hidden', borderRadius: 16, backgroundColor: colors.card }, image: { width: '100%', height: '100%' }, fallback: { flex: 1, alignItems: 'center', justifyContent: 'center' }, letter: { color: colors.muted, fontSize: 40, fontWeight: '900' }, badge: { position: 'absolute', right: 7, top: 7, color: colors.text, backgroundColor: '#000b', borderRadius: 9, padding: 4, fontSize: 8, fontWeight: '900' }, rank: { position: 'absolute', bottom: 2, left: 7, color: colors.text, fontSize: 34, fontWeight: '900' }, title: { color: colors.text, fontSize: 13, fontWeight: '800' }, meta: { color: colors.muted, fontSize: 10 } });
