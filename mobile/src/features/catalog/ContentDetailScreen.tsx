import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { ImageBackground, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { EmptyState, ErrorState, LoadingState } from '@/components/ScreenStates';
import { CommentsPanel } from '@/features/community/CommentsPanel';
import { setLike } from '@/features/community/api';
import { getFeatureFlags } from '@/features/configuration/api';
import { RatingControl } from '@/features/personalization/RatingControl';
import { useI18n } from '@/i18n';
import { useAuthStore } from '@/stores/auth-store';
import { colors } from '@/theme';

import { getContentDetail, getEpisodes, toggleFavorite } from './api';
import type { ContentDetail } from './types';

export function ContentDetailScreen({ type, slug }: { type: 'series' | 'movie'; slug: string }) {
  const { t } = useI18n();
  const router = useRouter();
  const queryClient = useQueryClient();
  const session = useAuthStore((state) => state.session);
  const detailKey = ['content', type, slug] as const;
  const detail = useQuery({ queryKey: detailKey, queryFn: () => getContentDetail(type, slug) });
  const flags = useQuery({ queryKey: ['feature-flags'], queryFn: getFeatureFlags });
  const episodes = useQuery({
    queryKey: ['episodes', detail.data?.series_id],
    queryFn: () => getEpisodes(detail.data!.series_id!),
    enabled: type === 'series' && Boolean(detail.data?.series_id),
  });
  const favorite = useMutation({
    mutationFn: () => toggleFavorite(detail.data!.id, Boolean(detail.data!.is_favorite)),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: detailKey });
      queryClient.setQueryData(detailKey, (old: ContentDetail | undefined) => old ? { ...old, is_favorite: !old.is_favorite } : old);
    },
    onSettled: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: detailKey }),
        queryClient.invalidateQueries({ queryKey: ['favorites'] }),
      ]);
    },
  });
  const like = useMutation({
    mutationFn: () => setLike('content', detail.data!.id, Boolean(detail.data!.is_liked)),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: detailKey });
      queryClient.setQueryData(detailKey, (old: ContentDetail | undefined) => old ? {
        ...old,
        is_liked: !old.is_liked,
        like_count: Math.max(0, (old.like_count ?? 0) + (old.is_liked ? -1 : 1)),
      } : old);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: detailKey }),
  });

  if (detail.isPending) return <LoadingState />;
  if (detail.isError) return <ErrorState retry={() => void detail.refetch()} />;

  const item = detail.data;
  const play = () => {
    if (type === 'movie' && item.movie_id) {
      router.push({ pathname: '/watch/[id]', params: { id: item.movie_id, target: 'movie' } });
    } else if (episodes.data?.[0]) {
      router.push({ pathname: '/watch/[id]', params: { id: episodes.data[0].id, target: 'episode' } });
    }
  };

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <ImageBackground source={item.backdrop_url ? { uri: item.backdrop_url } : undefined} style={styles.hero}>
        <View style={styles.shade}>
          <Text style={styles.badge}>{item.premium ? 'PREMIUM ORIGINAL' : item.type === 'movie' ? t('content.movie').toUpperCase() : item.type.toUpperCase()}</Text>
          <Text style={styles.title}>{item.title}</Text>
          <Text style={styles.meta}>{item.release_date?.slice(0, 4) ?? 'New'} · {item.age_rating} · ★ {Number(item.rating).toFixed(1)}</Text>
        </View>
      </ImageBackground>
      <View style={styles.body}>
        <Text style={styles.description}>{item.description ?? item.short_description}</Text>
        <View style={styles.actions}>
          <Pressable onPress={play} style={styles.play}><Text style={styles.playText}>▶ {t('content.play')}</Text></Pressable>
          <Pressable onPress={() => session ? favorite.mutate() : router.push('/login')} style={styles.actionPill}>
            <Text style={styles.actionText}>{item.is_favorite ? `✓ ${t('content.saved')}` : `+ ${t('content.myList')}`}</Text>
          </Pressable>
          <Pressable onPress={() => session ? like.mutate() : router.push('/login')} style={styles.actionPill}>
            <Text style={[styles.actionText, item.is_liked && styles.likedText]}>{item.is_liked ? '♥' : '♡'} {item.like_count ?? 0}</Text>
          </Pressable>
        </View>
        {item.genres.length ? <Text style={styles.small}>{t('content.genres')} · {item.genres.map((genre) => genre.name).join(' · ')}</Text> : null}
        {item.cast.length ? <View style={styles.section}><Text style={styles.heading}>{t('content.cast')}</Text><Text style={styles.small}>{item.cast.map((credit) => `${credit.actor.name}${credit.character_name ? ` · ${credit.character_name}` : ''}`).join('  •  ')}</Text></View> : null}
        {session && flags.data?.ratings_enabled?.enabled ? <RatingControl contentId={item.id} /> : null}
        {type === 'series' ? <View style={styles.section}>
          <Text style={styles.heading}>{t('content.episodes')}</Text>
          {episodes.isPending ? <LoadingState /> : episodes.data?.length ? episodes.data.map((episode) => (
            <Pressable key={episode.id} onPress={() => router.push({ pathname: '/watch/[id]', params: { id: episode.id, target: 'episode' } })} style={styles.episode}>
              <View><Text style={styles.episodeTitle}>{episode.episode_number}. {episode.title}</Text><Text style={styles.small}>{episode.duration_seconds ? `${Math.ceil(episode.duration_seconds / 60)} min` : episode.access_type}</Text></View>
              <Text style={styles.episodePlay}>▶</Text>
            </Pressable>
          )) : <EmptyState title={t('content.noEpisodes')} body={t('content.noEpisodesBody')} />}
        </View> : null}
        {flags.data?.comments_enabled?.enabled ? <CommentsPanel targetId={item.id} targetType="content" /> : null}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background }, content: { paddingBottom: 36 }, hero: { height: 430, backgroundColor: colors.card },
  shade: { flex: 1, justifyContent: 'flex-end', gap: 9, padding: 24, backgroundColor: '#00000045' }, badge: { color: colors.accent, fontSize: 10, fontWeight: '900', letterSpacing: 1.4 },
  title: { color: colors.text, fontSize: 38, fontWeight: '900' }, meta: { color: '#ddd', fontWeight: '700' }, body: { padding: 20, gap: 18 }, description: { color: '#d1d5db', fontSize: 15, lineHeight: 23 },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 }, play: { minWidth: 130, flexGrow: 1, alignItems: 'center', padding: 15, borderRadius: 99, backgroundColor: colors.text }, playText: { color: colors.background, fontWeight: '900' },
  actionPill: { minWidth: 105, flexGrow: 1, alignItems: 'center', padding: 15, borderRadius: 99, backgroundColor: colors.card }, actionText: { color: colors.text, fontWeight: '900' }, likedText: { color: colors.accent },
  small: { color: colors.muted, lineHeight: 21 }, section: { gap: 12, marginTop: 10 }, heading: { color: colors.text, fontSize: 21, fontWeight: '900' },
  episode: { minHeight: 68, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 14, borderRadius: 16, backgroundColor: colors.card }, episodeTitle: { color: colors.text, fontWeight: '800', marginBottom: 5 }, episodePlay: { color: colors.accent, fontSize: 20 },
});
