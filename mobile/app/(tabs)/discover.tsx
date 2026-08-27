import { Ionicons } from '@expo/vector-icons';
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { ContentCard } from '@/components/ContentCard';
import { PageHeader } from '@/components/PageHeader';
import { EmptyState, ErrorState, LoadingState } from '@/components/ScreenStates';
import { getDiscover, getGenres } from '@/features/catalog/api';
import { useI18n } from '@/i18n';
import { colors } from '@/theme';

export default function Discover() {
  const { t } = useI18n();
  const inset = useSafeAreaInsets();
  const router = useRouter();
  const [genre, setGenre] = useState<string>();
  const [sort, setSort] = useState('popular');
  const genres = useQuery({ queryKey: ['genres'], queryFn: getGenres });
  const discover = useQuery({ queryKey: ['discover', genre, sort], queryFn: () => getDiscover({ genre, sort, limit: 40 }) });
  const sortLabels: Record<string, string> = { popular: t('discover.popular'), new: t('discover.new'), rating: t('discover.rating') };
  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <View style={{ paddingTop: inset.top }}><PageHeader /></View>
      <View style={styles.heading}>
        <Text style={styles.eyebrow}>{t('discover.eyebrow')}</Text>
        <Text style={styles.title}>{t('nav.discover')}</Text>
        <Pressable onPress={() => router.push('/search')} style={styles.search}>
          <Ionicons color={colors.muted} name="search-outline" size={20} />
          <Text style={styles.searchText}>{t('discover.search')}</Text>
        </Pressable>
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filters}>
        <Pressable onPress={() => setGenre(undefined)} style={[styles.chip, !genre && styles.active]}><Text style={[styles.chipText, !genre && styles.activeText]}>{t('discover.all')}</Text></Pressable>
        {genres.data?.map((item) => <Pressable key={item.id} onPress={() => setGenre(item.slug)} style={[styles.chip, genre === item.slug && styles.active]}><Text style={[styles.chipText, genre === item.slug && styles.activeText]}>{item.name}</Text></Pressable>)}
      </ScrollView>
      <View style={styles.sort}>{['popular', 'new', 'rating'].map((item) => <Pressable key={item} onPress={() => setSort(item)}><Text style={{ color: sort === item ? colors.text : colors.muted, fontWeight: '800' }}>{sortLabels[item]}</Text></Pressable>)}</View>
      {discover.isPending ? <LoadingState /> : null}
      {discover.isError ? <ErrorState retry={() => void discover.refetch()} /> : null}
      {discover.data ? discover.data.data.length ? <View style={styles.grid}>{discover.data.data.map((item) => <ContentCard key={item.id} item={item} />)}</View> : <EmptyState title={t('discover.emptyTitle')} body={t('discover.emptyBody')} /> : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background }, content: { paddingBottom: 34 }, heading: { padding: 18, gap: 8 }, eyebrow: { color: colors.accent, fontSize: 10, fontWeight: '900', letterSpacing: 1.4 }, title: { color: colors.text, fontSize: 38, fontWeight: '900' },
  search: { height: 52, flexDirection: 'row', alignItems: 'center', gap: 9, borderRadius: 18, paddingHorizontal: 17, backgroundColor: colors.card }, searchText: { color: colors.muted }, filters: { gap: 9, paddingHorizontal: 18, paddingBottom: 12 },
  chip: { paddingHorizontal: 15, paddingVertical: 10, borderRadius: 99, backgroundColor: colors.card }, active: { backgroundColor: colors.text }, chipText: { color: colors.muted, fontWeight: '700' }, activeText: { color: colors.background }, sort: { flexDirection: 'row', gap: 22, padding: 18 }, grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 14, paddingHorizontal: 18 },
});
