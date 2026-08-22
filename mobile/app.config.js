const baseConfig = require('./app.json').expo;

module.exports = () => {
  const googleServicesFile = process.env.GOOGLE_SERVICES_FILE;
  return {
    ...baseConfig,
    android: {
      ...baseConfig.android,
      ...(googleServicesFile ? { googleServicesFile } : {}),
    },
  };
};
