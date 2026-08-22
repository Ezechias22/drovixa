const baseConfig = require('./app.json').expo;

module.exports = () => {
  const googleServicesFile = process.env.GOOGLE_SERVICES_FILE;
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
