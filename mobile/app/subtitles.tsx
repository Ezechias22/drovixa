import { Pressable, ScrollView, StyleSheet, Switch, Text, View } from 'react-native';

import { useSubtitleStore } from '@/stores/subtitle-store';
import { colors } from '@/theme';

const languages = [
  ['ht', 'Kreyòl ayisyen'],
  ['en', 'English'],
  ['fr', 'Français'],
  ['es', 'Español'],
  ['pt', 'Português'],
] as const;

export default function SubtitleSettingsScreen() {
  const enabled = useSubtitleStore((state) => state.enabled);
  const preferredLanguage = useSubtitleStore((state) => state.preferredLanguage);
  const update = useSubtitleStore((state) => state.update);
  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Subtitles</Text>
      <Text style={styles.subtitle}>Choose real subtitle tracks when a video provides VTT or SRT captions. You can still change or turn them off inside the player.</Text>
      <View style={styles.card}>
        <View style={styles.copy}><Text style={styles.label}>Show subtitles automatically</Text><Text style={styles.body}>Uses your preferred language when it is available.</Text></View>
        <Switch value={enabled} onValueChange={(value) => void update({ enabled: value })} trackColor={{ true: colors.accent }} />
      </View>
      <Text style={styles.heading}>Preferred language</Text>
      <View style={styles.languages}>{languages.map(([code, label]) => <Pressable key={code} onPress={() => void update({ preferredLanguage: code })} style={[styles.language, preferredLanguage === code && styles.selected]}><Text style={styles.languageText}>{label}</Text><Text style={styles.code}>{preferredLanguage === code ? '✓' : code.toUpperCase()}</Text></Pressable>)}</View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background }, content: { gap: 14, padding: 20, paddingBottom: 48 },
  title: { color: colors.text, fontSize: 34, fontWeight: '900' }, subtitle: { color: colors.muted, lineHeight: 21, marginBottom: 6 },
  card: { flexDirection: 'row', alignItems: 'center', gap: 18, padding: 18, borderRadius: 20, backgroundColor: colors.card }, copy: { flex: 1, gap: 6 }, label: { color: colors.text, fontSize: 17, fontWeight: '900' }, body: { color: colors.muted, lineHeight: 20 },
  heading: { color: colors.text, fontSize: 20, fontWeight: '900', marginTop: 8 }, languages: { gap: 8 }, language: { minHeight: 56, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 17, borderRadius: 16, backgroundColor: colors.card }, selected: { borderWidth: 1, borderColor: colors.accent }, languageText: { color: colors.text, fontWeight: '800' }, code: { color: colors.accent, fontWeight: '900' },
});
