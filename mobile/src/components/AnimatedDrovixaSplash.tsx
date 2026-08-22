import { useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import { useEffect, useRef } from 'react';
import {
  AccessibilityInfo,
  Animated,
  Easing,
  Platform,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { colors } from '@/theme';

const mark = require('../../assets/icon.png');
const introSound = require('../../assets/audio/drovixa-intro.mp3');

type Props = {
  onFinished: () => void;
};

export function AnimatedDrovixaSplash({ onFinished }: Props) {
  const player = useAudioPlayer(introSound, { downloadFirst: true });
  const playerStatus = useAudioPlayerStatus(player);
  const soundStarted = useRef(false);
  const backgroundOpacity = useRef(new Animated.Value(0)).current;
  const haloOpacity = useRef(new Animated.Value(0)).current;
  const haloScale = useRef(new Animated.Value(0.75)).current;
  const markOpacity = useRef(new Animated.Value(0)).current;
  const markScale = useRef(new Animated.Value(0.68)).current;
  const markLift = useRef(new Animated.Value(14)).current;
  const wordOpacity = useRef(new Animated.Value(0)).current;
  const wordSpacing = useRef(new Animated.Value(10)).current;
  const taglineOpacity = useRef(new Animated.Value(0)).current;
  const lineScale = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    let active = true;
    let finishTimer: ReturnType<typeof setTimeout> | undefined;

    const start = (reduceMotion: boolean) => {
      if (!active) return;

      if (reduceMotion) {
        Animated.timing(backgroundOpacity, {
          toValue: 1,
          duration: 250,
          useNativeDriver: true,
        }).start();
        markOpacity.setValue(1);
        markScale.setValue(1);
        markLift.setValue(0);
        wordOpacity.setValue(1);
        wordSpacing.setValue(0);
        taglineOpacity.setValue(1);
        lineScale.setValue(1);
        finishTimer = setTimeout(onFinished, 1_250);
        return;
      }

      Animated.parallel([
        Animated.timing(backgroundOpacity, {
          toValue: 1,
          duration: 420,
          easing: Easing.out(Easing.quad),
          useNativeDriver: true,
        }),
        Animated.sequence([
          Animated.delay(110),
          Animated.parallel([
            Animated.timing(markOpacity, {
              toValue: 1,
              duration: 500,
              easing: Easing.out(Easing.cubic),
              useNativeDriver: true,
            }),
            Animated.spring(markScale, {
              toValue: 1,
              damping: 12,
              stiffness: 88,
              mass: 0.8,
              useNativeDriver: true,
            }),
            Animated.timing(markLift, {
              toValue: 0,
              duration: 720,
              easing: Easing.out(Easing.cubic),
              useNativeDriver: true,
            }),
          ]),
        ]),
        Animated.sequence([
          Animated.delay(260),
          Animated.parallel([
            Animated.timing(haloOpacity, {
              toValue: 0.7,
              duration: 620,
              useNativeDriver: true,
            }),
            Animated.timing(haloScale, {
              toValue: 1.2,
              duration: 1_350,
              easing: Easing.out(Easing.cubic),
              useNativeDriver: true,
            }),
          ]),
          Animated.timing(haloOpacity, {
            toValue: 0.18,
            duration: 700,
            useNativeDriver: true,
          }),
        ]),
        Animated.sequence([
          Animated.delay(890),
          Animated.parallel([
            Animated.timing(wordOpacity, {
              toValue: 1,
              duration: 560,
              useNativeDriver: true,
            }),
            Animated.timing(wordSpacing, {
              toValue: 0,
              duration: 760,
              easing: Easing.out(Easing.cubic),
              useNativeDriver: true,
            }),
          ]),
        ]),
        Animated.sequence([
          Animated.delay(1_420),
          Animated.parallel([
            Animated.timing(taglineOpacity, {
              toValue: 1,
              duration: 520,
              useNativeDriver: true,
            }),
            Animated.spring(lineScale, {
              toValue: 1,
              damping: 14,
              stiffness: 95,
              useNativeDriver: true,
            }),
          ]),
        ]),
      ]).start();

      finishTimer = setTimeout(onFinished, 2_850);
    };

    void AccessibilityInfo.isReduceMotionEnabled()
      .then(start)
      .catch(() => start(false));

    return () => {
      active = false;
      if (finishTimer) clearTimeout(finishTimer);
    };
  }, [
    backgroundOpacity,
    haloOpacity,
    haloScale,
    lineScale,
    markLift,
    markOpacity,
    markScale,
    onFinished,
    taglineOpacity,
    wordOpacity,
    wordSpacing,
  ]);

  useEffect(() => {
    if (Platform.OS === 'web' || !playerStatus.isLoaded || soundStarted.current) return;
    soundStarted.current = true;
    player.volume = 0.72;
    player.play();
  }, [player, playerStatus.isLoaded]);

  return (
    <Animated.View style={[styles.screen, { opacity: backgroundOpacity }]}>
      <View style={styles.stage}>
        <Animated.View
          style={[
            styles.halo,
            {
              opacity: haloOpacity,
              transform: [{ scale: haloScale }],
            },
          ]}
        />
        <Animated.Image
          accessibilityLabel="Drovixa"
          resizeMode="cover"
          source={mark}
          style={[
            styles.mark,
            {
              opacity: markOpacity,
              transform: [{ translateY: markLift }, { scale: markScale }],
            },
          ]}
        />
        <Animated.View
          style={[
            styles.wordWrap,
            {
              opacity: wordOpacity,
              transform: [{ translateY: wordSpacing }],
            },
          ]}
        >
          <Text style={styles.word}>DROVIXA</Text>
        </Animated.View>
        <Animated.View
          style={[
            styles.signature,
            {
              opacity: taglineOpacity,
              transform: [{ scaleX: lineScale }],
            },
          ]}
        >
          <View style={styles.line} />
          <View style={styles.play} />
          <View style={styles.line} />
        </Animated.View>
        <Animated.Text style={[styles.tagline, { opacity: taglineOpacity }]}>
          STORIES TODAY. LEGENDS TOMORROW.
        </Animated.Text>
      </View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
  },
  stage: {
    width: '100%',
    maxWidth: 430,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 28,
  },
  halo: {
    position: 'absolute',
    width: 260,
    height: 260,
    borderRadius: 130,
    backgroundColor: '#7C3AED42',
    shadowColor: '#F04DDC',
    shadowOpacity: 0.8,
    shadowRadius: 42,
    elevation: 18,
  },
  mark: {
    width: 190,
    height: 190,
    borderRadius: 42,
  },
  wordWrap: {
    marginTop: 20,
  },
  word: {
    color: '#FFFFFF',
    fontSize: 34,
    fontWeight: '900',
    letterSpacing: 6,
  },
  signature: {
    width: 180,
    marginTop: 20,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  line: {
    width: 62,
    height: 2,
    borderRadius: 2,
    backgroundColor: '#C65BFF',
  },
  play: {
    width: 0,
    height: 0,
    borderTopWidth: 7,
    borderBottomWidth: 7,
    borderLeftWidth: 12,
    borderTopColor: 'transparent',
    borderBottomColor: 'transparent',
    borderLeftColor: '#FF4DB8',
  },
  tagline: {
    marginTop: 13,
    color: '#C9A7FF',
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 2.2,
    textAlign: 'center',
  },
});
