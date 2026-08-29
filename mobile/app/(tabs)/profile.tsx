import { Ionicons } from '@expo/vector-icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { ActivityIndicator, Alert, Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { deleteProfilePhoto, logout, uploadProfilePhoto } from '@/features/auth/api';
import { getFeatureFlags } from '@/features/configuration/api';
import { useI18n } from '@/i18n';
import { useAuthStore } from '@/stores/auth-store';
import { colors } from '@/theme';

type IconName = keyof typeof Ionicons.glyphMap;

export default function ProfileScreen() {
  const inset = useSafeAreaInsets();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { t } = useI18n();
  const session = useAuthStore((state) => state.session);
  const setSession = useAuthStore((state) => state.setSession);
  const flags = useQuery({ queryKey: ['feature-flags'], queryFn: getFeatureFlags });
  const items: Array<{ id: string; label: string; route: string; icon: IconName }> = [
    { id: 'profiles', label: t('profile.profiles'), route: '/profiles', icon: 'people-outline' },
    { id: 'premium', label: t('profile.premium'), route: '/premium', icon: 'diamond-outline' },
    { id: 'coins', label: t('profile.coins'), route: '/coins', icon: 'cash-outline' },
    { id: 'growth', label: t('profile.rewards'), route: '/growth', icon: 'gift-outline' },
    { id: 'library', label: t('profile.myList'), route: '/(tabs)/library', icon: 'heart-outline' },
    { id: 'downloads', label: t('profile.downloads'), route: '/downloads', icon: 'download-outline' },
    { id: 'notifications', label: t('profile.notifications'), route: '/notifications', icon: 'notifications-outline' },
    { id: 'language', label: t('profile.language'), route: '/language', icon: 'language-outline' },
    { id: 'subtitles', label: t('profile.subtitles'), route: '/subtitles', icon: 'text-outline' },
    { id: 'playback', label: t('profile.playback'), route: '/playback-settings', icon: 'play-circle-outline' },
    { id: 'devices', label: t('profile.devices'), route: '/devices', icon: 'phone-portrait-outline' },
    { id: 'security', label: t('profile.security'), route: '/security', icon: 'shield-checkmark-outline' },
    { id: 'help', label: t('profile.help'), route: '/help', icon: 'help-circle-outline' },
  ];
  const visibleItems = items.filter((item) =>
    (item.id !== 'premium' || flags.data?.subscriptions_enabled?.enabled) &&
    (item.id !== 'coins' || flags.data?.coins_enabled?.enabled));
  const signOut = useMutation({
    mutationFn: logout,
    onSettled: async () => { await setSession(null); queryClient.clear(); },
  });
  const photo = useMutation({
    mutationFn: async () => {
      // @ts-ignore expo-image-picker is installed by the Phase 12.8 apply script.
      const picker = await import('expo-image-picker');
      const permission = await picker.requestMediaLibraryPermissionsAsync();
      if (!permission.granted) throw new Error('Photo library permission is required.');
      const result = await picker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        allowsEditing: true,
        aspect: [1, 1],
        quality: 0.72,
        base64: true,
      });
      if (result.canceled || !result.assets[0]?.base64) return null;
      const asset = result.assets[0];
      const mimeType = asset.mimeType === 'image/png' || asset.mimeType === 'image/webp'
        ? asset.mimeType
        : 'image/jpeg';
      return uploadProfilePhoto(mimeType, asset.base64!);
    },
    onSuccess: async (user) => {
      if (user && session) await setSession({ ...session, user });
    },
    onError: (error) => Alert.alert('Profile photo', error instanceof Error ? error.message : 'Could not update photo.'),
  });
  const removePhoto = useMutation({
    mutationFn: deleteProfilePhoto,
    onSuccess: async (user) => { if (session) await setSession({ ...session, user }); },
    onError: () => Alert.alert('Profile photo', 'Could not remove photo.'),
  });
  return (
    <ScrollView style={styles.screen} contentContainerStyle={[styles.content, { paddingTop: inset.top + 18 }]}>
      <Text style={styles.eyebrow}>{t('profile.eyebrow')}</Text>
      <Text style={styles.title}>{t('profile.title')}</Text>
      {session ? (
        <View style={styles.account}>
          <Pressable disabled={photo.isPending} onPress={() => photo.mutate()} style={styles.avatarButton}>
            {session.user.avatar_url ? <Image source={{ uri: session.user.avatar_url }} style={styles.avatarImage} /> : <View style={styles.avatar}><Text style={styles.avatarText}>{session.user.name.slice(0, 1).toUpperCase()}</Text></View>}
            <View style={styles.cameraBadge}>{photo.isPending ? <ActivityIndicator color="#fff" size="small" /> : <Ionicons color="#fff" name="camera" size={14} />}</View>
          </Pressable>
          <View style={styles.accountCopy}><Text style={styles.name}>{session.user.name}</Text><Text style={styles.email}>{session.user.email}</Text><View style={styles.photoActions}><Pressable onPress={() => photo.mutate()}><Text style={styles.photoAction}>Change photo</Text></Pressable>{session.user.avatar_url ? <Pressable disabled={removePhoto.isPending} onPress={() => removePhoto.mutate()}><Text style={styles.removePhoto}>Remove</Text></Pressable> : null}</View></View>
        </View>
      ) : (
        <View style={styles.guest}>
          <Text style={styles.name}>{t('profile.guest')}</Text>
          <Text style={styles.email}>{t('profile.guestBody')}</Text>
          <View style={styles.authRow}>
            <Pressable style={styles.primary} onPress={() => router.push('/login')}><Text style={styles.primaryText}>{t('common.signIn')}</Text></Pressable>
            <Pressable style={styles.secondary} onPress={() => router.push('/register')}><Text style={styles.secondaryText}>{t('profile.createAccount')}</Text></Pressable>
          </View>
        </View>
      )}
      <View style={styles.menu}>
        {visibleItems.map((item) => (
          <Pressable key={item.id} style={styles.menuItem} onPress={() => router.push(item.route as never)}>
            <Ionicons color={colors.muted} name={item.icon} size={21} />
            <Text style={styles.menuText}>{item.label}</Text>
            <Ionicons color={colors.muted} name="chevron-forward" size={19} />
          </Pressable>
        ))}
      </View>
      {session ? <Pressable disabled={signOut.isPending} style={styles.logout} onPress={() => signOut.mutate()}><Text style={styles.logoutText}>{signOut.isPending ? t('profile.signingOut') : t('profile.signOut')}</Text></Pressable> : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background }, content: { padding: 18, paddingBottom: 42 },
  eyebrow: { color: colors.accent, fontSize: 10, fontWeight: '900', letterSpacing: 1.5 }, title: { color: colors.text, fontSize: 38, fontWeight: '900', marginTop: 7, marginBottom: 22 },
  account: { flexDirection: 'row', alignItems: 'center', gap: 15, padding: 19, borderRadius: 22, backgroundColor: colors.card }, accountCopy: { flex: 1 }, avatarButton: { width: 64, height: 64 }, avatar: { width: 64, height: 64, borderRadius: 32, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.accent }, avatarImage: { width: 64, height: 64, borderRadius: 32, backgroundColor: colors.cardSecondary }, avatarText: { color: colors.text, fontSize: 23, fontWeight: '900' }, cameraBadge: { position: 'absolute', right: -2, bottom: -2, width: 25, height: 25, borderRadius: 13, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.accent, borderWidth: 2, borderColor: colors.card }, photoActions: { flexDirection: 'row', gap: 14, marginTop: 8 }, photoAction: { color: colors.accent, fontSize: 12, fontWeight: '900' }, removePhoto: { color: colors.danger, fontSize: 12, fontWeight: '800' },
  name: { color: colors.text, fontSize: 20, fontWeight: '900' }, email: { color: colors.muted, marginTop: 4, lineHeight: 20 }, guest: { padding: 22, borderRadius: 22, backgroundColor: colors.card }, authRow: { flexDirection: 'row', gap: 10, marginTop: 18 },
  primary: { padding: 13, borderRadius: 99, backgroundColor: colors.text }, primaryText: { color: colors.background, fontWeight: '900' }, secondary: { padding: 13, borderRadius: 99, backgroundColor: colors.cardSecondary }, secondaryText: { color: colors.text, fontWeight: '800' },
  menu: { marginTop: 22, borderRadius: 22, overflow: 'hidden', backgroundColor: colors.card }, menuItem: { minHeight: 56, flexDirection: 'row', alignItems: 'center', gap: 13, paddingHorizontal: 18, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.line }, menuText: { flex: 1, color: colors.text, fontWeight: '700' },
  logout: { alignItems: 'center', marginTop: 22, padding: 15, borderRadius: 99, backgroundColor: '#ef44441f' }, logoutText: { color: colors.danger, fontWeight: '900' },
});
