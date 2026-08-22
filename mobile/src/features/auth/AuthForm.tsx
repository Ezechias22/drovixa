import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { useRouter } from 'expo-router';
import { Controller, useForm } from 'react-hook-form';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { z } from 'zod';

import { Brand } from '@/components/Brand';
import { useAuthStore } from '@/stores/auth-store';
import { colors } from '@/theme';

import { login, register } from './api';

const loginSchema = z.object({
  name: z.string(),
  email: z.string().trim().email('Enter a valid email.'),
  password: z.string().min(1, 'Enter your password.'),
});

const registerSchema = loginSchema.extend({
  name: z.string().trim().min(2, 'Name must contain at least 2 characters.'),
  password: z
    .string()
    .min(8, 'Use at least 8 characters.')
    .regex(/[A-Za-z]/, 'Password must include at least one letter.')
    .regex(/\d/, 'Password must include at least one number.'),
});

type Values = z.infer<typeof registerSchema>;

function getErrorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) {
    return error instanceof Error ? error.message : 'Something went wrong. Please try again.';
  }

  const apiMessage = error.response?.data?.error?.message;
  if (typeof apiMessage === 'string' && apiMessage.length > 0) return apiMessage;

  if (!error.response) {
    return __DEV__
      ? 'Cannot reach the Drovixa API. Confirm that your phone and computer use the same Wi-Fi and that EXPO_PUBLIC_API_URL contains your computer IP.'
      : 'Cannot connect to Drovixa. Check your internet connection and try again.';
  }

  return 'Something went wrong. Please try again.';
}

export function AuthForm({ mode }: { mode: 'login' | 'register' }) {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const queryClient = useQueryClient();
  const setSession = useAuthStore((state) => state.setSession);
  const isLogin = mode === 'login';
  const schema = isLogin ? loginSchema : registerSchema;
  const {
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', email: '', password: '' },
  });

  const mutation = useMutation({
    mutationFn: async (values: Values) => {
      const email = values.email.trim().toLowerCase();
      return isLogin
        ? login(email, values.password)
        : register(values.name.trim(), email, values.password);
    },
    onSuccess: async (data) => {
      await setSession({
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        user: data.user,
      });
      queryClient.clear();
      router.replace('/(tabs)');
    },
  });

  const submit = handleSubmit((values) => mutation.mutate(values));
  const message = mutation.error ? getErrorMessage(mutation.error) : null;

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      style={styles.screen}
    >
      <ScrollView
        contentContainerStyle={[
          styles.content,
          { paddingTop: insets.top + 12, paddingBottom: insets.bottom + 30 },
        ]}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.header}>
          <Brand />
          <Pressable
            accessibilityLabel="Close"
            accessibilityRole="button"
            hitSlop={10}
            onPress={() => (router.canGoBack() ? router.back() : router.replace('/(tabs)'))}
            style={styles.close}
          >
            <Text style={styles.closeText}>×</Text>
          </Pressable>
        </View>

        <View style={styles.card}>
          <View style={styles.copy}>
            <Text style={styles.eyebrow}>{isLogin ? 'WELCOME BACK' : 'JOIN DROVIXA'}</Text>
            <Text style={styles.title}>{isLogin ? 'Sign in' : 'Create account'}</Text>
            <Text style={styles.subtitle}>Your next cinematic obsession is waiting.</Text>
          </View>

          {!isLogin ? (
            <Field
              autoComplete="name"
              control={control}
              error={errors.name?.message}
              label="Name"
              name="name"
              textContentType="name"
            />
          ) : null}

          <Field
            autoCapitalize="none"
            autoComplete="email"
            control={control}
            error={errors.email?.message}
            keyboardType="email-address"
            label="Email"
            name="email"
            textContentType="emailAddress"
          />

          <Field
            autoCapitalize="none"
            autoComplete={isLogin ? 'current-password' : 'new-password'}
            control={control}
            error={errors.password?.message}
            label="Password"
            name="password"
            onSubmitEditing={submit}
            secureTextEntry
            textContentType={isLogin ? 'password' : 'newPassword'}
          />

          {message ? (
            <View accessibilityLiveRegion="polite" style={styles.errorBox}>
              <Text style={styles.errorBoxText}>{message}</Text>
            </View>
          ) : null}

          <Pressable
            accessibilityRole="button"
            disabled={mutation.isPending}
            onPress={submit}
            style={({ pressed }) => [
              styles.button,
              pressed && styles.buttonPressed,
              mutation.isPending && styles.buttonDisabled,
            ]}
          >
            {mutation.isPending ? (
              <ActivityIndicator color={colors.background} />
            ) : (
              <Text style={styles.buttonText}>{isLogin ? 'Sign in' : 'Create account'}</Text>
            )}
          </Pressable>

          <Pressable
            accessibilityRole="button"
            onPress={() => router.replace(isLogin ? '/register' : '/login')}
            style={styles.switchButton}
          >
            <Text style={styles.switchText}>
              {isLogin ? 'New to Drovixa? ' : 'Already have an account? '}
              <Text style={styles.switchAccent}>{isLogin ? 'Create account' : 'Sign in'}</Text>
            </Text>
          </Pressable>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

