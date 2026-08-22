import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Dimensions, FlatList, ImageBackground, Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { ErrorState, LoadingState } from '@/components/ScreenStates';
import { getShorts } from '@/features/catalog/api';
import type { ShortData } from '@/features/catalog/types';
import { CommentsPanel } from '@/features/community/CommentsPanel';
import { getLikeStatus, setLike } from '@/features/community/api';
import { getFeatureFlags } from '@/features/configuration/api';
import { useAuthStore } from '@/stores/auth-store';
import { colors } from '@/theme';

const ITEM_HEIGHT = Dimensions.get('window').height - 70;

export default function ShortsScreen() {
  const [commentingOn, setCommentingOn] = useState<ShortData | null>(null);
  const shorts = useQuery({ queryKey: ['shorts'], queryFn: getShorts });
  const flags = useQuery({ queryKey: ['feature-flags'], queryFn: getFeatureFlags });
  if (shorts.isPending) return <LoadingState label="Loading shorts…" />;
  if (shorts.isError) return <ErrorState retry={() => void shorts.refetch()} />;
  return <>
    <FlatList data={shorts.data} keyExtractor={(item) => item.id} pagingEnabled showsVerticalScrollIndicator={false}
      ListEmptyComponent={<View style={styles.empty}><Text style={styles.emptyTitle}>Shorts are coming</Text><Text style={styles.muted}>Published vertical episodes will appear here.</Text></View>}
      renderItem={({ item }) => <ShortCard commentsEnabled={flags.data?.comments_enabled?.enabled === true} item={item} onComments={() => setCommentingOn(item)} />} />
    <Modal animationType="slide" onRequestClose={() => setCommentingOn(null)} visible={Boolean(commentingOn)}>
      <View style={styles.commentsScreen}>
        <View style={styles.commentsHeader}><View><Text style={styles.commentsTitle}>Comments</Text><Text style={styles.muted}>{commentingOn?.series.title}</Text></View><Pressable onPress={() => setCommentingOn(null)}><Text style={styles.close}>×</Text></Pressable></View>
        <ScrollView contentContainerStyle={styles.commentsContent}>{commentingOn ? <CommentsPanel targetId={commentingOn.id} targetType="short" /> : null}</ScrollView>
      </View>
    </Modal>
  </>;
}

function ShortCard({ commentsEnabled, item, onComments }: { commentsEnabled: boolean; item: ShortData; onComments: () => void }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const session = useAuthStore((state) => state.session);
  const key = ['like', 'short', item.id] as const;
  const status = useQuery({ queryKey: key, queryFn: () => getLikeStatus('short', item.id), enabled: Boolean(session) });
  const like = useMutation({
    mutationFn: () => setLike('short', item.id, Boolean(status.data?.liked)),
    onMutate: async () => { await queryClient.cancelQueries({ queryKey: key }); queryClient.setQueryData(key, (old: typeof status.data) => old ? { ...old, liked: !old.liked, count: Math.max(0, old.count + (old.liked ? -1 : 1)) } : old); },
    onSettled: () => queryClient.invalidateQueries({ queryKey: key }),
  });
  return <View style={styles.item}><ImageBackground source={item.thumbnail_url ? { uri: item.thumbnail_url } : undefined} style={styles.media}>
    <Pressable onPress={() => router.push({ pathname: '/watch/[id]', params: { id: item.id, target: 'episode' } })} style={styles.scrim}><View style={styles.copy}><Text style={styles.series}>{item.series.title}</Text><Text style={styles.episode}>Episode {item.episode_number} · {item.title}</Text><Text style={styles.play}>▶ Tap to watch</Text></View></Pressable>
    <View style={styles.actions}>
      <Pressable accessibilityLabel="Like short" onPress={() => session ? like.mutate() : router.push('/login')} style={styles.action}><Text style={[styles.actionText, status.data?.liked && styles.liked]}>{status.data?.liked ? '♥' : '♡'}</Text><Text style={styles.actionCount}>{status.data?.count ?? 0}</Text></Pressable>
      {commentsEnabled ? <Pressable accessibilityLabel="Open comments" onPress={onComments} style={styles.action}><Text style={styles.actionText}>◌</Text><Text style={styles.actionCount}>Talk</Text></Pressable> : null}
      <View style={styles.action}><Text style={styles.actionText}>↗</Text><Text style={styles.actionCount}>Share</Text></View>
    </View>
  </ImageBackground></View>;
}

const styles = StyleSheet.create({
  item: { height: ITEM_HEIGHT, backgroundColor: '#000' }, media: { flex: 1, backgroundColor: colors.card }, scrim: { flex: 1, justifyContent: 'flex-end', padding: 22, paddingRight: 86, paddingBottom: 34, backgroundColor: '#00000025' }, copy: { gap: 8 }, series: { color: colors.text, fontSize: 22, fontWeight: '900' }, episode: { color: '#eee', fontSize: 14 }, play: { color: colors.accent, fontWeight: '900', marginTop: 7 },
  actions: { position: 'absolute', right: 18, bottom: 32, gap: 14 }, action: { width: 52, minHeight: 52, alignItems: 'center', justifyContent: 'center', borderRadius: 26, backgroundColor: '#000b' }, actionText: { color: colors.text, fontSize: 22 }, actionCount: { color: colors.text, fontSize: 9, fontWeight: '800' }, liked: { color: colors.accent },
  empty: { height: ITEM_HEIGHT, alignItems: 'center', justifyContent: 'center', gap: 10, padding: 30, backgroundColor: colors.background }, emptyTitle: { color: colors.text, fontSize: 24, fontWeight: '900' }, muted: { color: colors.muted, textAlign: 'center' },
  commentsScreen: { flex: 1, backgroundColor: colors.background }, commentsHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingTop: 56, paddingBottom: 14, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.line }, commentsTitle: { color: colors.text, fontSize: 24, fontWeight: '900' }, close: { color: colors.text, fontSize: 32 }, commentsContent: { padding: 20, paddingBottom: 48 },
});
