import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';

import { LoadingState } from '@/components/ScreenStates';
import { createProfile, getProfiles, verifyProfilePin } from '@/features/personalization/api';
import type { ViewerProfile } from '@/features/personalization/types';
import { useProfileStore } from '@/stores/profile-store';
import { colors } from '@/theme';

const avatars = ['nova', 'comet', 'moon', 'rocket', 'crown'];

export default function ProfilesScreen() {
  const queryClient = useQueryClient();
  const active = useProfileStore((state) => state.activeProfile);
  const setActive = useProfileStore((state) => state.setActiveProfile);
  const profiles = useQuery({ queryKey: ['profiles'], queryFn: getProfiles });
  const [name, setName] = useState('');
  const [kids, setKids] = useState(false);
  const [pin, setPin] = useState('');
  const [unlocking, setUnlocking] = useState<ViewerProfile | null>(null);
  const [avatar, setAvatar] = useState('nova');

  useEffect(() => {
    if (!active && profiles.data?.[0]) void setActive(profiles.data[0]);
  }, [active, profiles.data, setActive]);

  const create = useMutation({
    mutationFn: () =>
      createProfile({
        name,
        is_kids: kids,
        age_limit: kids ? 13 : 18,
        language_code: 'ht',
        pin: pin || undefined,
        avatar_key: avatar,
      }),
    onSuccess: async (profile) => {
      setName('');
      setPin('');
      setKids(false);
      await setActive(profile);
      await queryClient.invalidateQueries({ queryKey: ['profiles'] });
      queryClient.clear();
    },
    onError: () => Alert.alert('Profile', 'Profile la pa rive kreye. Verifye koneksyon an.'),
  });

  const select = async (profile: ViewerProfile) => {
    if (profile.pin_protected) {
      setPin('');
      setUnlocking(profile);
      return;
    }
    await setActive(profile);
    queryClient.clear();
  };

  const unlock = useMutation({
    mutationFn: async () => Boolean(unlocking && (await verifyProfilePin(unlocking.id, pin))),
    onSuccess: async (valid) => {
      if (!valid || !unlocking) {
        Alert.alert('PIN pa bon', 'Eseye ankò.');
        return;
      }
      await setActive(unlocking);
      setUnlocking(null);
      setPin('');
      queryClient.clear();
    },
  });

  if (profiles.isPending) return <LoadingState label="Loading profiles…" />;

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.eyebrow}>WHO IS WATCHING?</Text>
      <Text style={styles.title}>Profiles</Text>
      <View style={styles.grid}>
        {profiles.data?.map((profile) => (
          <Pressable
            key={profile.id}
            onPress={() => void select(profile)}
            style={[styles.profile, active?.id === profile.id && styles.active]}
          >
            <View style={styles.avatar}>
              <Text style={styles.avatarText}>{profile.name.slice(0, 1).toUpperCase()}</Text>
            </View>
            <Text style={styles.profileName}>{profile.name}</Text>
            <Text style={styles.profileMeta}>
              {profile.is_kids ? `Kids · ${profile.age_limit}+` : 'Standard'}
              {profile.pin_protected ? ' · PIN' : ''}
            </Text>
          </Pressable>
        ))}
      </View>

      {unlocking ? (
        <View style={styles.card}>
          <Text style={styles.heading}>Unlock {unlocking.name}</Text>
          <TextInput
            keyboardType="number-pad"
            maxLength={6}
            placeholder="PIN"
            placeholderTextColor={colors.muted}
            secureTextEntry
            style={styles.input}
            value={pin}
            onChangeText={setPin}
          />
          <View style={styles.row}>
            <Pressable style={styles.secondary} onPress={() => setUnlocking(null)}>
              <Text style={styles.secondaryText}>Cancel</Text>
            </Pressable>
            <Pressable style={styles.primary} onPress={() => unlock.mutate()}>
              <Text style={styles.primaryText}>Unlock</Text>
            </Pressable>
          </View>
        </View>
      ) : null}

      {(profiles.data?.length ?? 0) < 5 ? (
        <View style={styles.card}>
          <Text style={styles.heading}>Add a profile</Text>
          <TextInput
            placeholder="Profile name"
            placeholderTextColor={colors.muted}
            style={styles.input}
            value={name}
            onChangeText={setName}
          />
          <View style={styles.avatarRow}>
            {avatars.map((item) => (
              <Pressable
                key={item}
                onPress={() => setAvatar(item)}
                style={[styles.dot, avatar === item && styles.dotActive]}
              />
            ))}
          </View>
          <View style={styles.switchRow}>
            <View>
              <Text style={styles.label}>Kids profile</Text>
              <Text style={styles.profileMeta}>Server-enforced age filter</Text>
            </View>
            <Switch value={kids} onValueChange={setKids} trackColor={{ true: colors.accent }} />
          </View>
          <TextInput
            keyboardType="number-pad"
            maxLength={6}
            placeholder="Optional 4–6 digit PIN"
            placeholderTextColor={colors.muted}
            secureTextEntry
            style={styles.input}
            value={pin}
            onChangeText={setPin}
          />
          <Pressable
            disabled={name.trim().length < 1 || create.isPending}
            style={styles.primary}
            onPress={() => create.mutate()}
          >
            <Text style={styles.primaryText}>{create.isPending ? 'Creating…' : 'Create profile'}</Text>
          </Pressable>
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: 20, paddingBottom: 48 },
  eyebrow: { color: colors.accent, fontSize: 10, fontWeight: '900', letterSpacing: 1.5 },
  title: { color: colors.text, fontSize: 38, fontWeight: '900', marginTop: 7, marginBottom: 22 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  profile: { width: '47%', alignItems: 'center', padding: 16, borderRadius: 22, backgroundColor: colors.card },
  active: { borderWidth: 2, borderColor: colors.accent },
  avatar: { width: 64, height: 64, borderRadius: 20, alignItems: 'center', justifyContent: 'center', backgroundColor: '#6D28D9' },
  avatarText: { color: colors.text, fontSize: 27, fontWeight: '900' },
  profileName: { color: colors.text, fontWeight: '900', fontSize: 17, marginTop: 10 },
  profileMeta: { color: colors.muted, fontSize: 12, marginTop: 4 },
  card: { gap: 14, padding: 18, borderRadius: 22, backgroundColor: colors.card, marginTop: 22 },
  heading: { color: colors.text, fontSize: 21, fontWeight: '900' },
  input: { minHeight: 52, color: colors.text, borderRadius: 15, paddingHorizontal: 15, backgroundColor: colors.cardSecondary },
  row: { flexDirection: 'row', gap: 10 },
  primary: { flexGrow: 1, alignItems: 'center', padding: 15, borderRadius: 99, backgroundColor: colors.text },
  primaryText: { color: colors.background, fontWeight: '900' },
  secondary: { flexGrow: 1, alignItems: 'center', padding: 15, borderRadius: 99, backgroundColor: colors.cardSecondary },
  secondaryText: { color: colors.text, fontWeight: '800' },
  switchRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  label: { color: colors.text, fontWeight: '800' },
  avatarRow: { flexDirection: 'row', gap: 10 },
  dot: { width: 28, height: 28, borderRadius: 10, backgroundColor: '#4C1D95' },
  dotActive: { borderWidth: 3, borderColor: colors.accent },
});
