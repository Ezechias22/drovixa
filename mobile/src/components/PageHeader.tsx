import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useAuthStore } from '@/stores/auth-store';
import { useI18n } from '@/i18n';
import { colors } from '@/theme';

import { Brand } from './Brand';

export function PageHeader() {
  const router = useRouter();
  const session = useAuthStore((state) => state.session);
  const { t } = useI18n();

  return (
    <View style={styles.row}>
      <Brand />
      <View style={styles.actions}>
        <Pressable
          accessibilityLabel="Search"
          accessibilityRole="button"
          onPress={() => router.push('/search')}
          style={styles.iconButton}
        >
          <Ionicons color={colors.text} name="search-outline" size={22} />
        </Pressable>
        {session ? (
          <Pressable
            accessibilityLabel="Notifications"
            accessibilityRole="button"
            onPress={() => router.push('/notifications')}
            style={styles.iconButton}
          >
            <Ionicons color={colors.text} name="notifications-outline" size={22} />
          </Pressable>
        ) : (
          <Pressable
            accessibilityRole="button"
            onPress={() => router.push('/login')}
            style={styles.signInButton}
          >
            <Text style={styles.signInText}>{t('common.signIn')}</Text>
          </Pressable>
        )}
        <Pressable
          accessibilityLabel="Profile"
          accessibilityRole="button"
          onPress={() => router.push('/(tabs)/profile')}
          style={styles.avatar}
        >
          <Ionicons color={colors.text} name="person-circle-outline" size={25} />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 18,
    paddingVertical: 12,
  },
  actions: { flexDirection: 'row', alignItems: 'center', gap: 7 },
  iconButton: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.card,
  },
  signInButton: {
    minHeight: 38,
    justifyContent: 'center',
    paddingHorizontal: 14,
    borderRadius: 19,
    backgroundColor: colors.text,
  },
  signInText: { color: colors.background, fontSize: 12, fontWeight: '900' },
  avatar: {
    width: 38,
    height: 38,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 19,
    backgroundColor: colors.cardSecondary,
  },
});
