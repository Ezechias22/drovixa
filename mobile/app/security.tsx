import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { changePassword, logoutAll } from '@/features/auth/api';
import { useI18n } from '@/i18n';
import { useAuthStore } from '@/stores/auth-store';
import { colors } from '@/theme';

export default function SecurityScreen() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { t } = useI18n();
  const session = useAuthStore((state) => state.session);
  const setSession = useAuthStore((state) => state.setSession);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const change = useMutation({
    mutationFn: () => changePassword(currentPassword, newPassword),
    onSuccess: () => {
      setCurrentPassword(''); setNewPassword(''); setConfirmation('');
      Alert.alert(t('security.updated'));
    },
    onError: () => Alert.alert(t('common.errorTitle'), t('common.errorBody')),
  });
  const closeAll = useMutation({
    mutationFn: logoutAll,
    onSettled: async () => {
      await setSession(null); queryClient.clear(); router.replace('/login');
    },
  });
  if (!session) return <View style={styles.center}><Text style={styles.title}>{t('security.title')}</Text><Pressable style={styles.primary} onPress={() => router.push('/login')}><Text style={styles.primaryText}>{t('common.signIn')}</Text></Pressable></View>;
  const valid = currentPassword.length > 0 && newPassword.length >= 8 && newPassword === confirmation;
  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <Text style={styles.title}>{t('security.title')}</Text>
      <Text style={styles.subtitle}>{t('security.subtitle')}</Text>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>{t('security.password')}</Text>
        <PasswordField placeholder={t('security.current')} value={currentPassword} onChangeText={setCurrentPassword} />
        <PasswordField placeholder={t('security.new')} value={newPassword} onChangeText={setNewPassword} />
        <PasswordField placeholder={t('security.confirm')} value={confirmation} onChangeText={setConfirmation} />
        <Pressable disabled={!valid || change.isPending} onPress={() => change.mutate()} style={[styles.primary, (!valid || change.isPending) && styles.disabled]}><Text style={styles.primaryText}>{t('security.update')}</Text></Pressable>
      </View>
      <Pressable onPress={() => router.push('/devices')} style={styles.secondary}><Text style={styles.secondaryText}>{t('security.devices')}</Text></Pressable>
      <Pressable onPress={() => Alert.alert(t('security.logoutConfirm'), t('security.logoutBody'), [
        { text: t('common.cancel'), style: 'cancel' },
        { text: t('security.logoutAll'), style: 'destructive', onPress: () => closeAll.mutate() },
      ])} style={styles.danger}><Text style={styles.dangerText}>{t('security.logoutAll')}</Text></Pressable>
    </ScrollView>
  );
}

function PasswordField({ placeholder, value, onChangeText }: { placeholder: string; value: string; onChangeText: (value: string) => void }) {
  return <TextInput autoCapitalize="none" autoCorrect={false} onChangeText={onChangeText} placeholder={placeholder} placeholderTextColor={colors.muted} secureTextEntry style={styles.input} value={value} />;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background }, content: { gap: 14, padding: 20, paddingBottom: 48 }, center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 18, padding: 24, backgroundColor: colors.background },
  title: { color: colors.text, fontSize: 34, fontWeight: '900' }, subtitle: { color: colors.muted, lineHeight: 21, marginBottom: 5 },
  card: { gap: 12, padding: 18, borderRadius: 20, backgroundColor: colors.card }, cardTitle: { color: colors.text, fontSize: 18, fontWeight: '900', marginBottom: 3 },
  input: { minHeight: 52, paddingHorizontal: 15, borderRadius: 14, color: colors.text, backgroundColor: colors.cardSecondary },
  primary: { alignItems: 'center', justifyContent: 'center', minHeight: 50, paddingHorizontal: 20, borderRadius: 99, backgroundColor: colors.text }, primaryText: { color: colors.background, fontWeight: '900' }, disabled: { opacity: 0.4 },
  secondary: { alignItems: 'center', padding: 15, borderRadius: 99, backgroundColor: colors.card }, secondaryText: { color: colors.text, fontWeight: '900' },
  danger: { alignItems: 'center', padding: 15, borderRadius: 99, backgroundColor: '#ef44441f' }, dangerText: { color: colors.danger, fontWeight: '900' },
});
