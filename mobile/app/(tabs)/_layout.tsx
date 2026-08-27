import { Ionicons } from '@expo/vector-icons';
import { Tabs } from 'expo-router';
import { StyleSheet } from 'react-native';

import { colors } from '@/theme';
import { useI18n } from '@/i18n';

const icons: Record<string, { active: keyof typeof Ionicons.glyphMap; inactive: keyof typeof Ionicons.glyphMap }> = {
  index: { active: 'home', inactive: 'home-outline' },
  discover: { active: 'compass', inactive: 'compass-outline' },
  shorts: { active: 'play-circle', inactive: 'play-circle-outline' },
  library: { active: 'heart', inactive: 'heart-outline' },
  profile: { active: 'person-circle', inactive: 'person-circle-outline' },
};

export default function Layout() {
  const { t } = useI18n();
  return (
    <Tabs
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: colors.text,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: styles.bar,
        tabBarLabelStyle: styles.label,
        tabBarIcon: ({ color, focused, size }) => {
          const icon = icons[route.name] ?? icons.index;
          return <Ionicons color={color} name={focused ? icon.active : icon.inactive} size={size} />;
        },
      })}
    >
      <Tabs.Screen name="index" options={{ title: t('nav.home') }} />
      <Tabs.Screen name="discover" options={{ title: t('nav.discover') }} />
      <Tabs.Screen name="shorts" options={{ title: t('nav.shorts') }} />
      <Tabs.Screen name="library" options={{ title: t('nav.library') }} />
      <Tabs.Screen name="profile" options={{ title: t('nav.profile') }} />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  bar: {
    height: 70,
    paddingTop: 8,
    paddingBottom: 8,
    backgroundColor: '#0B0D10',
    borderTopColor: colors.line,
  },
  label: { fontSize: 10, fontWeight: '700' },
});
