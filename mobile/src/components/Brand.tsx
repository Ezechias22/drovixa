import { Image, StyleSheet, Text, View } from 'react-native';
import { colors } from '@/theme';

const mark = require('../../assets/icon.png');

export function Brand() {
  return <View style={styles.row}><Image source={mark} style={styles.mark} /><Text style={styles.name}>DROVIXA</Text></View>;
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 9 },
  mark: { width: 36, height: 36, borderRadius: 11 },
  name: { color: colors.text, fontSize: 19, fontWeight: '900', letterSpacing: 2 },
});
