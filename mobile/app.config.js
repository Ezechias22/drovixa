const baseConfig = require('./app.json').expo;

module.exports = () => {
  const googleServicesFile = process.env.GOOGLE_SERVICES_FILE;
  const appEnvironment = process.env.EXPO_PUBLIC_APP_ENV ?? 'development';
  const apiUrl = process.env.EXPO_PUBLIC_API_URL ?? '';

  if (appEnvironment === 'production') {
    if (!apiUrl.startsWith('https://')) {
      throw new Error('Production mobile builds require an HTTPS EXPO_PUBLIC_API_URL.');
    }
    if (/localhost|127\.0\.0\.1|192\.168\.|10\./.test(apiUrl)) {
      throw new Error('Production mobile builds cannot use a local API address.');
    }
  }

  return {
    ...baseConfig,
    plugins: [
      ...(baseConfig.plugins ?? []),
      [
        'react-native-google-cast',
        {
          receiverAppId: process.env.GOOGLE_CAST_RECEIVER_APP_ID ?? 'CC1AD845',
          expandedController: true,
        },
      ],
    ],
    android: {
      ...baseConfig.android,
      ...(googleServicesFile ? { googleServicesFile } : {}),
    },
  };
};
