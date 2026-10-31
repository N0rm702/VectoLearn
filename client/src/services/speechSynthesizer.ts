export interface WordBoundaryEvent {
  sentenceIndex: number;
  totalSentences: number;
  sentenceText: string;
  charIndex: number;
  wordIndex: number;
  word: string;
  spokenWords: string[];
  allWords: string[];
  isSentenceEnd: boolean;
}

export interface SpeechCallbacks {
  onStart?: () => void;
  onSentenceStart?: (sentenceIndex: number, sentenceText: string, totalSentences: number) => void;
  onWordBoundary?: (event: WordBoundaryEvent) => void;
  onEnd?: () => void;
  onError?: (error: any) => void;
}

class SpeechSynthesizerService {
  private synth: SpeechSynthesis | null = null;
  private voices: SpeechSynthesisVoice[] = [];
  private selectedVoice: SpeechSynthesisVoice | null = null;
  private isSupported: boolean = false;
  private isSpeakingState: boolean = false;
  private keepAliveInterval: number | null = null;
  private wordWatchdogInterval: number | null = null;
  private sentenceWatchdogTimeout: number | null = null;
  private nextSentenceTimeout: number | null = null;
  private activeJobId: number = 0;
  private sentenceList: string[] = [];
  private currentSentenceIndex: number = 0;

