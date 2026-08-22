import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { getRating, setRating } from './api';
import { colors } from '@/theme';

export function RatingControl({ contentId }: { contentId: string }) {
  const queryClient = useQueryClient();
  const rating = useQuery({ queryKey: ['rating', contentId], queryFn: () => getRating(contentId), retry: false });
  const save = useMutation({
    mutationFn: (score: number) => setRating(contentId, score),
    onSuccess: (data) => queryClient.setQueryData(['rating', contentId], data),
  });
  return (
    <View style={styles.wrap}>
      <View>
        <Text style={styles.heading}>Rate this story</Text>
        <Text style={styles.meta}>{rating.data ? `${Number(rating.data.average).toFixed(1)}/10 · ${rating.data.count} ratings` : 'Your opinion improves discovery.'}</Text>
      </View>
      <View style={styles.stars}>
        {[1, 2, 3, 4, 5].map((score) => (
          <Pressable key={score} onPress={() => save.mutate(score)}>
            <Text style={[styles.star, score <= (rating.data?.score ?? 0) && styles.active]}>★</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 12, padding: 16, borderRadius: 18, backgroundColor: colors.card },
  heading: { color: colors.text, fontSize: 18, fontWeight: '900' },
  meta: { color: colors.muted, marginTop: 4, fontSize: 12 },
  stars: { flexDirection: 'row', gap: 10 }, star: { color: '#444', fontSize: 29 }, active: { color: '#FBBF24' },
});
