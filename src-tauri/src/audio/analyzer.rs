// Real-time audio analysis for the visualizer. While a visualizer is visible, the streaming
// source captures left-channel samples in a lock-free ring; a separate thread snapshots the
// latest window, runs an FFT, buckets the spectrum into log-spaced bands, and emits them to
// the UI as `audio-levels` events. Single-producer (audio thread) / single-consumer (analysis
// thread), so relaxed atomics + a monotonic write counter are enough.
use rustfft::{num_complex::Complex, Fft, FftPlanner};
use std::sync::atomic::{AtomicBool, AtomicU32, AtomicUsize, Ordering};
use std::sync::Arc;

pub const FFT_SIZE: usize = 2048;
pub const NUM_BANDS: usize = 48;

pub struct AnalysisBuffer {
    buf: Vec<AtomicU32>, // ring of mono f32 samples (bit-cast)
    pos: AtomicUsize,    // total samples written (monotonic, wraps harmlessly)
    sample_rate: u32,
    enabled: Arc<AtomicBool>,
}

impl AnalysisBuffer {
    pub fn new(sample_rate: u32, enabled: Arc<AtomicBool>) -> Self {
        let mut buf = Vec::with_capacity(FFT_SIZE);
        for _ in 0..FFT_SIZE {
            buf.push(AtomicU32::new(0));
        }
        AnalysisBuffer {
            buf,
            pos: AtomicUsize::new(0),
            sample_rate: sample_rate.max(8000),
            enabled,
        }
    }

    #[inline]
    pub fn push(&self, s: f32) {
        if !self.enabled.load(Ordering::Relaxed) {
            return;
        }
        let p = self.pos.load(Ordering::Relaxed);
        self.buf[p % FFT_SIZE].store(s.to_bits(), Ordering::Relaxed);
        self.pos.store(p.wrapping_add(1), Ordering::Release);
    }

    pub fn written(&self) -> usize {
        self.pos.load(Ordering::Acquire)
    }
    pub fn sample_rate(&self) -> u32 {
        self.sample_rate
    }

    // Copy the most recent FFT_SIZE samples in chronological order.
    pub fn snapshot(&self, out: &mut [f32; FFT_SIZE]) {
        let end = self.pos.load(Ordering::Acquire);
        let start = end.wrapping_sub(FFT_SIZE);
        for i in 0..FFT_SIZE {
            let idx = start.wrapping_add(i) % FFT_SIZE;
            out[i] = f32::from_bits(self.buf[idx].load(Ordering::Relaxed));
        }
    }
}

pub struct Analyzer {
    fft: Arc<dyn Fft<f32>>,
    hann: Vec<f32>,
    band_edges: Vec<usize>, // NUM_BANDS+1 FFT-bin boundaries (log spaced)
    fft_buffer: Vec<Complex<f32>>,
}

impl Analyzer {
    pub fn new(sample_rate: u32) -> Self {
        let fft = FftPlanner::<f32>::new().plan_fft_forward(FFT_SIZE);
        let hann: Vec<f32> = (0..FFT_SIZE)
            .map(|i| {
                0.5 - 0.5 * (2.0 * std::f32::consts::PI * i as f32 / (FFT_SIZE as f32 - 1.0)).cos()
            })
            .collect();
        let bins = FFT_SIZE / 2;
        let nyq = sample_rate as f32 / 2.0;
        let fmin = 30.0f32;
        let fmax = nyq.min(16000.0).max(fmin * 2.0);
        let band_edges: Vec<usize> = (0..=NUM_BANDS)
            .map(|b| {
                let f = fmin * (fmax / fmin).powf(b as f32 / NUM_BANDS as f32);
                (((f / nyq) * bins as f32).round() as usize).min(bins.saturating_sub(1))
            })
            .collect();
        Analyzer {
            fft,
            hann,
            band_edges,
            fft_buffer: vec![Complex { re: 0.0, im: 0.0 }; FFT_SIZE],
        }
    }

    // Returns (bands 0..1, overall level 0..1). `bands` smoothed/scaled for display.
    pub fn analyze(&mut self, samples: &[f32; FFT_SIZE]) -> ([f32; NUM_BANDS], f32) {
        for (i, sample) in samples.iter().enumerate() {
            self.fft_buffer[i] = Complex {
                re: sample * self.hann[i],
                im: 0.0,
            };
        }
        self.fft.process(&mut self.fft_buffer);

        let bins = FFT_SIZE / 2;
        let mut out = [0.0f32; NUM_BANDS];
        for b in 0..NUM_BANDS {
            let lo = self.band_edges[b];
            let hi = self.band_edges[b + 1].max(lo + 1).min(bins);
            let mut sum = 0.0f32;
            for k in lo..hi {
                sum += self.fft_buffer[k].norm();
            }
            let avg = sum / (hi - lo).max(1) as f32 / FFT_SIZE as f32;
            // Log magnitude → 0..1, steeper than before so bands keep their contrast
            // (the previous mapping squashed everything into a narrow mid range). Raw,
            // unsmoothed — the UI applies its own (configurable) temporal smoothing.
            let v = ((avg.max(1e-7).ln() + 9.0) / 7.0).clamp(0.0, 1.0);
            out[b] = v;
        }

        // Overall level = RMS of the window.
        let mut sq = 0.0f32;
        for &s in samples.iter() {
            sq += s * s;
        }
        let rms = (sq / FFT_SIZE as f32).sqrt();
        let level = (rms * 3.0).clamp(0.0, 1.0);

        (out, level)
    }
}
