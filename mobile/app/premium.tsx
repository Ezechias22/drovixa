import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { Alert, Platform, Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { EmptyState, ErrorState, LoadingState } from '@/components/ScreenStates';
import { cancelSubscription, getCurrentSubscription, getSubscriptionPlans } from '@/features/monetization/api';
import { useAuthStore } from '@/stores/auth-store';
import { colors } from '@/theme';

const labels: Record<string, string> = { no_ads:'No interruptions',premium_content:'Premium Originals',offline_download:'Offline downloads',hd:'HD streaming',full_hd:'Full HD streaming',early_access:'Early access',bonus_coins:'Bonus coins',exclusive_content:'Exclusive episodes',device_limit:'Registered devices' };

export default function PremiumScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { width } = useWindowDimensions();
  const session = useAuthStore((state) => state.session);
  const plans = useQuery({ queryKey: ['subscription-plans'], queryFn: getSubscriptionPlans });
  const current = useQuery({ queryKey: ['subscription-current'], queryFn: getCurrentSubscription, enabled: Boolean(session) });
  const cancel = useMutation({ mutationFn: cancelSubscription, onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['subscription-current'] }) });
  const cardWidth = width >= 700 ? '48.5%' : '100%';
  if (plans.isPending || (session && current.isPending)) return <LoadingState label="Loading Premium…" />;
  if (plans.isError || current.isError) return <ErrorState retry={() => { void plans.refetch(); void current.refetch(); }} />;
  return <ScrollView style={styles.screen} contentContainerStyle={[styles.content,{paddingTop:insets.top+18}]}><Text style={styles.eyebrow}>DROVIXA PREMIUM</Text><Text style={styles.title}>Stories without limits.</Text><Text style={styles.subtitle}>Every benefit below is controlled remotely by Drovixa administration.</Text>
    {current.data ? <View style={styles.active}><Text style={styles.activeLabel}>ACTIVE MEMBERSHIP</Text><Text style={styles.activeTitle}>{current.data.plan.name}</Text><Text style={styles.muted}>Through {new Date(current.data.current_period_end).toLocaleDateString()}</Text>{!current.data.cancel_at_period_end?<Pressable style={styles.cancel} disabled={cancel.isPending} onPress={()=>cancel.mutate()}><Text style={styles.cancelText}>{cancel.isPending?'Updating…':'Cancel renewal'}</Text></Pressable>:<Text style={styles.ends}>Ends this period</Text>}</View>:null}
    {!plans.data?.length?<EmptyState title="No plans published" body="Premium plans will appear here when ready."/>:<View style={styles.grid}>{plans.data.map(plan=><View key={plan.id} style={[styles.card,{width:cardWidth},plan.featured&&styles.featured]}>{plan.featured?<Text style={styles.badge}>RECOMMENDED</Text>:null}<Text style={styles.planName}>{plan.name}</Text><Text style={styles.price}>{new Intl.NumberFormat(undefined,{style:'currency',currency:plan.currency}).format(Number(plan.price))}<Text style={styles.interval}> / {plan.interval}</Text></Text>{plan.trial_days>0?<Text style={styles.trial}>{plan.trial_days}-day trial</Text>:null}<View style={styles.benefits}>{Object.entries(plan.benefits).filter(([,value])=>Boolean(value)).map(([key,value])=><Text key={key} style={styles.benefit}>✓ {labels[key]??key.replaceAll('_',' ')}{typeof value==='number'?`: ${value}`:''}</Text>)}</View>{session?<Pressable disabled={Boolean(current.data)} style={[styles.choose,current.data&&styles.disabled]} onPress={()=>Alert.alert('Store billing setup',`The ${Platform.OS==='ios'?'Apple':'Google Play'} receipt-verification API is ready. Connect the native billing client before production purchases.`)}><Text style={styles.chooseText}>{current.data?'Membership active':'Choose plan'}</Text></Pressable>:<Pressable style={styles.choose} onPress={()=>router.push('/login')}><Text style={styles.chooseText}>Sign in to continue</Text></Pressable>}</View>)}</View>}
  </ScrollView>;
}

const styles=StyleSheet.create({screen:{flex:1,backgroundColor:colors.background},content:{padding:18,paddingBottom:50},eyebrow:{color:colors.accent,fontSize:10,fontWeight:'900',letterSpacing:1.8},title:{color:colors.text,fontSize:42,lineHeight:47,fontWeight:'900',marginTop:10,maxWidth:620},subtitle:{color:colors.muted,fontSize:15,lineHeight:22,marginTop:12,maxWidth:620},active:{marginTop:25,borderRadius:24,padding:20,backgroundColor:'#201226',borderWidth:1,borderColor:'rgba(244,114,182,.4)'},activeLabel:{color:'#f9a8d4',fontSize:9,fontWeight:'900',letterSpacing:1.4},activeTitle:{color:colors.text,fontSize:23,fontWeight:'900',marginTop:7},muted:{color:colors.muted,marginTop:5},cancel:{alignSelf:'flex-start',marginTop:16,borderRadius:99,paddingHorizontal:17,paddingVertical:10,backgroundColor:colors.cardSecondary},cancelText:{color:colors.text,fontWeight:'800'},ends:{color:colors.muted,fontWeight:'800',marginTop:15},grid:{flexDirection:'row',flexWrap:'wrap',gap:10,marginTop:27},card:{minHeight:410,borderRadius:27,padding:22,backgroundColor:colors.card},featured:{borderWidth:1,borderColor:'rgba(244,114,182,.55)',backgroundColor:'#1b1320'},badge:{alignSelf:'flex-start',borderRadius:99,paddingHorizontal:9,paddingVertical:4,backgroundColor:'#f9a8d4',color:colors.background,fontSize:9,fontWeight:'900'},planName:{color:colors.text,fontSize:24,fontWeight:'900',marginTop:18},price:{color:colors.text,fontSize:30,fontWeight:'900',marginTop:17},interval:{color:colors.muted,fontSize:12,fontWeight:'700'},trial:{color:'#f9a8d4',fontWeight:'800',marginTop:7},benefits:{gap:10,marginTop:23},benefit:{color:'#d1d5db',fontSize:13,textTransform:'capitalize'},choose:{marginTop:'auto',alignItems:'center',borderRadius:99,backgroundColor:colors.text,padding:14},disabled:{opacity:.4},chooseText:{color:colors.background,fontWeight:'900'}});
