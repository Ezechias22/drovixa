import { useQuery } from '@tanstack/react-query';
import * as SecureStore from 'expo-secure-store';
import { usePathname, useRouter } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';

import { getEngagementConfig } from '@/features/growth/engagement-api';
import { useI18n } from '@/i18n';
import { useAuthStore } from '@/stores/auth-store';
import { colors } from '@/theme';

const copy = {
  ht: { eyebrow: 'YON EKSPERYANS SAN PIBLISITE', title: 'Pase sou Drovixa Premium', body: 'Gade san piblisite epi jwenn tout avantaj Premium yo.', action: 'Gade plan yo', later: 'Pa kounye a' },
  fr: { eyebrow: 'UNE EXPÉRIENCE SANS PUBLICITÉ', title: 'Passez à Drovixa Premium', body: 'Regardez sans publicité et profitez de tous les avantages Premium.', action: 'Voir les offres', later: 'Pas maintenant' },
  'pt-BR': { eyebrow: 'UMA EXPERIÊNCIA SEM ANÚNCIOS', title: 'Assine o Drovixa Premium', body: 'Assista sem anúncios e aproveite todos os benefícios Premium.', action: 'Ver planos', later: 'Agora não' },
  es: { eyebrow: 'UNA EXPERIENCIA SIN ANUNCIOS', title: 'Pásate a Drovixa Premium', body: 'Mira sin anuncios y disfruta todos los beneficios Premium.', action: 'Ver planes', later: 'Ahora no' },
  en: { eyebrow: 'AN AD-FREE EXPERIENCE', title: 'Upgrade to Drovixa Premium', body: 'Watch without ads and enjoy every Premium benefit.', action: 'See plans', later: 'Not now' },
} as const;

function blockedRoute(pathname: string) {
  return ['/watch', '/offline', '/premium', '/login', '/register'].some((route) => pathname.startsWith(route));
}

function savedOfferState(raw: string | null): { day: string; count: number } | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as { day?: unknown; count?: unknown };
    return typeof parsed.day === 'string' && typeof parsed.count === 'number'
      ? { day: parsed.day, count: parsed.count }
      : null;
  } catch {
    return null;
  }
}

export function PremiumOfferBridge() {
  const router = useRouter();
  const pathname = usePathname();
  const { language } = useI18n();
  const userId = useAuthStore((state) => state.session?.user.id);
  const [visible, setVisible] = useState(false);
  const shownInSession = useRef(0);
  const query = useQuery({
    queryKey: ['engagement-config', userId],
    queryFn: getEngagementConfig,
    enabled: Boolean(userId),
    staleTime: 60_000,
  });

  useEffect(() => {
    const config = query.data?.premium_offer;
    if (!userId || !config?.enabled || blockedRoute(pathname) || visible) return;
    if (shownInSession.current >= config.max_per_session) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    void (async () => {
      const today = new Date().toISOString().slice(0, 10);
      const key = `drovixa.premium-offers.${userId}`;
      const saved = await SecureStore.getItemAsync(key).catch(() => null);
      const state = savedOfferState(saved) ?? { day: today, count: 0 };
      const dailyCount = state.day === today ? state.count : 0;
      if (dailyCount >= config.max_per_day || cancelled) return;
      const delay = shownInSession.current === 0
        ? config.first_delay_seconds
        : config.repeat_delay_seconds;
      timer = setTimeout(() => {
        if (!cancelled) setVisible(true);
      }, delay * 1000);
    })();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [pathname, query.data, userId, visible]);

  const close = async (openPremium: boolean) => {
    setVisible(false);
    shownInSession.current += 1;
    if (userId) {
      const today = new Date().toISOString().slice(0, 10);
      const key = `drovixa.premium-offers.${userId}`;
      const saved = await SecureStore.getItemAsync(key).catch(() => null);
      const state = savedOfferState(saved);
      await SecureStore.setItemAsync(key, JSON.stringify({
        day: today,
        count: state?.day === today ? state.count + 1 : 1,
      })).catch(() => undefined);
    }
    if (openPremium) router.push('/premium');
  };

  const text = copy[language];
  return <Modal animationType="fade" onRequestClose={() => void close(false)} transparent visible={visible}>
    <View style={styles.backdrop}>
      <View style={styles.card}>
        <Text style={styles.eyebrow}>{text.eyebrow}</Text>
        <Text style={styles.title}>{text.title}</Text>
        <Text style={styles.body}>{text.body}</Text>
        <Pressable onPress={() => void close(true)} style={styles.action}><Text style={styles.actionText}>{text.action}</Text></Pressable>
        <Pressable onPress={() => void close(false)} style={styles.later}><Text style={styles.laterText}>{text.later}</Text></Pressable>
      </View>
    </View>
  </Modal>;
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, justifyContent: 'center', padding: 24, backgroundColor: '#000000bb' },
  card: { padding: 26, borderRadius: 28, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.line },
  eyebrow: { color: colors.accent, fontSize: 10, fontWeight: '900', letterSpacing: 1.4 },
  title: { color: colors.text, fontSize: 28, fontWeight: '900', marginTop: 10 },
  body: { color: colors.muted, fontSize: 15, lineHeight: 23, marginTop: 10, marginBottom: 22 },
  action: { alignItems: 'center', padding: 15, borderRadius: 99, backgroundColor: colors.accent },
  actionText: { color: colors.text, fontWeight: '900' },
  later: { alignItems: 'center', padding: 14, marginTop: 6 },
  laterText: { color: colors.muted, fontWeight: '800' },
});
