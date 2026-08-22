import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { logout } from '@/features/auth/api';
import { getFeatureFlags } from '@/features/configuration/api';
import { useAuthStore } from '@/stores/auth-store';
import { colors } from '@/theme';

const menu = ['Profiles', 'Premium', 'Coins', 'My List', 'Downloads', 'Notifications', 'Language', 'Subtitle settings', 'Playback', 'Devices', 'Security', 'Help center'];
export default function ProfileScreen() {
  const inset=useSafeAreaInsets(), router=useRouter(), queryClient=useQueryClient();
  const session=useAuthStore((state)=>state.session), setSession=useAuthStore((state)=>state.setSession);
  const flags=useQuery({queryKey:['feature-flags'],queryFn:getFeatureFlags});
  const visibleMenu=menu.filter((item)=>(item!=='Premium'||flags.data?.subscriptions_enabled?.enabled)&&(item!=='Coins'||flags.data?.coins_enabled?.enabled));
  const signOut=useMutation({mutationFn:logout,onSettled:async()=>{await setSession(null);queryClient.clear();}});
  return <ScrollView style={styles.screen} contentContainerStyle={[styles.content,{paddingTop:inset.top+18}]}><Text style={styles.eyebrow}>ACCOUNT</Text><Text style={styles.title}>Profile</Text>
    {session?<View style={styles.account}><View style={styles.avatar}><Text style={styles.avatarText}>{session.user.name.slice(0,1).toUpperCase()}</Text></View><View><Text style={styles.name}>{session.user.name}</Text><Text style={styles.email}>{session.user.email}</Text></View></View>:<View style={styles.guest}><Text style={styles.name}>Guest mode</Text><Text style={styles.email}>Sign in to unlock your personalized Drovixa experience.</Text><View style={styles.authRow}><Pressable style={styles.primary} onPress={()=>router.push('/login')}><Text style={styles.primaryText}>Sign in</Text></Pressable><Pressable style={styles.secondary} onPress={()=>router.push('/register')}><Text style={styles.secondaryText}>Create account</Text></Pressable></View></View>}
    <View style={styles.menu}>{visibleMenu.map((item)=><Pressable key={item} style={styles.menuItem} onPress={()=>{if(item==='Profiles')router.push('/profiles');if(item==='Premium')router.push('/premium');if(item==='Coins')router.push('/coins');if(item==='My List')router.push('/(tabs)/library');if(item==='Downloads')router.push('/downloads');if(item==='Notifications')router.push('/notifications');if(item==='Devices')router.push('/devices')}}><Text style={styles.menuText}>{item}</Text><Text style={styles.chevron}>›</Text></Pressable>)}</View>
    {session?<Pressable disabled={signOut.isPending} style={styles.logout} onPress={()=>signOut.mutate()}><Text style={styles.logoutText}>{signOut.isPending?'Signing out…':'Sign out'}</Text></Pressable>:null}
  </ScrollView>;
}
const styles=StyleSheet.create({screen:{flex:1,backgroundColor:colors.background},content:{padding:18,paddingBottom:42},eyebrow:{color:colors.accent,fontSize:10,fontWeight:'900',letterSpacing:1.5},title:{color:colors.text,fontSize:38,fontWeight:'900',marginTop:7,marginBottom:22},account:{flexDirection:'row',alignItems:'center',gap:15,padding:19,borderRadius:22,backgroundColor:colors.card},avatar:{width:56,height:56,borderRadius:28,alignItems:'center',justifyContent:'center',backgroundColor:colors.accent},avatarText:{color:colors.text,fontSize:23,fontWeight:'900'},name:{color:colors.text,fontSize:20,fontWeight:'900'},email:{color:colors.muted,marginTop:4,lineHeight:20},guest:{padding:22,borderRadius:22,backgroundColor:colors.card},authRow:{flexDirection:'row',gap:10,marginTop:18},primary:{padding:13,borderRadius:99,backgroundColor:colors.text},primaryText:{color:colors.background,fontWeight:'900'},secondary:{padding:13,borderRadius:99,backgroundColor:colors.cardSecondary},secondaryText:{color:colors.text,fontWeight:'800'},menu:{marginTop:22,borderRadius:22,overflow:'hidden',backgroundColor:colors.card},menuItem:{height:56,flexDirection:'row',alignItems:'center',justifyContent:'space-between',paddingHorizontal:18,borderBottomWidth:StyleSheet.hairlineWidth,borderBottomColor:colors.line},menuText:{color:colors.text,fontWeight:'700'},chevron:{color:colors.muted,fontSize:24},logout:{alignItems:'center',marginTop:22,padding:15,borderRadius:99,backgroundColor:'#ef44441f'},logoutText:{color:colors.danger,fontWeight:'900'}});
