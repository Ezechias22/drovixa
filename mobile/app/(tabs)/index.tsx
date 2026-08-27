import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { FlatList, ImageBackground, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { ContentCard } from '@/components/ContentCard';
import { PageHeader } from '@/components/PageHeader';
import { EmptyState, ErrorState, LoadingState } from '@/components/ScreenStates';
import { getHome } from '@/features/catalog/api';
import { AdCard } from '@/features/growth/AdCard';
import { useI18n } from '@/i18n';
import { colors } from '@/theme';

export default function Home() {
  const { t } = useI18n();
  const inset = useSafeAreaInsets();
  const router = useRouter();
  const home = useQuery({ queryKey: ['home'], queryFn: getHome });
  if (home.isPending) return <LoadingState />;
  if (home.isError) return <ErrorState retry={() => void home.refetch()} />;
  const hero = home.data.hero[0];
  const openHero = () => hero && router.push({
    pathname: hero.type === 'series' ? '/series/[slug]' : '/movie/[slug]',
    params: { slug: hero.slug },
  });
  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <View style={{ paddingTop: inset.top }}><PageHeader /></View>
      {hero ? (
        <ImageBackground source={hero.backdrop_url ? { uri: hero.backdrop_url } : undefined} style={styles.hero} imageStyle={styles.heroImage}>
          <View style={styles.shade}>
            <Text style={styles.premium}>{hero.premium ? t('home.original') : t('home.featured')}</Text>
            <Text style={styles.heroTitle}>{hero.title}</Text>
            <Text numberOfLines={3} style={styles.description}>{hero.short_description}</Text>
            <View style={styles.actions}>
              <Pressable onPress={openHero} style={styles.primary}><Text style={styles.primaryText}>▶ {t('home.watch')}</Text></Pressable>
              <Pressable onPress={openHero} style={styles.secondary}><Text style={styles.secondaryText}>{t('home.more')}</Text></Pressable>
            </View>
          </View>
        </ImageBackground>
      ) : null}
      <View style={styles.sections}>
        <AdCard />
        {home.data.sections.map((section) => (
          <View key={section.id} style={styles.section}>
            <Text style={styles.sectionTitle}>{section.title}</Text>
            <FlatList
              contentContainerStyle={styles.row}
              data={section.items}
              horizontal
              keyExtractor={(item) => 'content' in item ? item.progress.id : item.id}
              renderItem={({ item, index }) => <ContentCard item={item} rank={section.presentation === 'ranked' ? index + 1 : undefined} />}
              showsHorizontalScrollIndicator={false}
            />
          </View>
        ))}
        {!hero && !home.data.sections.length ? <EmptyState title={t('home.emptyTitle')} body={t('home.emptyBody')} /> : null}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background }, content: { paddingBottom: 36 },
  hero: { height: 510, marginHorizontal: 14, borderRadius: 26, overflow: 'hidden', backgroundColor: colors.card }, heroImage: { borderRadius: 26 }, shade: { flex: 1, justifyContent: 'flex-end', gap: 10, padding: 22, backgroundColor: '#08090b55' },
  premium: { color: colors.accent, fontSize: 10, fontWeight: '900', letterSpacing: 1.5 }, heroTitle: { color: colors.text, fontSize: 36, lineHeight: 40, fontWeight: '900' }, description: { color: '#ddd', fontSize: 14, lineHeight: 20 },
  actions: { flexDirection: 'row', gap: 10, marginTop: 8 }, primary: { backgroundColor: colors.text, borderRadius: 99, padding: 13 }, primaryText: { color: colors.background, fontWeight: '900' }, secondary: { backgroundColor: '#ffffff22', borderRadius: 99, padding: 13 }, secondaryText: { color: colors.text, fontWeight: '800' },
  sections: { paddingTop: 28, gap: 30 }, section: { gap: 12 }, sectionTitle: { color: colors.text, fontSize: 20, fontWeight: '900', paddingHorizontal: 18 }, row: { gap: 12, paddingHorizontal: 18 },
});
