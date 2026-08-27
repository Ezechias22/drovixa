import { Ionicons } from '@expo/vector-icons';
import { useMemo, useState } from 'react';
import { Linking, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { useI18n } from '@/i18n';
import { colors } from '@/theme';

export default function HelpScreen() {
  const { t } = useI18n();
  const [search, setSearch] = useState('');
  const supportEmail = process.env.EXPO_PUBLIC_SUPPORT_EMAIL ?? 'support@drovixa.com';
  const faqs = useMemo(() => [
    { question: t('help.faq1q'), answer: t('help.faq1a') },
    { question: t('help.faq2q'), answer: t('help.faq2a') },
    { question: t('help.faq3q'), answer: t('help.faq3a') },
  ], [t]);
  const query = search.trim().toLocaleLowerCase();
  const visibleFaqs = faqs.filter((faq) => `${faq.question} ${faq.answer}`.toLocaleLowerCase().includes(query));
  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <Text style={styles.title}>{t('help.title')}</Text>
      <Text style={styles.subtitle}>{t('help.subtitle')}</Text>
      <View style={styles.searchBox}>
        <Ionicons color={colors.muted} name="search-outline" size={20} />
        <TextInput
          onChangeText={setSearch}
          placeholder={t('help.search')}
          placeholderTextColor={colors.muted}
          style={styles.input}
          value={search}
        />
      </View>
      <View style={styles.faqs}>
        {visibleFaqs.map((faq) => <View key={faq.question} style={styles.faq}>
          <Text style={styles.question}>{faq.question}</Text>
          <Text style={styles.answer}>{faq.answer}</Text>
        </View>)}
      </View>
      <View style={styles.contact}>
        <Text style={styles.contactTitle}>{t('help.contact')}</Text>
        <Pressable
          onPress={() => void Linking.openURL(`mailto:${supportEmail}?subject=Drovixa%20Support`)}
          style={styles.button}
        >
          <Ionicons color={colors.background} name="mail-outline" size={19} />
          <Text style={styles.buttonText}>{t('help.email')}</Text>
        </Pressable>
        <Text style={styles.email}>{supportEmail}</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background }, content: { gap: 14, padding: 20, paddingBottom: 48 },
  title: { color: colors.text, fontSize: 34, fontWeight: '900' }, subtitle: { color: colors.muted, lineHeight: 21 },
  searchBox: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 52, paddingHorizontal: 15, borderRadius: 18, backgroundColor: colors.card },
  input: { flex: 1, color: colors.text, fontSize: 15 }, faqs: { gap: 10 },
  faq: { gap: 7, padding: 17, borderRadius: 18, backgroundColor: colors.card }, question: { color: colors.text, fontSize: 16, fontWeight: '900' }, answer: { color: colors.muted, lineHeight: 21 },
  contact: { alignItems: 'center', gap: 10, marginTop: 6, padding: 20, borderRadius: 20, backgroundColor: colors.cardSecondary }, contactTitle: { color: colors.text, fontSize: 18, fontWeight: '900' },
  button: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 20, paddingVertical: 13, borderRadius: 99, backgroundColor: colors.text }, buttonText: { color: colors.background, fontWeight: '900' }, email: { color: colors.muted, fontSize: 12 },
});
