import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import * as Linking from 'expo-linking';
import { useEffect, useRef } from 'react';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';

import { colors } from '@/theme';

import { getNextAd, trackAd } from './api';

export function AdCard() {
  const router = useRouter();
  const tracked = useRef<string | null>(null);
  const query = useQuery({ queryKey: ['ad', 'home_feed'], queryFn: () => getNextAd() });
  const ad = query.data;

  useEffect(() => {
    if (!ad || tracked.current === ad.delivery_id) return;
    tracked.current = ad.delivery_id;
    void trackAd(ad, 'impression').catch(() => undefined);
  }, [ad]);

  if (!ad) return null;

  const open = async () => {
    void trackAd(ad, 'click').catch(() => undefined);
    if (!ad.click_url) return;
    if (ad.click_url.startsWith('/')) router.push(ad.click_url as never);
    else await Linking.openURL(ad.click_url);
  };

  return (
    <Pressable onPress={open} style={styles.card}>
      {ad.media_url ? <Image source={{ uri: ad.media_url }} style={styles.image} /> : null}
      <View style={styles.copy}>
        <Text style={styles.sponsor}>SPONSORED · {ad.sponsor ?? 'DROVIXA'}</Text>
        <Text style={styles.title}>{ad.headline}</Text>
        {ad.body ? <Text style={styles.body}>{ad.body}</Text> : null}
      </View>
      <Text style={styles.action}>Explore →</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { marginHorizontal: 18, marginBottom: 28, padding: 18, borderRadius: 22, backgroundColor: '#26122f', borderWidth: 1, borderColor: '#ff4d8d44' },
  image: { width: '100%', height: 140, marginBottom: 15, borderRadius: 15 },
  copy: { gap: 6 },
  sponsor: { color: colors.accent, fontSize: 9, fontWeight: '900', letterSpacing: 1.2 },
  title: { color: colors.text, fontSize: 21, fontWeight: '900' },
  body: { color: colors.muted, lineHeight: 20 },
  action: { color: colors.text, marginTop: 14, fontWeight: '900' },
});