type FieldProps = {
  autoCapitalize?: 'none' | 'sentences' | 'words' | 'characters';
  autoComplete?: 'email' | 'name' | 'current-password' | 'new-password';
  control: ReturnType<typeof useForm<Values>>['control'];
  error?: string;
  keyboardType?: 'default' | 'email-address';
  label: string;
  name: keyof Values;
  onSubmitEditing?: () => void;
  secureTextEntry?: boolean;
  textContentType?: 'emailAddress' | 'name' | 'password' | 'newPassword';
};

function Field({
  autoCapitalize = 'sentences',
  autoComplete,
  control,
  error,
  keyboardType = 'default',
  label,
  name,
  onSubmitEditing,
  secureTextEntry,
  textContentType,
}: FieldProps) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <Controller
        control={control}
        name={name}
        render={({ field: { onBlur, onChange, value } }) => (
          <TextInput
            autoCapitalize={autoCapitalize}
            autoComplete={autoComplete}
            autoCorrect={false}
            keyboardType={keyboardType}
            onBlur={onBlur}
            onChangeText={onChange}
            onSubmitEditing={onSubmitEditing}
            placeholder={label}
            placeholderTextColor={colors.muted}
            returnKeyType={onSubmitEditing ? 'done' : 'next'}
            secureTextEntry={secureTextEntry}
            selectionColor={colors.accent}
            style={[styles.input, error && styles.inputError]}
            textContentType={textContentType}
            value={value}
          />
        )}
      />
      {error ? <Text style={styles.fieldError}>{error}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { flexGrow: 1, paddingHorizontal: 20 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 28,
  },
  close: {
    width: 42,
    height: 42,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 21,
    backgroundColor: colors.card,
  },
  closeText: { color: colors.text, fontSize: 30, lineHeight: 32, fontWeight: '300' },
  card: {
    width: '100%',
    maxWidth: 520,
    alignSelf: 'center',
    gap: 17,
    padding: 22,
    borderRadius: 28,
    backgroundColor: colors.card,
  },
  copy: { gap: 8, marginBottom: 4 },
  eyebrow: { color: colors.accent, fontSize: 10, fontWeight: '900', letterSpacing: 1.6 },
  title: { color: colors.text, fontSize: 36, lineHeight: 42, fontWeight: '900' },
  subtitle: { color: colors.muted, lineHeight: 21 },
  field: { gap: 7 },
  label: { color: colors.text, fontWeight: '800' },
  input: {
    height: 56,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 16,
    paddingHorizontal: 16,
    color: colors.text,
    backgroundColor: colors.cardSecondary,
  },
  inputError: { borderColor: colors.danger },
  fieldError: { color: colors.danger, fontSize: 12, lineHeight: 17 },
  errorBox: { padding: 13, borderRadius: 14, backgroundColor: '#ef44441f' },
  errorBoxText: { color: '#fca5a5', fontSize: 13, lineHeight: 19 },
  button: {
    minHeight: 56,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 99,
    backgroundColor: colors.text,
    marginTop: 2,
  },
  buttonPressed: { opacity: 0.86 },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: colors.background, fontWeight: '900' },
  switchButton: { paddingVertical: 7 },
  switchText: { color: colors.muted, textAlign: 'center', fontWeight: '700' },
  switchAccent: { color: colors.accent },
});
