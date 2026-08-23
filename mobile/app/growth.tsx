import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { useState } from 'react';
import { Alert, Pressable, Share, StyleSheet, Text, TextInput, View, ScrollView } from 'react-native';

import { applyReferral, claimDailyReward, getDailyReward, getReferralSummary } from '@/features/growth/api';
import { colors } from '@/theme';

function message(error: unknown) {
  return axios.isAxiosError(error) ? error.response?.data?.error?.message ?? 'Request failed.' : 'Request failed.';
}

export default function GrowthScreen() {
  const client = useQueryClient();
  const [code, setCode] = useState('');
  const reward = useQuery({ queryKey: ['daily-reward'], queryFn: getDailyReward });
  const referral = useQuery({ queryKey: ['referral'], queryFn: getReferralSummary });
  const claim = useMutation({ mutationFn: claimDailyReward, onSuccess: (data) => client.setQueryData(['daily-reward'], data), onError: (e) => Alert.alert('Daily reward', message(e)) });
  const apply = useMutation({ mutationFn: () => applyReferral(code), onSuccess: (data) => { client.setQueryData(['referral'], data); setCode(''); }, onError: (e) => Alert.alert('Referral', message(e)) });

  return <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
    <Text style={styles.eyebrow}>GROW WITH DROVIXA</Text><Text style={styles.title}>Rewards & referrals</Text>
    <View style={styles.card}><Text style={styles.cardTitle}>Daily streak</Text><Text style={styles.muted}>{reward.data?.claimed_today ? `Day ${reward.data.claim?.streak_day} claimed · +${reward.data.claim?.coins} coins` : `Day ${reward.data?.next_streak_day ?? 1} gives ${reward.data?.next_coins ?? 5} coins`}</Text><View style={styles.calendar}>{(reward.data?.calendar ?? [5,5,10,10,15,20,50]).map((coins,index)=><View key={index} style={[styles.day,reward.data?.claim?.streak_day === index+1 && styles.dayActive]}><Text style={styles.dayLabel}>D{index+1}</Text><Text style={styles.dayCoins}>{coins}</Text></View>)}</View><Pressable disabled={reward.data?.claimed_today || claim.isPending} onPress={()=>claim.mutate()} style={[styles.button,(reward.data?.claimed_today||claim.isPending)&&styles.disabled]}><Text style={styles.buttonText}>{reward.data?.claimed_today?'Come back tomorrow':claim.isPending?'Claiming…':'Claim daily coins'}</Text></Pressable></View>
    <View style={styles.card}><Text style={styles.cardTitle}>Invite friends</Text><Text style={styles.code}>{referral.data?.code ?? 'Loading…'}</Text><Text style={styles.muted}>{referral.data?.invited ?? 0} friends · {referral.data?.earned_coins ?? 0} coins earned</Text><Pressable onPress={()=>referral.data&&Share.share({message:`Join me on Drovixa with code ${referral.data.code}: ${referral.data.share_url}`})} style={styles.outline}><Text style={styles.outlineText}>Share invite</Text></Pressable>{!referral.data?.applied?<View style={styles.apply}><TextInput autoCapitalize="characters" onChangeText={setCode} placeholder="Referral code" placeholderTextColor={colors.muted} style={styles.input} value={code}/><Pressable disabled={!code||apply.isPending} onPress={()=>apply.mutate()} style={styles.smallButton}><Text style={styles.buttonText}>Apply</Text></Pressable></View>:<Text style={styles.success}>✓ Referral already applied</Text>}</View>
  </ScrollView>;
}

const styles=StyleSheet.create({screen:{flex:1,backgroundColor:colors.background},content:{padding:20,paddingBottom:48},eyebrow:{color:colors.accent,fontSize:10,fontWeight:'900',letterSpacing:1.5},title:{color:colors.text,fontSize:34,fontWeight:'900',marginTop:7,marginBottom:22},card:{padding:20,borderRadius:24,backgroundColor:colors.card,marginBottom:18},cardTitle:{color:colors.text,fontSize:21,fontWeight:'900'},muted:{color:colors.muted,marginTop:7,lineHeight:20},calendar:{flexDirection:'row',gap:5,marginVertical:18},day:{flex:1,alignItems:'center',paddingVertical:9,borderRadius:12,backgroundColor:colors.cardSecondary},dayActive:{backgroundColor:'#ff4d8d55'},dayLabel:{color:colors.muted,fontSize:9,fontWeight:'800'},dayCoins:{color:colors.text,fontWeight:'900',marginTop:3},button:{alignItems:'center',padding:15,borderRadius:99,backgroundColor:colors.accent},disabled:{opacity:.45},buttonText:{color:colors.text,fontWeight:'900'},code:{color:colors.accent,fontSize:28,fontWeight:'900',letterSpacing:2,marginTop:14},outline:{alignItems:'center',padding:14,borderRadius:99,borderWidth:1,borderColor:colors.line,marginTop:16},outlineText:{color:colors.text,fontWeight:'900'},apply:{flexDirection:'row',gap:8,marginTop:14},input:{flex:1,minHeight:50,paddingHorizontal:14,borderRadius:15,backgroundColor:colors.cardSecondary,color:colors.text},smallButton:{justifyContent:'center',paddingHorizontal:20,borderRadius:15,backgroundColor:colors.accent},success:{color:'#86efac',marginTop:16,fontWeight:'800'}});
