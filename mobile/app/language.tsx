import { Ionicons } from '@expo/vector-icons';
import { ScrollView, StyleSheet, Text, Pressable, View } from 'react-native';

import { languages, useI18n } from '@/i18n';
import { colors } from '@/theme';

export default function LanguageScreen() {
  const { language, setLanguage, t } = useI18n();
  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.title}>{t('language.title')}</Text>
      <Text style={styles.subtitle}>{t('language.subtitle')}</Text>
      <Text style={styles.note}>{t('language.device')}</Text>
      <View style={styles.list}>
        {languages.map((item) => {
          const selected = item.code === language;
          return (
            <Pressable
              accessibilityRole="radio"
              accessibilityState={{ checked: selected }}
              key={item.code}
              onPress={() => void setLanguage(item.code)}
              style={[styles.row, selected && styles.selected]}
            >
              <View style={styles.copy}>
                <Text style={styles.native}>{item.nativeLabel}</Text>
                <Text style={styles.english}>{item.label}</Text>
              </View>
              <Ionicons
                color={selected ? colors.accent : colors.muted}
                name={selected ? 'radio-button-on' : 'radio-button-off'}
                size={24}
              />
            </Pressable>
          );
        })}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { gap: 12, padding: 20, paddingBottom: 48 },
  title: { color: colors.text, fontSize: 34, fontWeight: '900' },
  subtitle: { color: colors.muted, fontSize: 15, lineHeight: 22 },
  note: { color: colors.accent, fontSize: 12, lineHeight: 18, marginBottom: 8 },
  list: { overflow: 'hidden', borderRadius: 22, backgroundColor: colors.card },
  row: { flexDirection: 'row', alignItems: 'center', minHeight: 72, paddingHorizontal: 18, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.line },
  selected: { backgroundColor: colors.cardSecondary },
  copy: { flex: 1, gap: 4 },
  native: { color: colors.text, fontSize: 17, fontWeight: '900' },
  english: { color: colors.muted, fontSize: 12 },
});
