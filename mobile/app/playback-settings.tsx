import { ScrollView, StyleSheet, Switch, Text, View } from 'react-native';

import { useI18n } from '@/i18n';
import { usePlaybackStore } from '@/stores/playback-store';
import { colors } from '@/theme';

export default function PlaybackSettingsScreen() {
  const { t } = useI18n();
  const autoplay = usePlaybackStore((state) => state.autoplay);
  const setAutoplay = usePlaybackStore((state) => state.setAutoplay);
  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.title}>{t('playback.title')}</Text>
      <Text style={styles.subtitle}>{t('playback.subtitle')}</Text>
      <View style={styles.card}>
        <View style={styles.copy}>
          <Text style={styles.label}>{t('playback.autoplay')}</Text>
          <Text style={styles.body}>{t('playback.autoplayBody')}</Text>
        </View>
        <Switch
          onValueChange={(value) => void setAutoplay(value)}
          thumbColor={colors.text}
          trackColor={{ false: colors.cardSecondary, true: colors.accent }}
          value={autoplay}
        />
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { gap: 12, padding: 20, paddingBottom: 48 },
  title: { color: colors.text, fontSize: 34, fontWeight: '900' },
  subtitle: { color: colors.muted, lineHeight: 21, marginBottom: 8 },
  card: { flexDirection: 'row', alignItems: 'center', gap: 18, padding: 18, borderRadius: 20, backgroundColor: colors.card },
  copy: { flex: 1, gap: 6 },
  label: { color: colors.text, fontSize: 17, fontWeight: '900' },
  body: { color: colors.muted, lineHeight: 20 },
});
