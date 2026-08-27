import { Ionicons } from '@expo/vector-icons';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { ContentCard } from '@/components/ContentCard';
import { EmptyState, ErrorState, LoadingState } from '@/components/ScreenStates';
import { getTrendingSearches, searchContent } from '@/features/catalog/api';
import { useI18n } from '@/i18n';
import { colors } from '@/theme';

export default function SearchScreen() {
  const { t } = useI18n();
  const [input, setInput] = useState('');
  const [query, setQuery] = useState('');
  useEffect(() => { const id = setTimeout(() => setQuery(input.trim()), 300); return () => clearTimeout(id); }, [input]);
  const results = useQuery({ queryKey: ['search', query], queryFn: () => searchContent(query), enabled: query.length >= 2 });
  const trending = useQuery({ queryKey: ['search', 'trending'], queryFn: getTrendingSearches });
  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <View style={styles.searchBox}>
        <Ionicons color={colors.muted} name="search-outline" size={21} />
        <TextInput autoFocus value={input} onChangeText={setInput} placeholder={t('search.placeholder')} placeholderTextColor={colors.muted} style={styles.input} />
      </View>
      {!query ? <><Text style={styles.heading}>{t('search.trending')}</Text><View style={styles.chips}>{trending.data?.map((item) => <Pressable key={item} style={styles.chip} onPress={() => setInput(item)}><Text style={styles.chipText}>{item}</Text></Pressable>)}</View></> : null}
      {results.isPending && query ? <LoadingState label={t('search.searching')} /> : null}
      {results.isError ? <ErrorState retry={() => void results.refetch()} /> : null}
      {results.data ? results.data.length ? <View style={styles.grid}>{results.data.map((item) => <ContentCard key={item.id} item={item} />)}</View> : <EmptyState title={t('search.emptyTitle')} body={t('search.emptyBody')} /> : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background }, content: { padding: 18, paddingBottom: 36 }, searchBox: { height: 54, flexDirection: 'row', alignItems: 'center', gap: 9, borderRadius: 18, paddingHorizontal: 17, backgroundColor: colors.card }, input: { flex: 1, color: colors.text, fontSize: 16 },
  heading: { color: colors.text, fontSize: 20, fontWeight: '900', marginTop: 26, marginBottom: 14 }, chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 9 }, chip: { paddingHorizontal: 14, paddingVertical: 10, borderRadius: 99, backgroundColor: colors.card }, chipText: { color: colors.muted, fontWeight: '700' }, grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 14, marginTop: 24 },
});
