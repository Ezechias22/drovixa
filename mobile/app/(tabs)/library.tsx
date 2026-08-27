import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { ContentCard } from '@/components/ContentCard';
import { EmptyState, ErrorState, LoadingState } from '@/components/ScreenStates';
import { getFavorites } from '@/features/catalog/api';
import { useI18n } from '@/i18n';
import { useAuthStore } from '@/stores/auth-store';
import { colors } from '@/theme';

export default function LibraryScreen() {
  const inset = useSafeAreaInsets(); const router = useRouter(); const session = useAuthStore((state) => state.session);
  const { t } = useI18n();
  const favorites = useQuery({ queryKey: ['favorites'], queryFn: getFavorites, enabled: Boolean(session) });
  return <ScrollView style={styles.screen} contentContainerStyle={[styles.content, { paddingTop: inset.top + 18 }]}>
    <Text style={styles.eyebrow}>{t('library.eyebrow')}</Text><Text style={styles.title}>{t('library.title')}</Text>
    {!session ? <View style={styles.guest}><Text style={styles.guestTitle}>{t('library.guestTitle')}</Text><Text style={styles.muted}>{t('library.guestBody')}</Text><Pressable style={styles.button} onPress={() => router.push('/login')}><Text style={styles.buttonText}>{t('common.signIn')}</Text></Pressable></View> : null}
    {favorites.isPending && session ? <LoadingState /> : null}
    {favorites.isError ? <ErrorState retry={() => void favorites.refetch()} /> : null}
    {favorites.data ? favorites.data.length ? <View style={styles.grid}>{favorites.data.map((item) => <ContentCard key={item.id} item={item} />)}</View> : <EmptyState title={t('library.emptyTitle')} body={t('library.emptyBody')} /> : null}
  </ScrollView>;
}
const styles = StyleSheet.create({screen:{flex:1,backgroundColor:colors.background},content:{padding:18,paddingBottom:40},eyebrow:{color:colors.accent,fontSize:10,fontWeight:'900',letterSpacing:1.5},title:{color:colors.text,fontSize:38,fontWeight:'900',marginTop:7,marginBottom:22},guest:{minHeight:330,alignItems:'center',justifyContent:'center',gap:14,padding:28,borderRadius:24,backgroundColor:colors.card},guestTitle:{color:colors.text,fontSize:23,fontWeight:'900',textAlign:'center'},muted:{color:colors.muted,textAlign:'center',lineHeight:21},button:{marginTop:8,paddingHorizontal:26,paddingVertical:13,borderRadius:99,backgroundColor:colors.text},buttonText:{color:colors.background,fontWeight:'900'},grid:{flexDirection:'row',flexWrap:'wrap',gap:14}});
