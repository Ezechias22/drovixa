import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { LoadingState } from '@/components/ScreenStates';
import { getDevices, removeDevice } from '@/features/personalization/api';
import { colors } from '@/theme';

export default function DevicesScreen() {
  const queryClient = useQueryClient();
  const devices = useQuery({ queryKey: ['devices'], queryFn: getDevices });
  const remove = useMutation({
    mutationFn: removeDevice,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['devices'] }),
  });
  if (devices.isPending) return <LoadingState label="Loading devices…" />;
  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Your devices</Text>
      <Text style={styles.muted}>Review every signed-in device and revoke sessions you do not recognize.</Text>
      {devices.data?.map((device) => (
        <View key={device.id} style={styles.card}>
          <View style={styles.flex}>
            <Text style={styles.name}>{device.name}</Text>
            <Text style={styles.muted}>{device.platform} · {new Date(device.last_seen_at).toLocaleString()}</Text>
            {device.current ? <Text style={styles.current}>CURRENT DEVICE</Text> : null}
          </View>
          {!device.current ? (
            <Pressable
              onPress={() => Alert.alert('Sign out device?', device.name, [
                { text: 'Cancel', style: 'cancel' },
                { text: 'Sign out', style: 'destructive', onPress: () => remove.mutate(device.id) },
              ])}
            >
              <Text style={styles.remove}>Remove</Text>
            </Pressable>
          ) : null}
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { gap: 14, padding: 20, paddingBottom: 48 },
  title: { color: colors.text, fontSize: 34, fontWeight: '900' },
  muted: { color: colors.muted, lineHeight: 20 },
  card: { flexDirection: 'row', alignItems: 'center', padding: 17, borderRadius: 18, backgroundColor: colors.card },
  flex: { flex: 1, gap: 4 }, name: { color: colors.text, fontSize: 17, fontWeight: '900' },
  current: { color: colors.success, fontSize: 10, fontWeight: '900', marginTop: 5 },
  remove: { color: colors.danger, fontWeight: '900' },
});
