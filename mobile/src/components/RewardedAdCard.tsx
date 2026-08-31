import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';

import { createRewardedAdSession, getEngagementConfig } from '@/features/growth/engagement-api';
import { useI18n } from '@/i18n';
import { useAuthStore } from '@/stores/auth-store';
import { colors } from '@/theme';

const copy = {
  ht: { title: 'Gade epi genyen coins', body: 'Gade yon piblisite rive nan fen. Google verifye li avan coins yo antre.', watch: 'Gade piblisite', loading: 'Piblisite ap chaje…', limit: 'Ou rive nan limit jodi a.', premium: 'Premium pa gen piblisite.', ready: 'Coins yo antre', pending: 'Google ap verifye rekonpans lan. Li pral antre otomatikman.', error: 'Piblisite a pa disponib kounye a.' },
  fr: { title: 'Regardez et gagnez des coins', body: "Regardez une publicité jusqu'à la fin. Google la vérifie avant l'ajout des coins.", watch: 'Regarder la publicité', loading: 'Chargement…', limit: 'Limite quotidienne atteinte.', premium: 'Premium est sans publicité.', ready: 'Coins ajoutés', pending: 'Google vérifie la récompense. Elle sera ajoutée automatiquement.', error: "La publicité n'est pas disponible maintenant." },
  'pt-BR': { title: 'Assista e ganhe moedas', body: 'Assista ao anúncio até o fim. O Google verifica antes de adicionar as moedas.', watch: 'Assistir anúncio', loading: 'Carregando anúncio…', limit: 'Limite diário atingido.', premium: 'Premium não tem anúncios.', ready: 'Moedas adicionadas', pending: 'O Google está verificando a recompensa. Ela será adicionada automaticamente.', error: 'O anúncio não está disponível agora.' },
  es: { title: 'Mira y gana monedas', body: 'Mira el anuncio completo. Google lo verifica antes de añadir las monedas.', watch: 'Ver anuncio', loading: 'Cargando anuncio…', limit: 'Límite diario alcanzado.', premium: 'Premium no tiene anuncios.', ready: 'Monedas añadidas', pending: 'Google está verificando la recompensa. Se añadirá automáticamente.', error: 'El anuncio no está disponible ahora.' },
  en: { title: 'Watch and earn coins', body: 'Finish one ad. Google verifies it before coins are added.', watch: 'Watch ad', loading: 'Loading ad…', limit: 'You reached today’s limit.', premium: 'Premium is ad-free.', ready: 'Coins added', pending: 'Google is verifying the reward. It will be added automatically.', error: 'An ad is not available right now.' },
} as const;

function wait(milliseconds: number) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

export function RewardedAdCard() {
  const { language } = useI18n();
  const userId = useAuthStore((state) => state.session?.user.id);
  const [loading, setLoading] = useState(false);
  const config = useQuery({
    queryKey: ['engagement-config', userId],
    queryFn: getEngagementConfig,
    enabled: Boolean(userId),
    staleTime: 15_000,
  });
  const text = copy[language];
  const reward = config.data?.rewarded_ad;

  const watch = async () => {
    if (!userId || loading) return;
    setLoading(true);
    try {
      const before = reward?.watched_today ?? 0;
      const session = await createRewardedAdSession();
      const ads = await import('react-native-google-mobile-ads');
      const rewarded = ads.RewardedAd.createForAdRequest(session.ad_unit_id, {
        requestNonPersonalizedAdsOnly: false,
        serverSideVerificationOptions: {
          userId: session.user_id,
          customData: session.custom_data,
        },
      });
      await new Promise<void>((resolve, reject) => {
        let settled = false;
        let timeout: ReturnType<typeof setTimeout>;
        const cleanups: Array<() => void> = [];
        const finish = (error?: unknown) => {
          if (settled) return;
          settled = true;
          clearTimeout(timeout);
          cleanups.forEach((unsubscribe) => unsubscribe());
          if (error) reject(error);
          else resolve();
        };
        cleanups.push(
          rewarded.addAdEventListener(ads.RewardedAdEventType.LOADED, () => {
            void rewarded.show().catch(finish);
          }),
          rewarded.addAdEventListener(ads.RewardedAdEventType.EARNED_REWARD, () => finish()),
          rewarded.addAdEventListener(ads.AdEventType.ERROR, finish),
          rewarded.addAdEventListener(ads.AdEventType.CLOSED, () => finish(new Error('Ad closed before reward'))),
        );
        rewarded.load();
        timeout = setTimeout(() => finish(new Error('Ad load timeout')), 30_000);
      });
      let credited = false;
      for (let attempt = 0; attempt < 8; attempt += 1) {
        await wait(attempt === 0 ? 1_000 : 2_000);
        const next = await config.refetch();
        if ((next.data?.rewarded_ad.watched_today ?? before) > before) {
          credited = true;
          break;
        }
      }
      Alert.alert(
        credited ? text.ready : text.title,
        credited ? `+${session.reward_coins} coins` : text.pending,
      );
    } catch (error) {
      const apiMessage = axios.isAxiosError(error)
        ? error.response?.data?.error?.message
        : undefined;
      Alert.alert(text.title, apiMessage ?? text.error);
    } finally {
      setLoading(false);
      await config.refetch();
    }
  };

  const disabled = loading || !reward?.enabled || reward.remaining_today <= 0;
  return <View style={styles.card}>
    <Text style={styles.cardTitle}>{text.title}</Text>
    <Text style={styles.muted}>{text.body}</Text>
    {reward ? <Text style={styles.reward}>+{reward.coins_per_ad} coins · {reward.remaining_today}/{reward.daily_limit} today</Text> : null}
    <Pressable disabled={disabled} onPress={() => void watch()} style={[styles.button, disabled && styles.disabled]}>
      <Text style={styles.buttonText}>{loading ? text.loading : reward?.remaining_today === 0 ? text.limit : config.data?.premium ? text.premium : text.watch}</Text>
    </Pressable>
  </View>;
}

const styles = StyleSheet.create({
  card: { padding: 20, borderRadius: 24, backgroundColor: colors.card, marginBottom: 18 },
  cardTitle: { color: colors.text, fontSize: 21, fontWeight: '900' },
  muted: { color: colors.muted, marginTop: 7, lineHeight: 20 },
  reward: { color: '#facc15', fontWeight: '900', marginVertical: 16 },
  button: { alignItems: 'center', padding: 15, borderRadius: 99, backgroundColor: colors.accent },
  disabled: { opacity: 0.45 },
  buttonText: { color: colors.text, fontWeight: '900' },
});
