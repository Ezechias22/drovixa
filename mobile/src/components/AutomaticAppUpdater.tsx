import * as Updates from 'expo-updates';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, AppState, StyleSheet, Text, View } from 'react-native';

import { colors } from '@/theme';

const FOREGROUND_CHECK_INTERVAL_MS = 5 * 60 * 1000;

export function AutomaticAppUpdater() {
  const updateState = Updates.useUpdates();
  const checking = useRef(false);
  const lastCheckAt = useRef(0);
  const reloading = useRef(false);
  const [updating, setUpdating] = useState(false);

  const check = useCallback(async (force = false) => {
    if (!Updates.isEnabled || __DEV__ || checking.current || reloading.current) return;
    if (!force && Date.now() - lastCheckAt.current < FOREGROUND_CHECK_INTERVAL_MS) return;

    checking.current = true;
    lastCheckAt.current = Date.now();

    try {
      const result = await Updates.checkForUpdateAsync();
      if (result.isAvailable) {
        setUpdating(true);
        const fetched = await Updates.fetchUpdateAsync();
        if (!fetched.isNew && !fetched.isRollBackToEmbedded) setUpdating(false);
      }
    } catch {
      // A temporary network or EAS outage must never block normal app startup.
      setUpdating(false);
    } finally {
      checking.current = false;
    }
  }, []);

  useEffect(() => {
    void check(true);

    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') void check();
    });

    return () => subscription.remove();
  }, [check]);

  useEffect(() => {
    if (!updateState.isUpdateAvailable || updateState.isUpdatePending || checking.current) return;

    setUpdating(true);
    checking.current = true;

    void Updates.fetchUpdateAsync()
      .then((fetched) => {
        if (!fetched.isNew && !fetched.isRollBackToEmbedded) setUpdating(false);
      })
      .catch(() => setUpdating(false))
      .finally(() => {
        checking.current = false;
      });
  }, [updateState.isUpdateAvailable, updateState.isUpdatePending]);

  useEffect(() => {
    if (!updateState.isUpdatePending || reloading.current) return;

    reloading.current = true;
    setUpdating(true);

    void Updates.reloadAsync({
      reloadScreenOptions: {
        backgroundColor: colors.background,
        spinner: { color: colors.accent },
      },
    }).catch(() => {
      reloading.current = false;
      setUpdating(false);
    });
  }, [updateState.isUpdatePending]);

  if (!updating) return null;

  return (
    <View accessibilityLiveRegion="polite" style={styles.overlay}>
      <ActivityIndicator color={colors.accent} size="large" />
      <Text style={styles.title}>Updating Drovixa…</Text>
      <Text style={styles.body}>The newest version is being installed automatically.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: 0,
    bottom: 0,
    zIndex: 9999,
    elevation: 9999,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 13,
    padding: 28,
    backgroundColor: colors.background,
  },
  title: {
    color: colors.text,
    fontSize: 22,
    fontWeight: '900',
  },
  body: {
    color: colors.muted,
    textAlign: 'center',
    lineHeight: 20,
  },
});
