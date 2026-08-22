'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { sessionRequest } from '@/lib/api';

const schema = z.object({
  email: z.email('Enter a valid email address.'),
  password: z.string().min(1, 'Password is required.'),
});

type LoginForm = z.infer<typeof schema>;

export default function LoginPage() {
  const router = useRouter();
  const form = useForm<LoginForm>({ resolver: zodResolver(schema) });
  const login = useMutation({
    mutationFn: (values: LoginForm) =>
      sessionRequest<{ user: { roles: string[] } }>('/login', {
        method: 'POST',
        body: JSON.stringify(values),
      }),
    onSuccess: () => router.replace('/dashboard'),
  });

  return (
    <main className="login-shell">
      <section className="login-brand">
        <div className="brand" style={{ position: 'relative' }}>
          <Image
            className="brand-logo"
            src="/brand/drovixa-logo.png"
            alt="Drovixa"
            width={42}
            height={42}
            priority
          />
          <span className="brand-copy">
            <strong>DROVIXA</strong>
            <small>Administration</small>
          </span>
        </div>
        <div className="login-quote">
          <div className="eyebrow">Stories today. Legends tomorrow.</div>
          <h1>Run the whole platform.</h1>
          <p>
            Content, viewers, revenue and every runtime control in one calm, cinematic command
            center.
          </p>
        </div>
        <small style={{ color: '#5f6470', position: 'relative' }}>Drovixa Admin · 0.9.0</small>
      </section>
      <section className="login-form-area">
        <div className="login-card">
          <div className="eyebrow">Protected access</div>
          <h2>Welcome back</h2>
          <p>Use a staff account with administrative permissions.</p>
          <form className="login-form" onSubmit={form.handleSubmit((values) => login.mutate(values))}>
            <div className="form-field">
              <label htmlFor="email">Email</label>
              <input id="email" className="field" autoComplete="email" {...form.register('email')} />
              {form.formState.errors.email ? (
                <span className="form-error">{form.formState.errors.email.message}</span>
              ) : null}
            </div>
            <div className="form-field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                className="field"
                type="password"
                autoComplete="current-password"
                {...form.register('password')}
              />
              {form.formState.errors.password ? (
                <span className="form-error">{form.formState.errors.password.message}</span>
              ) : null}
            </div>
            {login.error ? <div className="notice">{login.error.message}</div> : null}
            <button className="button button-accent" disabled={login.isPending}>
              {login.isPending ? 'Verifying…' : 'Enter control center'}
            </button>
          </form>
        </div>
      </section>
    </main>
  );
}