  constructor() {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      this.synth = window.speechSynthesis;
      this.isSupported = true;
      this.initVoices();
    }
  }

  private initVoices(): void {
    if (!this.synth) return;

    const loadVoices = () => {
      try {
        const availableVoices = this.synth?.getVoices() || [];
        if (availableVoices.length > 0) {
          this.voices = availableVoices;

          // PRIORITY 1: FAST LOCAL OFFLINE VOICES (0ms delay, zero network buffering)
          // On Windows: 'Microsoft David Desktop', 'Microsoft Zira Desktop', 'Microsoft Mark'
          // On macOS: 'Alex', 'Samantha' (Local)
          const fastLocalVoice = this.voices.find(
            (v) =>
              v.lang.startsWith('en') &&
              (v.localService === true ||
                v.name.includes('Desktop') ||
                v.name.includes('David') ||
                v.name.includes('Zira') ||
                v.name.includes('Mark'))
          );

          // PRIORITY 2: Any local service voice
          const anyLocalVoice = this.voices.find(
            (v) => v.lang.startsWith('en') && v.localService === true
          );

          // PRIORITY 3: Standard English voice (non-online)
          const standardEnglishVoice = this.voices.find(
            (v) => v.lang.startsWith('en') && !v.name.includes('Online')
          );

          // PRIORITY 4: Any English voice or first voice
          const fallbackEnglish = this.voices.find((v) => v.lang.startsWith('en'));

          this.selectedVoice =
            fastLocalVoice || anyLocalVoice || standardEnglishVoice || fallbackEnglish || this.voices[0] || null;
        }
      } catch (err) {
        console.warn('SpeechSynthesis voice resolution warning:', err);
      }
    };

    loadVoices();

    if (typeof window !== 'undefined' && window.speechSynthesis) {
      if (typeof window.speechSynthesis.addEventListener === 'function') {
        window.speechSynthesis.addEventListener('voiceschanged', loadVoices);
      } else if (this.synth.onvoiceschanged !== undefined) {
        this.synth.onvoiceschanged = loadVoices;
      }

      // Proactive async retries for Chromium where getVoices() is empty on first synchronous tick
      setTimeout(loadVoices, 100);
      setTimeout(loadVoices, 500);
    }
  }

  public getAvailableVoices(): SpeechSynthesisVoice[] {
    if (this.voices.length === 0 && this.synth) {
      const live = this.synth.getVoices();
      if (live && live.length > 0) {
        this.voices = live;
        if (!this.selectedVoice) {
          this.selectedVoice =
            this.voices.find((v) => v.lang.startsWith('en') && (v.localService || v.name.includes('David') || v.name.includes('Zira'))) ||
            this.voices.find((v) => v.lang.startsWith('en')) ||
            this.voices[0] ||
            null;
        }
      }
    }
    return this.voices;
  }

  public isVoiceLocal(voice: SpeechSynthesisVoice): boolean {
    return (
      voice.localService === true ||
      voice.name.includes('Desktop') ||
      voice.name.includes('David') ||
      voice.name.includes('Zira') ||
      voice.name.includes('Mark') ||
      (!voice.name.includes('Online') && !voice.name.includes('Google') && !voice.name.includes('Natural'))
    );
  }

  public setVoice(voice: SpeechSynthesisVoice): void {
    this.selectedVoice = voice;
  }

  public setVoiceByName(voiceName: string): boolean {
    const found = this.voices.find((v) => v.name === voiceName);
    if (found) {
      this.selectedVoice = found;
      return true;
    }
    return false;
  }

  public getSelectedVoice(): SpeechSynthesisVoice | null {
    if (!this.selectedVoice && this.voices.length > 0) {
      this.getAvailableVoices();
    }
    return this.selectedVoice;
  }

  public getSelectedVoiceName(): string {
    if (!this.isSupported) return 'Unsupported on device';
    if (!this.selectedVoice) return 'Hardware System Default';
    const isLocal = this.isVoiceLocal(this.selectedVoice);
    return `${this.selectedVoice.name} ${isLocal ? '⚡ (0ms Local)' : '☁️ (Cloud)'}`;
  }

  public isSpeechSupported(): boolean {
    return this.isSupported;
  }

  public isSpeaking(): boolean {
    return this.isSpeakingState || (this.synth?.speaking ?? false);
  }

  /**
   * Splits long paragraphs into short sentences for immediate audio streaming and synchronized captions.
   * Protects common abbreviations and numbers from incorrect splits.
   */
  public splitIntoSentences(text: string): string[] {
    if (!text || !text.trim()) return [];
    const protectedText = text
      .replace(/(\b(?:e\.g|i\.e|vs|etc|Dr|Mr|Ms|Prof)\.)/gi, (m) => m.replace(/\./g, '___DOT___'))
      .replace(/(\d+)\.(\d+)/g, '$1___DOT___$2');

    const rawChunks = protectedText.match(/[^.!?\n]+[.!?\n]+|[^.!?\n]+$/g) || [protectedText];
    const initialSentences = rawChunks
      .map((chunk) => chunk.replace(/___DOT___/g, '.').trim())
      .filter((chunk) => chunk.length > 0);

    // Fine-grained clause chunking: if any sentence exceeds 12 words, split on natural clauses (; : — or commas)
    // This allows sub-second seeking and prevents whole dialogues from repeating when seeking
    const granularSentences: string[] = [];
    for (const sent of initialSentences) {
      const words = sent.split(/\s+/).filter(Boolean);
      if (words.length <= 12) {
        granularSentences.push(sent);
      } else {
        // Split on semicolons, colons, em-dashes, or commas
        const subChunks = sent.split(/([;:]|(?<=\w)—|(?<=\w)\s*--\s*|,\s*(?=[A-Za-z]))/g);
        let currentSub = '';
        for (let i = 0; i < subChunks.length; i++) {
          const piece = subChunks[i].trim();
          if (!piece) continue;
          if (piece === ';' || piece === ':' || piece === '—' || piece === '--') {
            currentSub += piece;
            if (currentSub.split(/\s+/).filter(Boolean).length >= 4) {
              granularSentences.push(currentSub.trim());
              currentSub = '';
            }
          } else {
            if (currentSub && currentSub.split(/\s+/).filter(Boolean).length >= 7) {
              granularSentences.push(currentSub.trim());
              currentSub = piece;
            } else {
              currentSub = currentSub ? `${currentSub} ${piece}` : piece;
            }
          }
        }
        if (currentSub && currentSub.trim()) {
          granularSentences.push(currentSub.trim());
        }
      }
    }

    return granularSentences.length > 0 ? granularSentences : initialSentences;
  }

  /**
   * Speaks text using sequential single-utterance execution and real-time word boundary events.
   * Eliminates the multi-utterance Chromium freeze bug, GC drops, and desktop voice audio endpoint death.
   * Supports starting from an arbitrary sentence index for seamless pause/resume and timeline scrubbing.
   */
  public speak(
    text: string,
    rate: number = 1.0,
    callbacksOrOnStart?: SpeechCallbacks | (() => void),
    onEnd?: () => void,
    onError?: (error: any) => void,
    startSentenceIndex: number = 0
  ): void {
    if (!this.synth || !this.isSupported || !text.trim()) {
      if (typeof callbacksOrOnStart === 'object' && callbacksOrOnStart.onEnd) {
        callbacksOrOnStart.onEnd();
      } else {
        onEnd?.();
      }
      return;
    }

    const callbacks: SpeechCallbacks =
      typeof callbacksOrOnStart === 'function'
        ? { onStart: callbacksOrOnStart, onEnd, onError }
        : callbacksOrOnStart || {};

    try {
      // Allocate a new unique Job ID; any pending callbacks from previous runs become no-ops
      this.activeJobId++;
      const currentJob = this.activeJobId;

      this.stopWordWatchdog();
      this.stopSentenceWatchdog();
      this.stopNextSentenceTimeout();

      // Cleanly clear prior hardware speech state
      try {
        this.synth.cancel();
      } catch (err) {
        // silent catch
      }

      // Unpause if hardware synth is paused
      if (this.synth.paused) {
        this.synth.resume();
      }

      this.sentenceList = this.splitIntoSentences(text);
      if (this.sentenceList.length === 0) {
        callbacks.onEnd?.();
        return;
      }

      const clampedRate = Math.max(0.5, Math.min(2.0, rate));
      let hasStarted = false;

      // Safe non-destructive keep-alive (unpauses if stalled, never calls pause())
      this.startKeepAlive();

      const speakSentenceAtIndex = (idx: number) => {
        if (this.activeJobId !== currentJob) return;

        if (idx >= this.sentenceList.length) {
          // All sentences in this chunk completed naturally
          this.isSpeakingState = false;
          (window as any).__bcActiveUtterance = null;
          this.stopSentenceWatchdog();
          this.stopWordWatchdog();
          this.stopKeepAlive();
          callbacks.onEnd?.();
          return;
        }

        this.currentSentenceIndex = idx;
        const sentence = this.sentenceList[idx];

        // Parse words and word spans in this sentence for subtitles
        const words = sentence.trim().split(/\s+/).filter(Boolean);
        const wordSpans: { word: string; start: number; end: number }[] = [];
        let searchOffset = 0;
        for (const w of words) {
          const sIdx = sentence.indexOf(w, searchOffset);
          if (sIdx !== -1) {
            wordSpans.push({ word: w, start: sIdx, end: sIdx + w.length });
            searchOffset = sIdx + w.length;
          }
        }

        const utterance = new SpeechSynthesisUtterance(sentence);
        utterance.rate = clampedRate;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;

        if (this.selectedVoice) {
          utterance.voice = this.selectedVoice;
        }

        // Global window anchor prevents Chromium V8 garbage collection mid-speech
        (window as any).__bcActiveUtterance = utterance;

        // Sentence start handler
        utterance.onstart = () => {
          if (this.activeJobId !== currentJob) return;

          if (!hasStarted) {
            hasStarted = true;
            this.isSpeakingState = true;
            callbacks.onStart?.();
          }

          callbacks.onSentenceStart?.(idx, sentence, this.sentenceList.length);

          // Word 0 is spoken immediately when utterance begins
          if (words.length > 0) {
            callbacks.onWordBoundary?.({
              sentenceIndex: idx,
              totalSentences: this.sentenceList.length,
              sentenceText: sentence,
              charIndex: wordSpans[0]?.start ?? 0,
              wordIndex: 0,
              word: words[0],
              spokenWords: [words[0]],
              allWords: words,
              isSentenceEnd: words.length === 1,
            });
          }

          // Watchdog timer: smoothly advance words if browser onboundary event is sporadic
          this.stopWordWatchdog();
          let currentSpokenWordIdx = 0;
          const msPerWord = Math.max(200, Math.round(330 / clampedRate));
          this.wordWatchdogInterval = window.setInterval(() => {
            if (this.activeJobId !== currentJob) return;
            if (currentSpokenWordIdx < words.length - 1) {
              currentSpokenWordIdx++;
              callbacks.onWordBoundary?.({
                sentenceIndex: idx,
                totalSentences: this.sentenceList.length,
                sentenceText: sentence,
                charIndex: wordSpans[currentSpokenWordIdx]?.start ?? 0,
                wordIndex: currentSpokenWordIdx,
                word: words[currentSpokenWordIdx],
                spokenWords: words.slice(0, currentSpokenWordIdx + 1),
                allWords: words,
                isSentenceEnd: currentSpokenWordIdx === words.length - 1,
              });
            }
          }, msPerWord);
        };

        // Real-time word boundary hardware event
        utterance.onboundary = (e: SpeechSynthesisEvent) => {
          if (this.activeJobId !== currentJob) return;
          if (e.name === 'word' || !e.name) {
            const charIndex = typeof e.charIndex === 'number' ? e.charIndex : 0;
            let wIdx = wordSpans.findIndex((s) => charIndex >= s.start && charIndex < s.end);
            if (wIdx === -1) {
              wIdx = wordSpans.findIndex((s) => s.start >= charIndex);
              if (wIdx === -1) wIdx = wordSpans.length - 1;
            }

            if (wIdx >= 0 && wIdx < words.length) {
              callbacks.onWordBoundary?.({
                sentenceIndex: idx,
                totalSentences: this.sentenceList.length,
                sentenceText: sentence,
                charIndex: charIndex,
                wordIndex: wIdx,
                word: words[wIdx],
                spokenWords: words.slice(0, wIdx + 1),
                allWords: words,
                isSentenceEnd: wIdx === words.length - 1,
              });
            }
          }
        };

        // On sentence end: flush boundary state and schedule next sentence sequentially
        utterance.onend = () => {
          if (this.activeJobId !== currentJob) return;

          this.stopWordWatchdog();
          this.stopSentenceWatchdog();

          if (words.length > 0) {
            callbacks.onWordBoundary?.({
              sentenceIndex: idx,
              totalSentences: this.sentenceList.length,
              sentenceText: sentence,
              charIndex: sentence.length,
              wordIndex: words.length - 1,
              word: words[words.length - 1],
              spokenWords: words,
              allWords: words,
              isSentenceEnd: true,
            });
          }

          // 25ms natural breath interval between sentences gives the audio buffer a clean flush
          this.nextSentenceTimeout = window.setTimeout(() => {
            speakSentenceAtIndex(idx + 1);
          }, 25);
        };

        // Error fallback
        utterance.onerror = (e) => {
          if (this.activeJobId !== currentJob) return;

          this.stopWordWatchdog();
          this.stopSentenceWatchdog();

          if (e.error !== 'interrupted' && e.error !== 'canceled') {
            console.warn(`SpeechSynthesis sentence ${idx} event warning:`, e.error);
            callbacks.onError?.(e);
          }

          // Advance to next sentence so error never permanently hangs the player
          this.nextSentenceTimeout = window.setTimeout(() => {
            speakSentenceAtIndex(idx + 1);
          }, 25);
        };

        // FAILSAFE STUCK WATCHDOG: Guarantees narration NEVER freezes indefinitely
        this.stopSentenceWatchdog();
        const expectedMs = Math.max(5000, Math.ceil((words.length * 1000) / clampedRate) + 3500);
        this.sentenceWatchdogTimeout = window.setTimeout(() => {
          if (this.activeJobId !== currentJob) return;
          console.warn(`SpeechSynthesis watchdog triggered for sentence ${idx} (${expectedMs}ms). Auto-advancing.`);
          this.stopWordWatchdog();
          try {
            this.synth?.cancel();
          } catch (err) {}
          speakSentenceAtIndex(idx + 1);
        }, expectedMs);

        // Speak the single utterance sequentially
        this.synth?.speak(utterance);
        if (this.synth?.paused) {
          this.synth.resume();
        }
      };

      const safeStartIdx = Math.max(0, Math.min(startSentenceIndex, this.sentenceList.length - 1));
      speakSentenceAtIndex(safeStartIdx);
    } catch (err) {
      console.warn('Hardware speech engine caught error:', err);
      this.stopWordWatchdog();
      this.stopSentenceWatchdog();
      this.stopNextSentenceTimeout();
      this.isSpeakingState = false;
      this.stopKeepAlive();
      callbacks.onEnd?.();
    }
  }

  private stopWordWatchdog(): void {
    if (this.wordWatchdogInterval !== null) {
      clearInterval(this.wordWatchdogInterval);
      this.wordWatchdogInterval = null;
    }
  }

  private stopSentenceWatchdog(): void {
    if (this.sentenceWatchdogTimeout !== null) {
      clearTimeout(this.sentenceWatchdogTimeout);
      this.sentenceWatchdogTimeout = null;
    }
  }

  private stopNextSentenceTimeout(): void {
    if (this.nextSentenceTimeout !== null) {
      clearTimeout(this.nextSentenceTimeout);
      this.nextSentenceTimeout = null;
    }
  }

  private startKeepAlive(): void {
    this.stopKeepAlive();
    // Non-destructive keep-alive: unpauses if browser paused in background, NEVER calls pause()
    if (typeof window !== 'undefined') {
      this.keepAliveInterval = window.setInterval(() => {
        if (this.synth?.paused) {
          this.synth.resume();
        }
      }, 5000);
    }
  }

  private stopKeepAlive(): void {
    if (this.keepAliveInterval !== null) {
      clearInterval(this.keepAliveInterval);
      this.keepAliveInterval = null;
    }
  }

  public cancel(): void {
    this.activeJobId++;
    this.stopWordWatchdog();
    this.stopSentenceWatchdog();
    this.stopNextSentenceTimeout();
    this.stopKeepAlive();
    (window as any).__bcActiveUtterance = null;
    if (this.synth) {
      try {
        this.synth.cancel();
      } catch (err) {
        // silent catch
      }
    }
    this.isSpeakingState = false;
  }

  public pause(): void {
    if (this.synth && this.synth.speaking) {
      this.synth.pause();
    }
  }

  public resume(): void {
    if (this.synth) {
      this.synth.resume();
    }
  }

  public getCurrentSentenceIndex(): number {
    return this.currentSentenceIndex;
  }
}

export const speechSynthesizer = new SpeechSynthesizerService();
