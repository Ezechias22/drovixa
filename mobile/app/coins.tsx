import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { Alert, Platform, Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { EmptyState, ErrorState, LoadingState } from '@/components/ScreenStates';
import { getCoinPackages, getWallet } from '@/features/monetization/api';
import { useAuthStore } from '@/stores/auth-store';
import { colors } from '@/theme';

const nativePlatform = Platform.OS === 'ios' ? 'ios' : 'android';

export default function CoinsScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { width } = useWindowDimensions();
  const session = useAuthStore((state) => state.session);
  const wallet = useQuery({ queryKey: ['wallet'], queryFn: getWallet, enabled: Boolean(session) });
  const packages = useQuery({
    queryKey: ['coin-packages', nativePlatform],
    queryFn: () => getCoinPackages(nativePlatform),
  });
  const cardWidth = width >= 700 ? '48.5%' : '100%';

  if (!session) {
    return <View style={styles.gate}><Text style={styles.gateIcon}>✦</Text><Text style={styles.gateTitle}>Your Drovixa wallet</Text><Text style={styles.muted}>Sign in to sync purchases and unlock episodes.</Text><Pressable style={styles.primary} onPress={() => router.push('/login')}><Text style={styles.primaryText}>Sign in</Text></Pressable></View>;
  }
  if (wallet.isPending || packages.isPending) return <LoadingState label="Loading your wallet…" />;
  if (wallet.isError || packages.isError) return <ErrorState retry={() => { void wallet.refetch(); void packages.refetch(); }} />;

  return <ScrollView style={styles.screen} contentContainerStyle={[styles.content, { paddingTop: insets.top + 18 }]}>
    <Text style={styles.eyebrow}>DROVIXA WALLET</Text><Text style={styles.title}>Coins</Text>
    <View style={styles.balance}><Text style={styles.balanceLabel}>Available balance</Text><View style={styles.balanceRow}><Text style={styles.balanceValue}>{wallet.data?.total_balance ?? 0}</Text><Text style={styles.balanceUnit}>coins</Text></View><View style={styles.balanceParts}><View style={styles.balancePart}><Text style={styles.partLabel}>Purchased</Text><Text style={styles.partValue}>{wallet.data?.coin_balance ?? 0}</Text></View><View style={styles.balancePart}><Text style={styles.partLabel}>Bonus</Text><Text style={styles.partValue}>{wallet.data?.bonus_coin_balance ?? 0}</Text></View></View></View>
    <Text style={styles.sectionTitle}>Choose a coin pack</Text><Text style={styles.muted}>Your balance changes only after server-side store verification.</Text>
    {!packages.data?.length ? <EmptyState title="No coin packs yet" body="Published mobile packages will appear here." /> : <View style={styles.grid}>{packages.data.map((item) => <View key={item.id} style={[styles.card, { width: cardWidth }, item.featured && styles.featured]}>{item.featured ? <Text style={styles.badge}>BEST VALUE</Text> : null}<Text style={styles.cardLabel}>{item.name}</Text><Text style={styles.coins}>{item.coins.toLocaleString()}</Text><Text style={styles.cardLabel}>coins</Text>{item.bonus_coins > 0 ? <Text style={styles.bonus}>+ {item.bonus_coins.toLocaleString()} bonus</Text> : null}<Pressable style={styles.buy} onPress={() => Alert.alert('Store billing setup', 'The secure Apple/Google receipt-verification architecture is ready. Activate the native store product before production purchases.')}><Text style={styles.buyText}>{new Intl.NumberFormat(undefined, { style: 'currency', currency: item.currency }).format(Number(item.price))}</Text></Pressable></View>)}</View>}
  </ScrollView>;
}

const styles = StyleSheet.create({screen:{flex:1,backgroundColor:colors.background},content:{padding:18,paddingBottom:50},gate:{flex:1,alignItems:'center',justifyContent:'center',padding:30,backgroundColor:colors.background},gateIcon:{color:colors.accent,fontSize:45},gateTitle:{color:colors.text,fontSize:32,fontWeight:'900',textAlign:'center',marginTop:16},muted:{color:colors.muted,lineHeight:21,marginTop:7},primary:{marginTop:24,borderRadius:99,backgroundColor:colors.text,paddingHorizontal:26,paddingVertical:14},primaryText:{color:colors.background,fontWeight:'900'},eyebrow:{color:colors.accent,fontSize:10,fontWeight:'900',letterSpacing:1.8},title:{color:colors.text,fontSize:40,fontWeight:'900',marginTop:7,marginBottom:20},balance:{borderRadius:28,padding:24,backgroundColor:'#1b1021'},balanceLabel:{color:colors.muted,fontSize:13},balanceRow:{flexDirection:'row',alignItems:'baseline',gap:8,marginTop:5},balanceValue:{color:colors.text,fontSize:58,fontWeight:'900'},balanceUnit:{color:'#f9a8d4',fontWeight:'800'},balanceParts:{flexDirection:'row',gap:10,marginTop:18},balancePart:{flex:1,padding:14,borderRadius:17,backgroundColor:'rgba(255,255,255,.06)'},partLabel:{color:colors.muted,fontSize:11},partValue:{color:colors.text,fontSize:20,fontWeight:'900',marginTop:3},sectionTitle:{color:colors.text,fontSize:25,fontWeight:'900',marginTop:31},grid:{flexDirection:'row',flexWrap:'wrap',gap:10,marginTop:18},card:{minHeight:270,borderRadius:24,padding:20,backgroundColor:colors.card},featured:{borderWidth:1,borderColor:'rgba(244,114,182,.55)',backgroundColor:'#1b1320'},badge:{alignSelf:'flex-start',color:colors.background,backgroundColor:'#f9a8d4',fontSize:9,fontWeight:'900',paddingHorizontal:9,paddingVertical:4,borderRadius:99},cardLabel:{color:colors.muted,fontSize:13,marginTop:10},coins:{color:colors.text,fontSize:38,fontWeight:'900',marginTop:8},bonus:{color:'#f9a8d4',fontWeight:'800',marginTop:12},buy:{marginTop:'auto',alignItems:'center',borderRadius:99,backgroundColor:colors.text,padding:13},buyText:{color:colors.background,fontWeight:'900'}});
